# Casambi Geräte-IDs erklärt

Um die Verwirrung bezüglich der verschiedenen Identifikatoren in den Casambi-Geräten zu klären, habe ich hier eine strukturierte Übersicht erstellt.

## Die verschiedenen Identifikatoren im Überblick

| Identifikator | Beschreibung | Beispielwert | Konstant? |
|---------------|--------------|--------------|-----------|
| Bluetooth MAC-Adresse | Physische Adresse des Bluetooth-Geräts | 05:A3:9D:10:4B:18 | Bleibt normalerweise konstant, kann aber in manchen Situationen wechseln |
| Unit-Adresse | Interne Seriennummer des Casambi-Geräts (erste 6 Bytes der Herstellerdaten) | 184b109da305 | Ja, bleibt konstant über alle Zustände hinweg |
| Herstellercode | Identifiziert den Gerätehersteller | 963 (für Casambi) | Ja |
| Service UUID | Identifiziert den Bluetooth-Dienst eines konfigurierten Geräts | 0000fe4d-0000-1000-8000-00805f9b34fb | Erscheint nur im konfigurierten Zustand |
| Andere MAC-Adressen | MAC-Adressen anderer Netzwerkgeräte in den Herstellerdaten | 36:B6:9D:AF:62:AE | Nein, ändert sich je nach Netzwerkkonfiguration |

## Was ist die eigentliche Geräte-Identifikation?

Als wir alle Tests durchgeführt haben, haben wir festgestellt, dass die **Unit-Adresse** (`184b109da305` in unseren Tests) die zuverlässigste Identifikation für ein Casambi-Gerät ist. Sie bleibt konstant, selbst wenn das Gerät zurückgesetzt oder neu konfiguriert wird.

## Verwirrung mit MAC-Adressen erklärt

In unseren Tests haben wir zwei verschiedene MAC-Adressen gesehen:

1. **05:A3:9D:10:4B:18** - Dies ist die Bluetooth MAC-Adresse des Geräts, mit dem wir die Tests durchgeführt haben
2. **36:B6:9D:AF:62:AE** - Dies ist die MAC-Adresse eines anderen Casambi-Geräts im Netzwerk

Die Verwirrung entsteht, weil:

1. Ein Gerät in seinen Herstellerdaten die MAC-Adresse eines anderen Geräts enthalten kann
2. In manchen Bluetooth-Implementierungen kann ein Gerät tatsächlich seine MAC-Adresse ändern (MAC-Randomisierung als Datenschutzfunktion)

## Die Mesh-Netzwerk-Hypothese

Nach weiteren Überlegungen haben wir eine wichtige Erkenntnis gewonnen: **Ein einzelnes physisches Casambi-Gerät kann möglicherweise in seinen Bluetooth-Werbedaten Informationen über mehrere Geräte aus demselben Netzwerk übertragen**.

Diese Hypothese würde erklären, warum wir scheinbar unterschiedliche Geräte in unseren Scans sehen, obwohl physisch nur ein Gerät vorhanden ist:

1. **Ein zurückgesetztes Gerät** sendet nur seine eigenen Daten
2. **Ein konfiguriertes Gerät** könnte zusätzlich zu seinen eigenen Daten auch "virtuelle" Informationen über andere Netzwerkgeräte senden, selbst wenn diese physisch nicht in Reichweite sind

Dies passt zu einem Mesh-Netzwerk-Ansatz, bei dem jedes Gerät Informationen über seine Netzwerkpartner speichert und weitergibt, um die Netzwerkabdeckung zu erweitern.

## Die beobachteten Gerätezustände

Basierend auf dieser neuen Perspektive können wir die beobachteten Zustände neu interpretieren:

### 1. Zurückgesetzter Zustand (physisches Gerät)
- Bluetooth MAC-Adresse: 05:A3:9D:10:4B:18
- Unit-Adresse: 184b109da305
- Herstellerdaten: `184b109da3052328f22c2800000000000000004b0000f0`
- Service UUID: Keine
- Besonderheit: Enthält eine Nullsequenz

### 2. Konfigurierter Zustand (physisches Gerät)
- Bluetooth MAC-Adresse: 05:A3:9D:10:4B:18
- Unit-Adresse: 184b109da305
- Herstellerdaten: `184b109da3052328f22c280036b69daf62ae094b0000f0`
- Service UUID: Keine
- Besonderheit: Enthält die MAC-Adresse eines anderen Geräts (36:B6:9D:AF:62:AE)
- Interpretation: Dies ist wahrscheinlich der normale konfigurierte Zustand des Geräts, mit Informationen über andere Netzwerkmitglieder

