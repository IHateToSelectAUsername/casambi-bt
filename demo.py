import asyncio
import logging
import sys
import time

from CasambiBt import Casambi, discover

# ---- LOGGING-SETUP FÜR DETAILLIERTE VERFOLGUNG ----
# Eigenes Log-Format mit Zeitstempel, Level und Nachricht erstellen
LOG_FORMAT = '%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s'
DATE_FORMAT = '%H:%M:%S'

# Root-Logger konfigurieren
_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.DEBUG)  # Root-Logger auf DEBUG setzen, um alle Nachrichten zu erfassen

# Console-Handler mit detailliertem Format
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
_LOGGER.addHandler(console_handler)

# Optional: Datei-Logger für spätere Analyse
file_handler = logging.FileHandler('casambi_demo.log')
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
_LOGGER.addHandler(file_handler)


async def main() -> None:
    _LOGGER.info("==================== DEMO GESTARTET ====================")
    
    # Alle Bibliotheks-Logger auf DEBUG setzen
    logging.getLogger("CasambiBt").setLevel(logging.DEBUG)
    _LOGGER.info("Logger auf DEBUG-Level gesetzt")

    # ---- PHASE 1: NETZWERKE ENTDECKEN ----
    _LOGGER.info("PHASE 1: STARTE NETZWERK-DISCOVERY")
    print("Searching...")
    
    discovery_start = time.time()
    _LOGGER.debug("Rufe discover() auf - Suche nach Casambi-Netzwerken in Bluetooth-Reichweite")
    devices = await discover()
    discovery_time = time.time() - discovery_start
    
    _LOGGER.info(f"Discovery abgeschlossen in {discovery_time:.2f} Sekunden")
    _LOGGER.info(f"Gefundene Geräte: {len(devices)}")
    
    # Anzeigen der gefundenen Netzwerke mit einem Index zur Auswahl
    for i, d in enumerate(devices):
        device_info = f"[{i}]\t{d.address}"
        print(device_info)
        _LOGGER.info(f"Gefundenes Gerät: {device_info}")
    
    if not devices:
        _LOGGER.error("Keine Geräte gefunden! Stellen Sie sicher, dass Bluetooth aktiviert ist und Casambi-Netzwerke in Reichweite sind.")
        return
    
    # Benutzer wählt ein Netzwerk aus der Liste
    selection = int(input("Select network: "))
    device = devices[selection]
    _LOGGER.info(f"Netzwerk [{selection}] mit Adresse {device.address} ausgewählt")
    
    if hasattr(device, 'name') and device.name:
        _LOGGER.info(f"Gerätename: {device.name}")
    
    # Passwort für das Netzwerk abfragen
    pwd = input("Enter password: ")
    _LOGGER.info("Passwort eingegeben (aus Sicherheitsgründen nicht geloggt)")

    # ---- PHASE 2: VERBINDUNG UND AUTHENTIFIZIERUNG ----
    _LOGGER.info("PHASE 2: STARTE VERBINDUNG UND AUTHENTIFIZIERUNG")
    
    # Erstellen einer Casambi-Instanz
    _LOGGER.debug("Erstelle Casambi-Instanz")
    casa = Casambi()
    _LOGGER.debug("Casambi-Instanz erstellt")
    
    try:
        # Verbindung zum Netzwerk herstellen
        _LOGGER.info(f"Beginne Verbindungsaufbau zu {device.address}")
        connection_start = time.time()
        
        _LOGGER.debug("Rufe casa.connect() auf - Dieser Prozess beinhaltet:")
        _LOGGER.debug("  1. Verbindung zur Casambi-Cloud zur Authentifizierung")
        _LOGGER.debug("  2. Abruf der Netzwerkinformationen (Geräte, Gruppen, Szenen)")
        _LOGGER.debug("  3. Aufbau der Bluetooth-Verbindung") 
        _LOGGER.debug("  4. Schlüsselaustausch und lokale Authentifizierung")
        
        await casa.connect(device, pwd)
        
        connection_time = time.time() - connection_start
        _LOGGER.info(f"Verbindung erfolgreich hergestellt in {connection_time:.2f} Sekunden")
        
        # Log Netzwerkinformationen
        _LOGGER.info(f"Verbunden mit Netzwerk: {casa.networkName}")
        _LOGGER.info(f"Netzwerk-ID: {casa.networkId}")
        _LOGGER.info(f"Anzahl Geräte: {len(casa.units)}")
        _LOGGER.info(f"Anzahl Gruppen: {len(casa.groups)}")
        _LOGGER.info(f"Anzahl Szenen: {len(casa.scenes)}")
        
        # ---- PHASE 3: GERÄTESTEUERUNG ----
        _LOGGER.info("PHASE 3: STARTE GERÄTESTEUERUNG")
        
        # Alle Lichter einschalten
        _LOGGER.info("Schalte alle Lichter ein (casa.turnOn(None))")
        turn_on_start = time.time()
        await casa.turnOn(None)
        _LOGGER.info(f"Alle Lichter eingeschaltet in {time.time() - turn_on_start:.2f} Sekunden")
        
        # Status der Geräte nach dem Einschalten
        _LOGGER.debug("Status nach dem Einschalten:")
        for unit in casa.units:
            _LOGGER.debug(f"Gerät {unit.name} (ID: {unit.deviceId}): Eingeschaltet={unit.is_on}, Online={unit.online}")
            if unit.state:
                _LOGGER.debug(f"  Zustand: {unit.state}")
        
        # 5 Sekunden warten
        _LOGGER.info("Warte 5 Sekunden")
        await asyncio.sleep(5)
        _LOGGER.info("Wartezeit beendet")

        # Alle Lichter ausschalten (Helligkeit auf 0)
        _LOGGER.info("Schalte alle Lichter aus (casa.setLevel(None, 0))")
        turn_off_start = time.time()
        await casa.setLevel(None, 0)
        _LOGGER.info(f"Alle Lichter ausgeschaltet in {time.time() - turn_off_start:.2f} Sekunden")
        
        # Status der Geräte nach dem Ausschalten
        _LOGGER.debug("Status nach dem Ausschalten:")
        for unit in casa.units:
            _LOGGER.debug(f"Gerät {unit.name} (ID: {unit.deviceId}): Eingeschaltet={unit.is_on}, Online={unit.online}")
            if unit.state:
                _LOGGER.debug(f"  Zustand: {unit.state}")
        
        await asyncio.sleep(1)
        _LOGGER.info("Kurze Wartezeit beendet")

        # ---- PHASE 4: NETZWERKINFORMATIONEN ANZEIGEN ----
        _LOGGER.info("PHASE 4: ZEIGE NETZWERKINFORMATIONEN")
        
        print("\nGeräte im Netzwerk:")
        for i, u in enumerate(casa.units):
            print(f"Gerät {i}: {u.__repr__()}")
            _LOGGER.info(f"Gerät {i}: {u.__repr__()}")
            
            # Zusätzliche Informationen über das Gerät
            _LOGGER.debug(f"  Typ-ID: {u._typeId}")
            _LOGGER.debug(f"  Geräte-ID: {u.deviceId}")
            _LOGGER.debug(f"  UUID: {u.uuid}")
            _LOGGER.debug(f"  Adresse: {u.address}")
            _LOGGER.debug(f"  Name: {u.name}")
            _LOGGER.debug(f"  Firmware: {u.firmwareVersion}")
            _LOGGER.debug(f"  Eingeschaltet: {u.is_on}")
            _LOGGER.debug(f"  Online: {u.online}")
            
            # Zusätzliche Informationen über verfügbare Steuerelemente
            _LOGGER.debug(f"  Unterstützte Steuerelemente:")
            for control in u.unitType.controls:
                _LOGGER.debug(f"    - {control.type.name}: Offset={control.offset}, Länge={control.length}, Standard={control.default}")
        
        # Gruppen-Informationen
        if casa.groups:
            _LOGGER.info("Gruppen im Netzwerk:")
            for i, g in enumerate(casa.groups):
                _LOGGER.info(f"  Gruppe {i}: {g.name} (ID: {g.groudId}), Enthält {len(g.units)} Geräte")
                # Liste der Geräte in der Gruppe
                for unit in g.units:
                    _LOGGER.debug(f"    - Gerät: {unit.name} (ID: {unit.deviceId})")
        
        # Szenen-Informationen
        if casa.scenes:
            _LOGGER.info("Szenen im Netzwerk:")
            for i, s in enumerate(casa.scenes):
                _LOGGER.info(f"  Szene {i}: {s.name} (ID: {s.sceneId})")
    
    except Exception as e:
        _LOGGER.exception(f"Fehler während der Demo: {str(e)}")
        _LOGGER.error(f"Details: {type(e).__name__}: {str(e)}")
        raise
    
    finally:
        # ---- PHASE 5: VERBINDUNG TRENNEN ----
        _LOGGER.info("PHASE 5: TRENNE VERBINDUNG")
        
        disconnect_start = time.time()
        await casa.disconnect()
        _LOGGER.info(f"Verbindung getrennt in {time.time() - disconnect_start:.2f} Sekunden")
        _LOGGER.info("==================== DEMO BEENDET ====================")


if __name__ == "__main__":
    _LOGGER.debug("Erstelle asyncio Event-Loop")
    loop = asyncio.new_event_loop()
    
    try:
        _LOGGER.debug("Starte main()-Funktion in der Event-Loop")
        loop.run_until_complete(main())
    except Exception as e:
        _LOGGER.exception(f"Unbehandelte Ausnahme: {str(e)}")
    finally:
        _LOGGER.debug("Schließe Event-Loop")
        loop.close()