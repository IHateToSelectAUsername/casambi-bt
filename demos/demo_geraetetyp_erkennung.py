import asyncio
import logging
import sys
from typing import Dict, Any, List, Set, Tuple, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('casambi_geraetetyp_erkennung.log')
    ]
)

_LOGGER = logging.getLogger(__name__)

# Konstanten für Casambi-Geräte
CASAMBI_MANUFACTURER_ID = 963  # Herstellercode für Casambi
CASAMBI_UUID_CONFIGURED = "0000fe4d-0000-1000-8000-00805f9b34fb"  # UUID für konfigurierte Geräte

# ANSI-Farben für bessere Lesbarkeit im Terminal
TEXT_GREEN = "\033[92m"
TEXT_YELLOW = "\033[93m"
TEXT_RED = "\033[91m"
TEXT_BLUE = "\033[94m"
TEXT_MAGENTA = "\033[95m"
TEXT_RESET = "\033[0m"
TEXT_BOLD = "\033[1m"


def print_colored(text: str, color: str = TEXT_RESET, bold: bool = False) -> None:
    """Gibt Text mit Farbe und optional fett gedruckt aus."""
    if bold:
        print(f"{TEXT_BOLD}{color}{text}{TEXT_RESET}")
    else:
        print(f"{color}{text}{TEXT_RESET}")


def extract_unit_address(data: bytes) -> Optional[str]:
    """
    Extrahiert die Unit-Adresse aus den Herstellerdaten, falls vorhanden.
    Bei physischen Geräten sind dies typischerweise die ersten 6 Bytes.
    
    Returns:
        Die Unit-Adresse als Hex-String oder None, wenn nicht extrahierbar
    """
    if len(data) >= 6:
        return data[:6].hex()
    return None


def determine_device_type(device: BLEDevice, adv_data: AdvertisementData) -> Tuple[str, Dict[str, Any]]:
    """
    Bestimmt den Typ eines Bluetooth-Geräts anhand der Werbedaten.
    
    Args:
        device: Das BLE-Gerät
        adv_data: Die empfangenen Werbedaten
        
    Returns:
        Tuple mit (Gerätetyp, Details-Dictionary)
    """
    device_type = "non_casambi"
    details = {
        "address": device.address,
        "name": getattr(device, 'name', None) or adv_data.local_name or "Unbekannt",
        "service_uuids": adv_data.service_uuids,
        "has_service_uuid": CASAMBI_UUID_CONFIGURED in adv_data.service_uuids,
    }
    
    # Prüfen, ob es ein Casambi-Gerät ist (Herstellercode 963)
    if CASAMBI_MANUFACTURER_ID not in adv_data.manufacturer_data:
        return device_type, details
    
    # Ab hier wissen wir, dass es ein Casambi-Gerät ist
    manufacturer_data = adv_data.manufacturer_data[CASAMBI_MANUFACTURER_ID]
    details["manufacturer_data_hex"] = manufacturer_data.hex()
    details["manufacturer_data_length"] = len(manufacturer_data)
    details["unit_address"] = extract_unit_address(manufacturer_data)
    
    # Prüfen auf Nullsequenz (typisch für zurückgesetzte Geräte)
    contains_nulls = b'\x00\x00\x00\x00\x00\x00' in manufacturer_data
    details["contains_nulls"] = contains_nulls
    
    # Prüfen, ob die eigene MAC-Adresse in den Daten enthalten ist (typisch für virtuelle Geräte)
    mac_ohne_trennzeichen = device.address.replace(":", "").lower()
    contains_own_mac = mac_ohne_trennzeichen in manufacturer_data.hex().lower()
    details["contains_own_mac"] = contains_own_mac
    
    # Anhand der Merkmale den Gerätetyp bestimmen
    if CASAMBI_UUID_CONFIGURED in adv_data.service_uuids:
        # Hat Service UUID -> virtuelles Gerät
        if len(manufacturer_data) <= 10 and contains_own_mac:
            device_type = "virtual"
        else:
            device_type = "unknown_casambi"
    else:
        # Kein Service UUID -> physisches Gerät
        if contains_nulls:
            device_type = "physical_reset"
        elif len(manufacturer_data) >= 20:
            device_type = "physical_configured"
        else:
            device_type = "unknown_casambi"

    details["device_type"] = device_type
    return device_type, details


