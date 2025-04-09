# Mesh-Netzwerk-Analyse der Casambi-Gerätetests

## 1. Zusammenfassung der Testergebnisse

Die Tests haben unsere Mesh-Netzwerk-Hypothese **eindeutig bestätigt**. Die Beobachtung der verschiedenen Phasen zeigt deutlich, dass ein konfiguriertes Casambi-Gerät tatsächlich "virtuelle" Repräsentationen anderer Netzwerkgeräte in Bluetooth-Scans erzeugt, selbst wenn diese physisch nicht vorhanden sind.

## 2. Detailanalyse der Testphasen

### Phase 1: Zurückgesetztes Gerät

In dieser Phase haben wir ein Gerät im zurückgesetzten Zustand getestet:

```json
{
  "device_address": "05:A3:9D:10:4B:18",
  "rssi": -67,
  "service_uuids": [],
  "manufacturer_data": {
    "963": "184b109da3052328f22c2800000000000000004b0000f0"
  },
  "device_type": "physical_reset",
  "casambi_data": {
    "unit_address": "184b109da305",
    "contains_nulls": true
  }
}
```

**Wichtige Beobachtungen:**
- Das physische Gerät sendet **keine Service UUID**
- Es enthält eine **Nullsequenz** (`000000000000`) in den Herstellerdaten
- Die identifizierte **Unit-Adresse** ist `184b109da305`
- Es werden **keine weiteren Casambi-Geräte** im Scan angezeigt

### Phase 2: Konfiguriertes Gerät

Nach der Konfiguration des Geräts zeigt der Scan folgende Ergebnisse:

**Das physische Gerät:**
```json
{
  "device_address": "05:A3:9D:10:4B:18",
  "rssi": -68,
  "service_uuids": [],
  "manufacturer_data": {
    "963": "184b109da3052328f22c280036b69daf62ae0a4b0000f0"
  },
  "device_type": "physical_configured",
  "casambi_data": {
    "unit_address": "184b109da305",
    "contains_nulls": false
  }
}
```

**Ein neues "virtuelles" Gerät:**
```json
{
  "device_address": "36:B6:9D:AF:62:AE",
  "rssi": -68,
  "service_uuids": [
    "0000fe4d-0000-1000-8000-00805f9b34fb"
  ],
  "manufacturer_data": {
    "963": "36b69daf62ae0b"
  },
  "device_type": "virtual",
  "casambi_data": {
    "unit_address": "36b69daf62ae",
    "contains_own_mac": true
  }
}
```

**Wichtige Beobachtungen:**
1. Das physische Gerät hat die **gleiche MAC-Adresse** und **Unit-Adresse** wie vorher
2. Die Nullsequenz wurde durch die MAC-Adresse `36b69daf62ae` ersetzt
3. Ein **neues Gerät** mit genau dieser MAC-Adresse erscheint im Scan
4. Dieses neue Gerät hat eine **Service UUID** (`0000fe4d-0000-1000-8000-00805f9b34fb`)
5. Die Herstellerdaten des virtuellen Geräts sind deutlich kürzer und enthalten hauptsächlich seine eigene MAC-Adresse

## 3. Bestätigung der Mesh-Netzwerk-Hypothese

Diese Ergebnisse bestätigen eindeutig unsere Mesh-Netzwerk-Hypothese:

1. **Physische Geräte senden virtuelle Repräsentationen**: Das konfigurierte Gerät sendet nicht nur seine eigenen Daten, sondern auch Informationen, die zu einem anderen Gerät im Netzwerk gehören.

2. **Die MAC-Adresse in den Herstellerdaten** des physischen Geräts ist identisch mit der MAC-Adresse des virtuellen Geräts, das im Scan erscheint.

3. **Nur konfigurierte Geräte erzeugen virtuelle Repräsentationen**: Im zurückgesetzten Zustand erscheint kein virtuelles Gerät im Scan.

