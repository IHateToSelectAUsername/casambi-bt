 #!/usr/bin/env python3
import asyncio
import json
import logging
import os
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Callable, Any, Dict, Deque

from CasambiBt import Casambi, discover, Unit, Group, Scene, UnitControlType, UnitState

_LOGGER = logging.getLogger()
_LOGGER.addHandler(logging.StreamHandler())

# Globale Variable für die Casambi-Instanz
casa = None

# Datei für gespeicherte Verbindungen
CONNECTIONS_FILE = os.path.expanduser("~/.casambi_connections.json")

# Netzwerkmonitor-Einträge
@dataclass
class NetworkEvent:
    """Repräsentiert ein Ereignis im Netzwerk."""
    timestamp: datetime
    event_type: str  # "command", "status_update", "connection", "disconnection"
    target: str  # Name des Ziels (Gerät, Gruppe oder "Network")
    action: str  # Aktion oder Status
    details: Optional[str] = None  # Zusätzliche Details

# Ereignis-Log für den Netzwerkmonitor, speichert die letzten 100 Ereignisse
network_events: Deque[NetworkEvent] = deque(maxlen=100)

def add_network_event(event_type: str, target: str, action: str, details: Optional[str] = None):
    """Fügt ein Ereignis zum Netzwerkmonitor hinzu."""
    event = NetworkEvent(
        timestamp=datetime.now(),
        event_type=event_type,
        target=target,
        action=action,
        details=details
    )
    network_events.append(event)