async def scan_for_casambi_devices(scan_time: float = 8.0) -> Dict[str, Dict[str, Any]]:
    """
    Scannt nach Bluetooth-Geräten und klassifiziert Casambi-Geräte nach ihren Typen.
    
    Args:
        scan_time: Dauer des Scans in Sekunden
        
    Returns:
        Dictionary mit Geräteadressen als Schlüssel und Details als Werte
    """
    _LOGGER.info(f"Starte Bluetooth-Scan für {scan_time} Sekunden...")
    print_colored(f"Scanne nach Bluetooth-Geräten für {scan_time} Sekunden...", TEXT_BLUE, bold=True)
    
    # Für den Scan verwendete Geräte
    devices_detected: Dict[str, Tuple[BLEDevice, AdvertisementData]] = {}
    
    # Callback für jedes gefundene Gerät
    def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData) -> None:
        devices_detected[device.address] = (device, advertisement_data)
    
    # Scanner starten
    scanner = BleakScanner(detection_callback=detection_callback)
    
    try:
        await scanner.start()
        
        # Fortschrittsanzeige während des Scans
        for i in range(int(scan_time)):
            print(f"Scanning... {i+1}/{int(scan_time)} Sekunden, {len(devices_detected)} Geräte gefunden", end="\r")
            await asyncio.sleep(1)
        
        await scanner.stop()
        print()  # Neue Zeile nach der Fortschrittsanzeige
        
        # Geräte auswerten
        results = {}
        
        for address, (device, adv_data) in devices_detected.items():
            device_type, details = determine_device_type(device, adv_data)
            # Nur Casambi-relevante Geräte in die Ergebnisse aufnehmen
            if device_type != "non_casambi":
                results[address] = details
        
        return results
    
    except Exception as e:
        _LOGGER.exception(f"Fehler beim Bluetooth-Scan: {str(e)}")
        raise


def display_device_details(device_details: Dict[str, Any]) -> None:
    """Zeigt detaillierte Informationen zu einem Gerät an."""
    address = device_details["address"]
    name = device_details["name"]
    device_type = device_details["device_type"]
    
    # Farbe und Titel je nach Gerätetyp wählen
    if device_type == "physical_reset":
        color = TEXT_YELLOW
        type_display = "ZURÜCKGESETZTES PHYSISCHES GERÄT"
    elif device_type == "physical_configured":
        color = TEXT_GREEN
        type_display = "KONFIGURIERTES PHYSISCHES GERÄT"
    elif device_type == "virtual":
        color = TEXT_MAGENTA
        type_display = "VIRTUELLES GERÄT"
    else:
        color = TEXT_RED
        type_display = "UNBEKANNTES CASAMBI-GERÄT"
    
    # Basisinformationen anzeigen
    print_colored(f"\n{type_display}: {name} ({address})", color, bold=True)
    
    # Unit-Adresse anzeigen, falls vorhanden
    if "unit_address" in device_details and device_details["unit_address"]:
        print(f"Unit-Adresse: {device_details['unit_address']}")
    
    # Service UUIDs anzeigen
    service_uuids = device_details.get("service_uuids", [])
    if service_uuids:
        print("Service UUIDs:")
        for uuid in service_uuids:
            uuid_str = f"  - {uuid}"
            if uuid == CASAMBI_UUID_CONFIGURED:
                uuid_str += f" {TEXT_GREEN}(CASAMBI KONFIGURIERT){TEXT_RESET}"
            print(uuid_str)
    else:
        print("Service UUIDs: Keine")
    
    # Herstellerdaten anzeigen
    print(f"Herstellerdaten (Hex): {device_details.get('manufacturer_data_hex', 'Keine')}")
    print(f"Herstellerdaten Länge: {device_details.get('manufacturer_data_length', 0)} Bytes")
    
    # Zusätzliche Erkennungsmerkmale anzeigen
    print("\nErkennungsmerkmale:")
    if device_details.get("contains_nulls", False):
        print_colored("  ✓ Enthält Nullsequenz (typisch für ZURÜCKGESETZTE Geräte)", TEXT_YELLOW)
    else:
        print("  ✗ Enthält keine Nullsequenz")
    
    if device_details.get("contains_own_mac", False):
        print_colored("  ✓ Enthält eigene MAC-Adresse (typisch für VIRTUELLE Geräte)", TEXT_MAGENTA)
    else:
        print("  ✗ Enthält nicht die eigene MAC-Adresse")
    
    if device_details.get("has_service_uuid", False):
        print_colored("  ✓ Hat Casambi Service UUID (typisch für VIRTUELLE Geräte)", TEXT_MAGENTA)
    else:
        print("  ✗ Hat keine Casambi Service UUID")


