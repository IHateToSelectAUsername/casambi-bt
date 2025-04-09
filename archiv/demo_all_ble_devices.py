import asyncio
import logging
import sys
import platform
from typing import Dict, Any, List, Tuple, Optional, Set

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakDBusError, BleakError

# Hier importieren wir die Casambi-spezifische UUID um die Geräte zu identifizieren
# Wir können auch direkt die UUID importieren, wenn verfügbar
try:
    from CasambiBt._constants import CASA_UUID
except ImportError:
    # Falls die UUID nicht direkt importiert werden kann, definieren wir sie hier
    # Dies ist die UUID, die in der _discover.py Datei verwendet wird
    CASA_UUID = "0000febb-0000-1000-8000-00805f9b34fb"

# Konstanten für die Ausgabe
CASAMBI_MANUFACTURER_ID = 963  # Herstellercode für Casambi
TEXT_RESET = "\033[0m"
TEXT_GREEN = "\033[92m"
TEXT_YELLOW = "\033[93m"
TEXT_CYAN = "\033[96m"
TEXT_BOLD = "\033[1m"

# Logging-Konfiguration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('all_ble_devices.log')
    ]
)

_LOGGER = logging.getLogger(__name__)


def print_colored(text: str, color: str = TEXT_RESET, bold: bool = False) -> None:
    """Gibt Text mit Farbe und optional fett gedruckt aus."""
    if bold:
        print(f"{TEXT_BOLD}{color}{text}{TEXT_RESET}")
    else:
        print(f"{color}{text}{TEXT_RESET}")


def format_manufacturer_data(data: Dict[int, bytes]) -> str:
    """Formatiert die Herstellerdaten für die Ausgabe."""
    if not data:
        return "Keine"
    
    result = []
    for company_id, raw_data in data.items():
        company_name = f"ID:{company_id}" + (f" (CASAMBI)" if company_id == CASAMBI_MANUFACTURER_ID else "")
        hex_data = raw_data.hex()
        result.append(f"{company_name}: {hex_data}")
    
    return ", ".join(result)


def format_service_uuids(uuids: List[str]) -> str:
    """Formatiert die Service UUIDs für die Ausgabe."""
    if not uuids:
        return "Keine"
    
    result = []
    for uuid in uuids:
        is_casambi = uuid == CASA_UUID
        uuid_str = f"{uuid}" + (f" (CASAMBI)" if is_casambi else "")
        result.append(uuid_str)
    
    return ", ".join(result)


def is_likely_casambi(adv_data: AdvertisementData) -> Tuple[bool, bool, bool]:
    """
    Prüft, ob ein Gerät wahrscheinlich ein Casambi-Gerät ist.
    
    Returns:
        Tuple mit drei Booleans:
        - Ob der Casambi-Herstellercode vorhanden ist
        - Ob die Casambi-UUID vorhanden ist
        - Ob beides vorhanden ist (vollständige Casambi-Erkennung)
    """
    has_manufacturer = CASAMBI_MANUFACTURER_ID in adv_data.manufacturer_data
    has_uuid = CASA_UUID in adv_data.service_uuids
    is_complete_casambi = has_manufacturer and has_uuid
    
    return has_manufacturer, has_uuid, is_complete_casambi


