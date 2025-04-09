import asyncio
import logging
import sys
import time
from logging import StreamHandler, FileHandler, Formatter

from CasambiBt import Casambi, discover

# ANSI-Farbcodes für Terminalausgabe
COLORS = {
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
    'BLACK': '\033[30m',
    'RED': '\033[31m',
    'GREEN': '\033[32m',
    'YELLOW': '\033[33m',
    'BLUE': '\033[34m',
    'MAGENTA': '\033[35m',
    'CYAN': '\033[36m',
    'WHITE': '\033[37m',
    'BRIGHT_BLACK': '\033[90m',
    'BRIGHT_RED': '\033[91m',
    'BRIGHT_GREEN': '\033[92m',
    'BRIGHT_YELLOW': '\033[93m',
    'BRIGHT_BLUE': '\033[94m',
    'BRIGHT_MAGENTA': '\033[95m',
    'BRIGHT_CYAN': '\033[96m',
    'BRIGHT_WHITE': '\033[97m',
}

# Farbiger Terminal-Output für Benutzereingaben und UI-Elemente
def print_ui(message, color=COLORS['BRIGHT_MAGENTA']):
    """Gibt eine farbige UI-Nachricht aus"""
    print(f"{color}{message}{COLORS['RESET']}")

def input_ui(prompt, color=COLORS['BRIGHT_MAGENTA']):
    """Fordert Benutzereingabe mit farbigem Prompt an"""
    return input(f"{color}{prompt}{COLORS['RESET']}")

def print_info(title, message, color=COLORS['BRIGHT_BLUE']):
    """Gibt eine formatierte Info-Nachricht mit Titel und Erklärung aus"""
    print_ui(f"ℹ️ {title}", color)
    print_ui(f"   {message}", COLORS['BRIGHT_WHITE'])

# Benutzerdefinierten Formatter erstellen
class ColoredFormatter(Formatter):
    """Formatter, der Logger-Namen, Log-Level UND Nachrichten farblich hervorhebt"""
    
    def format(self, record):
        # Original-Format speichern
        orig_format = self._style._fmt
        # Farben basierend auf Quelle und Log-Level festlegen
        name_color = COLORS['BRIGHT_BLACK']
        level_color = COLORS['BRIGHT_BLACK']
        message_color = COLORS['BRIGHT_BLACK']
        
        # Spezielle Farben für die Demo-Anwendung
        if record.name == "__main__":
            name_color = COLORS['BRIGHT_CYAN']
            level_color = COLORS['CYAN']
            message_color = COLORS['CYAN']
        
        # Farben für verschiedene Log-Level
        if record.levelno >= logging.ERROR:
            level_color = COLORS['RED']
            message_color = COLORS['RED']
        elif record.levelno >= logging.WARNING:
            level_color = COLORS['YELLOW']
            message_color = COLORS['YELLOW']
        elif record.levelno >= logging.INFO:
            # Info behält die oben festgelegte Farbe
            pass
            
        # Format mit Farben anpassen
        colored_format = (
            '%(asctime)s.%(msecs)03d '
            f'[{level_color}%(levelname)s{COLORS["RESET"]}] '
            f'{name_color}%(name)s{COLORS["RESET"]}: '
            f'{message_color}%(message)s{COLORS["RESET"]}'
        )
        
        self._style._fmt = colored_format
        
        # Log-Eintrag formatieren und Original-Format wiederherstellen
        result = Formatter.format(self, record)
        self._style._fmt = orig_format
        
        return result

# Logging-Handler für Konsole mit farbiger Ausgabe
console_handler = StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter(
    fmt='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
))

# Logging-Handler für Datei (ohne Farben)
file_handler = FileHandler('casambi_connect.log')
file_handler.setFormatter(Formatter(
    fmt='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
))

# Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[console_handler, file_handler]
)

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Hauptfunktion zur Demonstration des Verbindungsaufbaus zu einem Casambi-Netzwerk."""
    _LOGGER.info("===== DEMO: CASAMBI NETZWERK-VERBINDUNG =====")
    
    print_ui("\n🔍 CASAMBI NETZWERK-VERBINDUNG DEMO", COLORS['BRIGHT_WHITE'])
    print_ui("======================================", COLORS['BRIGHT_WHITE'])
    print_ui("Diese Demo zeigt den kompletten Verbindungsprozess zu einem Casambi-Netzwerk.", COLORS['BRIGHT_WHITE'])
    print_info("Verbindungsprozess", "Der Verbindungsprozess zu einem Casambi-Netzwerk umfasst mehrere Schritte:")
    print_ui("  1. Suche nach Casambi-Netzwerken in Bluetooth-Reichweite", COLORS['BRIGHT_WHITE'])
    print_ui("  2. Verbindung zur Casambi-Cloud zur Authentifizierung", COLORS['BRIGHT_WHITE'])
    print_ui("  3. Abruf der Netzwerkinformationen (Geräte, Gruppen, Szenen)", COLORS['BRIGHT_WHITE'])
    print_ui("  4. Aufbau der Bluetooth-Verbindung mit Schlüsselaustausch", COLORS['BRIGHT_WHITE'])
    print_ui("  5. Anzeige der Netzwerkinformationen und Steuerung der Geräte", COLORS['BRIGHT_WHITE'])
    print_ui("")
    
    # Setze den Logger der CasambiBt-Bibliothek auf DEBUG-Level für detaillierte Ausgaben
    logging.getLogger("CasambiBt").setLevel(logging.DEBUG)
    
    try:
        # --- SCHRITT 1: Bluetooth-Gerätesuche starten ---
        print_ui("\n🔍 SCHRITT 1: BLUETOOTH-GERÄTESUCHE", COLORS['BRIGHT_GREEN'])
        print_ui("--------------------------------", COLORS['BRIGHT_GREEN'])
        print_info("Gerätesuche", "Die Bibliothek sucht nach Casambi-Netzwerken in Bluetooth-Reichweite")
        print_ui("Technischer Hintergrund:", COLORS['BRIGHT_BLUE'])
        print_ui("  - Verwendet BleakScanner.discover() für die BLE-Gerätesuche", COLORS['BRIGHT_WHITE'])
        print_ui("  - Filtert nach Herstellerkennung (963) und spezieller Casambi-UUID", COLORS['BRIGHT_WHITE'])
        print_ui("  - Gibt gefundene Geräte als BLEDevice-Objekte zurück", COLORS['BRIGHT_WHITE'])
        
        _LOGGER.info("Starte Suche nach Casambi-Netzwerken in Bluetooth-Reichweite...")
        print_ui("Suche läuft...", COLORS['BRIGHT_YELLOW'])
        
        # Rufe die discover()-Funktion auf, die alle Casambi-Netzwerke in Reichweite sucht
        discovery_start = time.time()
        devices = await discover()
        discovery_time = time.time() - discovery_start
        
        _LOGGER.info(f"Suche abgeschlossen in {discovery_time:.2f} Sekunden. "
                    f"Gefundene Geräte: {len(devices)}")
        _LOGGER.debug(f"Suchmethode: BleakScanner.discover() mit Filterung nach Casambi-spezifischen Attributen")
        
        # Zeige die gefundenen Geräte mit einem Index an
        if not devices:
            print_ui("\nKeine Casambi-Netzwerke gefunden!", COLORS['BRIGHT_RED'])
            print_ui("Bitte stellen Sie sicher, dass:", COLORS['BRIGHT_WHITE'])
            print_ui("1. Bluetooth auf Ihrem Gerät aktiviert ist", COLORS['BRIGHT_WHITE'])
            print_ui("2. Casambi-Netzwerke in Reichweite sind", COLORS['BRIGHT_WHITE'])
            print_ui("3. Die Casambi-Geräte eingeschaltet sind", COLORS['BRIGHT_WHITE'])
            return
            
        print_ui("\nGefundene Casambi-Netzwerke:", COLORS['BRIGHT_GREEN'])
        print_ui("-----------------------------", COLORS['BRIGHT_GREEN'])
        for i, device in enumerate(devices):
            # Zeige Adresse und falls vorhanden, den Namen des Geräts
            device_info = f"[{i}] Adresse: {device.address}"
            if hasattr(device, 'name') and device.name:
                device_info += f", Name: {device.name}"
            
            print_ui(device_info, COLORS['BRIGHT_WHITE'])
            _LOGGER.debug(f"Gerät gefunden: {device_info}")
        
        # --- SCHRITT 2: Gerät auswählen und Verbindungsdaten eingeben ---
        print_ui("\n🔑 SCHRITT 2: NETZWERKAUSWAHL UND AUTHENTIFIZIERUNG", COLORS['BRIGHT_GREEN'])
        print_ui("----------------------------------------------", COLORS['BRIGHT_GREEN'])
        print_info("Netzwerkauswahl", "Wählen Sie ein Netzwerk und geben Sie das Passwort ein")
        print_ui("Technischer Hintergrund:", COLORS['BRIGHT_BLUE'])
        print_ui("  - Die BLE-Adresse identifiziert eindeutig das Casambi-Netzwerk", COLORS['BRIGHT_WHITE'])
        print_ui("  - Das Passwort wird für die Authentifizierung bei der Casambi-Cloud benötigt", COLORS['BRIGHT_WHITE'])
        print_ui("  - Bei erfolgreicher Authentifizierung werden Zugriffsschlüssel erhalten", COLORS['BRIGHT_WHITE'])
        
        print_ui("\nBitte wählen Sie ein Netzwerk aus der Liste:", COLORS['BRIGHT_MAGENTA'])
        selection = int(input_ui("Nummer eingeben: ", COLORS['BRIGHT_MAGENTA']))
        
        # Überprüfe, ob die Auswahl gültig ist
        if selection < 0 or selection >= len(devices):
            print_ui(f"Ungültige Auswahl: {selection}", COLORS['BRIGHT_RED'])
            return
            
        # Ausgewähltes Gerät
        device = devices[selection]
        _LOGGER.info(f"Netzwerk [{selection}] mit Adresse {device.address} ausgewählt")
        
        # Passwort für das Netzwerk abfragen
        print_ui("\nBitte geben Sie das Passwort für das Casambi-Netzwerk ein:", COLORS['BRIGHT_MAGENTA'])
        password = input_ui("Passwort: ", COLORS['BRIGHT_MAGENTA'])
        _LOGGER.info("Passwort eingegeben (aus Sicherheitsgründen nicht geloggt)")
        
        # --- SCHRITT 3: Verbindung zum Netzwerk herstellen ---
        print_ui("\n🔌 SCHRITT 3: VERBINDUNGSAUFBAU", COLORS['BRIGHT_GREEN'])
        print_ui("---------------------------", COLORS['BRIGHT_GREEN'])
        print_info("Verbindungsaufbau", "Der Verbindungsprozess umfasst mehrere Phasen")
        print_ui("Technischer Hintergrund:", COLORS['BRIGHT_BLUE'])
        print_ui("  - Zuerst erfolgt eine Anfrage an die Casambi-Cloud", COLORS['BRIGHT_WHITE'])
        print_ui("  - Nach Authentifizierung werden Netzwerkdaten geladen", COLORS['BRIGHT_WHITE'])
        print_ui("  - Anschließend wird eine Bluetooth-Verbindung zum Gateway aufgebaut", COLORS['BRIGHT_WHITE'])
        print_ui("  - Es folgt ein Schlüsselaustausch und lokale Authentifizierung", COLORS['BRIGHT_WHITE'])
        
        print_ui("\nVerbindung wird hergestellt...", COLORS['BRIGHT_YELLOW'])
        _LOGGER.info(f"Beginne Verbindungsaufbau zu {device.address}")
        # Erkläre den Verbindungsprozess
        _LOGGER.debug("Der Verbindungsprozess umfasst mehrere Schritte:")
        _LOGGER.debug("1. Verbindung zur Casambi-Cloud zur Authentifizierung")
        _LOGGER.debug("2. Abruf der Netzwerkinformationen (Geräte, Gruppen, Szenen)")
        _LOGGER.debug("3. Aufbau der Bluetooth-Verbindung")
        _LOGGER.debug("4. Schlüsselaustausch und lokale Authentifizierung")
        
        # Detaillierte Erklärungen hinzufügen
        _LOGGER.debug("Initialisiere Casambi-Objekt...")
        
        # Erstellen einer Casambi-Instanz
        _LOGGER.debug("Erstelle Casambi-Instanz")
        casa = Casambi()
        _LOGGER.debug("Casambi-Instanz erstellt - dies ist die Hauptklasse zur Steuerung des Netzwerks")
        
        # Verbindung herstellen
        # Verbindung herstellen
        print_ui("\nVerbindung wird aufgebaut...", COLORS['BRIGHT_YELLOW'])
        print_ui("Der Verbindungsprozess läuft automatisch in mehreren Phasen ab:", COLORS['BRIGHT_WHITE'])
        print_ui("- Die Logs der Bibliothek zeigen den detaillierten Fortschritt", COLORS['BRIGHT_WHITE'])
        print_ui("- Bitte warten Sie, bis alle Phasen abgeschlossen sind", COLORS['BRIGHT_WHITE'])
        
        connection_start = time.time()
        
        # Führe den tatsächlichen Verbindungsaufbau durch
        # (dieser durchläuft intern alle Phasen: Cloud-Auth, Netzwerkdaten, BLE-Verbindung, Schlüsselaustausch)
        await casa.connect(device, password)
        connection_time = time.time() - connection_start
        
        _LOGGER.info(f"Verbindung erfolgreich hergestellt in {connection_time:.2f} Sekunden")
        print_ui(f"\n✅ Verbindung erfolgreich hergestellt!", COLORS['BRIGHT_GREEN'])
        
        # Erkläre nachträglich, was passiert ist
        print_info("Verbindungsprozess abgeschlossen", "Folgende Phasen wurden durchlaufen:")
        print_ui("1. Verbindung zur Casambi-Cloud und Authentifizierung", COLORS['BRIGHT_WHITE'])
        print_ui("2. Abruf der Netzwerkinformationen (Geräte, Gruppen, Szenen)", COLORS['BRIGHT_WHITE'])
        print_ui("3. Bluetooth-Verbindung zum Gateway-Gerät", COLORS['BRIGHT_WHITE'])
        print_ui("4. Schlüsselaustausch und lokale Authentifizierung", COLORS['BRIGHT_WHITE'])
        print_ui("→ Netzwerkinformationen sind nun verfügbar und können angezeigt werden", COLORS['BRIGHT_WHITE'])
        
        # --- SCHRITT 4: Netzwerkinformationen anzeigen ---
        print_ui("\n📊 SCHRITT 4: NETZWERKINFORMATIONEN", COLORS['BRIGHT_GREEN'])
        print_ui("-------------------------------", COLORS['BRIGHT_GREEN'])
        print_info("Netzwerkdaten", "Anzeige der abgerufenen Informationen über das Casambi-Netzwerk")
        print_ui("Technischer Hintergrund:", COLORS['BRIGHT_BLUE'])
        print_ui("  - Netzwerkdaten werden aus dem Cloud-Speicher und lokalen Cache zusammengeführt", COLORS['BRIGHT_WHITE'])
        print_ui("  - Informationen über Geräte, Gruppen und Szenen sind nun verfügbar", COLORS['BRIGHT_WHITE'])
        print_ui("  - Diese Daten können für die Steuerung des Netzwerks verwendet werden", COLORS['BRIGHT_WHITE'])
        
        print_ui("\nNetzwerkinformationen:", COLORS['BRIGHT_GREEN'])
        print_ui("----------------------", COLORS['BRIGHT_GREEN'])
        print_ui(f"Netzwerk-Name: {casa.networkName}", COLORS['BRIGHT_WHITE'])
        print_ui(f"Netzwerk-ID: {casa.networkId}", COLORS['BRIGHT_WHITE'])
        print_ui(f"Anzahl Geräte: {len(casa.units)}", COLORS['BRIGHT_WHITE'])
        print_ui(f"Anzahl Gruppen: {len(casa.groups)}", COLORS['BRIGHT_WHITE'])
        print_ui(f"Anzahl Szenen: {len(casa.scenes)}", COLORS['BRIGHT_WHITE'])
        
        _LOGGER.info(f"Verbunden mit Netzwerk: {casa.networkName}")
        _LOGGER.info(f"Netzwerk-ID: {casa.networkId}")
        _LOGGER.info(f"Anzahl Geräte: {len(casa.units)}")
        _LOGGER.info(f"Anzahl Gruppen: {len(casa.groups)}")
        _LOGGER.info(f"Anzahl Szenen: {len(casa.scenes)}")
        
        # Zeige detaillierte Informationen zu Geräten
        if casa.units:
            print_ui("\nGeräte im Netzwerk:", COLORS['BRIGHT_GREEN'])
            print_info("Geräte (Units)", "Einzelne Leuchten oder Steuergeräte im Netzwerk")
            print_ui("------------------", COLORS['BRIGHT_GREEN'])
            for i, unit in enumerate(casa.units):
                print_ui(f"Gerät {i}: {unit.name} (ID: {unit.deviceId})", COLORS['BRIGHT_WHITE'])
                status_color = COLORS['BRIGHT_GREEN'] if unit.is_on else COLORS['BRIGHT_RED']
                online_color = COLORS['BRIGHT_GREEN'] if unit.online else COLORS['BRIGHT_RED']
                print_ui(f"  Status: {'Eingeschaltet' if unit.is_on else 'Ausgeschaltet'}", status_color)
                print_ui(f"  Online: {'Ja' if unit.online else 'Nein'}", online_color)
                
                if unit.state:
                    print_ui(f"  Zustand: {unit.state}", COLORS['BRIGHT_WHITE'])
                    
                _LOGGER.debug(f"Gerät {i}: {unit.__repr__()}")
                _LOGGER.debug(f"  Gerät-Typ: {unit._typeId}")
                _LOGGER.debug(f"  Geräte-ID: {unit.deviceId}")
                _LOGGER.debug(f"  UUID: {unit.uuid}")
                _LOGGER.debug(f"  Adresse: {unit.address}")
                _LOGGER.debug(f"  Firmware: {unit.firmwareVersion}")

        # Zeige Gruppen-Informationen
        if casa.groups:
            print_ui("\nGruppen im Netzwerk:", COLORS['BRIGHT_GREEN'])
            print_info("Gruppen", "Zusammenfassung mehrerer Geräte zur gemeinsamen Steuerung")
            print_ui("-------------------", COLORS['BRIGHT_GREEN'])
            for i, group in enumerate(casa.groups):
                print_ui(f"Gruppe {i}: {group.name} (ID: {group.groudId})", COLORS['BRIGHT_WHITE'])
                print_ui(f"  Enthält {len(group.units)} Geräte", COLORS['BRIGHT_WHITE'])
                
                # Liste der Geräte in der Gruppe
                for unit in group.units:
                    print_ui(f"  - Gerät: {unit.name} (ID: {unit.deviceId})", COLORS['BRIGHT_WHITE'])
                    
                _LOGGER.debug(f"Gruppe {i}: {group.name} (ID: {group.groudId})")
                
        # Zeige Szenen-Informationen
        if casa.scenes:
            print_ui("\nSzenen im Netzwerk:", COLORS['BRIGHT_GREEN'])
            print_info("Szenen", "Vordefinierte Beleuchtungseinstellungen für mehrere Geräte")
            print_ui("------------------", COLORS['BRIGHT_GREEN'])
            for i, scene in enumerate(casa.scenes):
                print_ui(f"Szene {i}: {scene.name} (ID: {scene.sceneId})", COLORS['BRIGHT_WHITE'])
                _LOGGER.debug(f"Szene {i}: {scene.name} (ID: {scene.sceneId})")
                
        # Warte einen Moment, damit der Benutzer die Informationen lesen kann
        print_ui("\n⏱️ Verbindung wird in 5 Sekunden getrennt...", COLORS['BRIGHT_YELLOW'])
        await asyncio.sleep(5)
        
    except Exception as e:
        _LOGGER.exception(f"Fehler während der Demo: {str(e)}")
        print_ui(f"\nFehler aufgetreten: {type(e).__name__}: {str(e)}", COLORS['RED'])
    
    finally:
        # --- SCHRITT 5: Verbindung trennen ---
        print_ui("\n🔌 SCHRITT 5: VERBINDUNG TRENNEN", COLORS['BRIGHT_GREEN'])
        print_ui("-----------------------------", COLORS['BRIGHT_GREEN'])
        print_info("Verbindungstrennung", "Ordnungsgemäßes Beenden der Verbindung zum Netzwerk")
        print_ui("Technischer Hintergrund:", COLORS['BRIGHT_BLUE'])
        print_ui("  - Schließt die Bluetooth-Verbindung", COLORS['BRIGHT_WHITE'])
        print_ui("  - Trennt die Verbindung zur Casambi-Cloud", COLORS['BRIGHT_WHITE'])
        print_ui("  - Gibt Systemressourcen frei", COLORS['BRIGHT_WHITE'])
        
        _LOGGER.info("Trenne Verbindung zum Netzwerk")
        print_ui("\nVerbindung wird getrennt...", COLORS['BRIGHT_YELLOW'])
        if 'casa' in locals():
            disconnect_start = time.time()
            _LOGGER.debug("Starte Trennungsprozess...")
            await casa.disconnect()
            _LOGGER.info(f"Verbindung getrennt in {time.time() - disconnect_start:.2f} Sekunden")
            _LOGGER.debug("Bluetooth-Verbindung geschlossen und Cloud-Verbindung beendet")
            print_ui("Verbindung erfolgreich getrennt.", COLORS['BRIGHT_GREEN'])
        
        _LOGGER.info("===== DEMO BEENDET =====")
        print_ui("\n✅ DEMO ERFOLGREICH BEENDET", COLORS['BRIGHT_WHITE'])
        print_ui("========================", COLORS['BRIGHT_WHITE'])
        print_ui("\nDiese Demo hat den vollständigen Verbindungsprozess zu einem Casambi-Netzwerk demonstriert:", COLORS['BRIGHT_WHITE'])
        print_ui("1. Suche nach Netzwerken über Bluetooth", COLORS['BRIGHT_WHITE'])
        print_ui("2. Authentifizierung bei der Casambi-Cloud", COLORS['BRIGHT_WHITE'])
        print_ui("3. Abruf der Netzwerkinformationen", COLORS['BRIGHT_WHITE'])
        print_ui("4. Anzeige von Geräten, Gruppen und Szenen", COLORS['BRIGHT_WHITE'])
        print_ui("5. Ordnungsgemäße Trennung der Verbindung", COLORS['BRIGHT_WHITE'])


if __name__ == "__main__":
    # Erstelle asyncio Event-Loop und führe die Hauptfunktion aus
    _LOGGER.debug("Erstelle asyncio Event-Loop")
    loop = asyncio.new_event_loop()
    
    try:
        _LOGGER.debug("Starte main()-Funktion in der Event-Loop")
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        _LOGGER.info("Programm durch Benutzer unterbrochen")
    except Exception as e:
        _LOGGER.exception(f"Unbehandelte Ausnahme: {str(e)}")
    finally:
        _LOGGER.debug("Schließe Event-Loop")
        loop.close()