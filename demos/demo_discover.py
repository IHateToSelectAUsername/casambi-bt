import asyncio
import logging
import sys
from logging import StreamHandler, FileHandler, Formatter

from CasambiBt import discover

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
file_handler = FileHandler('casambi_discover.log')
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
    """Hauptfunktion zur Demonstration der Bluetooth-Gerätesuche."""
    _LOGGER.info("===== DEMO: CASAMBI BLUETOOTH GERÄTESUCHE =====")
    
    print_ui("\n🔍 CASAMBI BLUETOOTH GERÄTESUCHE", COLORS['BRIGHT_WHITE'])
    print_ui("==============================", COLORS['BRIGHT_WHITE'])
    print_ui("Diese Demo zeigt, wie Casambi-Netzwerke in Bluetooth-Reichweite gefunden werden.", COLORS['BRIGHT_WHITE'])
    print_info("Discovery-Prozess", "Der Discovery-Prozess umfasst folgende Schritte:")
    print_ui("  1. Start eines Bluetooth-Low-Energy (BLE) Scans", COLORS['BRIGHT_WHITE'])
    print_ui("  2. Filterung der Geräte nach Casambi-spezifischen Merkmalen", COLORS['BRIGHT_WHITE'])
    print_ui("  3. Ausgabe der gefundenen Casambi-Netzwerke", COLORS['BRIGHT_WHITE'])
    print_ui("")
    
    # Setze den Logger der CasambiBt-Bibliothek auf DEBUG-Level für detaillierte Ausgaben
    logging.getLogger("CasambiBt").setLevel(logging.DEBUG)
    
    try:
        # --- SCHRITT 1: Bluetooth-Gerätesuche starten ---
        print_ui("\n🔍 SCHRITT 1: BLUETOOTH-GERÄTESUCHE", COLORS['BRIGHT_GREEN'])
        print_ui("--------------------------------", COLORS['BRIGHT_GREEN'])
        print_info("BLE-Scan", "Suche nach Bluetooth-Low-Energy Geräten in der Umgebung")
        print_ui("Technischer Hintergrund:", COLORS['BRIGHT_BLUE'])
        print_ui("  - Verwendet die Bleak-Bibliothek für plattformübergreifendes BLE-Scanning", COLORS['BRIGHT_WHITE'])
        print_ui("  - BleakScanner.discover() scannt nach allen BLE-Geräten in Reichweite", COLORS['BRIGHT_WHITE'])
        print_ui("  - Parameter return_adv=True erhält auch die Advertisement-Daten", COLORS['BRIGHT_WHITE'])
        print_ui("  - Spezialbehandlung für MacOS zur korrekten MAC-Adress-Erkennung", COLORS['BRIGHT_WHITE'])
        
        _LOGGER.info("Starte Suche nach Casambi-Netzwerken in Bluetooth-Reichweite...")
        print_ui("Suche läuft...", COLORS['BRIGHT_YELLOW'])
        
        # Rufe die discover()-Funktion auf, die alle Casambi-Netzwerke in Reichweite sucht
        # Diese Funktion gibt eine Liste von BLEDevice-Objekten zurück
        _LOGGER.debug("Starte discover()-Funktion, die BLE-Scan durchführt und Casambi-Geräte filtert")
        devices = await discover()
        
        # --- SCHRITT 2: Ergebnisse anzeigen ---
        print_ui("\n📋 SCHRITT 2: GEFUNDENE NETZWERKE", COLORS['BRIGHT_GREEN'])
        print_ui("-------------------------------", COLORS['BRIGHT_GREEN'])
        print_info("Filterprozess", "Casambi-Geräte werden anhand folgender Kriterien identifiziert:")
        print_ui("  - Herstellerkennung: 963 in den Advertisement-Daten", COLORS['BRIGHT_WHITE'])
        print_ui("  - Spezifische Service-UUID für Casambi-Geräte", COLORS['BRIGHT_WHITE'])
        print_ui("  - Die BLE-Adresse dient als eindeutige Kennung für das Netzwerk", COLORS['BRIGHT_WHITE'])
        
        _LOGGER.info(f"Suche abgeschlossen. Gefundene Geräte: {len(devices)}")
        _LOGGER.debug(f"discover()-Funktion hat {len(devices)} Casambi-Netzwerke identifiziert")
        
        # Zeige die gefundenen Geräte mit einem Index an
        if devices:
            _LOGGER.debug("Zeige Details der gefundenen Geräte an")
            print_ui("\nGefundene Casambi-Netzwerke:", COLORS['BRIGHT_GREEN'])
            print_ui("-----------------------------", COLORS['BRIGHT_GREEN'])
            for i, device in enumerate(devices):
                # Zeige Adresse und falls vorhanden, den Namen des Geräts
                device_info = f"[{i}] Adresse: {device.address}"
                if hasattr(device, 'name') and device.name:
                    device_info += f", Name: {device.name}"
                
                print_ui(device_info, COLORS['BRIGHT_WHITE'])
                _LOGGER.debug(f"Gerät gefunden: {device_info}")
                
                # Zeige alle verfügbaren Attribute des Geräts für Debugging-Zwecke
                # Direkte Anzeige der bekannten Attribute anstelle von __dict__
                _LOGGER.debug(f"Gerät-Details: Adresse={device.address}, Name={getattr(device, 'name', 'Nicht verfügbar')}")
                _LOGGER.debug(f"BLEDevice-Objekt enthält grundlegende Informationen zum Gerät")
        else:
            print_ui("\nKeine Casambi-Netzwerke gefunden!", COLORS['BRIGHT_RED'])
            _LOGGER.debug("Keine Geräte gefunden, die den Casambi-Kriterien entsprechen")
            print_ui("Bitte stellen Sie sicher, dass:", COLORS['BRIGHT_WHITE'])
            print_ui("1. Bluetooth auf Ihrem Gerät aktiviert ist", COLORS['BRIGHT_WHITE'])
            print_ui("2. Casambi-Netzwerke in Reichweite sind", COLORS['BRIGHT_WHITE'])
            print_ui("3. Die Casambi-Geräte eingeschaltet sind", COLORS['BRIGHT_WHITE'])
    
    except Exception as e:
        _LOGGER.exception(f"Fehler bei der Bluetooth-Suche: {str(e)}")
        print_ui(f"\nFehler aufgetreten: {type(e).__name__}: {str(e)}", COLORS['RED'])
        _LOGGER.debug("Mögliche Ursachen: Bluetooth deaktiviert, fehlende Berechtigungen, Hardware-Probleme")
    
    _LOGGER.info("===== DEMO BEENDET =====")
    print_ui("\n✅ DEMO ERFOLGREICH BEENDET", COLORS['BRIGHT_WHITE'])
    print_ui("========================", COLORS['BRIGHT_WHITE'])
    print_info("Zusammenfassung", "Diese Demo hat gezeigt, wie:")
    print_ui("1. Casambi-Netzwerke über Bluetooth-LE gefunden werden", COLORS['BRIGHT_WHITE'])
    print_ui("2. BLE-Geräte nach spezifischen Casambi-Merkmalen gefiltert werden", COLORS['BRIGHT_WHITE'])
    print_ui("3. Grundlegende Informationen zu den gefundenen Netzwerken angezeigt werden", COLORS['BRIGHT_WHITE'])
    print_ui("\nDiese Informationen können für den Verbindungsaufbau verwendet werden.", COLORS['BRIGHT_WHITE'])
    print_ui("\n===== DEMO BEENDET =====", COLORS['BRIGHT_WHITE'])


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