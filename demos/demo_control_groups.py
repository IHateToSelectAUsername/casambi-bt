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
        logging.FileHandler('casambi_control_groups.log')
    ]
)

_LOGGER = logging.getLogger(__name__)


async def print_group_status(group):
    """Hilfsfunktion zur Anzeige des Gruppenstatus."""
    print(f"Gruppe: '{group.name}' (ID: {group.groudId})")
    print(f"Anzahl Geräte in der Gruppe: {len(group.units)}")
    
    # Zeige Status jedes Geräts in der Gruppe
    print("\nGeräte in dieser Gruppe:")
    for i, unit in enumerate(group.units):
        print(f"  {i+1}. {unit.name}")
        print(f"     Status: {'Eingeschaltet' if unit.is_on else 'Ausgeschaltet'}")
        print(f"     Online: {'Ja' if unit.online else 'Nein'}")
        
        if unit.state and hasattr(unit.state, 'level'):
            print(f"     Helligkeit: {unit.state.level} ({round(unit.state.level/255*100)}%)")


async def main() -> None:
    """Hauptfunktion zur Demonstration der Steuerung von Gerätegruppen."""
    _LOGGER.info("===== DEMO: CASAMBI GRUPPENSTEUERUNG =====")
    
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
        
        # --- SCHRITT 4: Gruppenauswahl ---
        if not casa.groups:
            print("\nKeine Gruppen im Netzwerk gefunden!")
            print("Sie können jedoch trotzdem alle Geräte gleichzeitig steuern.")
            
            while True:
                print("\nSteuerungsoptionen für ALLE Geräte:")
                print("----------------------------------")
                print("[1] Alle Geräte einschalten")
                print("[2] Alle Geräte ausschalten")
                print("[3] Helligkeit für alle Geräte einstellen")
                print("[4] Status aller Geräte anzeigen")
                print("[0] Beenden")
                
                choice = input("\nBitte wählen Sie eine Option: ")
                
                if choice == "0":
                    break
                    
                elif choice == "1":
                    print("\nSchalte alle Geräte ein...")
                    await casa.turnOn(None)  # None bedeutet: alle Geräte
                    await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                    print("Alle Geräte sollten jetzt eingeschaltet sein.")
                
                elif choice == "2":
                    print("\nSchalte alle Geräte aus (Helligkeit 0)...")
                    await casa.setLevel(None, 0)  # None bedeutet: alle Geräte
                    await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                    print("Alle Geräte sollten jetzt ausgeschaltet sein.")
                
                elif choice == "3":
                    level_pct = int(input("\nBitte geben Sie die Helligkeit in Prozent ein (0-100): "))
                    level = min(255, max(0, int(level_pct * 255 / 100)))  # Umrechnung in 0-255 Bereich
                    print(f"\nSetze Helligkeit aller Geräte auf {level_pct}% ({level})...")
                    await casa.setLevel(None, level)  # None bedeutet: alle Geräte
                    await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                    print(f"Helligkeit aller Geräte sollte jetzt auf {level_pct}% gesetzt sein.")
                
                elif choice == "4":
                    print("\nStatus aller Geräte:")
                    for i, unit in enumerate(casa.units):
                        print(f"{i+1}. {unit.name}")
                        print(f"   Status: {'Eingeschaltet' if unit.is_on else 'Ausgeschaltet'}")
                        print(f"   Online: {'Ja' if unit.online else 'Nein'}")
                        if unit.state and hasattr(unit.state, 'level'):
                            print(f"   Helligkeit: {unit.state.level} ({round(unit.state.level/255*100)}%)")
                
                else:
                    print("\nUngültige Eingabe! Bitte erneut versuchen.")
                
            return
        
        # Es wurden Gruppen gefunden, zeige sie an
        print("\nVerfügbare Gruppen:")
        print("------------------")
        for i, group in enumerate(casa.groups):
            print(f"[{i}] {group.name} (ID: {group.groudId}), Enthält {len(group.units)} Geräte")
        
        # Option für die Steuerung aller Geräte hinzufügen
        print(f"[{len(casa.groups)}] ALLE GERÄTE")
        
        print("\nBitte wählen Sie eine Gruppe zum Steuern:")
        group_selection = int(input("Nummer eingeben: "))
        
        # Spezialfall: Alle Geräte steuern
        if group_selection == len(casa.groups):
            selected_group = None
            print("\nSie haben 'ALLE GERÄTE' zur Steuerung ausgewählt.")
        else:
            # Normale Gruppenauswahl
            if group_selection < 0 or group_selection >= len(casa.groups):
                print(f"Ungültige Auswahl: {group_selection}")
                return
                
            selected_group = casa.groups[group_selection]
            print(f"\nGruppe '{selected_group.name}' ausgewählt")
            await print_group_status(selected_group)
        
        # --- SCHRITT 5: Gruppensteuerung ---
        while True:
            group_label = selected_group.name if selected_group else "ALLE GERÄTE"
            
            print(f"\nSteuerungsoptionen für '{group_label}':")
            print("----------------------------------")
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
                print(f"\nSchalte '{group_label}' ein...")
                await casa.turnOn(selected_group)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"'{group_label}' sollte jetzt eingeschaltet sein.")
                
            elif choice == "2":
                print(f"\nSchalte '{group_label}' aus (Helligkeit 0)...")
                await casa.setLevel(selected_group, 0)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"'{group_label}' sollte jetzt ausgeschaltet sein.")
                
            elif choice == "3":
                level_pct = int(input("\nBitte geben Sie die Helligkeit in Prozent ein (0-100): "))
                level = min(255, max(0, int(level_pct * 255 / 100)))  # Umrechnung in 0-255 Bereich
                print(f"\nSetze Helligkeit von '{group_label}' auf {level_pct}% ({level})...")
                await casa.setLevel(selected_group, level)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"Helligkeit von '{group_label}' sollte jetzt auf {level_pct}% gesetzt sein.")
                
            elif choice == "4":
                temp = int(input("\nBitte geben Sie die Farbtemperatur in Kelvin ein (z.B. 2700-6500): "))
                print(f"\nSetze Farbtemperatur von '{group_label}' auf {temp}K...")
                await casa.setTemperature(selected_group, temp)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"Farbtemperatur von '{group_label}' sollte jetzt auf {temp}K gesetzt sein.")
                
            elif choice == "5":
                print("\nBitte geben Sie die RGB-Werte ein (0-255):")
                r = int(input("Rot: "))
                g = int(input("Grün: "))
                b = int(input("Blau: "))
                
                # Stelle sicher, dass die Werte im gültigen Bereich sind
                r = min(255, max(0, r))
                g = min(255, max(0, g))
                b = min(255, max(0, b))
                
                print(f"\nSetze RGB-Farbe von '{group_label}' auf R:{r}, G:{g}, B:{b}...")
                await casa.setColor(selected_group, (r, g, b))
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"RGB-Farbe von '{group_label}' sollte jetzt auf R:{r}, G:{g}, B:{b} gesetzt sein.")
                
            elif choice == "6":
                print("\nAktueller Status:")
                if selected_group:
                    await print_group_status(selected_group)
                else:
                    print("Status aller Geräte:")
                    for i, unit in enumerate(casa.units):
                        print(f"{i+1}. {unit.name}")
                        print(f"   Status: {'Eingeschaltet' if unit.is_on else 'Ausgeschaltet'}")
                        print(f"   Online: {'Ja' if unit.online else 'Nein'}")
                        if unit.state and hasattr(unit.state, 'level'):
                            print(f"   Helligkeit: {unit.state.level} ({round(unit.state.level/255*100)}%)")
                
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