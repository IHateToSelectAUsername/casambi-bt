import asyncio
import logging
import sys
import platform
import re
import binascii
from typing import Dict, Any, List, Tuple, Optional, Set

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakDBusError, BleakError

# Casambi-spezifische Konstanten
CASAMBI_MANUFACTURER_ID = 963  # Herstellercode für Casambi
CASAMBI_UUID_CONFIGURED = "0000fe4d-0000-1000-8000-00805f9b34fb"  # UUID für konfigurierte Geräte (basierend auf den Scan-Ergebnissen)
CASAMBI_UUID_LIBRARY = "0000febb-0000-1000-8000-00805f9b34fb"  # UUID in der CasambiBt-Bibliothek

# Konstanten für die Ausgabe
TEXT_RESET = "\033[0m"
TEXT_GREEN = "\033[92m"
TEXT_YELLOW = "\033[93m"
TEXT_RED = "\033[91m"
TEXT_BLUE = "\033[94m"
TEXT_CYAN = "\033[96m"
TEXT_MAGENTA = "\033[95m"
TEXT_BOLD = "\033[1m"

# Logging-Konfiguration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('casambi_device_states.log')
    ]
)

_LOGGER = logging.getLogger(__name__)


def print_colored(text: str, color: str = TEXT_RESET, bold: bool = False) -> None:
    """Gibt Text mit Farbe und optional fett gedruckt aus."""
    if bold:
        print(f"{TEXT_BOLD}{color}{text}{TEXT_RESET}")
    else:
        print(f"{color}{text}{TEXT_RESET}")


def is_mac_address(data: bytes) -> bool:
    """Prüft, ob die Bytes einem MAC-Adress-Format entsprechen (6 Bytes)."""
    return len(data) >= 6 and all(0 <= b <= 255 for b in data[:6])


def format_bytes_as_mac(data: bytes) -> str:
    """Formatiert 6 Bytes als MAC-Adresse."""
    if len(data) < 6:
        return "Ungültiges Format"
    return ":".join(f"{b:02X}" for b in data[:6])


def analyze_manufacturer_data(data: bytes, device_address: str) -> Dict[str, Any]:
    """
    Analysiert die Herstellerdaten eines Casambi-Geräts.
    
    Args:
        data: Die Herstellerdaten als Bytes
        device_address: Die MAC-Adresse des Geräts für Vergleiche
        
    Returns:
        Ein Dictionary mit der Analyse der Daten
    """
    result = {
        "raw_hex": data.hex(),
        "length": len(data),
        "contains_own_mac": False,
        "contains_other_mac": False,
        "contains_zeros": False,
        "mac_addresses": [],
    }
    
    # Konvertiere MAC-Adresse in verschiedene Formate für Vergleiche
    mac_no_colons = device_address.replace(":", "").lower()
    mac_bytes = bytes.fromhex(mac_no_colons)
    
    # Suche nach der eigenen MAC-Adresse im Hex-String
    if mac_no_colons in data.hex().lower():
        result["contains_own_mac"] = True
        index = data.hex().lower().find(mac_no_colons)
        result["own_mac_position"] = index // 2  # Position in Bytes
    
    # Suche nach Sequenzen von 6 Bytes, die wie MAC-Adressen aussehen
    for i in range(len(data) - 5):
        chunk = data[i:i+6]
        # Prüfe, ob es eine gültige MAC-Adresse sein könnte
        if is_mac_address(chunk):
            mac_str = format_bytes_as_mac(chunk)
            if mac_str.lower().replace(":", "") != mac_no_colons:
                result["contains_other_mac"] = True
                result["mac_addresses"].append({
                    "mac": mac_str,
                    "position": i
                })
    
    # Suche nach Nullsequenzen (mindestens 6 Nullen hintereinander)
    zero_sequence = bytes([0, 0, 0, 0, 0, 0])
    if zero_sequence in data:
        result["contains_zeros"] = True
        index = data.find(zero_sequence)
        result["zeros_position"] = index
    
    return result


def categorize_casambi_device(device: BLEDevice, adv_data: AdvertisementData) -> str:
    """
    Kategorisiert ein Casambi-Gerät basierend auf seinen Werbedaten.
    
    Returns:
        Eine der folgenden Kategorien:
        - "configured": Vollständig konfiguriertes Gerät
        - "unconfigured": Zurückgesetztes/neues Gerät
        - "unknown": Casambi-Gerät mit unklarem Status
    """
    if CASAMBI_MANUFACTURER_ID not in adv_data.manufacturer_data:
        return "non_casambi"
    
    # Analyse der Herstellerdaten
    mfr_data = adv_data.manufacturer_data[CASAMBI_MANUFACTURER_ID]
    mfr_analysis = analyze_manufacturer_data(mfr_data, device.address)
    
    # Prüfen auf konfiguriertes Gerät
    if (CASAMBI_UUID_CONFIGURED in adv_data.service_uuids or 
        CASAMBI_UUID_LIBRARY in adv_data.service_uuids):
        return "configured"
    
    # Prüfen auf zurückgesetztes Gerät
    if mfr_analysis["contains_zeros"] and not adv_data.service_uuids:
        return "unconfigured"
    
    # Wenn keine klare Kategorisierung möglich ist
    return "unknown"


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


