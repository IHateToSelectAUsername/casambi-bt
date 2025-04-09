# Erklärung der unterschiedlichen Namensanzeige bei Bluetooth-Tests

Nach Analyse der verschiedenen Testskripte und Logs habe ich den Grund für die unterschiedliche Anzeige der Gerätenamen identifiziert.

## Technische Ursache

Die Unterschiede in der Namensanzeige sind auf folgende technische Faktoren zurückzuführen:

### 1. Unterschiedliche Methoden der Bluetooth-Datenerfassung

**In demo_discover.py (Original):**
```python
devices_and_advertisements = await BleakScanner.discover(return_adv=True)
```

**In demo_all_ble_devices.py und neueren Tests:**
```python
devices_detected: Dict[str, Tuple[BLEDevice, AdvertisementData]] = {}

def _detection_callback(device: BLEDevice, advertisement_data: AdvertisementData) -> None:
    devices_detected[device.address] = (device, advertisement_data)

scanner.register_detection_callback(_detection_callback)
```

Der entscheidende Unterschied liegt darin, wie Bluetooth-Werbedaten erfasst werden. Die erste Methode verwendet direkt `BleakScanner.discover()`, während die zweite Methode einen Callback registriert, der nur den letzten Datensatz für jede Geräteadresse speichert.

### 2. Bluetooth LE Advertising-Pakettypen

Bluetooth LE-Geräte senden zwei Haupttypen von Werbepaketen:

1. **Standard Advertising Data (AD):** Enthält grundlegende Informationen wie MAC-Adresse und Service-Daten
2. **Scan Response Data (SRD):** Enthält zusätzliche Informationen, oft den vollständigen Gerätenamen

Die unterschiedlichen Erfassungsmethoden behandeln diese Pakettypen unterschiedlich:

- **`BleakScanner.discover()`** sammelt beide Pakettypen und kombiniert die Informationen
- **Der Callback-Ansatz** in den neueren Tests könnte ein AD-Paket mit einem späteren SRD-Paket überschreiben oder umgekehrt, wobei nur der letzte gespeicherte Zustand in der Log-Datei erscheint

### 3. Ereignisbehandlung in der Windows Bluetooth-Implementierung

In der Windows-Implementierung von Bleak (verwendet von `bleak.backends.winrt.scanner`) wird jedes Werbepaket als separates Ereignis verarbeitet. Die Log-Einträge wie:

```
Received 05:A3:9D:10:4B:18: .
Received 05:A3:9D:10:4B:18: CBU-DCS DALI Gateway.
```

zeigen, dass für dasselbe Gerät zwei verschiedene Pakete empfangen wurden - eines ohne Namen und eines mit Namen.

## Verwendete Bibliotheken

Beide Testskripte verwenden die gleiche unterliegende Bibliothek (Bleak), jedoch mit unterschiedlichen Methoden:

1. **CasambiBt (original):** Nutzt die `discover()`-Methode, die Informationen aus beiden Pakettypen zusammenführt
2. **Neuere Tests:** Nutzen die ereignisbasierte Callback-Methode, die nur den letzten Zustand speichert

## Warum es nicht um virtuelle Geräte geht

Es ist wichtig zu verstehen, dass dieses Verhalten nicht direkt mit der Mesh-Netzwerk-Hypothese oder virtuellen Geräten zusammenhängt. Es ist vielmehr eine technische Eigenheit der Bluetooth LE-Kommunikation:

1. Jedes Gerät (physisch oder virtuell) kann beide Arten von Paketen senden
2. Der Unterschied liegt in der Art und Weise, wie die Testskripte diese Pakete erfassen und verarbeiten
3. Die Namensanzeige ist ein Attribut der Bluetooth-Kommunikation selbst, nicht spezifisch für Casambi-Geräte

## Lösung für konsistente Namenserfassung

Um in zukünftigen Tests konsistent Gerätenamen zu erfassen, könnte man:

1. Die `discover()`-Methode verwenden, die automatisch Informationen aus verschiedenen Pakettypen kombiniert
2. Oder den Callback-Ansatz so modifizieren, dass er Informationen aus verschiedenen Paketen zusammenführt, anstatt sie zu überschreiben

```python
# Ein Ansatz, um Informationen zu kombinieren:
if device.address in devices_detected:
    existing_device, existing_adv = devices_detected[device.address]
    # Namen aus dem neuen Paket übernehmen, wenn vorhanden
    if advertisement_data.local_name and not existing_adv.local_name:
        # Informationen zusammenführen anstatt zu überschreiben
        # (Hier wäre eine tiefere Integration erforderlich)
```

## Fazit

Die unterschiedliche Anzeige der Gerätenamen ist ein rein technisches Phänomen, das auf die verschiedenen Methoden der Bluetooth-Datenerfassung zurückzuführen ist. Es handelt sich nicht um unterschiedliche Gerätetypen oder Zustände, sondern um verschiedene Pakettypen, die vom selben Gerät gesendet werden.