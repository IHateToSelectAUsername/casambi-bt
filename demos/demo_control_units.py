import asyncio
import logging
import sys
import time

from CasambiBt import Casambi, discover

# Einfaches Logging-Setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('casambi_control_units.log')
    ]
)

_LOGGER = logging.getLogger(__name__)


async def print_unit_status(unit):
    """Hilfsfunktion zur Anzeige des Gerätestatus."""
    print(f"Status von '{unit.name}':")
    print(f"  Eingeschaltet: {'Ja' if unit.is_on else 'Nein'}")
    print(f"  Online: {'Ja' if unit.online else 'Nein'}")
    
    if unit.state:
        # Zeige Helligkeitswert, falls verfügbar
        if hasattr(unit.state, 'level'):
            print(f"  Helligkeit: {unit.state.level} ({round(unit.state.level/255*100)}%)")
        
        # Zeige Farbtemperatur, falls verfügbar
        if hasattr(unit.state, 'temperature'):
            print(f"  Farbtemperatur: {unit.state.temperature}K")
        
        # Zeige RGB-Farbe, falls verfügbar
        if hasattr(unit.state, 'rgb'):
            rgb = unit.state.rgb
            print(f"  RGB-Farbe: R:{rgb[0]}, G:{rgb[1]}, B:{rgb[2]}")
    
    else:
        print("  Kein Statusobjekt verfügbar")