def print_device_details(device: BLEDevice, adv_data: AdvertisementData, category: str, show_analysis: bool = True) -> None:
    """Zeigt detaillierte Informationen zu einem Gerät an."""
    # Wähle Farbe basierend auf Kategorie
    if category == "configured":
        color = TEXT_GREEN
        status_text = "KONFIGURIERT"
    elif category == "unconfigured":
        color = TEXT_YELLOW
        status_text = "NICHT KONFIGURIERT"
    elif category == "unknown":
        color = TEXT_MAGENTA
        status_text = "UNKLARER STATUS"
    else:
        color = TEXT_RESET
        status_text = "NICHT CASAMBI"
    
    # Gerätename und Adresse
    print_colored(f"\n{status_text}: {device.name or 'Unbenannt'} ({device.address})", color, bold=True)
    
    # Grundlegende Informationen
    print(f"RSSI: {adv_data.rssi} dBm")
    print(f"Lokaler Name: {adv_data.local_name or 'Nicht angegeben'}")
    
    # Service UUIDs
    if adv_data.service_uuids:
        print("Service UUIDs:")
        for uuid in adv_data.service_uuids:
            uuid_str = uuid
            if uuid == CASAMBI_UUID_CONFIGURED:
                uuid_str += f" {TEXT_GREEN}(CASAMBI KONFIGURIERT){TEXT_RESET}"
            elif uuid == CASAMBI_UUID_LIBRARY:
                uuid_str += f" {TEXT_GREEN}(CASAMBI BIBLIOTHEK){TEXT_RESET}"
            print(f"  - {uuid_str}")
    else:
        print("Service UUIDs: Keine")
    
    # Herstellerdaten
    if CASAMBI_MANUFACTURER_ID in adv_data.manufacturer_data:
        mfr_data = adv_data.manufacturer_data[CASAMBI_MANUFACTURER_ID]
        print_colored(f"Casambi Herstellerdaten (ID: {CASAMBI_MANUFACTURER_ID}):", TEXT_CYAN)
        print(f"  Hex: {mfr_data.hex()}")
        print(f"  Länge: {len(mfr_data)} Bytes")
        
        # Detaillierte Analyse der Herstellerdaten
        if show_analysis:
            analysis = analyze_manufacturer_data(mfr_data, device.address)
            print("\nAnalyse der Herstellerdaten:")
            
            if analysis["contains_own_mac"]:
                print_colored(f"  ✓ Enthält eigene MAC-Adresse an Position {analysis['own_mac_position']}", TEXT_GREEN)
            else:
                print(f"  ✗ Enthält nicht die eigene MAC-Adresse")
                
            if analysis["contains_other_mac"]:
                print_colored("  ✓ Enthält andere MAC-Adressen:", TEXT_YELLOW)
                for mac_info in analysis["mac_addresses"]:
                    print(f"    - {mac_info['mac']} an Position {mac_info['position']}")
            
            if analysis["contains_zeros"]:
                print_colored(f"  ✓ Enthält Nullsequenz an Position {analysis['zeros_position']} "
                             f"(typisch für ZURÜCKGESETZTE Geräte)", TEXT_YELLOW)
    else:
        print("Keine Casambi Herstellerdaten vorhanden")
    
    # Andere Herstellerdaten
    other_mfr = {k: v for k, v in adv_data.manufacturer_data.items() if k != CASAMBI_MANUFACTURER_ID}
    if other_mfr:
        print("\nAndere Herstellerdaten:")
        for mfr_id, data in other_mfr.items():
            print(f"  ID: {mfr_id}, Daten: {data.hex()}")
    
    # Weitere Daten
    if adv_data.service_data:
        print(f"\nService Daten: {adv_data.service_data}")
    if adv_data.tx_power:
        print(f"TX Power: {adv_data.tx_power}")


