import asyncio
import logging
import sys
import time
from datetime import datetime

from CasambiBt import Casambi, discover, Unit

# Einfaches Logging-Setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('casambi_callbacks.log')
    ]
)

_LOGGER = logging.getLogger(__name__)


# --- Callback-Funktionen ---

def unit_changed_callback(unit: Unit) -> None:
    """Callback-Funktion, die aufgerufen wird, wenn sich der Status eines Geräts ändert."""
    # Aktuellen Zeitstempel für die Ausgabe hinzufügen
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    # Formatierte Statusanzeige
    status_line = f"[{timestamp}] Statusänderung: '{unit.name}' (ID: {unit.deviceId})"
    status_line += f", Ein: {'Ja' if unit.is_on else 'Nein'}"
    status_line += f", Online: {'Ja' if unit.online else 'Nein'}"
    
    # Zusätzliche Statusinformationen anzeigen, wenn verfügbar
    if unit.state:
        if hasattr(unit.state, 'level'):
            level_pct = round(unit.state.level/255*100)
            status_line += f", Helligkeit: {unit.state.level} ({level_pct}%)"
        
        if hasattr(unit.state, 'temperature'):
            status_line += f", Temperatur: {unit.state.temperature}K"
        
        if hasattr(unit.state, 'rgb'):
            rgb = unit.state.rgb
            status_line += f", RGB: ({rgb[0]},{rgb[1]},{rgb[2]})"
    
    print(status_line)
    _LOGGER.info(status_line)


def disconnect_callback() -> None:
    """Callback-Funktion, die aufgerufen wird, wenn die Bluetooth-Verbindung getrennt wird."""
    # Aktuellen Zeitstempel für die Ausgabe hinzufügen
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    message = f"[{timestamp}] TRENNUNG: Bluetooth-Verbindung wurde getrennt!"
    print(f"\n{message}")
    _LOGGER.warning(message)
    
    print("Bitte beachten Sie: Nach einer Verbindungstrennung werden automatisch alle Geräte als offline markiert.")


