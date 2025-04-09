import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, cast

import httpx
from httpx import AsyncClient, RequestError

from ._cache import Cache
from ._constants import DEVICE_NAME
from ._keystore import KeyStore
from ._unit import Group, Scene, Unit, UnitControl, UnitControlType, UnitType
from .errors import (
    AuthenticationError,
    NetworkNotFoundError,
    NetworkOnlineUpdateNeededError,
    NetworkUpdateError,
)

# Cache-Dateien für Sitzungsdaten und Gerätetypen
SESSION_CACHE_FILE: Final = "session.pck"  # Speichert Authentifizierungsdaten
TYPES_CACHE_FILE: Final = "types.pck"      # Speichert Informationen zu Gerätetypen


@dataclass()
class _NetworkSession:
    """
    Datenklasse zur Speicherung von Sitzungsinformationen für die Casambi-Cloud-Verbindung.
    
    Eine erfolgreiche Authentifizierung bei der Casambi-Cloud liefert ein Session-Token
    mit zeitlich begrenzter Gültigkeit, das für weitere API-Anfragen verwendet wird.
    """
    session: str      # Sitzungs-Token für API-Anfragen
    network: str      # Netzwerk-ID
    manager: bool     # Flag, ob Benutzer Manager-Rechte hat
    keyID: int        # ID des Schlüssels für die Kommunikation
    expires: datetime # Ablaufzeitpunkt des Tokens
    
    role: int = 3     # Standard: 3 (Benutzer) - andere Rollen könnten in Zukunft unterstützt werden

    def expired(self) -> bool:
        """Prüft, ob das Sitzungs-Token abgelaufen ist."""
        return datetime.utcnow() > self.expires