async def main() -> None:
    """Hauptfunktion zum Scannen und Analysieren von Casambi-Geräten."""
    _LOGGER.info("===== DEMO: CASAMBI GERÄTEZUSTÄNDE =====")
    print_colored("\n===== DEMO: CASAMBI GERÄTEZUSTÄNDE =====\n", TEXT_CYAN, bold=True)
    
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
        configured_devices = []
        unconfigured_devices = []
        unknown_casambi_devices = []
        other_devices = []
        
        for addr, (device, adv_data) in all_devices.items():
            category = categorize_casambi_device(device, adv_data)
            
            if category == "configured":
                configured_devices.append((device, adv_data, category))
            elif category == "unconfigured":
                unconfigured_devices.append((device, adv_data, category))
            elif category == "unknown":
                unknown_casambi_devices.append((device, adv_data, category))
            else:
                other_devices.append((device, adv_data, category))
        
        # Zähle die Geräte nach Kategorie
        print("\n=== ZUSAMMENFASSUNG DER GEFUNDENEN GERÄTE ===")
        print_colored(f"Gesamt gefundene Geräte: {len(all_devices)}", TEXT_CYAN, bold=True)
        print_colored(f"Konfigurierte Casambi-Geräte: {len(configured_devices)}", TEXT_GREEN, bold=True)
        print_colored(f"Nicht konfigurierte Casambi-Geräte: {len(unconfigured_devices)}", TEXT_YELLOW, bold=True)
        print_colored(f"Casambi-Geräte mit unklarem Status: {len(unknown_casambi_devices)}", TEXT_MAGENTA, bold=True)
        print(f"Andere Bluetooth LE Geräte: {len(other_devices)}")
        
        # Zeige konfigurierte Geräte an
        if configured_devices:
            print_colored("\n=== KONFIGURIERTE CASAMBI-GERÄTE ===", TEXT_GREEN, bold=True)
            for device, adv_data, category in configured_devices:
                print_device_details(device, adv_data, category)
        
        # Zeige nicht konfigurierte Geräte an
        if unconfigured_devices:
            print_colored("\n=== NICHT KONFIGURIERTE CASAMBI-GERÄTE ===", TEXT_YELLOW, bold=True)
            for device, adv_data, category in unconfigured_devices:
                print_device_details(device, adv_data, category)
        
        # Zeige Geräte mit unklarem Status an
        if unknown_casambi_devices:
            print_colored("\n=== CASAMBI-GERÄTE MIT UNKLAREM STATUS ===", TEXT_MAGENTA, bold=True)
            for device, adv_data, category in unknown_casambi_devices:
                print_device_details(device, adv_data, category)
        
        # Optionale Anzeige anderer Geräte
        show_others = input("\nMöchten Sie auch die anderen gefundenen Bluetooth-Geräte anzeigen? (j/n) ")
        if show_others.lower() in ('j', 'ja', 'y', 'yes'):
            print("\n=== ANDERE BLUETOOTH LE GERÄTE ===")
            for device, adv_data, category in other_devices:
                print(f"\nGerät: {device.name or 'Unbenannt'} ({device.address})")
                print(f"RSSI: {adv_data.rssi} dBm")
                print(f"Lokaler Name: {adv_data.local_name or 'Nicht angegeben'}")
                
                if adv_data.manufacturer_data:
                    print("Herstellerdaten:")
                    for mfr_id, data in adv_data.manufacturer_data.items():
                        print(f"  ID: {mfr_id}, Daten: {data.hex()}")
                
                if adv_data.service_uuids:
                    print("Service UUIDs:")
                    for uuid in adv_data.service_uuids:
                        print(f"  - {uuid}")
                
                if adv_data.service_data:
                    print(f"Service Daten: {adv_data.service_data}")
                if adv_data.tx_power:
                    print(f"TX Power: {adv_data.tx_power}")
        
        # Ausgabe für weitergehende Analyse
        print_colored("\n=== HINWEISE ZUR ANALYSE ===", TEXT_CYAN, bold=True)
        print("Konfigurierte Casambi-Geräte haben folgende Merkmale:")
        print(f"1. Herstellercode {CASAMBI_MANUFACTURER_ID} in den Herstellerdaten")
        print(f"2. Eine spezifische Service UUID (typischerweise {CASAMBI_UUID_CONFIGURED})")
        print("3. Herstellerdaten enthalten typischerweise die eigene MAC-Adresse")
        
        print("\nNicht konfigurierte Casambi-Geräte haben folgende Merkmale:")
        print(f"1. Herstellercode {CASAMBI_MANUFACTURER_ID} in den Herstellerdaten")
        print("2. Keine spezifischen Service UUIDs")
        print("3. Herstellerdaten enthalten typischerweise eine Nullsequenz")
        
        print("\nCasambi-Geräte mit unklarem Status erfüllen einige, aber nicht alle")
        print("Kriterien für konfigurierte oder nicht konfigurierte Geräte.")
        
    except Exception as e:
        _LOGGER.exception(f"Fehler während der Demo: {str(e)}")
        print_colored(f"\nFehler aufgetreten: {type(e).__name__}: {str(e)}", TEXT_RED)
    
    _LOGGER.info("===== DEMO BEENDET =====")
    print_colored("\n===== DEMO BEENDET =====", TEXT_CYAN)


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