import asyncio
import logging
import sys
import platform
import re
import binascii
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Set

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakDBusError, BleakError

# Casambi-spezifische Konstanten
CASAMBI_MANUFACTURER_ID = 963  # Herstellercode für Casambi
CASAMBI_UUID_CONFIGURED = "0000fe4d-0000-1000-8000-00805f9b34fb"  # UUID für konfigurierte Geräte
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

# Ordner für Testergebnisse
RESULTS_FOLDER = "casambi_mesh_results"

# Logging-Konfiguration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('casambi_mesh_analysis.log')
    ]
)

_LOGGER = logging.getLogger(__name__)


def print_colored(text: str, color: str = TEXT_RESET, bold: bool = False) -> None:
    """Gibt Text mit Farbe und optional fett gedruckt aus."""
    if bold:
        print(f"{TEXT_BOLD}{color}{text}{TEXT_RESET}")
    else:
        print(f"{color}{text}{TEXT_RESET}")


def clear_screen() -> None:
    """Löscht den Bildschirm für bessere Übersichtlichkeit."""
    os.system('cls' if os.name == 'nt' else 'clear')


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


def contains_nulls(data: bytes) -> bool:
    """Prüft, ob die Daten eine signifikante Nullsequenz enthalten."""
    null_sequence = bytes([0, 0, 0, 0, 0, 0])
    return null_sequence in data


def contains_mac_address(data: bytes, mac_address: str) -> bool:
    """
    Prüft, ob die Daten eine bestimmte MAC-Adresse enthalten.
    
    Args:
        data: Die zu durchsuchenden Daten
        mac_address: Die MAC-Adresse im Format "XX:XX:XX:XX:XX:XX"
    """
    mac_no_colons = mac_address.replace(":", "").lower()
    return mac_no_colons in data.hex().lower()


def determine_device_type(device: BLEDevice, adv_data: AdvertisementData) -> str:
    """
    Bestimmt den Typ eines Geräts basierend auf seinen Werbedaten.
    
    Returns:
        Eine der folgenden Kategorien:
        - "physical_reset": Physisches Gerät im zurückgesetzten Zustand
        - "physical_configured": Physisches Gerät im konfigurierten Zustand
        - "virtual": Virtuelles Gerät (Teil eines Mesh-Netzwerks)
        - "unknown": Casambi-Gerät mit unklarem Status
        - "non_casambi": Kein Casambi-Gerät
    """
    # Prüfe, ob es ein Casambi-Gerät ist
    if CASAMBI_MANUFACTURER_ID not in adv_data.manufacturer_data:
        return "non_casambi"
    
    # Hole die Herstellerdaten
    mfr_data = adv_data.manufacturer_data[CASAMBI_MANUFACTURER_ID]
    has_uuid = CASAMBI_UUID_CONFIGURED in adv_data.service_uuids or CASAMBI_UUID_LIBRARY in adv_data.service_uuids
    
    # Besitzt kurze Herstellerdaten (7-8 Bytes)
    is_short_data = len(mfr_data) <= 8
    
    # Enthält die eigene MAC-Adresse
    contains_own_mac = contains_mac_address(mfr_data, device.address)
    
    # Enthält Nullsequenz
    has_nulls = contains_nulls(mfr_data)
    
    # Versuche die Unit-Adresse zu extrahieren
    unit_address = extract_unit_address(mfr_data)
    
    # Logische Regeln zur Bestimmung des Gerätetyps
    if has_uuid and is_short_data and contains_own_mac:
        return "virtual"
    elif has_nulls and not has_uuid:
        return "physical_reset"
    elif not has_uuid and unit_address and len(mfr_data) >= 20:
        return "physical_configured"
    else:
        return "unknown"