async def main() -> None:
    """Hauptfunktion zur Demonstration der Ereignisbehandlung (Callbacks)."""
    _LOGGER.info("===== DEMO: CASAMBI EREIGNISBEHANDLUNG (CALLBACKS) =====")
    
    # Setze den Logger der CasambiBt-Bibliothek auf DEBUG-Level für detaillierte Ausgaben
    logging.getLogger("CasambiBt").setLevel(logging.DEBUG)
    
    casa = None
    
    try:
        # --- SCHRITT 1: Bluetooth-Gerätesuche und Verbindung ---
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
        
        print("\nBitte wählen Sie ein Netzwerk aus der Liste:")
        selection = int(input("Nummer eingeben: "))
        
        if selection < 0 or selection >= len(devices):
            print(f"Ungültige Auswahl: {selection}")
            return
            
        device = devices[selection]
        
        print("\nBitte geben Sie das Passwort für das Casambi-Netzwerk ein:")
        password = input("Passwort: ")
        
        print("\nVerbindung wird hergestellt...")
        casa = Casambi()
        await casa.connect(device, password)
        print(f"\nVerbindung erfolgreich hergestellt zu Netzwerk: {casa.networkName}")
        
        if not casa.units:
            print("\nKeine Geräte im Netzwerk gefunden!")
            return
        
        # --- SCHRITT 2: Callbacks registrieren ---
        print("\nRegistriere Callbacks für Statusänderungen und Verbindungstrennung...")
        
        # Registriere Callback für Statusänderungen
        casa.registerUnitChangedHandler(unit_changed_callback)
        
        # Registriere Callback für Verbindungstrennung
        casa.registerDisconnectCallback(disconnect_callback)
        
        print("Callbacks erfolgreich registriert.")
        print("\nDie Anwendung wird nun auf Statusänderungen reagieren:")
        print("1. Wenn Sie Geräte über die Casambi-App oder andere Schnittstellen steuern")
        print("2. Wenn Sie Geräte über diese Demo steuern")
        print("3. Wenn die Bluetooth-Verbindung getrennt wird")
        
        # --- SCHRITT 3: Interaktives Menü zur Gerätesteuerung ---
        print("\nVerfügbare Geräte:")
        print("-----------------")
        for i, unit in enumerate(casa.units):
            print(f"[{i}] {unit.name} (ID: {unit.deviceId})")
        
        print("\nBeobachtungs- und Steuerungsmodus:")
        print("-------------------------------")
        print("Die Anwendung zeigt automatisch alle Statusänderungen von Geräten an.")
        print("Sie können auch Geräte steuern, um Statusänderungen auszulösen.")
        
        while True:
            print("\nWas möchten Sie tun?")
            print("[1] Ein Gerät auswählen und steuern")
            print("[2] Alle Geräte einschalten")
            print("[3] Alle Geräte ausschalten")
            print("[4] Verbindungstrennung simulieren")
            print("[0] Beenden")
            
            choice = input("\nBitte wählen Sie eine Option: ")
            
            if choice == "0":
                break
            
            elif choice == "1":
                # Geräteauswahl und -steuerung
                device_idx = int(input("\nWählen Sie ein Gerät (Nummer): "))
                
                if device_idx < 0 or device_idx >= len(casa.units):
                    print(f"Ungültige Auswahl: {device_idx}")
                    continue
                
                selected_unit = casa.units[device_idx]
                print(f"\nGerät '{selected_unit.name}' ausgewählt")
                
                # Steuerungsoptionen für das ausgewählte Gerät
                print("\nWas möchten Sie mit diesem Gerät tun?")
                print("[1] Einschalten")
                print("[2] Ausschalten")
                print("[3] Helligkeit ändern")
                
                action = input("Aktion auswählen: ")
                
                if action == "1":
                    print(f"\nSchalte '{selected_unit.name}' ein...")
                    await casa.turnOn(selected_unit)
                    print("Befehl gesendet. Beobachten Sie die Callback-Ausgaben...")
                
                elif action == "2":
                    print(f"\nSchalte '{selected_unit.name}' aus...")
                    await casa.setLevel(selected_unit, 0)
                    print("Befehl gesendet. Beobachten Sie die Callback-Ausgaben...")
                
                elif action == "3":
                    level_pct = int(input("\nHelligkeit in Prozent (0-100): "))
                    level = min(255, max(0, int(level_pct * 255 / 100)))
                    print(f"\nSetze Helligkeit von '{selected_unit.name}' auf {level_pct}%...")
                    await casa.setLevel(selected_unit, level)
                    print("Befehl gesendet. Beobachten Sie die Callback-Ausgaben...")
                
                else:
                    print("Ungültige Eingabe!")
            
            elif choice == "2":
                print("\nSchalte alle Geräte ein...")
                await casa.turnOn(None)  # None bedeutet: alle Geräte
                print("Befehl gesendet. Beobachten Sie die Callback-Ausgaben...")
            
            elif choice == "3":
                print("\nSchalte alle Geräte aus...")
                await casa.setLevel(None, 0)  # None bedeutet: alle Geräte
                print("Befehl gesendet. Beobachten Sie die Callback-Ausgaben...")
            
            elif choice == "4":
                print("\nSimuliere Verbindungstrennung (trennt wirklich die Verbindung)...")
                # Manuelles Auslösen der Verbindungstrennung durch tatsächliches Trennen
                await casa.disconnect()
                print("Verbindung getrennt. Das Disconnect-Callback sollte ausgelöst worden sein.")
                
                # Da die Verbindung getrennt wurde, müssen wir das Programm beenden
                print("\nDie Verbindung wurde getrennt. Das Programm wird beendet.")
                return
            
            else:
                print("\nUngültige Eingabe! Bitte erneut versuchen.")
            
            # Kleine Pause, um die Callback-Ausgaben zu sehen
            await asyncio.sleep(1)
    
    except Exception as e:
        _LOGGER.exception(f"Fehler während der Demo: {str(e)}")
        print(f"\nFehler aufgetreten: {type(e).__name__}: {str(e)}")
    
    finally:
        # --- SCHRITT 4: Callbacks abmelden und Verbindung trennen ---
        if casa:
            print("\nMelde Callbacks ab und trenne Verbindung...")
            
            # Callbacks abmelden, falls sie registriert wurden
            try:
                casa.unregisterUnitChangedHandler(unit_changed_callback)
                casa.unregisterDisconnectCallback(disconnect_callback)
                print("Callbacks abgemeldet.")
            except Exception as e:
                _LOGGER.error(f"Fehler beim Abmelden der Callbacks: {str(e)}")
            
            # Verbindung trennen, falls verbunden
            if casa.connected:
                await casa.disconnect()
                print("Verbindung getrennt.")
        
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