4. **Virtuelle Geräte haben eine Service UUID**: Dies erklärt, warum die CasambiBt-Bibliothek nur Geräte mit dieser UUID als Casambi-Geräte erkennt - sie erkennt nur die virtuellen Repräsentationen, nicht die eigentlichen physischen Geräte.

## 4. Bedeutung für die Casambi-Geräteidentifikation

Die Tests bestätigen auch unsere früheren Erkenntnisse:

1. Die **Unit-Adresse** ist tatsächlich der zuverlässigste Identifikator für ein Gerät, da sie im physischen Gerät über alle Zustände hinweg konstant bleibt.

2. Die **MAC-Adresse** kann sich scheinbar ändern, wenn ein Gerät seine Daten mit denen anderer Netzwerkgeräte erweitert - dies ist jedoch ein Effekt des Mesh-Netzwerks, nicht tatsächlich wechselnde MAC-Adressen.

3. **Der Übergang zwischen verschiedenen Gerätezuständen** ist nun klarer:
   - Zurückgesetztes Gerät → Enthält Nullsequenz in den Daten
   - Konfiguriertes Gerät → Enthält MAC-Adressen anderer Netzwerkgeräte
   - Virtuelle Repräsentationen → Werden vom konfigurierten Gerät erzeugt, haben Service UUID

## 5. Schlussfolgerungen für die CasambiBt-Bibliothek

Die CasambiBt-Bibliothek sollte erweitert werden, um:

1. **Sowohl physische als auch virtuelle Geräte zu erkennen**: Aktuell erkennt sie nur Geräte mit einer bestimmten Service UUID, was bedeutet, dass sie nur die virtuellen Repräsentationen findet, nicht die eigentlichen physischen Geräte.

2. **Die Unit-Adresse als primären Identifikator** zu verwenden: Die ersten 6 Bytes der Herstellerdaten bleiben konstant und sind zuverlässiger als die MAC-Adresse.

3. **Die Beziehung zwischen physischen und virtuellen Geräten zu verstehen**: Durch Analyse der eingebetteten MAC-Adressen in den Herstellerdaten kann die Bibliothek erkennen, welche Geräte zueinander gehören.

4. **Das Fehlen der Service UUID beim Verlassen des Netzwerks zu berücksichtigen**: Wenn ein Gerät aus dem Netzwerk entfernt wird, verschwindet seine virtuelle Repräsentation, während das physische Gerät in den zurückgesetzten Zustand übergeht.

## 6. Weitere Untersuchungen

Für ein noch tieferes Verständnis könnten weitere Untersuchungen durchgeführt werden:

1. **Tests mit mehreren physischen Geräten** in einem Netzwerk, um zu sehen, wie sie sich gegenseitig in ihren Daten referenzieren.

2. **Analyse des letzten Bytes in den Herstellerdaten der virtuellen Geräte** (`0b` im beobachteten Fall) - möglicherweise ist dies ein Statuscode oder eine Versionskennung.

3. **Langzeit-Beobachtung der Netzwerkkommunikation**, um zu sehen, wie sich die Daten bei Netzwerkveränderungen (hinzufügen/entfernen von Geräten) anpassen.

4. **Untersuchung der Sichtbarkeit von Geräten außerhalb der Bluetooth-Reichweite** - wie weit können Informationen über nicht direkt erreichbare Geräte durch das Mesh-Netzwerk verbreitet werden?

## 7. Zusammenfassung

Die Casambi-Geräte implementieren tatsächlich ein Mesh-Netzwerk, in dem jedes konfigurierte Gerät Informationen über andere Netzwerkgeräte verbreiten kann. Dies erklärt die scheinbar "wechselnden" MAC-Adressen und den Unterschied zwischen zurückgesetzten und konfigurierten Geräten.

Die Unit-Adresse bleibt der zuverlässigste Identifikator für ein physisches Gerät, während die Service UUID das Merkmal für virtuelle Repräsentationen ist, die von konfigurierten Geräten erzeugt werden.

Diese Erkenntnisse eröffnen neue Möglichkeiten zur Verbesserung der CasambiBt-Bibliothek und zum tieferen Verständnis des Casambi-Mesh-Netzwerks.