def extract_device_state(device: BLEDevice, adv_data: AdvertisementData) -> Dict[str, Any]:
    """
    Extrahiert den Zustand eines Geräts aus seinen Werbedaten.
    
    Returns:
        Ein Dictionary mit den relevanten Zustandsinformationen
    """
    # Basis-Geräteinformationen
    result = {
        "timestamp": datetime.now().isoformat(),
        "device_address": device.address,
        "device_name": device.name,
        "rssi": adv_data.rssi,
        "local_name": adv_data.local_name,
        "service_uuids": adv_data.service_uuids,
        "has_casambi_uuid": False,
        "manufacturer_data": {}
    }
    
    # Prüfe auf Casambi UUID
    if CASAMBI_UUID_CONFIGURED in adv_data.service_uuids or CASAMBI_UUID_LIBRARY in adv_data.service_uuids:
        result["has_casambi_uuid"] = True
    
    # Sammle alle Herstellerdaten
    for mfr_id, data in adv_data.manufacturer_data.items():
        result["manufacturer_data"][str(mfr_id)] = data.hex()
    
    # Bestimme den Gerätetyp
    result["device_type"] = determine_device_type(device, adv_data)
    
    # Spezifische Analyse für Casambi-Herstellerdaten
    if CASAMBI_MANUFACTURER_ID in adv_data.manufacturer_data:
        casambi_data = adv_data.manufacturer_data[CASAMBI_MANUFACTURER_ID]
        result["casambi_data"] = {
            "raw_hex": casambi_data.hex(),
            "length": len(casambi_data),
            "unit_address": extract_unit_address(casambi_data),
            "contains_nulls": contains_nulls(casambi_data),
            "contains_own_mac": contains_mac_address(casambi_data, device.address)
        }
        
        # Suche nach anderen MAC-Adressen in den Daten
        result["casambi_data"]["other_mac_addresses"] = []
        other_macs = find_embedded_mac_addresses(casambi_data, exclude_mac=device.address)
        if other_macs:
            result["casambi_data"]["other_mac_addresses"] = other_macs
    
    return result