async def main() -> None:
    """Hauptfunktion zum Scannen und Auswerten von Casambi-Geräten."""
    _LOGGER.info("===== DEMO: CASAMBI GERÄTETYP-ERKENNUNG =====")
    print_colored("\n===== CASAMBI GERÄTETYP-ERKENNUNG =====", TEXT_BLUE, bold=True)
    
    print("""
Diese Demo scannt nach Casambi-Geräten und klassifiziert sie in drei Kategorien:

1. ZURÜCKGESETZTES PHYSISCHES GERÄT - Ein Gerät im Werkszustand
2. KONFIGURIERTES PHYSISCHES GERÄT - Ein Gerät, das konfiguriert wurde und sich selbst darstellt
3. VIRTUELLES GERÄT - Ein Gerät, das von einem anderen physischen Gerät weitergeleitet wird

Die Erkennung basiert auf den in unseren Tests identifizierten eindeutigen Merkmalen.
""")
    
    try:
        # Scan durchführen
        devices = await scan_for_casambi_devices()
        
        # Ergebnisse anzeigen
        if not devices:
            print_colored("\nKeine Casambi-Geräte gefunden!", TEXT_RED)
            print("Stelle sicher, dass:")
            print("1. Bluetooth auf deinem Gerät aktiviert ist")
            print("2. Casambi-Geräte in Reichweite und eingeschaltet sind")
            return
        
        # Gruppieren nach Gerätetypen
        physical_reset = {}
        physical_configured = {}
        virtual = {}
        unknown = {}
        
        for addr, details in devices.items():
            if details["device_type"] == "physical_reset":
                physical_reset[addr] = details
            elif details["device_type"] == "physical_configured":
                physical_configured[addr] = details
            elif details["device_type"] == "virtual":
                virtual[addr] = details
            else:
                unknown[addr] = details
        
        # Zusammenfassung anzeigen
        print_colored(f"\nGefundene Casambi-Geräte: {len(devices)}", TEXT_BLUE, bold=True)
        print(f"- Zurückgesetzte physische Geräte: {len(physical_reset)}")
        print(f"- Konfigurierte physische Geräte: {len(physical_configured)}")
        print(f"- Virtuelle Geräte: {len(virtual)}")
        print(f"- Unbekannte Casambi-Geräte: {len(unknown)}")
        
        # Details für jeden Gerätetyp anzeigen
        if physical_reset:
            print_colored("\n=== ZURÜCKGESETZTE PHYSISCHE GERÄTE ===", TEXT_YELLOW, bold=True)
            for details in physical_reset.values():
                display_device_details(details)
        
        if physical_configured:
            print_colored("\n=== KONFIGURIERTE PHYSISCHE GERÄTE ===", TEXT_GREEN, bold=True)
            for details in physical_configured.values():
                display_device_details(details)
        
        if virtual:
            print_colored("\n=== VIRTUELLE GERÄTE ===", TEXT_MAGENTA, bold=True)
            for details in virtual.values():
                display_device_details(details)
        
        if unknown:
            print_colored("\n=== UNBEKANNTE CASAMBI-GERÄTE ===", TEXT_RED, bold=True)
            for details in unknown.values():
                display_device_details(details)
        
        # Analysiere Beziehungen zwischen physischen und virtuellen Geräten
        if physical_configured and virtual:
            print_colored("\n=== GERÄTEZUSAMMENHÄNGE ===", TEXT_BLUE, bold=True)
            
            for phys_addr, phys_details in physical_configured.items():
                phys_hex = phys_details.get("manufacturer_data_hex", "")
                phys_name = phys_details.get("name", "Unbekannt")
                
                for virt_addr, virt_details in virtual.items():
                    virt_addr_hex = virt_addr.replace(":", "").lower()
                    virt_name = virt_details.get("name", "Unbekannt")
                    
                    # Prüfen, ob das physische Gerät die MAC des virtuellen enthält
                    mac_relation = virt_addr_hex in phys_hex
                    
                    # Prüfen, ob die Namen übereinstimmen oder ähnlich sind
                    name_relation = False
                    if phys_name and virt_name and phys_name != "Unbekannt" and virt_name != "Unbekannt":
                        name_relation = (phys_name == virt_name) or (phys_name in virt_name) or (virt_name in phys_name)
                    
                    # Wenn entweder MAC-Beziehung oder Namensbeziehung besteht, zeige die Beziehung an
                    if mac_relation or name_relation:
                        relation_type = []
                        if mac_relation:
                            relation_type.append("MAC-Referenz")
                        if name_relation:
                            relation_type.append("gemeinsamer Name")
                        
                        relation_str = " und ".join(relation_type)
                        print_colored(f"! Physisches Gerät {phys_addr} und virtuelles Gerät {virt_addr} verbunden durch: {relation_str}",
                                      TEXT_GREEN, bold=True)
        
            # Zusätzliche Informationen zur Namensbeziehung
            print_colored("\nWichtiger Hinweis zur Namensbeziehung:", TEXT_BLUE, bold=True)
            print("Der Name, der von einem virtuellen Gerät angezeigt wird, ist oft der Name des")
            print("zugehörigen physischen Geräts. Dies ist ein weiteres Indiz für die Mesh-Netzwerk-")
            print("Kommunikation zwischen den Geräten.")
            
    except Exception as e:
        _LOGGER.exception(f"Unerwarteter Fehler: {str(e)}")
        print_colored(f"Fehler: {str(e)}", TEXT_RED)
    
    _LOGGER.info("===== DEMO BEENDET =====")
    print_colored("\n===== DEMO BEENDET =====", TEXT_BLUE, bold=True)


if __name__ == "__main__":
    # Erstelle asyncio Event-Loop und führe die Hauptfunktion aus
    loop = asyncio.new_event_loop()
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nProgramm durch Benutzer unterbrochen")
    except Exception as e:
        print(f"\nUnbehandelte Ausnahme: {str(e)}")
    finally:
        loop.close()