async def scan_for_devices(scan_time: float = 10.0) -> Dict[str, Tuple[BLEDevice, AdvertisementData]]:
    """
    Scannt nach allen BLE-Geräten im Umkreis und gibt sie mit ihren Werbedaten zurück.
    
    Args:
        scan_time: Zeit in Sekunden, für die gescannt werden soll
        
    Returns:
        Dictionary mit Geräteadresse als Schlüssel und Tupel aus Gerät und Werbedaten als Wert
    """
    _LOGGER.info(f"Starte Bluetooth-Scan für {scan_time} Sekunden...")
    print(f"Starte Bluetooth-Scan für {scan_time} Sekunden...")
    
    # Scanner mit besonderen Parametern für macOS, falls erforderlich
    if platform.system() == "Darwin":
        _LOGGER.debug("MacOS erkannt, verwende spezielle Scanner-Einstellungen")
        scanner = BleakScanner(detection_callback=None, scanning_mode='passive', cb={"use_bdaddr": True})
    else:
        scanner = BleakScanner(detection_callback=None, scanning_mode='passive')
    
    try:
        # Starte den Scanner und sammle Geräte für die angegebene Zeit
        devices_detected: Dict[str, Tuple[BLEDevice, AdvertisementData]] = {}
        
        def _detection_callback(device: BLEDevice, advertisement_data: AdvertisementData) -> None:
            devices_detected[device.address] = (device, advertisement_data)
        
        scanner.register_detection_callback(_detection_callback)
        await scanner.start()
        await asyncio.sleep(scan_time)
        await scanner.stop()
        
        _LOGGER.info(f"Scan abgeschlossen. {len(devices_detected)} Geräte gefunden.")
        return devices_detected
        
    except BleakDBusError as e:
        _LOGGER.error(f"DBus-Fehler beim Bluetooth-Scan: {e.dbus_error} - {e.dbus_error_details}")
        raise
    except BleakError as e:
        _LOGGER.error(f"Bluetooth-Fehler: {str(e)}")
        raise
    except Exception as e:
        _LOGGER.exception(f"Unerwarteter Fehler beim Scan: {str(e)}")
        raise