def find_embedded_mac_addresses(data: bytes, exclude_mac: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Sucht nach möglichen MAC-Adressen, die in den Daten eingebettet sind.
    
    Args:
        data: Die zu durchsuchenden Daten
        exclude_mac: Eine MAC-Adresse, die ausgeschlossen werden soll (z.B. die eigene)
        
    Returns:
        Eine Liste von gefundenen MAC-Adressen mit Position
    """
    result = []
    exclude_hex = exclude_mac.replace(":", "").lower() if exclude_mac else None
    
    # Betrachte jeden 6-Byte-Block als potenzielle MAC-Adresse
    for i in range(len(data) - 5):
        chunk = data[i:i+6]
        chunk_hex = chunk.hex()
        
        # Ignoriere Nullsequenzen und die ausgeschlossene MAC
        if chunk == bytes([0, 0, 0, 0, 0, 0]) or (exclude_hex and chunk_hex.lower() == exclude_hex):
            continue
        
        # Formatiere als MAC-Adresse
        formatted_mac = ":".join(chunk_hex[j:j+2] for j in range(0, 12, 2))
        
        result.append({
            "position": i,
            "hex": chunk_hex,
            "formatted": formatted_mac
        })
    
    return result


async def scan_for_devices(scan_time: float = 10.0) -> Dict[str, Dict[str, Any]]:
    """
    Scannt nach allen BLE-Geräten im Umkreis und extrahiert ihre Zustände.
    
    Args:
        scan_time: Zeit in Sekunden, für die gescannt werden soll
        
    Returns:
        Dictionary mit Geräteadresse als Schlüssel und Gerätezustand als Wert
    """
    _LOGGER.info(f"Starte Bluetooth-Scan für {scan_time} Sekunden...")
    print_colored(f"Starte Bluetooth-Scan für {scan_time} Sekunden...", TEXT_CYAN)
    
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
        
        # Zeige Fortschrittsanzeige während des Scans
        for i in range(int(scan_time)):
            print(f"Scanning... {i+1}/{int(scan_time)} Sekunden, {len(devices_detected)} Geräte gefunden", end="\r")
            await asyncio.sleep(1)
        
        await scanner.stop()
        print()  # Neue Zeile nach der Fortschrittsanzeige
        
        # Extrahiere Gerätezustände
        device_states = {}
        for addr, (device, adv_data) in devices_detected.items():
            device_states[addr] = extract_device_state(device, adv_data)
        
        _LOGGER.info(f"Scan abgeschlossen. {len(device_states)} Geräte gefunden.")
        return device_states
        
    except BleakDBusError as e:
        _LOGGER.error(f"DBus-Fehler beim Bluetooth-Scan: {e.dbus_error} - {e.dbus_error_details}")
        raise
    except BleakError as e:
        _LOGGER.error(f"Bluetooth-Fehler: {str(e)}")
        raise
    except Exception as e:
        _LOGGER.exception(f"Unerwarteter Fehler beim Scan: {str(e)}")
        raise


def summarize_scan_results(device_states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Erstellt eine Zusammenfassung der Scan-Ergebnisse."""
    # Kategorisiere die Geräte
    physical_reset = []
    physical_configured = []
    virtual_devices = []
    unknown_devices = []
    other_devices = []
    
    for addr, state in device_states.items():
        device_type = state.get("device_type", "non_casambi")
        device_info = {
            "address": addr,
            "name": state.get("device_name", "Unbenannt"),
            "device_type": device_type
        }
        
        if "casambi_data" in state:
            device_info["unit_address"] = state["casambi_data"].get("unit_address")
        
        if device_type == "physical_reset":
            physical_reset.append(device_info)
        elif device_type == "physical_configured":
            physical_configured.append(device_info)
        elif device_type == "virtual":
            virtual_devices.append(device_info)
        elif device_type == "unknown":
            unknown_devices.append(device_info)
        else:
            other_devices.append(device_info)
    
    # Suche nach zusammengehörigen Geräten (gleiche Unit-Adresse)
    related_devices = find_related_devices(device_states)
    
    return {
        "total_devices": len(device_states),
        "physical_reset_count": len(physical_reset),
        "physical_configured_count": len(physical_configured),
        "virtual_count": len(virtual_devices),
        "unknown_count": len(unknown_devices),
        "other_count": len(other_devices),
        "physical_reset": physical_reset,
        "physical_configured": physical_configured,
        "virtual_devices": virtual_devices,
        "unknown_devices": unknown_devices,
        "related_devices": related_devices
    }


def find_related_devices(device_states: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identifiziert Geräte, die wahrscheinlich zusammengehören (Teil desselben Mesh-Netzwerks sind).
    
    Dies geschieht durch Analyse der eingebetteten MAC-Adressen und Unit-Adressen.
    """
    related_groups = []
    
    # Sammle Unit-Adressen
    unit_address_map = {}
    for addr, state in device_states.items():
        if "casambi_data" in state and "unit_address" in state["casambi_data"]:
            unit_addr = state["casambi_data"]["unit_address"]
            if unit_addr:
                if unit_addr not in unit_address_map:
                    unit_address_map[unit_addr] = []
                unit_address_map[unit_addr].append(addr)
    
    # Identifiziere Geräte mit derselben Unit-Adresse
    for unit_addr, device_addrs in unit_address_map.items():
        if len(device_addrs) > 1:
            related_groups.append({
                "unit_address": unit_addr,
                "devices": device_addrs,
                "relation_type": "same_unit_address"
            })
    
    # Finde Geräte, die die MAC-Adresse eines anderen Geräts enthalten
    mac_references = {}
    for addr, state in device_states.items():
        if "casambi_data" in state and "other_mac_addresses" in state["casambi_data"]:
            for mac_info in state["casambi_data"]["other_mac_addresses"]:
                embedded_mac = mac_info["formatted"].replace(":", "").lower()
                for other_addr in device_states:
                    other_mac = other_addr.replace(":", "").lower()
                    if embedded_mac == other_mac:
                        if addr not in mac_references:
                            mac_references[addr] = []
                        mac_references[addr].append(other_addr)
    
    # Erstelle Gruppen basierend auf MAC-Referenzen
    for addr, referenced_addrs in mac_references.items():
        related_groups.append({
            "reference_device": addr,
            "referenced_devices": referenced_addrs,
            "relation_type": "mac_reference"
        })
    
    return related_groups


def print_device_details(device_state: Dict[str, Any], show_analysis: bool = True) -> None:
    """Zeigt detaillierte Informationen zu einem Gerät an."""
    # Bestimme Kategorie und Farbe
    device_type = device_state.get("device_type", "non_casambi")
    
    if device_type == "physical_reset":
        color = TEXT_YELLOW
        status_text = "PHYSISCHES GERÄT (ZURÜCKGESETZT)"
    elif device_type == "physical_configured":
        color = TEXT_GREEN
        status_text = "PHYSISCHES GERÄT (KONFIGURIERT)"
    elif device_type == "virtual":
        color = TEXT_MAGENTA
        status_text = "VIRTUELLES GERÄT"
    elif device_type == "unknown":
        color = TEXT_RED
        status_text = "UNBEKANNTER TYP"
    else:
        color = TEXT_RESET
        status_text = "NICHT CASAMBI"
    
    # Gerätename und Adresse
    name = device_state.get("device_name") or "Unbenannt"
    address = device_state.get("device_address", "")
    print_colored(f"\n{status_text}: {name} ({address})", color, bold=True)
    
    # Unit-Adresse, falls verfügbar
    if "casambi_data" in device_state and "unit_address" in device_state["casambi_data"]:
        unit_addr = device_state["casambi_data"]["unit_address"]
        print_colored(f"Unit-Adresse: {unit_addr}", TEXT_CYAN, bold=True)
    
    # Grundlegende Informationen
    print(f"RSSI: {device_state.get('rssi')} dBm")
    print(f"Lokaler Name: {device_state.get('local_name') or 'Nicht angegeben'}")
    
    # Service UUIDs
    service_uuids = device_state.get("service_uuids", [])
    if service_uuids:
        print("Service UUIDs:")
        for uuid in service_uuids:
            uuid_str = uuid
            if uuid == CASAMBI_UUID_CONFIGURED:
                uuid_str += f" {TEXT_GREEN}(CASAMBI KONFIGURIERT){TEXT_RESET}"
            elif uuid == CASAMBI_UUID_LIBRARY:
                uuid_str += f" {TEXT_GREEN}(CASAMBI BIBLIOTHEK){TEXT_RESET}"
            print(f"  - {uuid_str}")
    else:
        print("Service UUIDs: Keine")
    
    # Casambi-Herstellerdaten
    if "casambi_data" in device_state:
        casambi_data = device_state["casambi_data"]
        print_colored(f"Casambi Herstellerdaten (ID: {CASAMBI_MANUFACTURER_ID}):", TEXT_CYAN)
        print(f"  Hex: {casambi_data['raw_hex']}")
        print(f"  Länge: {casambi_data['length']} Bytes")
        
        # Detaillierte Analyse der Herstellerdaten
        if show_analysis:
            print("\nAnalyse der Herstellerdaten:")
            
            if casambi_data.get("contains_own_mac", False):
                print_colored(f"  ✓ Enthält eigene MAC-Adresse", TEXT_GREEN)
            else:
                print(f"  ✗ Enthält nicht die eigene MAC-Adresse")
                
            if casambi_data.get("contains_nulls", False):
                print_colored(f"  ✓ Enthält Nullsequenz (typisch für ZURÜCKGESETZTE Geräte)", TEXT_YELLOW)
                
            if "other_mac_addresses" in casambi_data and casambi_data["other_mac_addresses"]:
                print_colored("  ✓ Enthält mögliche MAC-Adressen anderer Geräte:", TEXT_CYAN)
                for mac_info in casambi_data["other_mac_addresses"]:
                    print(f"    - {mac_info['formatted']} an Position {mac_info['position']}")
    else:
        print("Keine Casambi Herstellerdaten vorhanden")


def print_scan_summary(summary: Dict[str, Any]) -> None:
    """Zeigt eine Zusammenfassung der Scan-Ergebnisse an."""
    print_colored("\n=== ZUSAMMENFASSUNG DER GEFUNDENEN GERÄTE ===", TEXT_CYAN, bold=True)
    print_colored(f"Gesamt gefundene Geräte: {summary['total_devices']}", TEXT_CYAN)
    print_colored(f"Physische Geräte (zurückgesetzt): {summary['physical_reset_count']}", TEXT_YELLOW)
    print_colored(f"Physische Geräte (konfiguriert): {summary['physical_configured_count']}", TEXT_GREEN)
    print_colored(f"Virtuelle Geräte: {summary['virtual_count']}", TEXT_MAGENTA)
    print_colored(f"Geräte mit unklarem Status: {summary['unknown_count']}", TEXT_RED)
    print(f"Andere Bluetooth LE Geräte: {summary['other_count']}")
    
    # Zeige zusammengehörige Gerätegruppen an
    if summary.get("related_devices"):
        print_colored("\n=== ZUSAMMENGEHÖRIGE GERÄTE ===", TEXT_BLUE, bold=True)
        for group in summary["related_devices"]:
            if group["relation_type"] == "same_unit_address":
                print_colored(f"\nGeräte mit derselben Unit-Adresse: {group['unit_address']}", TEXT_BLUE)
                for addr in group["devices"]:
                    print(f"- {addr}")
            elif group["relation_type"] == "mac_reference":
                print_colored(f"\nGerät {group['reference_device']} referenziert:", TEXT_BLUE)
                for addr in group["referenced_devices"]:
                    print(f"- {addr}")


def save_results(test_id: str, device_states: Dict[str, Dict[str, Any]]) -> str:
    """
    Speichert die Scan-Ergebnisse in einer JSON-Datei.
    
    Returns:
        Den Pfad zur gespeicherten Datei
    """
    # Stelle sicher, dass der Ordner existiert
    if not os.path.exists(RESULTS_FOLDER):
        os.makedirs(RESULTS_FOLDER)
    
    # Erstelle Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{test_id}_{timestamp}.json"
    filepath = os.path.join(RESULTS_FOLDER, filename)
    
    # Speichere Daten als JSON
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(device_states, f, indent=2)
    
    return filepath


async def run_test_phase(phase_name: str, scan_time: float) -> Dict[str, Dict[str, Any]]:
    """
    Führt eine Testphase durch (einen Scan mit Benutzerinteraktion).
    
    Args:
        phase_name: Name der Testphase
        scan_time: Dauer des Scans in Sekunden
        
    Returns:
        Die Scan-Ergebnisse
    """
    clear_screen()
    
    # Zeige Anweisungen
    print_colored(f"\n=== PHASE: {phase_name.upper()} ===", TEXT_CYAN, bold=True)
    print(f"\nIn dieser Phase scannen wir nach Casambi-Geräten für {scan_time} Sekunden.")
    
    # Warte auf Benutzerbereitschaft
    input("\nDrücken Sie ENTER, um den Scan zu starten...")
    
    # Führe den Scan durch
    device_states = await scan_for_devices(scan_time)
    
    # Zeige Zusammenfassung
    summary = summarize_scan_results(device_states)
    print_scan_summary(summary)
    
    # Zeige Details zu den interessanten Geräten
    if summary["physical_reset_count"] > 0:
        print_colored("\n=== PHYSISCHE GERÄTE (ZURÜCKGESETZT) ===", TEXT_YELLOW, bold=True)
        for device_info in summary["physical_reset"]:
            device_state = device_states[device_info["address"]]
            print_device_details(device_state)
    
    if summary["physical_configured_count"] > 0:
        print_colored("\n=== PHYSISCHE GERÄTE (KONFIGURIERT) ===", TEXT_GREEN, bold=True)
        for device_info in summary["physical_configured"]:
            device_state = device_states[device_info["address"]]
            print_device_details(device_state)
    
    if summary["virtual_count"] > 0:
        print_colored("\n=== VIRTUELLE GERÄTE ===", TEXT_MAGENTA, bold=True)
        for device_info in summary["virtual_devices"]:
            device_state = device_states[device_info["address"]]
            print_device_details(device_state)
    
    if summary["unknown_count"] > 0:
        print_colored("\n=== GERÄTE MIT UNKLAREM STATUS ===", TEXT_RED, bold=True)
        for device_info in summary["unknown_devices"]:
            device_state = device_states[device_info["address"]]
            print_device_details(device_state)
    
    # Speichere Ergebnisse
    test_id = f"mesh_analysis_{phase_name.lower().replace(' ', '_')}"
    save_path = save_results(test_id, device_states)
    print_colored(f"\nErgebnisse gespeichert unter: {save_path}", TEXT_CYAN)
    
    # Warte auf Benutzerbestätigung
    input("\nDrücken Sie ENTER, um fortzufahren...")
    
    return device_states


async def main() -> None:
    """Hauptfunktion für die Mesh-Netzwerk-Analyse."""
    clear_screen()
    print_colored("\n===== CASAMBI MESH-NETZWERK ANALYSE =====", TEXT_CYAN, bold=True)
    print("\nDieses Skript analysiert Casambi-Geräte mit Fokus auf die Mesh-Netzwerk-Hypothese.")
    print("Es führt einen strukturierten Test in klar definierten Phasen durch, um die")
    print("Unterschiede zwischen physischen und virtuellen Geräten zu verstehen.")
    
    # Frage nach der Scan-Zeit
    scan_time_str = input("\nWie lange soll jeder Scan dauern (Sekunden, Standard: 10)? ")
    scan_time = float(scan_time_str) if scan_time_str.strip() else 10.0
    
    # Erstelle Ordner für Ergebnisse, falls er nicht existiert
    if not os.path.exists(RESULTS_FOLDER):
        os.makedirs(RESULTS_FOLDER)
    
    try:
        # Phase 1: Zurückgesetztes Gerät
        clear_screen()
        print_colored("\n=== PHASE 1: ZURÜCKGESETZTES GERÄT ===", TEXT_YELLOW, bold=True)
        print("\nIn dieser Phase scannen wir ein Casambi-Gerät im zurückgesetzten Zustand.")
        print("\nAnweisungen zur Vorbereitung:")
        print("1. Stellen Sie sicher, dass Ihr Casambi-Gerät auf Werkseinstellungen zurückgesetzt ist")
        print("2. Falls das Gerät derzeit konfiguriert ist, setzen Sie es auf Werkseinstellungen zurück")
        print("   (Konsultieren Sie das Handbuch des Geräts für spezifische Anweisungen)")
        print("3. Vergewissern Sie sich, dass das Gerät eingeschaltet und in Reichweite ist")
        
        input("\nDrücken Sie ENTER, wenn Ihr Gerät zurückgesetzt und bereit ist...")
        await run_test_phase("PHASE1_ZURÜCKGESETZT", scan_time)
        
        # Phase 2: Gerät konfigurieren
        clear_screen()
        print_colored("\n=== PHASE 2: GERÄT KONFIGURIEREN ===", TEXT_MAGENTA, bold=True)
        print("\nJetzt werden wir das Gerät in ein Netzwerk einbinden.")
        print("\nAnweisungen zur Konfiguration:")
        print("1. Öffnen Sie die Casambi-App auf Ihrem Smartphone/Tablet")
        print("2. Fügen Sie das zurückgesetzte Gerät zu einem Netzwerk hinzu")
        print("3. Entfernen eines Geräts aus einem Netzwerk")
        print("4. Hinzufügen eines weiteren physischen Geräts zum Netzwerk")
        print("\nNach der Änderung führen wir einen weiteren Scan durch.")
        input("\nDrücken Sie ENTER, wenn Sie die Änderungen vorgenommen haben...")
        
        input("\nDrücken Sie ENTER, wenn die Konfiguration abgeschlossen ist...")
        await run_test_phase("PHASE2_KONFIGURIERT", scan_time)
        
        # Phase 3: Optional - Mehrere Geräte
        clear_screen()
        print_colored("\n=== PHASE 3: MEHRERE GERÄTE (OPTIONAL) ===", TEXT_GREEN, bold=True)
        print("\nDiese Phase ist optional und für Tests mit mehreren physischen Geräten gedacht.")
        
        has_multiple_devices = input("\nHaben Sie weitere physische Casambi-Geräte verfügbar? (j/n): ").lower().startswith('j')
        
        if has_multiple_devices:
            print("\nAnweisungen für mehrere Geräte:")
            print("1. Stellen Sie sicher, dass mindestens ein weiteres Casambi-Gerät verfügbar ist")
            print("2. Fügen Sie dieses weitere Gerät zum selben Netzwerk hinzu")
            print("3. Achten Sie darauf, dass beide Geräte eingeschaltet und in Reichweite sind")
            
            input("\nDrücken Sie ENTER, wenn mehrere Geräte konfiguriert und bereit sind...")
            await run_test_phase("PHASE3_MEHRERE_GERÄTE", scan_time)
        
        # Phase 4: Gerät aus Netzwerk entfernen
        clear_screen()
        print_colored("\n=== PHASE 4: GERÄT AUS NETZWERK ENTFERNEN ===", TEXT_RED, bold=True)
        print("\nJetzt werden wir ein Gerät aus dem Netzwerk entfernen und die Auswirkungen beobachten.")
        print("\nAnweisungen zum Entfernen des Geräts:")
        print("1. Öffnen Sie die Casambi-App auf Ihrem Smartphone/Tablet")
        print("2. Entfernen Sie eines der Casambi-Geräte aus dem Netzwerk")
        print("   (Bei mehreren Geräten: Entfernen Sie ein Gerät, lassen Sie aber mindestens ein Gerät im Netzwerk)")
        
        input("\nDrücken Sie ENTER, wenn ein Gerät aus dem Netzwerk entfernt wurde...")
        await run_test_phase("PHASE4_NACH_ENTFERNUNG", scan_time)
        
        # Abschließende Zusammenfassung
        clear_screen()
        print_colored("\n===== ZUSAMMENFASSUNG DER ANALYSE =====", TEXT_CYAN, bold=True)
        print("\nWir haben einen strukturierten Test in den folgenden Phasen durchgeführt:")
        print("1. Zurückgesetztes Gerät - Sollte keine virtuellen Geräte zeigen, nur physische mit Nullsequenz")
        print("2. Konfiguriertes Gerät - Sollte physische Geräte mit eingebetteten MAC-Adressen und")
        print("   möglicherweise zusätzliche virtuelle Geräte mit Service UUID zeigen")
        if has_multiple_devices:
            print("3. Mehrere physische Geräte - Sollte mehrere physische Geräte und möglicherweise")
            print("   mehrere virtuelle Geräte zeigen, die sich gegenseitig referenzieren")
        print(f"{'3' if not has_multiple_devices else '4'}. Nach Entfernung eines Geräts - Sollte zeigen, wie sich das Netzwerk anpasst")
        
        print_colored("\nDie Mesh-Netzwerk-Hypothese besagt:", TEXT_BLUE)
        print("- Ein physisches Casambi-Gerät kann in seinen Werbedaten Informationen über")
        print("  andere Geräte im selben Netzwerk übertragen")
        print("- Die Unit-Adresse bleibt in allen Zuständen konstant")
        print("- Virtuelle Geräte werden nur angezeigt, wenn zugehörige physische Geräte")
        print("  konfiguriert und im Netzwerk sind")
    
    except Exception as e:
        _LOGGER.exception(f"Fehler während der Analyse: {str(e)}")
        print_colored(f"\nFehler aufgetreten: {type(e).__name__}: {str(e)}", TEXT_RED)
    
    print_colored("\n===== ANALYSE ABGESCHLOSSEN =====", TEXT_CYAN, bold=True)


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
    