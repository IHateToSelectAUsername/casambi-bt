# Eindeutige Merkmale zur Unterscheidung von Casambi-Gerätetypen

Basierend auf unseren umfangreichen Tests und Analysen können wir folgende eindeutige Merkmale zur zuverlässigen Unterscheidung der verschiedenen Casambi-Gerätetypen definieren:

## 1. Zurückgesetztes/nicht initialisiertes physisches Gerät

| Merkmal | Beschreibung | Beispielwert |
|---------|--------------|--------------|
| **Service UUID** | Keine Service UUID vorhanden | `[]` (leere Liste) |
| **Herstellerdaten-Länge** | Längere Herstellerdaten (ca. 23 Bytes) | `184b109da3052328f22c2800000000000000004b0000f0` |
| **Nullsequenz** | Enthält eine signifikante Sequenz von Nullbytes | `000000000000` |
| **Unit-Adresse** | Die ersten 6 Bytes der Herstellerdaten | `184b109da305` |
| **Gerätename** | Oft leer oder Nullen | Leer oder `000000000000` |

**Technisches Erkennungskriterium:**
```python
def ist_zurueckgesetztes_geraet(manufacturer_data, service_uuids):
    # Prüfen, ob es ein Casambi-Gerät ist
    if CASAMBI_MANUFACTURER_ID not in manufacturer_data:
        return False
    
    # Prüfen, ob keine Service UUID vorhanden ist
    if service_uuids:
        return False
    
    # Prüfen, ob die Herstellerdaten eine Nullsequenz enthalten
    daten = manufacturer_data[CASAMBI_MANUFACTURER_ID]
    return b'\x00\x00\x00\x00\x00\x00' in daten
```

## 2. Konfiguriertes physisches Gerät

| Merkmal | Beschreibung | Beispielwert |
|---------|--------------|--------------|
| **Service UUID** | Keine Service UUID vorhanden | `[]` (leere Liste) |
| **Herstellerdaten-Länge** | Längere Herstellerdaten (ca. 23 Bytes) | `184b109da3052328f22c280036b69daf62ae0a4b0000f0` |
| **Eingebettete MAC-Adresse** | Enthält die MAC-Adresse eines anderen Geräts | `36b69daf62ae` |
| **Unit-Adresse** | Die ersten 6 Bytes der Herstellerdaten | `184b109da305` |
| **Gerätename** | Oft leer oder Nullen | Leer oder `000000000000` |

**Technisches Erkennungskriterium:**
```python
def ist_konfiguriertes_physisches_geraet(manufacturer_data, service_uuids):
    # Prüfen, ob es ein Casambi-Gerät ist
    if CASAMBI_MANUFACTURER_ID not in manufacturer_data:
        return False
    
    # Prüfen, ob keine Service UUID vorhanden ist
    if service_uuids:
        return False
    
    # Prüfen, ob die Herstellerdaten keine Nullsequenz enthalten
    daten = manufacturer_data[CASAMBI_MANUFACTURER_ID]
    if b'\x00\x00\x00\x00\x00\x00' in daten:
        return False
    
    # Prüfen, ob die Herstellerdaten etwa 23 Bytes lang sind
    return len(daten) >= 20
```

## 3. Virtuelles Gerät

| Merkmal | Beschreibung | Beispielwert |
|---------|--------------|--------------|
| **Service UUID** | Casambi-spezifische Service UUID | `0000fe4d-0000-1000-8000-00805f9b34fb` |
| **Herstellerdaten-Länge** | Kürzere Herstellerdaten (ca. 7 Bytes) | `36b69daf62ae0b` |
| **MAC-Adresse in Daten** | Enthält seine eigene MAC-Adresse | `36b69daf62ae` |
| **Gerätename** | Enthält oft den korrekten Gerätenamen | `CBU-DCS DALI Gateway` |

**Technisches Erkennungskriterium:**
```python
def ist_virtuelles_geraet(manufacturer_data, service_uuids, device_address):
    # Prüfen, ob die Service UUID vorhanden ist
    if CASAMBI_UUID_CONFIGURED not in service_uuids:
        return False
    
    # Prüfen, ob es ein Casambi-Gerät ist
    if CASAMBI_MANUFACTURER_ID not in manufacturer_data:
        return False
    
    # Prüfen, ob die Herstellerdaten kurz sind (ca. 7-8 Bytes)
    daten = manufacturer_data[CASAMBI_MANUFACTURER_ID]
    if len(daten) > 10:
        return False
    
    # Prüfen, ob die eigene MAC-Adresse in den Daten enthalten ist
    mac_ohne_trennzeichen = device_address.replace(":", "").lower()
    return mac_ohne_trennzeichen in daten.hex().lower()
```

## Entscheidungsbaum zur Geräteerkennung

Für eine schnelle und eindeutige Erkennung kann folgender Entscheidungsbaum verwendet werden:

```
Hat das Gerät eine Casambi Service UUID?
├── JA → Ist ein virtuelles Gerät
└── NEIN → Enthält die Herstellerdaten mit ID 963?
    ├── NEIN → Kein Casambi-Gerät
    └── JA → Enthält eine Nullsequenz?
        ├── JA → Zurückgesetztes Gerät
        └── NEIN → Konfiguriertes physisches Gerät
```

## Zusammenfassung der Schlüsselunterscheidungsmerkmale

| Merkmal | Zurückgesetztes Gerät | Konfiguriertes Physisches Gerät | Virtuelles Gerät |
|---------|------------------------|--------------------------------|------------------|
| Service UUID | Keine | Keine | Vorhanden |
| Herstellerdaten | Lang mit Nullsequenz | Lang mit MAC-Adresse | Kurz |
| MAC/Adresse-Relation | - | Enthält fremde MAC | Enthält eigene MAC |
| Unit-Adresse | Konstant | Konstant | Neue ID |
| Gerätename | Leer/Nullen | Leer/Nullen | Physischer Gerätename |

## Wichtiger Hinweis zur Namensbeziehung

Eine wichtige Beobachtung ist, dass der Name, der für ein **virtuelles Gerät** angezeigt wird, tatsächlich der Name des **physischen Geräts** ist. Dies ist ein weiterer Beleg für die Beziehung zwischen physischen und virtuellen Geräten im Mesh-Netzwerk.

Bei korrekter Konfiguration haben sowohl das physische als auch das zugehörige virtuelle Gerät den gleichen Namen (z.B. "CBU-DCS DALI Gateway"). Dies kann als zusätzliches Merkmal zur Identifizierung zusammengehöriger Geräte verwendet werden.

Da physische Geräte in unseren Tests oft keinen oder leere Namen hatten, die virtuellen Geräte aber den korrekten Namen zeigten, kann diese Asymmetrie in der Namensanzeige ebenfalls ein Hinweis auf die unterschiedliche Natur dieser Geräte sein.

Diese Merkmale stellen eine zuverlässige und robuste Methode dar, um die drei verschiedenen Casambi-Gerätetypen zu unterscheiden. Durch die Anwendung dieser Kriterien kann die CasambiBt-Bibliothek erweitert werden, um alle Gerätetypen korrekt zu erkennen und zu verarbeiten.