async def main() -> None:
    """Hauptfunktion zum Scannen und Analysieren von BLE-Geräten."""
    _LOGGER.info("===== DEMO: ALLE BLUETOOTH LE GERÄTE =====")
    print("\n===== DEMO: ALLE BLUETOOTH LE GERÄTE =====\n")
    
    try:
        # Frage nach Scan-Zeit
        scan_time_str = input("Wie lange soll gescannt werden (Sekunden, Standard: 10)? ")
        scan_time = float(scan_time_str) if scan_time_str.strip() else 10.0
        
        # Führe den Scan durch
        all_devices = await scan_for_devices(scan_time)
        
        if not all_devices:
            print_colored("\nKeine Bluetooth LE Geräte gefunden!", TEXT_YELLOW, bold=True)
            return
        
        # Kategorisiere die Geräte
        complete_casambi_devices: List[Tuple[BLEDevice, AdvertisementData]] = []
        partial_casambi_devices: List[Tuple[BLEDevice, AdvertisementData, bool, bool]] = []
        other_devices: List[Tuple[BLEDevice, AdvertisementData]] = []
        
        for addr, (device, adv_data) in all_devices.items():
            has_manufacturer, has_uuid, is_complete = is_likely_casambi(adv_data)
            
            if is_complete:
                complete_casambi_devices.append((device, adv_data))
            elif has_manufacturer or has_uuid:
                partial_casambi_devices.append((device, adv_data, has_manufacturer, has_uuid))
            else:
                other_devices.append((device, adv_data))
        
        # Zähle die Geräte nach Kategorie
        print("\n=== ZUSAMMENFASSUNG DER GEFUNDENEN GERÄTE ===")
        print_colored(f"Gesamt gefundene Geräte: {len(all_devices)}", TEXT_CYAN, bold=True)
        print_colored(f"Vollständig erkannte Casambi-Geräte: {len(complete_casambi_devices)}", TEXT_GREEN, bold=True)
        print_colored(f"Teilweise erkannte Casambi-Geräte: {len(partial_casambi_devices)}", TEXT_YELLOW, bold=True)
        print(f"Andere Bluetooth LE Geräte: {len(other_devices)}")
        
        # Zeige detaillierte Geräteinformationen
        if complete_casambi_devices:
            print("\n=== VOLLSTÄNDIG ERKANNTE CASAMBI-GERÄTE ===")
            for i, (device, adv_data) in enumerate(complete_casambi_devices):
                print_colored(f"\nGerät {i+1}: {device.name or 'Unbenannt'} ({device.address})", TEXT_GREEN, bold=True)
                print(f"RSSI: {adv_data.rssi} dBm")
                print(f"Lokaler Name: {adv_data.local_name or 'Nicht angegeben'}")
                print(f"Herstellerdaten: {format_manufacturer_data(adv_data.manufacturer_data)}")
                print(f"Service UUIDs: {format_service_uuids(adv_data.service_uuids)}")
                print(f"Service Daten: {adv_data.service_data}")
                print(f"TX Power: {adv_data.tx_power or 'Nicht angegeben'}")
                if hasattr(device, 'metadata') and device.metadata:
                    print(f"Metadaten: {device.metadata}")
        
        if partial_casambi_devices:
            print("\n=== TEILWEISE ERKANNTE CASAMBI-GERÄTE (möglicherweise neu oder nicht konfiguriert) ===")
            for i, (device, adv_data, has_manufacturer, has_uuid) in enumerate(partial_casambi_devices):
                print_colored(f"\nGerät {i+1}: {device.name or 'Unbenannt'} ({device.address})", TEXT_YELLOW, bold=True)
                print(f"Casambi-Erkennung: " + 
                     f"{'✓' if has_manufacturer else '✗'} Herstellercode, " +
                     f"{'✓' if has_uuid else '✗'} UUID")
                print(f"RSSI: {adv_data.rssi} dBm")
                print(f"Lokaler Name: {adv_data.local_name or 'Nicht angegeben'}")
                print(f"Herstellerdaten: {format_manufacturer_data(adv_data.manufacturer_data)}")
                print(f"Service UUIDs: {format_service_uuids(adv_data.service_uuids)}")
                print(f"Service Daten: {adv_data.service_data}")
                print(f"TX Power: {adv_data.tx_power or 'Nicht angegeben'}")
                if hasattr(device, 'metadata') and device.metadata:
                    print(f"Metadaten: {device.metadata}")
        
        if other_devices:
            print("\n=== ANDERE BLUETOOTH LE GERÄTE ===")
            for i, (device, adv_data) in enumerate(other_devices):
                print(f"\nGerät {i+1}: {device.name or 'Unbenannt'} ({device.address})")
                print(f"RSSI: {adv_data.rssi} dBm")
                print(f"Lokaler Name: {adv_data.local_name or 'Nicht angegeben'}")
                print(f"Herstellerdaten: {format_manufacturer_data(adv_data.manufacturer_data)}")
                print(f"Service UUIDs: {format_service_uuids(adv_data.service_uuids)}")
                if adv_data.service_data:
                    print(f"Service Daten: {adv_data.service_data}")
                if adv_data.tx_power:
                    print(f"TX Power: {adv_data.tx_power}")
                if hasattr(device, 'metadata') and device.metadata:
                    print(f"Metadaten: {device.metadata}")
        
        # Ausgabe für weitergehende Analyse
        print("\n=== HINWEISE ZUR ANALYSE ===")
        print("Vollständig erkannte Casambi-Geräte haben:")
        print(f"1. Herstellercode {CASAMBI_MANUFACTURER_ID} in den Herstellerdaten")
        print(f"2. UUID {CASA_UUID} in den Service UUIDs")
        print("\nTeilweise erkannte Geräte haben nur eines dieser Merkmale und könnten:")
        print("- Neue, noch nicht konfigurierte Casambi-Geräte sein")
        print("- Casambi-Geräte im Konfigurationsmodus sein")
        print("- Geräte mit ähnlichen Eigenschaften sein")
        print("\nUm die Unterschiede genauer zu untersuchen, vergleichen Sie die Werbedaten")
        print("zwischen konfigurierten und nicht konfigurierten Casambi-Geräten.")
        
    except Exception as e:
        _LOGGER.exception(f"Fehler während der Demo: {str(e)}")
        print_colored(f"\nFehler aufgetreten: {type(e).__name__}: {str(e)}", TEXT_YELLOW)
    
    _LOGGER.info("===== DEMO BEENDET =====")
    print("\n===== DEMO BEENDET =====")


if __name__ == "__main__":
    # Erstelle asyncio Event-Loop und führe die Hauptfunktion aus
    loop = asyncio.new_event_loop()
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nProgramm durch Benutzer unterbrochen")
    except Exception as e:
        print(f"\nUnbehandelte Ausnahme: {type(e).__name__}: {str(e)}")
    finally:
        loop.close()