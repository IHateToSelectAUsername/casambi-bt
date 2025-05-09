import asyncio
import logging
from binascii import b2a_hex as b2a
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from bleak.backends.device import BLEDevice
from httpx import AsyncClient, RequestError

from ._cache import Cache
from ._client import CasambiClient, ConnectionState, IncommingPacketType
from ._network import Network
from ._operation import OpCode, OperationsContext
from ._unit import Group, Scene, Unit, UnitControlType, UnitState
from .errors import ConnectionStateError, ProtocolError


class Casambi:
    """Class to manage one Casambi network.

    This is the central point of interaction and should be preferred to dealing with the internal components,
    e.g. ``Network`` or ``CasambiClient``, directly.
    """

    def __init__(
        self,
        httpClient: AsyncClient | None = None,
        cachePath: Path | None = None,
    ) -> None:
        self._casaClient: CasambiClient | None = None
        self._casaNetwork: Network | None = None

        self._unitChangedCallbacks: list[Callable[[Unit], None]] = []
        self._disconnectCallbacks: list[Callable[[], None]] = []

        self._logger = logging.getLogger(__name__)
        # Initialisiere den Operationskontext für die Kommunikation mit dem Netzwerk
        self._opContext = OperationsContext()
        self._ownHttpClient = httpClient is None
        self._httpClient = httpClient

        self._cache = Cache(cachePath)

    def _checkNetwork(self) -> None:
        if not self._casaNetwork or not self._casaNetwork._networkRevision:
            raise ConnectionStateError(
                ConnectionState.AUTHENTICATED,
                ConnectionState.NONE,
                "Network information missing.",
            )

    @property
    def networkName(self) -> str:
        self._checkNetwork()
        return self._casaNetwork._networkName  # type: ignore

    @property
    def networkId(self) -> str:
        return self._casaNetwork._id  # type: ignore

    @property
    def units(self) -> list[Unit]:
        """Get the units in the network if connected.

        :return: A list of all units in the network.
        :raises ConnectionStateError: There is no connection to the network.
        """
        self._checkNetwork()
        return self._casaNetwork.units  # type: ignore

    @property
    def groups(self) -> list[Group]:
        """Get the groups in the network if connected.

        :return: A list of all groups in the network.
        :raises ConnectionStateError: There is no connection to the network.
        """
        self._checkNetwork()
        return self._casaNetwork.groups  # type: ignore

    @property
    def scenes(self) -> list[Scene]:
        """Get the scenes of the network if connected.

        :return: A list of all scenes in the network.
        :raises ConnectionStateError: There is no connection to the network.
        """
        self._checkNetwork()
        return self._casaNetwork.scenes  # type: ignore

    @property
    def connected(self) -> bool:
        """Check whether there is an active connection to the network."""
        return (
            self._casaClient is not None
            and self._casaClient._connectionState == ConnectionState.AUTHENTICATED
        )

    async def connect(
        self,
        addr_or_device: str | BLEDevice,
        password: str,
        forceOffline: bool = False,
    ) -> None:
        """Connect and authenticate to a network.

        :param addr: The MAC address of the network or a BLEDevice. Use `discover` to find the address of a network.
        :param password: The password for the network.
        :param forceOffline: Whether to avoid contacting the casambi servers.
        :raises AuthenticationError: The supplied password is invalid.
        :raises ProtocolError: The network did not follow the expected protocol.
        :raises NetworkNotFoundError: No network was found under the supplied address.
        :raises NetworkOnlineUpdateNeededError: An offline update isn't possible in the current state.
        :raises BluetoothError: An error occurred in the bluetooth stack.
        """

        if isinstance(addr_or_device, BLEDevice):
            addr = addr_or_device.address
        else:
            # Add colons if necessary.
            if ":" not in addr_or_device:
                addr_or_device = ":".join(["".join(p) for p in pairwise(addr)][::2])
            addr = addr_or_device

        self._logger.info(f"Verbindungsaufbau zum Casambi-Netzwerk {addr} wird gestartet...")
        self._logger.debug("--- VERBINDUNGSPROZESS PHASE 1: VORBEREITUNG ---")
        self._logger.debug(f"Verwendete Adresse: {addr} (UUID: {addr.replace(':', '').lower()})")

        # Erstelle einen HTTP-Client, falls noch keiner existiert
        if not self._httpClient:
            self._logger.debug("Erstelle HTTP-Client für die Kommunikation mit der Casambi-Cloud")
            self._httpClient = AsyncClient()

        # Netzwerkinformationen abrufen
        self._logger.debug("--- VERBINDUNGSPROZESS PHASE 2: CLOUD-KOMMUNIKATION ---")
        uuid = addr.replace(":", "").lower()
        self._logger.debug(f"Setze UUID im Cache: {uuid}")
        await self._cache.setUuid(uuid)
        
        self._logger.debug("Erstelle Network-Objekt für die Kommunikation mit der Casambi-Cloud")
        self._casaNetwork = Network(uuid, self._httpClient, self._cache)
        
        self._logger.debug("Lade Netzwerkdaten aus dem Cache (falls vorhanden)")
        await self._casaNetwork.load()
        try:
            self._logger.info("Starte Authentifizierung bei der Casambi-Cloud")
            self._logger.debug(f"Offline-Modus erzwingen: {forceOffline}")
            await self._casaNetwork.logIn(password, forceOffline)
            self._logger.info("Authentifizierung bei der Casambi-Cloud erfolgreich")
        # TODO: I don't like that this logic is in this class but I couldn't think of a better way.
        except RequestError:
            self._logger.warning(
                "Netzwerkfehler bei der Anmeldung bei der Casambi-Cloud. Versuche Offline-Betrieb.",
                exc_info=True,
            )
            forceOffline = True
            self._logger.debug("Offline-Modus aktiviert aufgrund von Netzwerkproblemen")

        self._logger.debug("Aktualisiere Netzwerkdaten (Geräte, Gruppen, Szenen)")
        await self._casaNetwork.update(forceOffline)
        self._logger.debug(f"Netzwerkdaten aktualisiert. Offline-Modus: {forceOffline}")

        self._logger.debug("--- VERBINDUNGSPROZESS PHASE 3: BLUETOOTH-VERBINDUNG ---")
        self._logger.debug("Erstelle CasambiClient für die Bluetooth-Kommunikation")
        self._casaClient = CasambiClient(
            addr_or_device,
            self._dataCallback,        # Callback für eingehende Daten
            self._disconnectCallback,  # Callback für Verbindungsabbrüche
            self._casaNetwork,         # Netzwerkinformationen für die Authentifizierung
        )
        self._logger.debug("Starte Bluetooth-Verbindung mit dem Casambi-Gateway")
        await self._connectClient()
        self._logger.info("Verbindung zum Casambi-Netzwerk erfolgreich hergestellt")

    async def _connectClient(self) -> None:
        """Initiiere die Bluetooth-Verbindung."""
        self._logger.debug("Starte internen Verbindungsprozess zum Casambi-Gateway")
        self._casaClient = cast(CasambiClient, self._casaClient)
        
        # 1. Physische Bluetooth-Verbindung herstellen
        self._logger.debug("Verbinde über Bluetooth mit dem Gateway-Gerät")
        await self._casaClient.connect()
        self._logger.debug("Bluetooth-Verbindung hergestellt, starte Schlüsselaustausch")
        
        try:
            # 2. Schlüsselaustausch für die verschlüsselte Kommunikation
            self._logger.debug("Führe Schlüsselaustausch durch (Diffie-Hellman-Verfahren)")
            await self._casaClient.exchangeKey()
            self._logger.debug("Schlüsselaustausch erfolgreich, starte lokale Authentifizierung")
            
            # 3. Authentifizierung mit den von der Cloud erhaltenen Zugangsdaten
            self._logger.debug("Authentifiziere bei der lokalen Bluetooth-Schnittstelle")
            await self._casaClient.authenticate()
            self._logger.debug("Lokale Authentifizierung erfolgreich abgeschlossen")
        except ProtocolError as e:
            self._logger.error(f"Protokollfehler während der Verbindung: {str(e)}")
            self._logger.debug("Trenne Bluetooth-Verbindung aufgrund des Fehlers")
            await self._casaClient.disconnect()
            raise e

    async def setUnitState(self, target: Unit, state: UnitState) -> None:
        """Set the state of one unit directly.

        :param target: The targeted unit.
        :param state: The desired state.
        :return: Nothing is returned by this function. To get the new state register a change handler.
        """
        stateBytes = target.getStateAsBytes(state)
        await self._send(target, stateBytes, OpCode.SetState)

    async def setLevel(self, target: Unit | Group | None, level: int) -> None:
        """Set the level (brightness) for one or multiple units.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :param level: The desired level in range [0, 255]. If 0 the unit is turned off.
        :return: Nothing is returned by this function. To get the new state register a change handler.
        :raises ValueError: The supplied level isn't in range
        """
        if level < 0 or level > 255:
            raise ValueError()

        payload = level.to_bytes(1, byteorder="big", signed=False)
        await self._send(target, payload, OpCode.SetLevel)

    async def setVertical(self, target: Unit | Group | None, vertical: int) -> None:
        """Set the vertical (balance between top and bottom LED) for one or multiple units.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :param vertical: The desired vertical balance in range [0, 255]. If 0 the unit is turned off.
        :return: Nothing is returned by this function. To get the new state register a change handler.
        :raises ValueError: The supplied level isn't in range
        """
        if vertical < 0 or vertical > 255:
            raise ValueError()

        payload = vertical.to_bytes(1, byteorder="big", signed=False)
        await self._send(target, payload, OpCode.SetVertical)

    async def setSlider(self, target: Unit | Group | None, value: int) -> None:
        """Set the slider for one or multiple units.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :param value: The desired value in range [0, 255].
        :return: Nothing is returned by this function. To get the new state register a change handler.
        :raises ValueError: The supplied level isn't in range
        """
        if value < 0 or value > 255:
            raise ValueError()

        payload = value.to_bytes(1, byteorder="big", signed=False)
        await self._send(target, payload, OpCode.SetSlider)

    async def setWhite(self, target: Unit | Group | None, level: int) -> None:
        """Set the white level for one or multiple units.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :param level: The desired level in range [0, 255].
        :return: Nothing is returned by this function. To get the new state register a change handler.
        :raises ValueError: The supplied level isn't in range
        """
        if level < 0 or level > 255:
            raise ValueError()

        payload = level.to_bytes(1, byteorder="big", signed=False)
        await self._send(target, payload, OpCode.SetWhite)

    async def setColor(
        self, target: Unit | Group | None, rgbColor: tuple[int, int, int]
    ) -> None:
        """Set the rgb color for one or multiple units.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :param rgbColor: The desired color as a tuple of three ints in range [0, 255].
        :return: Nothing is returned by this function. To get the new state register a change handler.
        :raises ValueError: The supplied rgbColor isn't in range
        """

        state = UnitState()
        state.rgb = rgbColor
        hs: tuple[float, float] = state.hs  # type: ignore[assignment]
        hue = round(hs[0] * 1023)
        sat = round(hs[1] * 255)

        payload = hue.to_bytes(2, byteorder="little", signed=False) + sat.to_bytes(
            1, byteorder="little", signed=False
        )
        await self._send(target, payload, OpCode.SetColor)

    async def setTemperature(
        self, target: Unit | Group | None, temperature: int
    ) -> None:
        """Set the temperature for one or multiple units.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :param temperature: The desired temperature in degrees Kelvin.
        :return: Nothing is returned by this function. To get the new state register a change handler.
        :raises ValueError: The supplied temperature isn't in range
        """

        temperature = int(temperature / 50)
        payload = temperature.to_bytes(1, byteorder="big", signed=False)
        await self._send(target, payload, OpCode.SetTemperature)

    async def setColorXY(
        self, target: Unit | Group | None, xyColor: tuple[float, float]
    ) -> None:
        """Set the xy color for one or multiple units.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :param xyColor: The desired color as a pair of floats in the range [0.0, 1.0].
        :return: Nothing is returned by this function. To get the new state register a change handler.
        :raises ValueError: The supplied XYColor isn't in range or not supported by the supplied unit.
        """

        if xyColor[0] < 0.0 or xyColor[0] > 1.0 or xyColor[1] < 0.0 or xyColor[1] > 1.0:
            raise ValueError("Color out of range.")

        # We assume a default length of 22 bits, so 11 bits per coordinate. Is this sane?
        coordLen = 11
        if target is not None and isinstance(target, Unit):
            control = target.unitType.get_control(UnitControlType.XY)
            if control is None:
                raise ValueError("The control isn't supported by this unit.")
            coordLen = control.length // 2
        mask = (1 << coordLen) - 1
        x = round(xyColor[0] * mask) & mask
        y = round(xyColor[1] * mask) & mask

        payload = ((x << coordLen) | y).to_bytes(3, byteorder="little", signed=False)
        await self._send(target, payload, OpCode.SetColorXY)

    async def turnOn(self, target: Unit | Group | None) -> None:
        """Turn one or multiple units on to their last level.

        If ``target`` is of type ``Unit`` only this unit is affected.
        If ``target`` is of type ``Group`` the whole group is affected.
        if ``target`` is of type ``None`` all units in the network are affected.

        :param target: One or multiple targeted units.
        :return: Nothing is returned by this function. To get the new state register a change handler.
        """

        # Use -1 to indicate special packet format
        # Use RestoreLastLevel flag (1) and UseFullTimeFlag (4).
        # Not sure what UseFullTime does but this is what the app uses.
        await self._send(target, b"\xff\x05", OpCode.SetLevel)

    async def switchToScene(self, target: Scene, level: int = 0xFF) -> None:
        """Switch the network to a predefined scene.

        :param target: The scene to switch to.
        :param level: An optional relative brightness for all units in the scene.
        :return: Nothing is returned by this function. To get the new state register a change handler.
        """
        await self.setLevel(target, level)  # type: ignore[arg-type]

    async def _send(
        self, target: Unit | Group | Scene | None, state: bytes, opcode: OpCode
    ) -> None:
        if self._casaClient is None:
            raise ConnectionStateError(
                ConnectionState.AUTHENTICATED,
                ConnectionState.NONE,
            )

        targetCode = 0
        if isinstance(target, Unit):
            assert target.deviceId <= 0xFF
            targetCode = (target.deviceId << 8) | 0x01
        elif isinstance(target, Group):
            assert target.groudId <= 0xFF
            targetCode = (target.groudId << 8) | 0x02
        elif isinstance(target, Scene):
            assert target.sceneId <= 0xFF
            targetCode = (target.sceneId << 8) | 0x04
        elif target is not None:
            raise TypeError(f"Unkown target type {type(target)}")

        self._logger.debug(
            f"Sende Operation {opcode.name} mit Nutzlast {b2a(state)} an Ziel 0x{targetCode:x}"
        )

        opPkt = self._opContext.prepareOperation(opcode, targetCode, state)

        try:
            await self._casaClient.send(opPkt)
        except ConnectionStateError as exc:
            if exc.got == ConnectionState.NONE:
                self._logger.info("Verbindung unterbrochen, versuche einmal neu zu verbinden...")
                self._logger.debug("Starte Neuverbindungsprozess zur Wiederherstellung der Kommunikation")
                await self._connectClient()
                self._logger.debug("Verbindung wiederhergestellt, sende Paket erneut")
                await self._casaClient.send(opPkt)
                self._logger.debug("Paket nach Neuverbindung erfolgreich gesendet")
            else:
                self._logger.error(f"Verbindungsfehler: Erwarteter Status {exc.expected}, aktueller Status {exc.got}")
                raise exc

    def _dataCallback(
        self, packetType: IncommingPacketType, data: dict[str, Any]
    ) -> None:
        """Callback für eingehende Daten vom Casambi-Netzwerk."""
        self._logger.info(f"Eingehende Daten vom Typ {packetType} empfangen")
        if packetType == IncommingPacketType.UnitState:
            self._logger.debug(
                f"Verarbeite Statusänderung für Gerät {data['id']}: Neuer Status {b2a(data['state'])}"
            )

            found = False
            self._logger.debug(f"Suche nach Gerät mit ID {data['id']} im Netzwerk")
            for u in self._casaNetwork.units:  # type: ignore[union-attr]
                if u.deviceId == data["id"]:
                    found = True
                    self._logger.debug(f"Gerät {u.name} (ID: {u.deviceId}) gefunden, aktualisiere Status")
                    u.setStateFromBytes(data["state"])
                    u._on = data["on"]
                    u._online = data["online"]
                    self._logger.debug(f"Neuer Status: Ein={u._on}, Online={u._online}")

                    # Notify listeners
                    for h in self._unitChangedCallbacks:
                        try:
                            h(u)
                        except Exception:
                            self._logger.error(
                                f"Fehler im UnitChangedCallback {h} aufgetreten.",
                                exc_info=True,
                            )

            if not found:
                self._logger.error(
                    f"Statusänderung für unbekanntes Gerät mit ID {data['id']} empfangen"
                )
        else:
            self._logger.warning(f"Handler für Pakettyp {packetType} ist nicht implementiert!")

    def registerUnitChangedHandler(self, handler: Callable[[Unit], None]) -> None:
        """Register a new handler for unit state changed.

        This handler is called whenever a new state for a unit is received.
        The handler is supplied by the unit for which the state changed
        and the state property of the unit is set to the new state.

        :param handler: The method to call when a new unit state is received.
        """
        self._unitChangedCallbacks.append(handler)
        self._logger.debug(f"Handler für Gerätestatusänderungen registriert: {handler}")

    def unregisterUnitChangedHandler(self, handler: Callable[[Unit], None]) -> None:
        """Unregister an existing unit state change handler.

        :param handler: The handler to unregister.
        :raises ValueError: If the handler isn't registered.
        """
        self._unitChangedCallbacks.remove(handler)
        self._logger.debug(f"Handler für Gerätestatusänderungen entfernt: {handler}")

    def registerDisconnectCallback(self, callback: Callable[[], None]) -> None:
        """Register a disconnect callback.

        The callback is called whenever the Bluetooth stack reports that
        the Bluetooth connection to the network was disconnected.

        :params callback: The callback to register.
        """
        self._disconnectCallbacks.append(callback)
        self._logger.debug(f"Callback für Verbindungsabbrüche registriert: {callback}")

    def unregisterDisconnectCallback(self, callback: Callable[[], None]) -> None:
        """Unregister an existing disconnect callback.

        :param callback: The callback to unregister.
        :raises ValueError: If the callback isn't registered.
        """
        self._disconnectCallbacks.remove(callback)
        self._logger.debug(f"Callback für Verbindungsabbrüche entfernt: {callback}")

    async def invalidateCache(self, uuid: str) -> None:
        """Invalidates the cache for a network.

        :param uuid: The address of the network.
        """

        # We can't use our own cache here since the invalidation happens
        # before the first connection attempt.
        tempCache = Cache(self._cache._cachePath)
        await tempCache.setUuid(uuid)
        await tempCache.invalidateCache()

    def _disconnectCallback(self) -> None:
        # Mark all units as offline on disconnect.
        for u in self.units:
            u._online = False
            for h in self._unitChangedCallbacks:
                try:
                    h(u)
                except Exception:
                    self._logger.error(
                        f"Fehler im UnitChangedHandler {h} bei Verbindungsabbruch.",
                        exc_info=True,
                    )

        for d in self._disconnectCallbacks:
            try:
                d()
            except Exception:
                self._logger.error(
                    f"Fehler im DisconnectCallback {d} bei Verbindungsabbruch.",
                    exc_info=True,
                )

    async def disconnect(self) -> None:
        """Trenne die Verbindung zum Netzwerk."""
        self._logger.info("Starte Verbindungstrennung vom Casambi-Netzwerk")
        if self._casaClient:
            self._logger.debug("Trenne Bluetooth-Verbindung zum Client")
            try:
                self._logger.debug("Führe sicheres Trennen der Bluetooth-Verbindung durch")
                await asyncio.shield(self._casaClient.disconnect())
                self._logger.debug("Bluetooth-Verbindung erfolgreich getrennt")
            except Exception:
                self._logger.error("Fehler beim Trennen der Bluetooth-Verbindung.", exc_info=True)
        if self._casaNetwork:
            self._logger.debug("Trenne Verbindung zur Casambi-Cloud")
            try:
                await asyncio.shield(self._casaNetwork.disconnect())
                self._logger.debug("Cloud-Verbindung erfolgreich getrennt")
            except Exception:
                self._logger.error("Fehler beim Trennen der Cloud-Verbindung.", exc_info=True)
            self._logger.debug("Setze Netzwerkobjekt zurück")
            self._casaNetwork = None
        if self._ownHttpClient and self._httpClient is not None:
            self._logger.debug("Schließe HTTP-Client-Verbindung")
            try:
                await asyncio.shield(self._httpClient.aclose())
                self._logger.debug("HTTP-Client erfolgreich geschlossen")
            except Exception:
                self._logger.error("Fehler beim Schließen des HTTP-Clients.", exc_info=True)
        
        self._logger.info("Verbindungstrennung vom Casambi-Netzwerk abgeschlossen")
