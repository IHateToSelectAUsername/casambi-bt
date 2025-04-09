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
        logging.FileHandler('casambi_scenes.log')
    ]
)

_LOGGER = logging.getLogger(__name__)


async def print_scene_info(scene, units):
    """Hilfsfunktion zur Anzeige von Szenen-Informationen."""
    print(f"Szene: '{scene.name}' (ID: {scene.sceneId})")
    print("\nGeräte, die von dieser Szene gesteuert werden könnten:")
    
    # Da die API nicht direkt anzeigt, welche Geräte in einer Szene enthalten sind,
    # zeigen wir einfach alle Geräte des Netzwerks an
    for unit in units:
        print(f"- {unit.name} (ID: {unit.deviceId})")


async def main() -> None:
    """Hauptfunktion zur Demonstration der Szenensteuerung."""
    _LOGGER.info("===== DEMO: CASAMBI SZENENSTEUERUNG =====")
    
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
        
        # --- SCHRITT 4: Szenenauswahl ---
        if not casa.scenes:
            print("\nKeine Szenen im Netzwerk gefunden!")
            print("Sie können Szenen in der Casambi-App erstellen und konfigurieren.")
            return
            
        print("\nVerfügbare Szenen:")
        print("-----------------")
        for i, scene in enumerate(casa.scenes):
            print(f"[{i}] {scene.name} (ID: {scene.sceneId})")
        
        print("\nBitte wählen Sie eine Szene zum Aktivieren:")
        scene_selection = int(input("Nummer eingeben: "))
        
        if scene_selection < 0 or scene_selection >= len(casa.scenes):
            print(f"Ungültige Auswahl: {scene_selection}")
            return
            
        selected_scene = casa.scenes[scene_selection]
        print(f"\nSzene '{selected_scene.name}' ausgewählt")
        await print_scene_info(selected_scene, casa.units)
        
        # --- SCHRITT 5: Szenensteuerung ---
        while True:
            print("\nSteuerungsoptionen:")
            print("------------------")
            print("[1] Szene aktivieren (Standard-Helligkeit)")
            print("[2] Szene aktivieren mit angepasster Helligkeit")
            print("[3] Andere Szene auswählen")
            print("[4] Alle Geräte ausschalten")
            print("[0] Beenden")
            
            choice = input("\nBitte wählen Sie eine Option: ")
            
            if choice == "0":
                break
                
            elif choice == "1":
                print(f"\nAktiviere Szene '{selected_scene.name}'...")
                # Standard-Helligkeit (255 = 100%)
                await casa.switchToScene(selected_scene)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print("Szene sollte jetzt aktiviert sein.")
                
                # Zeige den aktuellen Status der Geräte nach der Aktivierung
                print("\nAktueller Status der Geräte nach Aktivierung der Szene:")
                for unit in casa.units:
                    print(f"- {unit.name}: {'Eingeschaltet' if unit.is_on else 'Ausgeschaltet'}, "
                         f"{'Online' if unit.online else 'Offline'}")
                    if unit.state and hasattr(unit.state, 'level'):
                        print(f"  Helligkeit: {unit.state.level} ({round(unit.state.level/255*100)}%)")
                
            elif choice == "2":
                level_pct = int(input("\nBitte geben Sie die relative Helligkeit in Prozent ein (0-100): "))
                level = min(255, max(0, int(level_pct * 255 / 100)))  # Umrechnung in 0-255 Bereich
                
                print(f"\nAktiviere Szene '{selected_scene.name}' mit {level_pct}% Helligkeit...")
                await casa.switchToScene(selected_scene, level)
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print(f"Szene sollte jetzt mit {level_pct}% Helligkeit aktiviert sein.")
                
                # Zeige den aktuellen Status der Geräte nach der Aktivierung
                print("\nAktueller Status der Geräte nach Aktivierung der Szene:")
                for unit in casa.units:
                    print(f"- {unit.name}: {'Eingeschaltet' if unit.is_on else 'Ausgeschaltet'}, "
                         f"{'Online' if unit.online else 'Offline'}")
                    if unit.state and hasattr(unit.state, 'level'):
                        print(f"  Helligkeit: {unit.state.level} ({round(unit.state.level/255*100)}%)")
                
            elif choice == "3":
                print("\nVerfügbare Szenen:")
                print("-----------------")
                for i, scene in enumerate(casa.scenes):
                    print(f"[{i}] {scene.name} (ID: {scene.sceneId})")
                
                scene_selection = int(input("\nBitte wählen Sie eine Szene: "))
                
                if scene_selection < 0 or scene_selection >= len(casa.scenes):
                    print(f"Ungültige Auswahl: {scene_selection}")
                    continue
                    
                selected_scene = casa.scenes[scene_selection]
                print(f"\nSzene '{selected_scene.name}' ausgewählt")
                await print_scene_info(selected_scene, casa.units)
                
            elif choice == "4":
                print("\nSchalte alle Geräte aus...")
                await casa.setLevel(None, 0)  # None = alle Geräte, Helligkeit 0 = aus
                await asyncio.sleep(0.5)  # Kurze Pause, um Statusänderung zu verarbeiten
                print("Alle Geräte sollten jetzt ausgeschaltet sein.")
                
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