### 3. "Virtuelles" Netzwerkgerät
- Bluetooth MAC-Adresse: 36:B6:9D:AF:62:AE
- Herstellerdaten: `36b69daf62ae0b` (enthält die eigene MAC-Adresse)
- Service UUID: 0000fe4d-0000-1000-8000-00805f9b34fb
- Besonderheit: Kurze Herstellerdaten, sendet Service UUID
- Interpretation: Dies könnte eine "virtuelle" Repräsentation eines anderen Netzwerkgeräts sein, dessen Daten vom physischen Gerät weitergegeben werden, obwohl das Gerät selbst nicht physisch anwesend ist

### 4. Weitere "virtuelle" Geräte
Es wurde eine weitere Unit-Adresse `113d827bfaf9` erwähnt, die zu einem anderen Gerät im Netzwerk gehören könnte und möglicherweise nach der Konfiguration in den Bluetooth-Scans erscheinen kann, obwohl es physisch nicht in Reichweite ist.

## Erklärung der "wechselnden" MAC-Adressen

Es gibt drei mögliche Erklärungen für die Beobachtung von "wechselnden" MAC-Adressen:

1. **Eingebettete MAC-Adressen**: Die Herstellerdaten eines Casambi-Geräts enthalten manchmal die MAC-Adressen anderer Geräte. In unseren Tests haben wir gesehen, dass das Gerät mit MAC 05:A3:9D:10:4B:18 die MAC-Adresse 36:B6:9D:AF:62:AE in seinen Daten enthielt.

2. **Mehrere Geräte im Netzwerk**: Bei manchen Scans könnten wir tatsächlich zwei verschiedene physische Geräte gesehen haben - dein Testgerät und ein anderes Casambi-Gerät im Netzwerk.

3. **MAC-Randomisierung**: Einige Betriebssysteme und Bluetooth-Implementierungen verwenden eine Datenschutzfunktion namens MAC-Randomisierung, bei der die ausgesendete MAC-Adresse regelmäßig geändert wird. Dies ist jedoch unwahrscheinlich bei fest installierten IoT-Geräten wie Casambi-Leuchten.

## Unsere beste Annahme

Basierend auf allen Daten ist die wahrscheinlichste Erklärung, dass:

1. Wir haben die Tests mit dem Gerät `05:A3:9D:10:4B:18` (Unit-Adresse `184b109da305`) durchgeführt
2. Dieses Gerät kommuniziert mit einem anderen Gerät `36:B6:9D:AF:62:AE` im selben Netzwerk
3. Das Gerät enthält im Übergangszustand die MAC-Adresse des anderen Geräts in seinen Herstellerdaten
4. Die Unit-Adresse (`184b109da305`) ist die zuverlässigste Möglichkeit, ein bestimmtes Casambi-Gerät über verschiedene Zustände hinweg zu identifizieren

## Visualisierung der Herstellerdaten

### Zurückgesetzter Zustand:
```
184b109da3052328f22c2800000000000000004b0000f0
|--Unit-Adresse--|-----|--Nullsequenz--|---|Ende|
```

### Übergangszustand:
```
184b109da3052328f22c280036b69daf62ae094b0000f0
|--Unit-Adresse--|-----|--MAC-Adresse--|---|Ende|
```

### "Virtuelles" Netzwerkgerät:
```
36b69daf62ae0b
|-MAC-Adr.-|End|
```

## Empfehlungen für die CasambiBt-Bibliothek

Basierend auf dieser erweiterten Analyse wäre es sinnvoll, die CasambiBt-Bibliothek so zu erweitern, dass sie:

1. Die Unit-Adresse als primären Identifikator für Geräte verwendet, nicht die Bluetooth MAC-Adresse
2. Beide Gerätezustände (zurückgesetzt und konfiguriert) erkennt und entsprechend behandelt
3. Die Beziehungen zwischen Geräten im Netzwerk basierend auf den eingebetteten MAC-Adressen analysiert
4. Zwischen physisch vorhandenen und "virtuellen" Geräten unterscheiden kann, indem sie Muster in den Werbedaten erkennt

## Weitere Untersuchungsmöglichkeiten

Um diese Mesh-Netzwerk-Hypothese zu bestätigen, könnten wir:

1. **Test mit mehreren physischen Geräten**: Beobachten, wie die Bluetooth-Werbedaten sich ändern, wenn mehrere physische Geräte im selben Netzwerk sind
   
2. **Protokollanalyse während der Konfiguration**: Die gesamte Bluetooth-Kommunikation während des Konfigurationsprozesses aufzeichnen, um zu sehen, wann und wie Geräteinformationen ausgetauscht werden
   
3. **Überprüfung der neuen Unit-Adresse**: Scannen nach der Unit-Adresse `113d827bfaf9` und beobachten, unter welchen Umständen sie erscheint