async def main() -> None:
    """Hauptfunktion zur Demonstration der Steuerung einzelner Geräte."""
    _LOGGER.info("===== DEMO: CASAMBI GERÄTESTEUERUNG =====")
    
    # Setze den Logger der CasambiBt-Bibliothek auf DEBUG-Level für detaillierte Ausgaben
    logging.getLogger("CasambiBt").setLevel(logging.DEBUG)
    
    casa = None
    
    try:
        # --- SCHRITT 1: Bluetooth-Gerätesuche starten ---
        _LOGGER.info("Starte Suche nach Casambi-Netzwerken in Bluetooth-Reichweite...")
        print("Suche läuft...")
        
        devices = await discover()
        
        if not devices:
            print("\nKeine Casambi-Netzwerke gefunden!")
            return
            
        print("\nGefundene Casambi-Netzwerke:")
        print("-----------------------------")
        for i, device in enumerate(devices):
            device_info = f"[{i}] Adresse: {device.address}"
            if hasattr(device, 'name') and device.name:
                device_info += f", Name: {device.name}"
            print(device_info)
        
        # --- SCHRITT 2: Netzwerk auswählen und verbinden ---
        print("\nBitte wählen Sie ein Netzwerk aus der Liste:")
        selection = int(input("Nummer eingeben: "))
        
        if selection < 0 or selection >= len(devices):
            print(f"Ungültige Auswahl: {selection}")
            return
            
        device = devices[selection]
        _LOGGER.info(f"Netzwerk [{selection}] mit Adresse {device.address} ausgewählt")
        
        print("\nBitte geben Sie das Passwort für das Casambi-Netzwerk ein:")
        password = input("Passwort: ")
        
        # --- SCHRITT 3: Verbindung zum Netzwerk herstellen ---
        print("\nVerbindung wird hergestellt...")
        casa = Casambi()
        await casa.connect(device, password)
        print(f"\nVerbindung erfolgreich hergestellt zu Netzwerk: {casa.networkName}")
        
        # --- SCHRITT 4: Geräteauswahl ---
        if not casa.units:
            print("\nKeine Geräte im Netzwerk gefunden!")
            return
            
        print("\nVerfügbare Geräte:")
        print("-----------------")
        for i, unit in enumerate(casa.units):
            print(f"[{i}] {unit.name} (ID: {unit.deviceId}), "
                 f"Status: {'Ein' if unit.is_on else 'Aus'}, "
                 f"Online: {'Ja' if unit.online else 'Nein'}")
        
        print("\nBitte wählen Sie ein Gerät zum Steuern:")
        unit_selection = int(input("Nummer eingeben: "))
        
        if unit_selection < 0 or unit_selection >= len(casa.units):
            print(f"Ungültige Auswahl: {unit_selection}")
            return
            
        selected_unit = casa.units[unit_selection]
        print(f"\nGerät '{selected_unit.name}' ausgewählt")
        
        # Zeige aktuelle Steuerelemente für das ausgewählte Gerät
        print("\nVerfügbare Steuerelemente für dieses Gerät:")
        for control in selected_unit.unitType.controls:
            print(f"- {control.type.name}")
        
        # --- SCHRITT 5: Gerätesteuerung ---
        while True:
            print("\nSteuerungsoptionen:")
            print("------------------")
            print("[1] Einschalten")
            print("[2] Ausschalten (Helligkeit 0)")
            print("[3] Helligkeit einstellen")
            print("[4] Farbtemperatur einstellen (falls unterstützt)")
            print("[5] RGB-Farbe einstellen (falls unterstützt)")
            print("[6] Aktuellen Status anzeigen")
            print("[0] Beenden")
            
            choice = input("\nBitte wählen Sie eine Option: ")
            
            if choice == "0":
                break
                
            elif choice == "1":
                print(f"\nSchalte '{selected_unit.name}' ein...")
                await casa.turnOn(selected_unit)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print("Gerät sollte jetzt eingeschaltet sein.")
                await print_unit_status(selected_unit)
                
            elif choice == "2":
                print(f"\nSchalte '{selected_unit.name}' aus (Helligkeit 0)...")
                await casa.setLevel(selected_unit, 0)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print("Gerät sollte jetzt ausgeschaltet sein.")
                await print_unit_status(selected_unit)
                
            elif choice == "3":
                level_pct = int(input("\nBitte geben Sie die Helligkeit in Prozent ein (0-100): "))
                level = min(255, max(0, int(level_pct * 255 / 100)))  # Umrechnung in 0-255 Bereich
                print(f"\nSetze Helligkeit von '{selected_unit.name}' auf {level_pct}% ({level})...")
                await casa.setLevel(selected_unit, level)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"Helligkeit sollte jetzt auf {level_pct}% gesetzt sein.")
                await print_unit_status(selected_unit)
                
            elif choice == "4":
                # Prüfe, ob das Gerät Farbtemperatur unterstützt
                has_temp_control = any(
                    control.type.name == "Temperature" 
                    for control in selected_unit.unitType.controls
                )
                
                if not has_temp_control:
                    print(f"\nDas Gerät '{selected_unit.name}' unterstützt keine Farbtemperatursteuerung!")
                    continue
                    
                temp = int(input("\nBitte geben Sie die Farbtemperatur in Kelvin ein (z.B. 2700-6500): "))
                print(f"\nSetze Farbtemperatur von '{selected_unit.name}' auf {temp}K...")
                await casa.setTemperature(selected_unit, temp)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"Farbtemperatur sollte jetzt auf {temp}K gesetzt sein.")
                await print_unit_status(selected_unit)
                
            elif choice == "5":
                # Prüfe, ob das Gerät RGB-Farbe unterstützt
                has_rgb_control = any(
                    control.type.name in ["RGB", "XY"] 
                    for control in selected_unit.unitType.controls
                )
                
                if not has_rgb_control:
                    print(f"\nDas Gerät '{selected_unit.name}' unterstützt keine RGB-Farbsteuerung!")
                    continue
                    
                print("\nBitte geben Sie die RGB-Werte ein (0-255):")
                r = int(input("Rot: "))
                g = int(input("Grün: "))
                b = int(input("Blau: "))
                
                # Stelle sicher, dass die Werte im gültigen Bereich sind
                r = min(255, max(0, r))
                g = min(255, max(0, g))
                b = min(255, max(0, b))
                
                print(f"\nSetze RGB-Farbe von '{selected_unit.name}' auf R:{r}, G:{g}, B:{b}...")
                await casa.setColor(selected_unit, (r, g, b))
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"RGB-Farbe sollte jetzt auf R:{r}, G:{g}, B:{b} gesetzt sein.")
                await print_unit_status(selected_unit)
                
            elif choice == "6":
                print("\nAktueller Status:")
                await print_unit_status(selected_unit)
                
            else:
                print("\nUngültige Eingabe! Bitte erneut versuchen.")
    
    except Exception as e:
        _LOGGER.exception(f"Fehler während der Demo: {str(e)}")
        print(f"\nFehler aufgetreten: {type(e).__name__}: {str(e)}")
    
    finally:
        # --- SCHRITT 6: Verbindung trennen ---
        if casa and casa.connected:
            print("\nVerbindung wird getrennt...")
            await casa.disconnect()
            print("Verbindung erfolgreich getrennt.")
        
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