class Network:
    """
    Hauptklasse für die Kommunikation mit dem Casambi-Netzwerk über die Cloud-API.
    
    Diese Klasse ist verantwortlich für:
    - Authentifizierung bei der Casambi-Cloud
    - Abruf und Speicherung von Netzwerkinformationen (Geräte, Gruppen, Szenen)
    - Caching von Netzwerkdaten für Offline-Betrieb
    - Verwaltung von Gerätetyp-Informationen
    
    Der Verbindungsprozess umfasst mehrere Schritte:
    1. Abruf der Netzwerk-ID anhand der UUID
    2. Authentifizierung mit Passwort
    3. Abruf der Netzwerkdaten (Geräte, Gruppen, Szenen)
    4. Abruf zusätzlicher Gerätetyp-Informationen
    """
    def __init__(self, uuid: str, httpClient: AsyncClient, cache: Cache) -> None:
        """
        Initialisiert die Network-Klasse.
        
        :param uuid: Die Bluetooth-Adresse des Netzwerks ohne Doppelpunkte
        :param httpClient: Ein HTTP-Client für die Kommunikation mit der Casambi-Cloud
        :param cache: Ein Cache-Objekt zum Speichern und Laden von Netzwerkdaten
        """
        self._session: _NetworkSession | None = None

        self._networkName: str | None = None
        self._networkRevision: int | None = None
        self._protocolVersion: int = -1

        self._unitTypes: dict[int, tuple[UnitType | None, datetime]] = {}
        self.units: list[Unit] = []
        self.groups: list[Group] = []
        self.scenes: list[Scene] = []

        self._logger = logging.getLogger(__name__)
        # TODO: Einen LoggingAdapter erstellen, der die UUID als Präfix verwendet, 
        # um Logs verschiedener Netzwerke besser unterscheiden zu können

        self._id: str | None = None
        self._uuid = uuid
        self._httpClient = httpClient

        self._cache = cache

    async def load(self) -> None:
        """
        Lädt Sitzungsdaten und Gerätetypen aus dem Cache.
        
        Diese Methode wird beim Start aufgerufen, um vorhandene Daten
        aus dem Cache zu laden, bevor eine neue Verbindung hergestellt wird.
        """
        # Schlüsselspeicher für die Verschlüsselung initialisieren und laden
        self._keystore = KeyStore(self._cache)
        await self._keystore.load()

        # Vorhandene Sitzung und Typcache laden
        await self._loadSession()
        await self._loadTypeCache()

    async def _loadSession(self) -> None:
        """
        Lädt eine vorhandene Sitzung aus dem Cache, falls vorhanden.
        
        Eine gültige Sitzung ermöglicht eine erneute Verbindung ohne erneute
        Authentifizierung, solange das Token nicht abgelaufen ist.
        """
        self._logger.debug("Lade Sitzungsdaten aus dem Cache...")
        async with self._cache as cachePath:
            if await (cachePath / SESSION_CACHE_FILE).exists():
                sessionData = await (cachePath / SESSION_CACHE_FILE).read_bytes()
                self._session = pickle.loads(sessionData)
                self._logger.info("Sitzungsdaten erfolgreich geladen.")

    async def _saveSesion(self) -> None:
        """
        Speichert die aktuelle Sitzung im Cache für spätere Verwendung.
        
        Ermöglicht eine schnellere Wiederverbindung ohne erneute Authentifizierung.
        """
        self._logger.debug("Speichere Sitzungsdaten im Cache...")
        async with self._cache as cachePath:
            sessionData = pickle.dumps(self._session)
            await (cachePath / SESSION_CACHE_FILE).write_bytes(sessionData)
            self._logger.debug("Sitzungsdaten erfolgreich gespeichert.")

    async def _loadTypeCache(self) -> None:
        """
        Lädt die Gerätetyp-Informationen aus dem Cache.
        
        Gerätetyp-Informationen enthalten wichtige Details über die Fähigkeiten
        und Steuerungsmöglichkeiten der verschiedenen Geräte im Netzwerk.
        """
        self._logger.debug("Lade Gerätetyp-Cache...")
        async with self._cache as cachePath:
            if await (cachePath / TYPES_CACHE_FILE).exists():
                typeData = await (cachePath / TYPES_CACHE_FILE).read_bytes()
                self._unitTypes = pickle.loads(typeData)
                self._logger.info("Gerätetyp-Cache erfolgreich geladen.")

    async def _saveTypeCache(self) -> None:
        """
        Speichert die Gerätetyp-Informationen im Cache.
        
        Da Gerätetyp-Informationen sich selten ändern, werden sie
        für längere Zeit im Cache gespeichert, um API-Aufrufe zu reduzieren.
        """
        self._logger.debug("Speichere Gerätetyp-Cache...")
        async with self._cache as cachePath:
            typeData = pickle.dumps(self._unitTypes)
            await (cachePath / TYPES_CACHE_FILE).write_bytes(typeData)
            self._logger.debug("Gerätetyp-Cache erfolgreich gespeichert.")

    async def getNetworkId(self, forceOffline: bool = False) -> None:
        """
        Ermittelt die Netzwerk-ID anhand der Bluetooth-UUID.
        
        Die Netzwerk-ID ist notwendig für alle weiteren API-Aufrufe.
        Sie wird entweder aus dem Cache geladen oder von der Casambi-Cloud abgerufen.
        
        :param forceOffline: Wenn True, wird nur der Cache verwendet ohne API-Aufrufe
        :raises NetworkOnlineUpdateNeededError: Wenn im Offline-Modus keine ID im Cache ist
        :raises NetworkNotFoundError: Wenn die API kein Netzwerk mit dieser UUID findet
        """
        self._logger.info("Ermittle Netzwerk-ID anhand der UUID...")

        async with self._cache as cachePath:
            networkCacheFile = cachePath / "networkid"

            if await networkCacheFile.exists():
                self._id = await networkCacheFile.read_text()

        if forceOffline:
            if not self._id:
                raise NetworkOnlineUpdateNeededError("Network isn't cached.")
            else:
                return

        # Falls wir nicht offline arbeiten, versuche die Netzwerk-ID von der API zu bekommen
        getNetworkIdUrl = f"https://api.casambi.com/network/uuid/{self._uuid}"
        self._logger.debug(f"Sende Anfrage an Casambi-API: {getNetworkIdUrl}")
        try:
            res = await self._httpClient.get(getNetworkIdUrl)
        except RequestError as err:
            if not self._id:
                raise NetworkOnlineUpdateNeededError from err
            else:
                self._logger.warning(
                    "Netzwerkfehler beim Abruf der Netzwerk-ID. Verwende Cache-Daten.",
                    exc_info=True,
                )
                self._logger.debug(f"Verwende zwischengespeicherte Netzwerk-ID: {self._id}")
                return

        if res.status_code == httpx.codes.NOT_FOUND:
            self._logger.error("Netzwerk wurde von der API nicht gefunden (404).")
            raise NetworkNotFoundError(
                "API konnte kein Netzwerk mit dieser UUID finden. Ist das Netzwerk korrekt konfiguriert?"
            )
        if res.status_code != httpx.codes.OK:
            self._logger.error(f"Unerwarteter Status-Code von der API: {res.status_code}")
            raise NetworkNotFoundError(
                f"Abruf der Netzwerk-ID lieferte unerwarteten Status-Code {res.status_code}"
            )

        new_id = cast(str, res.json()["id"])
        # Prüfe, ob sich die Netzwerk-ID geändert hat und aktualisiere ggf. den Cache
        if self._id != new_id:
            self._logger.info(f"Netzwerk-ID hat sich geändert: {self._id} -> {new_id}.")
            async with self._cache as cachePath:
                networkCacheFile = cachePath / "networkid"
                await networkCacheFile.write_text(new_id)
                self._logger.debug(f"Neue Netzwerk-ID im Cache gespeichert: {new_id}")
            self._id = new_id
        self._logger.info(f"Netzwerk-ID ermittelt: {self._id}.")

    def authenticated(self) -> bool:
        """
        Prüft, ob eine gültige, nicht abgelaufene Sitzung besteht.
        
        :return: True, wenn eine aktive Sitzung mit der Casambi-Cloud besteht
        """
        if not self._session:
            return False
        
        valid = not self._session.expired()
        if not valid:
            self._logger.debug("Sitzung ist abgelaufen und nicht mehr gültig.")
        return valid

    @property
    def keyStore(self) -> KeyStore:
        return self._keystore

    @property
    def protocolVersion(self) -> int:
        return self._protocolVersion

    async def logIn(self, password: str, forceOffline: bool = False) -> None:
        """
        Authentifiziert sich bei der Casambi-Cloud mit dem Netzwerk-Passwort.
        
        Diese Methode erhält ein Session-Token, das für weitere API-Anfragen
        verwendet wird. Das Token wird im Cache gespeichert.
        
        :param password: Das Passwort für das Casambi-Netzwerk
        :param forceOffline: Wenn True, wird keine Authentifizierung durchgeführt
        :raises AuthenticationError: Bei falschen Anmeldedaten oder API-Fehlern
        """
        # Zuerst die Netzwerk-ID ermitteln
        self._logger.debug("Ermittle Netzwerk-ID vor der Authentifizierung")
        await self.getNetworkId(forceOffline)

        # Keine Authentifizierung nötig, wenn wir offline arbeiten oder bereits authentifiziert sind
        if self.authenticated():
            self._logger.info("Bereits authentifiziert mit gültigem Token.")
            return
            
        if forceOffline:
            self._logger.info("Offline-Modus aktiviert, überspringe Authentifizierung.")
            return

        self._logger.info("Authentifiziere bei der Casambi-Cloud...")
        # Sitzungs-Token von der API anfordern
        getSessionUrl = f"https://api.casambi.com/network/{self._id}/session"
        self._logger.debug(f"Sende Authentifizierungsanfrage an: {getSessionUrl}")

        # Passwort und Gerätename an die API senden
        res = await self._httpClient.post(
            getSessionUrl, json={"password": password, "deviceName": DEVICE_NAME}
        )
        self._logger.debug(f"Authentifizierungsantwort erhalten: Status {res.status_code}")
        if res.status_code == httpx.codes.OK:
            # Session-Daten aus der Antwort extrahieren und speichern
            sessionJson = res.json()
            # Umwandlung des Timestamps in ein datetime-Objekt
            sessionJson["expires"] = datetime.utcfromtimestamp(
                sessionJson["expires"] / 1000
            )
            self._session = _NetworkSession(**sessionJson)
            self._logger.info("Authentifizierung erfolgreich! Session-Token erhalten.")
            self._logger.debug(f"Session gültig bis: {self._session.expires.isoformat()}")
            # Sitzungsdaten im Cache speichern für spätere Verwendung
            await self._saveSesion()
        else:
            self._logger.error(f"Authentifizierung fehlgeschlagen: Status {res.status_code}")
            raise AuthenticationError(f"Anmeldung fehlgeschlagen: {res.status_code}\n{res.text}")

    async def update(self, forceOffline: bool = False) -> None:
        """
        Aktualisiert die Netzwerkinformationen (Geräte, Gruppen, Szenen).
        
        Diese Methode ruft die aktuellen Daten vom Casambi-Server ab
        und aktualisiert die lokalen Objekte. Die Daten werden auch im Cache
        gespeichert, um offline arbeiten zu können.
        
        :param forceOffline: Wenn True, werden nur zwischengespeicherte Daten verwendet
        :raises AuthenticationError: Wenn keine gültige Sitzung besteht
        :raises NetworkOnlineUpdateNeededError: Wenn keine Daten im Cache sind
        :raises NetworkUpdateError: Bei API-Fehlern während der Aktualisierung
        """
        self._logger.info("Aktualisiere Netzwerkinformationen...")
        # Prüfen, ob wir authentifiziert sind, falls wir nicht offline arbeiten
        if not self.authenticated() and not forceOffline:
            self._logger.error("Keine gültige Authentifizierung für Netzwerkaktualisierung")
            raise AuthenticationError("Nicht authentifiziert! Bitte zuerst anmelden.")

        # Die Netzwerk-ID muss bekannt sein
        assert self._id is not None, "Netzwerk-ID muss gesetzt sein, bevor Netzwerk aktualisiert werden kann."

        # TODO: Revision speichern und senden, um nur tatsächliche Änderungen zu erhalten?
        # Dies würde die Datenmenge und Ladezeit reduzieren

        async with self._cache as cachePath:
            cachedNetworkPah = cachePath / f"{self._id}.json"
            if await cachedNetworkPah.exists():
                network = json.loads(await cachedNetworkPah.read_bytes())
                self._networkRevision = network["network"]["revision"]
                self._logger.info(
                    f"Netzwerkdaten aus Cache geladen. Revision: {self._networkRevision}"
                )
                self._logger.debug("Verwende zwischengespeicherte Netzwerkdaten")
            else:
                if forceOffline:
                    self._logger.error("Offline-Modus aktiviert, aber keine Netzwerkdaten im Cache vorhanden")
                    raise NetworkOnlineUpdateNeededError("Netzwerkdaten sind nicht im Cache. Online-Update erforderlich.")
                self._logger.debug("Keine Netzwerkdaten im Cache. Setze Revision auf 0 für vollständiges Update.")
                self._networkRevision = 0

        if not forceOffline:
            # Hole Netzwerkdaten von der Casambi-Cloud
            getNetworkUrl = f"https://api.casambi.com/network/{self._id}/"
            self._logger.debug(f"Rufe Netzwerkdaten von API ab: {getNetworkUrl}")

            try:
                # **SICHERHEIT**: Session-Header nur hier setzen, nicht im Client!
                # Dies könnte sonst das Session-Token an externe Clients weitergeben.
                res = await self._httpClient.put(
                    getNetworkUrl,
                    json={
                        "formatVersion": 1,
                        "deviceName": DEVICE_NAME,
                        "revision": self._networkRevision,
                    },
                    headers={"X-Casambi-Session": self._session.session},  # type: ignore[union-attr]
                )

                # Dies passiert typischerweise, wenn sich das Netzwerk-Passwort geändert hat.
                # In diesem Fall sollten wir zumindest die Sitzung ungültig machen.
                # Aktuell invalidieren wir den gesamten Cache, da seine Neuerstellung nicht viel kostet.
                # HTTP 410 GONE bedeutet, dass das Netzwerk gelöscht oder neu konfiguriert wurde
                if res.status_code == httpx.codes.GONE:
                    self._logger.error(
                        "API meldet, dass das Netzwerk nicht mehr existiert. Lösche Cache und versuche später erneut."
                    )
                    self._logger.debug("Cache wird invalidiert, da Netzwerk nicht mehr existiert")
                    await self._cache.invalidateCache()

                # Prüfe auf andere Fehler
                if res.status_code != httpx.codes.OK:
                    self._logger.error(f"Netzwerkaktualisierung fehlgeschlagen: Status {res.status_code}")
                    self._logger.debug(f"API-Antwort: {res.text}")
                    raise NetworkUpdateError(f"Netzwerk konnte nicht aktualisiert werden! Status: {res.status_code}")

                # Verarbeite die erhaltenen Netzwerkdaten
                self._logger.debug("Netzwerkdaten erfolgreich von API erhalten")

                updateResult = res.json()
                # Prüfe, ob Aktualisierung notwendig ist
                if updateResult["status"] != "UPTODATE":
                    self._networkRevision = updateResult["network"]["revision"]
                    # Speichere die neuen Netzwerkdaten im Cache
                    async with self._cache as cachePath:
                        cachedNetworkPah = cachePath / f"{self._id}.json"
                        await cachedNetworkPah.write_bytes(res.content)
                        self._logger.debug(f"Neue Netzwerkdaten im Cache gespeichert: {self._id}.json")
                    network = updateResult
                    self._logger.info(
                        f"Aktualisierte Netzwerkdaten mit Revision {self._networkRevision} erhalten"
                    )
                else:
                    self._logger.info("Netzwerkdaten bereits aktuell, keine Änderungen notwendig")
            except RequestError as err:
                # Bei Netzwerkfehlern
                if self._networkRevision == 0:
                    # Wenn wir noch keine Daten haben, können wir nicht offline weiterarbeiten
                    self._logger.error("Netzwerkfehler bei erster Aktualisierung, keine Daten im Cache")
                    raise NetworkUpdateError from err
                self._logger.warning(
                    "Netzwerkfehler bei Aktualisierung. Arbeite mit zwischengespeicherten Daten weiter.",
                    exc_info=True
                )
                self._logger.debug(f"Verwende Netzwerkdaten aus Cache mit Revision {self._networkRevision}")

        # Parsen der allgemeinen Netzwerkinformationen
        self._logger.debug("Verarbeite Netzwerkdaten...")
        self._networkName = network["network"]["name"]
        self._protocolVersion = network["network"]["protocolVersion"]
        self._logger.debug(f"Netzwerkname: {self._networkName}, Protokollversion: {self._protocolVersion}")

        # Parsen der Verschlüsselungsschlüssel für die Bluetooth-Kommunikation
        if "keyStore" in network["network"]:
            self._logger.debug("Verarbeite Schlüssel aus dem Schlüsselspeicher")
            keys = network["network"]["keyStore"]["keys"]
            for k in keys:
                await self._keystore.addKey(k)
            self._logger.debug(f"{len(keys)} Schlüssel zum Schlüsselspeicher hinzugefügt")

        # TODO: Manager- und Besucher-Schlüssel für klassische Netzwerke parsen.
        # Dies wäre für ältere Casambi-Netzwerke relevant

        # Parsen der Geräte (Units) im Netzwerk
        self._logger.debug("Verarbeite Geräte (Units)...")
        self.units = []
        units = network["network"]["units"]
        self._logger.debug(f"Gefundene Geräte: {len(units)}")
        
        for u in units:
            # Gerätetyp-Informationen abrufen (entweder aus Cache oder von der API)
            self._logger.debug(f"Hole Typinformationen für Gerät mit Typ-ID {u['type']}")
            uType = await self._fetchUnitInfo(u["type"])
            if uType is None:
                self._logger.info(
                    f"Konnte Typinformationen für Gerät {u['type']} nicht abrufen. Überspringe."
                )
                continue
            # Gerät-Objekt erstellen und zur Liste hinzufügen
            uObj = Unit(
                u["type"],        # Typ-ID des Geräts
                u["deviceID"],    # Interne Geräte-ID
                u["uuid"],        # Eindeutige ID des Geräts
                u["address"],     # Bluetooth-Adresse
                u["name"],        # Name des Geräts
                str(u["firmware"]), # Firmware-Version
                uType,            # Typinformationen mit Steuerungsmöglichkeiten
            )
            self.units.append(uObj)
            self._logger.debug(f"Gerät hinzugefügt: {uObj.name} (ID: {uObj.deviceId})")

        # Parsen der Gruppen (Cells)
        self._logger.debug("Verarbeite Gruppen...")
        self.groups = []
        cells = network["network"]["grid"]["cells"]
        self._logger.debug(f"Gefundene Zellen im Grid: {len(cells)}")
        for c in cells:
            # Aktuell wird nur ein Zellentyp auf oberster Ebene unterstützt (Typ 2 = Gruppe)
            if c["type"] != 2:
                continue

            # Parsen der Gruppenmitglieder (enthaltene Geräte)
            group_units = []
            # Wir gehen davon aus, dass es keine verschachtelten Gruppen gibt
            self._logger.debug(f"Verarbeite Gruppe '{c['name']}' (ID: {c['groupID']}) mit {len(c['cells'])} Zellen")
            for subC in c["cells"]:
                # Ignoriere alles, was kein Gerät ist (Typ 1 = Gerät)
                if subC["type"] != 1:
                    self._logger.debug(f"Überspringe Zelle mit Typ {subC['type']} (kein Gerät)")
                    continue

                # Suche das passende Gerät anhand der ID
                unitMatch = list(
                    filter(lambda u: u.deviceId == subC["unit"], self.units)
                )
                if len(unitMatch) != 1:
                    self._logger.warning(
                        f"Inkonsistente Gerätereferenz {subC['unit']} in Gruppe {c['groupID']}. {len(unitMatch)} Übereinstimmungen gefunden."
                    )
                    continue
                # Gerät zur Gruppe hinzufügen
                group_units.append(unitMatch[0])
                self._logger.debug(f"Gerät '{unitMatch[0].name}' zur Gruppe hinzugefügt")

            gObj = Group(c["groupID"], c["name"], group_units)
            self.groups.append(gObj)

        self._logger.debug(f"Verarbeitete Gruppen: {len(self.groups)}")

        # Parsen der Szenen
        self._logger.debug("Verarbeite Szenen...")
        self.scenes = []
        scenes = network["network"]["scenes"]
        self._logger.debug(f"Gefundene Szenen: {len(scenes)}")
        for s in scenes:
            # Szenen-Objekt erstellen und zur Liste hinzufügen
            sObj = Scene(s["sceneID"], s["name"])
            self.scenes.append(sObj)
            self._logger.debug(f"Szene hinzugefügt: {sObj.name} (ID: {sObj.sceneId})")

        # TODO: Weitere Netzwerkelemente parsen
        # - Hier könnten in Zukunft zusätzliche Informationen wie Zeitpläne oder benutzerdefinierte Einstellungen verarbeitet werden

        # Gerätetyp-Cache speichern für zukünftige Verwendung
        await self._saveTypeCache()

        self._logger.info("Netzwerkaktualisierung abgeschlossen.")
        self._logger.debug(f"Statistik: {len(self.units)} Geräte, {len(self.groups)} Gruppen, {len(self.scenes)} Szenen")

    async def _fetchUnitInfo(self, id: int) -> UnitType | None:
        """
        Lädt Typinformationen für ein bestimmtes Gerät.
        
        Diese Methode ruft detaillierte Informationen über einen Gerätetyp ab,
        die für die korrekte Steuerung und Statusinterpretation benötigt werden.
        Die Informationen werden zunächst im Cache gesucht und nur bei Bedarf
        von der API abgerufen.
        
        :param id: Die Typ-ID des Geräts
        :return: Ein UnitType-Objekt oder None bei Fehlern
        """
        self._logger.info(f"Hole Typinformationen für Gerätetyp mit ID {id}...")

        # Prüfe, ob der Typ bereits im Cache ist
        if id in self._unitTypes:
            cachedType, cacheExpiry = self._unitTypes[id]

            # Typen haben ein Ablaufdatum im Cache, um gelegentliche Updates zu ermöglichen
            if cacheExpiry < datetime.utcnow():
                self._logger.info(f"Cache für Typ {id} abgelaufen. Hole neue Daten.")
                self._unitTypes.pop(id)
            else:
                self._logger.info(f"Verwende zwischengespeicherte Typinformationen für ID {id}.")
                self._logger.debug(f"Cache gültig bis: {cacheExpiry.isoformat()}")
                return cachedType

        # Falls nicht im Cache, von der API abrufen
        getUnitInfoUrl = f"https://api.casambi.com/fixture/{id}"
        self._logger.debug(f"Rufe Gerätetyp-Informationen von API ab: {getUnitInfoUrl}")
        res = await self._httpClient.get(getUnitInfoUrl)

        # Bei Fehlern temporär im Cache als "nicht verfügbar" markieren
        if res.status_code != httpx.codes.OK:
            self._logger.error(f"Abruf der Gerätetyp-Informationen fehlgeschlagen: Status {res.status_code}")
            # Negative Caching: Speichere den Fehler für 7 Tage, um wiederholte Anfragen zu vermeiden
            self._unitTypes[id] = (
                None,
                datetime.utcnow() + timedelta(days=7),
            )
            self._logger.debug(f"Typ {id} im negativen Cache gespeichert für 7 Tage")
            return None

        # Parsen der Typinformationen aus der API-Antwort
        unitTypeJson = res.json()
        self._logger.debug(f"Gerätetyp-Informationen erhalten: {unitTypeJson['model']} von {unitTypeJson['vendor']}")

        # Parsen der Steuerungsmöglichkeiten (UnitControls)
        self._logger.debug("Verarbeite Steuerungsmöglichkeiten des Geräts...")
        controls = []
        for controlJson in unitTypeJson["controls"]:
            typeStr = controlJson["type"].upper()
            try:
                type = UnitControlType[typeStr]
            except KeyError:
                self._logger.warning(
                    f"Nicht unterstützter Steuerungsmodus '{typeStr}' in Gerätetyp {id}."
                )
                self._logger.debug(f"Verwende UNKNOWN als Fallback für Steuerungsmodus '{typeStr}'")
                type = UnitControlType.UNKOWN

            controlObj = UnitControl(
                type,
                controlJson["offset"],
                controlJson["length"],
                controlJson["default"],
                controlJson["readonly"],
                controlJson.get("min", None),
                controlJson.get("max", None),
            )

            controls.append(controlObj)

        # Gerätetyp-Objekt erstellen mit allen Steuerungsmöglichkeiten
        self._logger.debug(f"Erstelle UnitType-Objekt für Modell {unitTypeJson['model']} mit {len(controls)} Steuerungsmöglichkeiten")
        unitTypeObj = UnitType(
            unitTypeJson["id"],
            unitTypeJson["model"],
            unitTypeJson["vendor"],
            unitTypeJson["mode"],
            unitTypeJson["stateLength"],
            controls,
        )

        # Gerätetyp im Cache speichern (gültig für 28 Tage)
        self._unitTypes[unitTypeObj.id] = (
            unitTypeObj,
            datetime.utcnow() + timedelta(days=28),
        )
        self._logger.debug(f"Gerätetyp {id} im Cache gespeichert für 28 Tage")

        self._logger.info(f"Gerätetyp-Informationen erfolgreich abgerufen: {unitTypeObj.model}")
        return unitTypeObj

    async def disconnect(self) -> None:
        """
        Trennt die Verbindung zum Netzwerk.
        
        Diese Methode ist ein Platzhalter für zukünftige Funktionalität.
        Aktuell werden keine aktiven Verbindungen zur Cloud aufrechterhalten,
        die explizit getrennt werden müssten.
        """
        self._logger.debug("Netzwerk-Verbindung wird getrennt (keine Aktion erforderlich)")
        return None