# Farben für die Konsole (ANSI-Escape-Codes)
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def clear_screen():
    """Bildschirm löschen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title: str):
    """Druckt einen Menü-Header."""
    clear_screen()
    width = 60
    print(Colors.BLUE + "=" * width + Colors.ENDC)
    print(Colors.BOLD + title.center(width) + Colors.ENDC)
    print(Colors.BLUE + "=" * width + Colors.ENDC)
    
    # Verbindungsstatus anzeigen
    if casa and casa.connected:
        print(Colors.GREEN + f"Connected to network: {casa.networkName}" + Colors.ENDC)
    else:
        print(Colors.YELLOW + "Not connected to any network" + Colors.ENDC)
    print()

def print_menu_option(index: int, text: str, color: str = Colors.CYAN):
    """Druckt eine Menüoption."""
    print(f"{color}[{index}]{Colors.ENDC} {text}")

def print_back_option():
    """Druckt die Option zum Zurückkehren."""
    print(f"\n{Colors.YELLOW}[0]{Colors.ENDC} Back")

def get_user_input(prompt: str, valid_options: List = None) -> str:
    """Fordert den Benutzer zur Eingabe auf und überprüft die Gültigkeit."""
    while True:
        try:
            choice = input(f"\n{prompt}: ")
            if valid_options is None or choice in valid_options:
                return choice
            print(f"{Colors.RED}Invalid option. Please try again.{Colors.ENDC}")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return "0"  # Zurück zum vorherigen Menü
        except Exception:
            print(f"{Colors.RED}Invalid input. Please try again.{Colors.ENDC}")

def get_int_input(prompt: str, min_val: int = None, max_val: int = None) -> int:
    """Fordert den Benutzer zur Eingabe einer Zahl auf."""
    while True:
        try:
            value = int(input(f"\n{prompt}: "))
            if (min_val is None or value >= min_val) and (max_val is None or value <= max_val):
                return value
            range_str = ""
            if min_val is not None and max_val is not None:
                range_str = f" between {min_val} and {max_val}"
            elif min_val is not None:
                range_str = f" ≥ {min_val}"
            elif max_val is not None:
                range_str = f" ≤ {max_val}"
            print(f"{Colors.RED}Please enter a value{range_str}.{Colors.ENDC}")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return -1
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number.{Colors.ENDC}")

def get_float_input(prompt: str, min_val: float = None, max_val: float = None) -> float:
    """Fordert den Benutzer zur Eingabe einer Dezimalzahl auf."""
    while True:
        try:
            value = float(input(f"\n{prompt}: "))
            if (min_val is None or value >= min_val) and (max_val is None or value <= max_val):
                return value
            range_str = ""
            if min_val is not None and max_val is not None:
                range_str = f" between {min_val} and {max_val}"
            elif min_val is not None:
                range_str = f" ≥ {min_val}"
            elif max_val is not None:
                range_str = f" ≤ {max_val}"
            print(f"{Colors.RED}Please enter a value{range_str}.{Colors.ENDC}")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return -1
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number.{Colors.ENDC}")

def load_saved_connections() -> List[Dict]:
    """Gespeicherte Verbindungen laden."""
    try:
        if os.path.exists(CONNECTIONS_FILE):
            with open(CONNECTIONS_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"{Colors.RED}Error loading saved connections: {e}{Colors.ENDC}")
        return []

def save_connection(name: str, address: str, password: str = None, save_password: bool = False):
    """Verbindung speichern."""
    connections = load_saved_connections()
    
    # Prüfen, ob die Verbindung bereits existiert
    for i, conn in enumerate(connections):
        if conn["address"] == address:
            # Aktualisieren der vorhandenen Verbindung
            connections[i] = {
                "name": name,
                "address": address
            }
            if save_password and password:
                connections[i]["password"] = password
            elif "password" in connections[i] and not save_password:
                del connections[i]["password"]
            break
    else:
        # Neue Verbindung hinzufügen
        new_conn = {
            "name": name,
            "address": address
        }
        if save_password and password:
            new_conn["password"] = password
        connections.append(new_conn)
    
    try:
        with open(CONNECTIONS_FILE, "w") as f:
            json.dump(connections, f, indent=2)
        return True
    except Exception as e:
        print(f"{Colors.RED}Error saving connection: {e}{Colors.ENDC}")
        return False

def delete_connection(index: int) -> bool:
    """Gespeicherte Verbindung löschen."""
    connections = load_saved_connections()
    
    if index < 0 or index >= len(connections):
        return False
    
    del connections[index]
    
    try:
        with open(CONNECTIONS_FILE, "w") as f:
            json.dump(connections, f, indent=2)
        return True
    except Exception as e:
        print(f"{Colors.RED}Error deleting connection: {e}{Colors.ENDC}")
        return False

def print_status_info(unit: Unit):
    """Zeigt detaillierte Statusinformationen für ein Gerät an."""
    state_str = f"{Colors.GREEN}ON{Colors.ENDC}" if unit.is_on else f"{Colors.RED}OFF{Colors.ENDC}"
    online_str = f"{Colors.GREEN}ONLINE{Colors.ENDC}" if unit.online else f"{Colors.RED}OFFLINE{Colors.ENDC}"
    
    print(f"{Colors.BOLD}{unit.name}{Colors.ENDC} (ID: {unit.deviceId})")
    print(f"  Status: {state_str}, {online_str}")
    print(f"  Type: {unit.unitType.model} ({unit.unitType.manufacturer})")
    print(f"  Firmware: {unit.firmwareVersion}")
    
    if unit.state:
        print("  State:")
        if unit.state.dimmer is not None:
            level_percent = round(unit.state.dimmer / 255 * 100)
            print(f"    • Brightness: {level_percent}%")
        if unit.state.rgb is not None:
            print(f"    • Color: RGB{unit.state.rgb}")
        if unit.state.temperature is not None:
            print(f"    • Temperature: {unit.state.temperature}K")
        if unit.state.white is not None:
            white_percent = round(unit.state.white / 255 * 100)
            print(f"    • White: {white_percent}%")
        if unit.state.vertical is not None:
            vertical_percent = round(unit.state.vertical / 255 * 100)
            print(f"    • Vertical: {vertical_percent}%")

def is_control_supported(unit: Unit, control_type: UnitControlType) -> bool:
    """Überprüft, ob ein Gerät einen bestimmten Steuertyp unterstützt."""
    return unit.unitType.get_control(control_type) is not None

async def discover_networks() -> List:
    """Sucht nach Casambi-Netzwerken."""
    print_header("Searching for Casambi Networks")
    print("Scanning... Please wait...\n")
    
    try:
        devices = await discover()
        
        if not devices:
            print(f"{Colors.YELLOW}No Casambi networks found!{Colors.ENDC}")
            input("\nPress Enter to continue...")
            return []
        
        print(f"{Colors.GREEN}Found {len(devices)} Casambi networks:{Colors.ENDC}\n")
        for i, d in enumerate(devices, 1):
            print_menu_option(i, f"Network at {d.address}")
            
        print_back_option()
        
        choice = get_int_input("Select a network", 0, len(devices))
        if choice == 0:
            return []
        
        return [devices[choice-1]]
    except Exception as e:
        print(f"{Colors.RED}Error during discovery: {e}{Colors.ENDC}")
        input("\nPress Enter to continue...")
        return []

async def manage_saved_connections():
    """Gespeicherte Verbindungen verwalten."""
    while True:
        print_header("Manage Saved Connections")
        
        connections = load_saved_connections()
        
        if not connections:
            print("No saved connections.")
            print_menu_option(1, "Add a new connection")
            print_back_option()
            
            choice = get_int_input("Choose an option", 0, 1)
            if choice == 0:
                return
            elif choice == 1:
                await add_new_connection()
        else:
            print(f"{Colors.BOLD}Saved Connections:{Colors.ENDC}")
            for i, conn in enumerate(connections, 1):
                password_info = " (with saved password)" if "password" in conn else ""
                print_menu_option(i, f"{conn['name']} - {conn['address']}{password_info}")
            
            print_menu_option(len(connections) + 1, "Add a new connection")
            print_back_option()
            
            choice = get_int_input("Choose an option", 0, len(connections) + 1)
            if choice == 0:
                return
            elif choice == len(connections) + 1:
                await add_new_connection()
            else:
                await manage_specific_connection(choice - 1)

async def add_new_connection():
    """Neue Verbindung hinzufügen."""
    print_header("Add New Connection")
    
    # Option zum Entdecken von Netzwerken oder manueller Eingabe
    print_menu_option(1, "Discover networks")
    print_menu_option(2, "Enter address manually")
    print_back_option()
    
    choice = get_int_input("Choose an option", 0, 2)
    if choice == 0:
        return
    
    address = None
    if choice == 1:
        devices = await discover_networks()
        if not devices:
            return
        address = devices[0].address
    else:
        address = input("\nEnter MAC address (format xx:xx:xx:xx:xx:xx): ")
    
    name = input("\nEnter a name for this connection: ")
    if not name.strip():
        name = f"Network {address}"
    
    password = input("\nEnter password (leave empty to skip): ")
    
    save_pwd = False
    if password:
        save_pwd_input = get_user_input("Save password? (WARNING: Saved in plain text) (y/n)", ["y", "n"])
        save_pwd = save_pwd_input.lower() == "y"
    
    if save_connection(name, address, password, save_pwd):
        print(f"\n{Colors.GREEN}Connection saved successfully!{Colors.ENDC}")
    else:
        print(f"\n{Colors.RED}Failed to save connection.{Colors.ENDC}")
    
    input("\nPress Enter to continue...")

async def manage_specific_connection(index: int):
    """Bestimmte Verbindung verwalten."""
    connections = load_saved_connections()
    if index < 0 or index >= len(connections):
        return
    
    connection = connections[index]
    
    while True:
        print_header(f"Manage Connection: {connection['name']}")
        
        print(f"Address: {connection['address']}")
        if "password" in connection:
            print("Password: [Saved]")
        
        print_menu_option(1, "Connect")
        print_menu_option(2, "Rename")
        if "password" in connection:
            print_menu_option(3, "Update password")
            print_menu_option(4, "Remove password")
        else:
            print_menu_option(3, "Add password")
        print_menu_option(5, f"{Colors.RED}Delete connection{Colors.ENDC}")
        print_back_option()
        
        max_option = 5
        choice = get_int_input("Choose an option", 0, max_option)
        
        if choice == 0:
            return
        elif choice == 1:
            # Verbinden - direkt die Adresse verwenden
            address = connection["address"]
            
            password = connection.get("password", None)
            if not password:
                password = input("\nEnter password: ")
            
            await connect_to_network(address, password)
            return
        elif choice == 2:
            # Umbenennen
            new_name = input("\nEnter new name: ")
            if new_name.strip():
                save_connection(new_name, connection["address"], 
                               connection.get("password"), "password" in connection)
                connection["name"] = new_name
                print(f"\n{Colors.GREEN}Connection renamed!{Colors.ENDC}")
                input("\nPress Enter to continue...")
        elif choice == 3:
            # Passwort hinzufügen/aktualisieren
            new_password = input("\nEnter new password: ")
            if new_password:
                save_connection(connection["name"], connection["address"], new_password, True)
                connection["password"] = new_password
                print(f"\n{Colors.GREEN}Password updated!{Colors.ENDC}")
            else:
                print(f"\n{Colors.YELLOW}Password unchanged.{Colors.ENDC}")
            input("\nPress Enter to continue...")
        elif choice == 4 and "password" in connection:
            # Passwort entfernen
            confirm = get_user_input("Are you sure you want to remove the saved password? (y/n)", ["y", "n"])
            if confirm.lower() == "y":
                save_connection(connection["name"], connection["address"], None, False)
                if "password" in connection:
                    del connection["password"]
                print(f"\n{Colors.GREEN}Password removed!{Colors.ENDC}")
                input("\nPress Enter to continue...")
        elif choice == 5:
            # Löschen
            confirm = get_user_input(f"Are you sure you want to delete '{connection['name']}'? (y/n)", ["y", "n"])
            if confirm.lower() == "y":
                if delete_connection(index):
                    print(f"\n{Colors.GREEN}Connection deleted!{Colors.ENDC}")
                    input("\nPress Enter to continue...")
                    return
                else:
                    print(f"\n{Colors.RED}Failed to delete connection.{Colors.ENDC}")
                    input("\nPress Enter to continue...")

async def connect_to_network(device=None, password=None):
    """Verbindet sich mit einem Netzwerk."""
    global casa
    
    print_header("Connect to Casambi Network")
    
    if device is None:
        # Optionen anzeigen
        print_menu_option(1, "Use a saved connection")
        print_menu_option(2, "Enter a network address")
        print_menu_option(3, "Discover networks")
        print_back_option()
        
        choice = get_int_input("Choose an option", 0, 3)
        
        if choice == 0:
            return
        elif choice == 1:
            # Gespeicherte Verbindung verwenden
            connections = load_saved_connections()
            if not connections:
                print(f"\n{Colors.YELLOW}No saved connections. Please add one first.{Colors.ENDC}")
                input("\nPress Enter to continue...")
                return
            
            print(f"\n{Colors.BOLD}Select a connection:{Colors.ENDC}")
            for i, conn in enumerate(connections, 1):
                password_info = " (with saved password)" if "password" in conn else ""
                print_menu_option(i, f"{conn['name']} - {conn['address']}{password_info}")
            
            print_back_option()
            
            conn_choice = get_int_input("Choose a connection", 0, len(connections))
            if conn_choice == 0:
                return
            
            connection = connections[conn_choice - 1]
            device = connection["address"]  # Direkt die Adresse verwenden
            password = connection.get("password", None)
        elif choice == 2:
            # Direkt die Adresse verwenden
            device = input("\nEnter MAC address (format xx:xx:xx:xx:xx:xx): ")
        elif choice == 3:
            devices = await discover_networks()
            if not devices:
                return
            device = devices[0]  # Dies ist bereits ein BLEDevice, das korrekt initialisiert wurde
            
            # Fragen, ob diese Verbindung gespeichert werden soll
            save_this = get_user_input("Do you want to save this connection for future use? (y/n)", ["y", "n"])
            if save_this.lower() == "y":
                name = input("\nEnter a name for this connection: ")
                if not name.strip():
                    name = f"Network {device.address}"
                
                address = device.address
                
                # Passwort wird später abgefragt
    
    # Wenn noch kein Passwort gesetzt wurde, danach fragen
    if password is None:
        password = input("\nEnter password: ")
    
    # Verbindung zum Netzwerk herstellen
    print("\nConnecting to network...")
    
    if casa is not None:
        await casa.disconnect()
    
    casa = Casambi()
    try:
        await casa.connect(device, password)
        print(f"\n{Colors.GREEN}Successfully connected to network '{casa.networkName}'!{Colors.ENDC}")
        
        add_network_event("connection", "Network", "Connected", 
                         f"Connected to network {casa.networkName}")
        
        # Wenn wir zuvor gefragt haben, ob die Verbindung gespeichert werden soll
        if 'choice' in locals() and choice == 3 and save_this.lower() == "y":
            save_pwd = get_user_input("Save password? (WARNING: Saved in plain text) (y/n)", ["y", "n"])
            save_connection(name, address, password, save_pwd.lower() == "y")
            print(f"\n{Colors.GREEN}Connection saved!{Colors.ENDC}")
        
        casa.registerUnitChangedHandler(on_unit_changed)
        casa.registerDisconnectCallback(on_disconnect)
    except Exception as e:
        print(f"\n{Colors.RED}Connection failed: {e}{Colors.ENDC}")
        casa = None
    
    input("\nPress Enter to continue...")

def on_unit_changed(unit: Unit):
    """Callback für Änderungen am Gerätezustand."""
    status = "ON" if unit.is_on else "OFF"
    details = f"Online: {unit.online}"
    
    if unit.state:
        detail_parts = []
        if unit.state.dimmer is not None:
            level_percent = round(unit.state.dimmer / 255 * 100)
            detail_parts.append(f"Brightness: {level_percent}%")
        if unit.state.rgb is not None:
            detail_parts.append(f"RGB: {unit.state.rgb}")
        if unit.state.temperature is not None:
            detail_parts.append(f"Temp: {unit.state.temperature}K")
        
        if detail_parts:
            details += f", {', '.join(detail_parts)}"
    
    add_network_event("status_update", unit.name, status, details)

def on_disconnect():
    """Callback für Verbindungsabbrüche."""
    print(f"\n{Colors.YELLOW}Disconnected from network!{Colors.ENDC}")
    add_network_event("disconnection", "Network", "Disconnected", "Connection lost")

async def show_network_status():
    """Zeigt den Status des Netzwerks an."""
    if not casa or not casa.connected:
        print(f"{Colors.RED}Not connected to any network!{Colors.ENDC}")
        input("\nPress Enter to continue...")
        return
    
    print_header(f"Network Status: {casa.networkName}")
    
    # Geräte anzeigen
    print(f"{Colors.BOLD}Units:{Colors.ENDC}")
    if not casa.units:
        print("  No units found.")
    for i, unit in enumerate(casa.units, 1):
        state_str = f"{Colors.GREEN}ON{Colors.ENDC}" if unit.is_on else f"{Colors.RED}OFF{Colors.ENDC}"
        online_str = f"{Colors.GREEN}ONLINE{Colors.ENDC}" if unit.online else f"{Colors.RED}OFFLINE{Colors.ENDC}"
        print(f"  {i}. {unit.name}: {state_str}, {online_str}")
    
    # Gruppen anzeigen
    print(f"\n{Colors.BOLD}Groups:{Colors.ENDC}")
    if not casa.groups:
        print("  No groups found.")
    for i, group in enumerate(casa.groups, 1):
        print(f"  {i}. {group.name}: {len(group.units)} units")
    
    # Szenen anzeigen
    print(f"\n{Colors.BOLD}Scenes:{Colors.ENDC}")
    if not casa.scenes:
        print("  No scenes found.")
    for i, scene in enumerate(casa.scenes, 1):
        print(f"  {i}. {scene.name}")
    
    input("\nPress Enter to continue...")

async def control_unit_menu():
    """Menü zur Steuerung einzelner Geräte."""
    if not casa or not casa.connected:
        print(f"{Colors.RED}Not connected to any network!{Colors.ENDC}")
        input("\nPress Enter to continue...")
        return
    
    while True:
        print_header("Control Units")
        
        if not casa.units:
            print("No units found in the network.")
            print_back_option()
            choice = get_int_input("Choose an option", 0, 0)
            return
        
        print(f"{Colors.BOLD}Select a unit to control:{Colors.ENDC}")
        for i, unit in enumerate(casa.units, 1):
            state_str = f"{Colors.GREEN}ON{Colors.ENDC}" if unit.is_on else f"{Colors.RED}OFF{Colors.ENDC}"
            print_menu_option(i, f"{unit.name}: {state_str}")
        
        print_back_option()
        
        choice = get_int_input("Choose a unit", 0, len(casa.units))
        if choice == 0:
            return
        
        unit = casa.units[choice-1]
        await control_specific_unit(unit)

async def control_specific_unit(unit: Unit):
    """Steuerungsmenü für ein spezifisches Gerät."""
    while True:
        print_header(f"Control Unit: {unit.name}")
        
        print_status_info(unit)
        print(f"\n{Colors.BOLD}Available Controls:{Colors.ENDC}")
        
        options = []
        
        # Einfaches Ein-/Ausschalten ist immer verfügbar
        options.append(("Turn ON", lambda: turn_on_unit(unit)))
        options.append(("Turn OFF", lambda: turn_off_unit(unit)))
        
        # Überprüfen, welche Steuertypen unterstützt werden
        if is_control_supported(unit, UnitControlType.DIMMER):
            options.append(("Set brightness", lambda: set_brightness(unit)))
            
        if is_control_supported(unit, UnitControlType.RGB):
            options.append(("Set RGB color", lambda: set_rgb_color(unit)))
            
        if is_control_supported(unit, UnitControlType.TEMPERATURE):
            options.append(("Set temperature", lambda: set_temperature(unit)))
            
        if is_control_supported(unit, UnitControlType.VERTICAL):
            options.append(("Set vertical", lambda: set_vertical(unit)))
            
        if is_control_supported(unit, UnitControlType.WHITE):
            options.append(("Set white level", lambda: set_white(unit)))
            
        if is_control_supported(unit, UnitControlType.SLIDER):
            options.append(("Set slider", lambda: set_slider(unit)))
        
        for i, (option_text, _) in enumerate(options, 1):
            print_menu_option(i, option_text)
        
        print_back_option()
        
        choice = get_int_input("Choose an action", 0, len(options))
        if choice == 0:
            return
        
        # Ausgewählte Aktion ausführen
        action_func = options[choice-1][1]
        await action_func()

async def turn_on_unit(unit: Unit):
    """Schaltet ein Gerät ein."""
    print(f"\nTurning ON {unit.name}...")
    add_network_event("command", unit.name, "Turn ON", None)
    await casa.turnOn(unit)
    print(f"{Colors.GREEN}Unit turned ON{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def turn_off_unit(unit: Unit):
    """Schaltet ein Gerät aus."""
    print(f"\nTurning OFF {unit.name}...")
    add_network_event("command", unit.name, "Turn OFF", None)
    await casa.setLevel(unit, 0)
    print(f"{Colors.GREEN}Unit turned OFF{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_brightness(unit: Unit):
    """Helligkeit eines Geräts einstellen."""
    print_header(f"Set Brightness: {unit.name}")
    
    brightness = get_float_input("Enter brightness (0-100%)", 0, 100)
    if brightness < 0:  # Abgebrochen
        return
    
    # Umrechnung von Prozent in 0-255
    level = int(brightness * 255 / 100)
    
    print("\nSetting brightness...")
    add_network_event("command", unit.name, "Set Brightness", f"{brightness}%")
    await casa.setLevel(unit, level)
    print(f"{Colors.GREEN}Brightness set to {brightness}%{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_rgb_color(unit: Unit):
    """RGB-Farbe eines Geräts einstellen."""
    print_header(f"Set RGB Color: {unit.name}")
    
    r = get_int_input("Red (0-255)", 0, 255)
    if r < 0: return
    
    g = get_int_input("Green (0-255)", 0, 255)
    if g < 0: return
    
    b = get_int_input("Blue (0-255)", 0, 255)
    if b < 0: return
    
    print("\nSetting color...")
    add_network_event("command", unit.name, "Set RGB Color", f"RGB({r}, {g}, {b})")
    await casa.setColor(unit, (r, g, b))
    print(f"{Colors.GREEN}Color set to RGB({r}, {g}, {b}){Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_temperature(unit: Unit):
    """Farbtemperatur eines Geräts einstellen."""
    print_header(f"Set Temperature: {unit.name}")
    
    # Die meisten Tunable White LEDs unterstützen einen Bereich von etwa 2700K-6500K
    temp = get_int_input("Enter temperature in Kelvin (e.g., 2700-6500)", 2000, 10000)
    if temp < 0:
        return
    
    print("\nSetting temperature...")
    add_network_event("command", unit.name, "Set Temperature", f"{temp}K")
    await casa.setTemperature(unit, temp)
    print(f"{Colors.GREEN}Temperature set to {temp}K{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_vertical(unit: Unit):
    """Vertikalen Wert eines Geräts einstellen."""
    print_header(f"Set Vertical: {unit.name}")
    
    vertical = get_float_input("Enter vertical value (0-100%)", 0, 100)
    if vertical < 0:
        return
    
    # Umrechnung von Prozent in 0-255
    value = int(vertical * 255 / 100)
    
    print("\nSetting vertical value...")
    add_network_event("command", unit.name, "Set Vertical", f"{vertical}%")
    await casa.setVertical(unit, value)
    print(f"{Colors.GREEN}Vertical value set to {vertical}%{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_white(unit: Unit):
    """Weißpegel eines Geräts einstellen."""
    print_header(f"Set White Level: {unit.name}")
    
    white = get_float_input("Enter white level (0-100%)", 0, 100)
    if white < 0:
        return
    
    # Umrechnung von Prozent in 0-255
    value = int(white * 255 / 100)
    
    print("\nSetting white level...")
    add_network_event("command", unit.name, "Set White", f"{white}%")
    await casa.setWhite(unit, value)
    print(f"{Colors.GREEN}White level set to {white}%{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_slider(unit: Unit):
    """Slider-Wert eines Geräts einstellen."""
    print_header(f"Set Slider: {unit.name}")
    
    slider = get_float_input("Enter slider value (0-100%)", 0, 100)
    if slider < 0:
        return
    
    # Umrechnung von Prozent in 0-255
    value = int(slider * 255 / 100)
    
    print("\nSetting slider value...")
    add_network_event("command", unit.name, "Set Slider", f"{slider}%")
    await casa.setSlider(unit, value)
    print(f"{Colors.GREEN}Slider value set to {slider}%{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def control_group_menu():
    """Menü zur Steuerung von Gruppen."""
    if not casa or not casa.connected:
        print(f"{Colors.RED}Not connected to any network!{Colors.ENDC}")
        input("\nPress Enter to continue...")
        return
    
    while True:
        print_header("Control Groups")
        
        if not casa.groups:
            print("No groups found in the network.")
            print_back_option()
            choice = get_int_input("Choose an option", 0, 0)
            return
        
        print(f"{Colors.BOLD}Select a group to control:{Colors.ENDC}")
        for i, group in enumerate(casa.groups, 1):
            print_menu_option(i, f"{group.name}: {len(group.units)} units")
        
        print_menu_option(len(casa.groups) + 1, "Control all units")
        print_back_option()
        
        choice = get_int_input("Choose a group", 0, len(casa.groups) + 1)
        if choice == 0:
            return
        
        if choice <= len(casa.groups):
            group = casa.groups[choice-1]
            await control_specific_group(group)
        else:
            await control_all_units()

async def control_specific_group(group: Group):
    """Steuerungsmenü für eine spezifische Gruppe."""
    while True:
        print_header(f"Control Group: {group.name}")
        
        print(f"{Colors.BOLD}Units in Group:{Colors.ENDC}")
        for unit in group.units:
            state_str = f"{Colors.GREEN}ON{Colors.ENDC}" if unit.is_on else f"{Colors.RED}OFF{Colors.ENDC}"
            print(f"  • {unit.name}: {state_str}")
        
        print(f"\n{Colors.BOLD}Available Controls:{Colors.ENDC}")
        
        options = [
            ("Turn ON", lambda: turn_on_group(group)),
            ("Turn OFF", lambda: turn_off_group(group)),
            ("Set brightness", lambda: set_group_brightness(group)),
            ("Set RGB color", lambda: set_group_rgb(group)),
            ("Set temperature", lambda: set_group_temperature(group)),
            ("Set vertical", lambda: set_group_vertical(group))
        ]
        
        for i, (option_text, _) in enumerate(options, 1):
            print_menu_option(i, option_text)
        
        print_back_option()
        
        choice = get_int_input("Choose an action", 0, len(options))
        if choice == 0:
            return
        
        # Ausgewählte Aktion ausführen
        action_func = options[choice-1][1]
        await action_func()

async def turn_on_group(group: Group):
    """Schaltet eine Gruppe ein."""
    print(f"\nTurning ON group {group.name}...")
    add_network_event("command", f"Group: {group.name}", "Turn ON", None)
    await casa.turnOn(group)
    print(f"{Colors.GREEN}Group turned ON{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def turn_off_group(group: Group):
    """Schaltet eine Gruppe aus."""
    print(f"\nTurning OFF group {group.name}...")
    add_network_event("command", f"Group: {group.name}", "Turn OFF", None)
    await casa.setLevel(group, 0)
    print(f"{Colors.GREEN}Group turned OFF{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def control_all_units():
    """Steuerung aller Geräte im Netzwerk."""
    while True:
        print_header("Control All Units")
        
        print(f"{Colors.BOLD}Network-wide Controls:{Colors.ENDC}")
        
        options = [
            ("Turn ON all units", lambda: turn_on_all()),
            ("Turn OFF all units", lambda: turn_off_all()),
            ("Set brightness for all", lambda: set_all_brightness()),
            ("Set RGB color for all", lambda: set_all_rgb()),
            ("Set temperature for all", lambda: set_all_temperature()),
            ("Set vertical for all", lambda: set_all_vertical())
        ]
        
        for i, (option_text, _) in enumerate(options, 1):
            print_menu_option(i, option_text)
        
        print_back_option()
        
        choice = get_int_input("Choose an action", 0, len(options))
        if choice == 0:
            return
        
        # Ausgewählte Aktion ausführen
        action_func = options[choice-1][1]
        await action_func()

async def turn_on_all():
    """Schaltet alle Geräte ein."""
    print("\nTurning ON all units...")
    add_network_event("command", "All Units", "Turn ON", None)
    await casa.turnOn(None)
    print(f"{Colors.GREEN}All units turned ON{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def turn_off_all():
    """Schaltet alle Geräte aus."""
    print("\nTurning OFF all units...")
    add_network_event("command", "All Units", "Turn OFF", None)
    await casa.setLevel(None, 0)
    print(f"{Colors.GREEN}All units turned OFF{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_group_brightness(group: Group):
    """Helligkeit einer Gruppe einstellen."""
    print_header(f"Set Group Brightness: {group.name}")
    
    brightness = get_float_input("Enter brightness (0-100%)", 0, 100)
    if brightness < 0:
        return
    
    # Umrechnung von Prozent in 0-255
    level = int(brightness * 255 / 100)
    
    print("\nSetting brightness...")
    add_network_event("command", f"Group: {group.name}", "Set Brightness", f"{brightness}%")
    await casa.setLevel(group, level)
    print(f"{Colors.GREEN}Brightness set to {brightness}% for all units in group{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_group_rgb(group: Group):
    """RGB-Farbe einer Gruppe einstellen."""
    print_header(f"Set Group RGB Color: {group.name}")
    
    r = get_int_input("Red (0-255)", 0, 255)
    if r < 0: return
    
    g = get_int_input("Green (0-255)", 0, 255)
    if g < 0: return
    
    b = get_int_input("Blue (0-255)", 0, 255)
    if b < 0: return
    
    print("\nSetting color...")
    add_network_event("command", f"Group: {group.name}", "Set RGB Color", f"RGB({r}, {g}, {b})")
    await casa.setColor(group, (r, g, b))
    print(f"{Colors.GREEN}Color set to RGB({r}, {g}, {b}) for all units in group{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_group_temperature(group: Group):
    """Farbtemperatur einer Gruppe einstellen."""
    print_header(f"Set Group Temperature: {group.name}")
    
    temp = get_int_input("Enter temperature in Kelvin (e.g., 2700-6500)", 2000, 10000)
    if temp < 0:
        return
    
    print("\nSetting temperature...")
    add_network_event("command", f"Group: {group.name}", "Set Temperature", f"{temp}K")
    await casa.setTemperature(group, temp)
    print(f"{Colors.GREEN}Temperature set to {temp}K for all units in group{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_group_vertical(group: Group):
    """Vertikalen Wert einer Gruppe einstellen."""
    print_header(f"Set Group Vertical: {group.name}")
    
    vertical = get_float_input("Enter vertical value (0-100%)", 0, 100)
    if vertical < 0:
        return
    
    # Umrechnung von Prozent in 0-255
    value = int(vertical * 255 / 100)
    
    print("\nSetting vertical value...")
    add_network_event("command", f"Group: {group.name}", "Set Vertical", f"{vertical}%")
    await casa.setVertical(group, value)
    print(f"{Colors.GREEN}Vertical value set to {vertical}% for all units in group{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_all_brightness():
    """Helligkeit aller Geräte einstellen."""
    print_header("Set Brightness for All Units")
    
    brightness = get_float_input("Enter brightness (0-100%)", 0, 100)
    if brightness < 0:
        return
    
    # Umrechnung von Prozent in 0-255
    level = int(brightness * 255 / 100)
    
    print("\nSetting brightness...")
    add_network_event("command", "All Units", "Set Brightness", f"{brightness}%")
    await casa.setLevel(None, level)
    print(f"{Colors.GREEN}Brightness set to {brightness}% for all units{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_all_rgb():
    """RGB-Farbe aller Geräte einstellen."""
    print_header("Set RGB Color for All Units")
    
    r = get_int_input("Red (0-255)", 0, 255)
    if r < 0: return
    
    g = get_int_input("Green (0-255)", 0, 255)
    if g < 0: return
    
    b = get_int_input("Blue (0-255)", 0, 255)
    if b < 0: return
    
    print("\nSetting color...")
    add_network_event("command", "All Units", "Set RGB Color", f"RGB({r}, {g}, {b})")
    await casa.setColor(None, (r, g, b))
    print(f"{Colors.GREEN}Color set to RGB({r}, {g}, {b}) for all units{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_all_temperature():
    """Farbtemperatur aller Geräte einstellen."""
    print_header("Set Temperature for All Units")
    
    temp = get_int_input("Enter temperature in Kelvin (e.g., 2700-6500)", 2000, 10000)
    if temp < 0:
        return
    
    print("\nSetting temperature...")
    add_network_event("command", "All Units", "Set Temperature", f"{temp}K")
    await casa.setTemperature(None, temp)
    print(f"{Colors.GREEN}Temperature set to {temp}K for all units{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def set_all_vertical():
    """Vertikalen Wert aller Geräte einstellen."""
    print_header("Set Vertical for All Units")
    
    vertical = get_float_input("Enter vertical value (0-100%)", 0, 100)
    if vertical < 0:
        return
    
    # Umrechnung von Prozent in 0-255
    value = int(vertical * 255 / 100)
    
    print("\nSetting vertical value...")
    add_network_event("command", "All Units", "Set Vertical", f"{vertical}%")
    await casa.setVertical(None, value)
    print(f"{Colors.GREEN}Vertical value set to {vertical}% for all units{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def scene_control_menu():
    """Menü zur Steuerung von Szenen."""
    if not casa or not casa.connected:
        print(f"{Colors.RED}Not connected to any network!{Colors.ENDC}")
        input("\nPress Enter to continue...")
        return
    
    print_header("Activate Scene")
    
    if not casa.scenes:
        print("No scenes found in the network.")
        input("\nPress Enter to continue...")
        return
    
    print(f"{Colors.BOLD}Select a scene to activate:{Colors.ENDC}")
    for i, scene in enumerate(casa.scenes, 1):
        print_menu_option(i, scene.name)
    
    print_back_option()
    
    choice = get_int_input("Choose a scene", 0, len(casa.scenes))
    if choice == 0:
        return
    
    scene = casa.scenes[choice-1]
    
    # Optionale Helligkeitsanpassung
    level_option = get_user_input("Adjust brightness? (y/n)", ["y", "n"])
    level = 255
    if level_option.lower() == "y":
        brightness = get_float_input("Enter brightness (0-100%)", 0, 100)
        if brightness < 0:
            return
        level = int(brightness * 255 / 100)
    
    print("\nActivating scene...")
    brightness_str = f" at {round(level / 255 * 100)}%" if level_option.lower() == "y" else ""
    add_network_event("command", f"Scene: {scene.name}", "Activate", brightness_str)
    await casa.switchToScene(scene, level)
    print(f"{Colors.GREEN}Scene '{scene.name}' activated{Colors.ENDC}")
    
    input("\nPress Enter to continue...")

async def network_monitor():
    """Netzwerkmonitor-Ansicht zur Überwachung der Aktivitäten."""
    print_header("Network Monitor")
    
    if not casa or not casa.connected:
        print(f"{Colors.RED}Not connected to any network!{Colors.ENDC}")
        input("\nPress Enter to continue...")
        return
    
    # Modusauswahl
    print(f"{Colors.BOLD}Choose monitoring mode:{Colors.ENDC}")
    print_menu_option(1, "Live monitor (press Ctrl+C to exit)")
    print_menu_option(2, "View event history")
    print_back_option()
    
    choice = get_int_input("Choose an option", 0, 2)
    if choice == 0:
        return
    elif choice == 1:
        await live_monitor()
    elif choice == 2:
        await view_event_history()

async def live_monitor():
    """Zeigt einen Live-Monitor der Netzwerkaktivitäten an."""
    try:
        update_counter = 0
        print("\nLive network monitoring. Press Ctrl+C to exit.\n")
        print(f"{Colors.BLUE}{'Timestamp':<20} {'Type':<14} {'Target':<20} {'Action':<15} {'Details'}{Colors.ENDC}")
        print("-" * 80)
        
        last_events_count = len(network_events)
        
        while True:
            current_events_count = len(network_events)
            
            # Zeige nur neue Ereignisse an
            if current_events_count > last_events_count:
                for i in range(last_events_count, current_events_count):
                    event = network_events[i]
                    timestamp = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
                    
                    type_color = Colors.CYAN
                    if event.event_type == "command":
                        type_color = Colors.YELLOW
                    elif event.event_type == "status_update":
                        type_color = Colors.GREEN
                    elif event.event_type == "connection":
                        type_color = Colors.GREEN
                    elif event.event_type == "disconnection":
                        type_color = Colors.RED
                    
                    print(f"{timestamp:<20} {type_color}{event.event_type:<14}{Colors.ENDC} {event.target:<20} {event.action:<15} {event.details or ''}")
                
                last_events_count = current_events_count
            
            # Periodisch den Status aktualisieren
            update_counter += 1
            if update_counter >= 20:  # Alle 2 Sekunden
                update_counter = 0
                if not casa or not casa.connected:
                    print(f"\n{Colors.RED}Connection lost!{Colors.ENDC}")
                    break
            
            await asyncio.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    
    input("\nPress Enter to continue...")

async def view_event_history():
    """Zeigt die Historie der Netzwerkaktivitäten an."""
    print_header("Event History")
    
    if not network_events:
        print("No events recorded yet.")
        input("\nPress Enter to continue...")
        return
    
    print(f"{Colors.BLUE}{'Timestamp':<20} {'Type':<14} {'Target':<20} {'Action':<15} {'Details'}{Colors.ENDC}")
    print("-" * 80)
    
    for event in network_events:
        timestamp = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
        
        type_color = Colors.CYAN
        if event.event_type == "command":
            type_color = Colors.YELLOW
        elif event.event_type == "status_update":
            type_color = Colors.GREEN
        elif event.event_type == "connection":
            type_color = Colors.GREEN
        elif event.event_type == "disconnection":
            type_color = Colors.RED
        
        print(f"{timestamp:<20} {type_color}{event.event_type:<14}{Colors.ENDC} {event.target:<20} {event.action:<15} {event.details or ''}")
    
    input("\nPress Enter to continue...")

async def save_event_log():
    """Speichert das Ereignisprotokoll in eine Datei."""
    print_header("Save Event Log")
    
    if not network_events:
        print("No events to save.")
        input("\nPress Enter to continue...")
        return
    
    filename = input("\nEnter filename (default: casambi_events.log): ").strip()
    if not filename:
        filename = "casambi_events.log"
    
    try:
        with open(filename, "w") as f:
            f.write(f"{'Timestamp':<20} {'Type':<14} {'Target':<20} {'Action':<15} {'Details'}\n")
            f.write("-" * 80 + "\n")
            
            for event in network_events:
                timestamp = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
                f.write(f"{timestamp:<20} {event.event_type:<14} {event.target:<20} {event.action:<15} {event.details or ''}\n")
        
        print(f"\n{Colors.GREEN}Event log saved to {filename}{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}Error saving log: {e}{Colors.ENDC}")
    
    input("\nPress Enter to continue...")

async def disconnect_network():
    """Verbindung zum Netzwerk trennen."""
    global casa
    
    if casa is None:
        print(f"{Colors.YELLOW}Not connected to any network.{Colors.ENDC}")
        input("\nPress Enter to continue...")
        return
    
    print_header("Disconnect from Network")
    print("Disconnecting...")
    
    add_network_event("disconnection", "Network", "Manual Disconnect", "User requested disconnect")
    await casa.disconnect()
    casa = None
    
    print(f"{Colors.GREEN}Disconnected from network.{Colors.ENDC}")
    input("\nPress Enter to continue...")

async def configure_logging():
    """Loglevel konfigurieren."""
    print_header("Configure Logging")
    
    print(f"{Colors.BOLD}Select log level:{Colors.ENDC}")
    print_menu_option(1, "DEBUG (verbose)")
    print_menu_option(2, "INFO (normal)")
    print_menu_option(3, "WARNING (minimal)")
    print_menu_option(4, "ERROR (errors only)")
    print_back_option()
    
    choice = get_int_input("Choose a log level", 0, 4)
    
    if choice == 0:
        return
    elif choice == 1:
        logging.getLogger("CasambiBt").setLevel(logging.DEBUG)
        print("\nLog level set to DEBUG")
    elif choice == 2:
        logging.getLogger("CasambiBt").setLevel(logging.INFO)
        print("\nLog level set to INFO")
    elif choice == 3:
        logging.getLogger("CasambiBt").setLevel(logging.WARNING)
        print("\nLog level set to WARNING")
    elif choice == 4:
        logging.getLogger("CasambiBt").setLevel(logging.ERROR)
        print("\nLog level set to ERROR")
    
    input("\nPress Enter to continue...")

async def main_menu():
    """Hauptmenü der Anwendung."""
    while True:
        print_header("Casambi Bluetooth Control")
        
        print(f"{Colors.BOLD}Main Menu:{Colors.ENDC}")
        print_menu_option(1, "Connect to Network")
        print_menu_option(2, "Manage Saved Connections")
        
        if casa and casa.connected:
            print_menu_option(3, "Show Network Status")
            print_menu_option(4, "Control Units")
            print_menu_option(5, "Control Groups")
            print_menu_option(6, "Activate Scene")
            print_menu_option(7, "Network Monitor")
            print_menu_option(8, "Save Event Log")
            print_menu_option(9, "Disconnect")
        
        print_menu_option(10, "Configure Logging")
        print_menu_option(11, "Exit")
        
        max_option = 11
        choice = get_int_input("Choose an option", 1, max_option)
        
        if choice == 1:
            await connect_to_network()
        elif choice == 2:
            await manage_saved_connections()
        elif choice == 3 and casa and casa.connected:
            await show_network_status()
        elif choice == 4 and casa and casa.connected:
            await control_unit_menu()
        elif choice == 5 and casa and casa.connected:
            await control_group_menu()
        elif choice == 6 and casa and casa.connected:
            await scene_control_menu()
        elif choice == 7 and casa and casa.connected:
            await network_monitor()
        elif choice == 8 and casa and casa.connected:
            await save_event_log()
        elif choice == 9 and casa and casa.connected:
            await disconnect_network()
        elif choice == 10:
            await configure_logging()
        elif choice == 11:
            if casa:
                await casa.disconnect()
            print("\nExiting...\n")
            return

async def main():
    """Hauptfunktion."""
    try:
        # Standard-Loglevel setzen
        logging.getLogger("CasambiBt").setLevel(logging.INFO)
        
        await main_menu()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        if casa:
            await casa.disconnect()
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.ENDC}")
        if casa:
            await casa.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)