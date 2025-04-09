# Analyse der Casambi Bluetooth-Gerätezustände

## Einführung

Diese Analyse untersucht das Bluetooth-Kommunikationsverhalten von Casambi-Beleuchtungsgeräten in verschiedenen Konfigurationszuständen. Durch systematische Tests wurde das Verhalten eines Geräts vor und nach der Zurücksetzung sowie vor und nach der Konfiguration beobachtet und analysiert.

## Methodologie

Die Tests wurden mit mehreren sequentiellen Bluetooth-Scans durchgeführt:

1. **Runde 1: Zurücksetzungstest**
   - **Scan 1**: Gerät im Anfangszustand
   - **Scan 2**: Gerät nach Zurücksetzung auf Werkseinstellungen

2. **Runde 2: Konfigurationstest**
   - **Scan 3**: Gerät im zurückgesetzten Zustand
   - **Scan 4**: Gerät nach Konfiguration/Netzwerkeinbindung

Für alle Scans wurden die Bluetooth-Werbedaten erfasst und analysiert, mit besonderem Fokus auf:
- Vorhandensein von Service UUIDs
- Herstellerspezifische Daten (Manufacturer Data)
- Zustandsänderungen und Datenmuster

## Beobachtete Gerätezustände

Während der Tests wurden **drei verschiedene Zustände** beobachtet:

### 1. Zurückgesetzter Zustand

**Merkmale:**
- Keine Service UUID
- Herstellerdaten mit Nullsequenz
- Beispiel: `184b109da3052328f22c2800000000000000004b0000f0`

### 2. Übergangszustand ("Unklarer Status")

**Merkmale:**
- Keine Service UUID
- Nullsequenz durch MAC-Adresse eines anderen Geräts ersetzt
- Beispiel: `184b109da3052328f22c280036b69daf62ae094b0000f0`

### 3. Vollständig konfigurierter Zustand

**Merkmale:**
- Service UUID vorhanden (`0000fe4d-0000-1000-8000-00805f9b34fb`)
- Kurze Herstellerdaten, oft nur die eigene MAC-Adresse
- In früheren Tests beobachtet, nicht in den aktuellen Tests erfasst

## Detailanalyse der Herstellerdaten

### Struktur der Herstellerdaten

Die Herstellerdaten (Manufacturer Data) mit Hersteller-ID 963 zeigen ein klares Muster:

#### Zurückgesetzter Zustand:
```
184b109da3052328f22c2800000000000000004b0000f0
|--------Unit-ID------|-----|--Nullsequenz--|---|
```

#### Übergangszustand:
```
184b109da3052328f22c280036b69daf62ae094b0000f0
|--------Unit-ID------|-----|--MAC-Adresse--|---|
```

### Unit-Adresse

Die ersten 6 Bytes (`184b109da305`) bleiben in allen Tests **konstant**, unabhängig vom Konfigurationszustand. Dies bestätigt, dass es sich um eine permanente Geräteidentifikation handelt, vergleichbar mit einer Seriennummer.

### Kommunikationsbereich

Der mittlere Teil der Daten zeigt deutliche Zustandsänderungen:
- In einem zurückgesetzten Gerät enthält dieser Bereich eine Nullsequenz (`000000000000`)
- Im Übergangszustand wird dieser Bereich durch die MAC-Adresse eines anderen Netzwerkgeräts (`36b69daf62ae`) ersetzt

### Status-Indikator

Das Byte nach der eingebetteten MAC-Adresse änderte sich zwischen den Tests:
- Im ersten Test: `08`
- Im zweiten Test: `09`

Diese Inkrementierung könnte als Zähler oder Statuscode dienen.

## Wichtigste Erkenntnisse

1. **Unit-Adresse als permanente Kennung**: Die ersten 6 Bytes der Herstellerdaten (`184b109da305`) sind eine unveränderliche Gerätekennung, die Konfigurationsänderungen übersteht.

2. **Gerätestatus wird in den Herstellerdaten kodiert**: Der Wechsel zwischen Nullsequenz und MAC-Adresse zeigt den Übergang zwischen verschiedenen Konfigurationszuständen.

3. **Mehrphasiger Konfigurationsprozess**: Die Beobachtung des Übergangszustands zeigt, dass der Konfigurationsprozess von Casambi-Geräten aus mehreren Phasen besteht und nicht nur ein einfacher Zustandswechsel ist.

4. **Mesh-Kommunikation sichtbar**: Die Einbettung der MAC-Adresse eines anderen Geräts in die Herstellerdaten deutet auf eine Mesh-Netzwerkkommunikation hin, bei der Geräte Informationen über andere Netzwerkmitglieder speichern.

## Auswirkungen auf die CasambiBt-Bibliothek

Die aktuelle Implementierung der CasambiBt-Bibliothek erkennt Geräte anhand von zwei Kriterien:
1. Herstellercode 963
2. Vorhandensein einer spezifischen Service UUID

Dadurch werden Geräte im zurückgesetzten Zustand und im Übergangszustand nicht erkannt, obwohl sie durch ihre Unit-Adresse eindeutig identifizierbar wären. Die Bibliothek könnte erweitert werden, um:

1. **Geräte im Übergangszustand zu erkennen**: Dies würde eine bessere Unterstützung des Konfigurationsprozesses ermöglichen.

2. **Die Unit-Adresse für die Geräteidentifikation zu nutzen**: Dies würde eine zuverlässigere Geräteverfolgung über Statusänderungen hinweg ermöglichen.

## Inkonsistenzen und offene Fragen

1. **Unvollständige Konfiguration**: Im zweiten Test endete das Gerät im Übergangszustand statt im vollständig konfigurierten Zustand. Dies deutet darauf hin, dass wir möglicherweise nicht den gesamten Konfigurationsprozess erfasst haben.

2. **Rolle des Status-Indikators**: Die Bedeutung des inkrementierenden Bytes nach der MAC-Adresse ist noch unklar und könnte weitere Einblicke in den Konfigurationsprozess bieten.

3. **Weitere Statusübergänge**: Es könnten noch weitere Zwischenzustände existieren, die in unseren Tests nicht erfasst wurden.

## Vorschläge für weitere Untersuchungen

1. **Längere Beobachtung nach der Konfiguration**: Die vollständige Konfiguration könnte mehr Zeit benötigen oder zusätzliche Interaktionen erfordern.

2. **Untersuchung des Netzwerkverhaltens mit mehreren Geräten**: Tests mit mehr als zwei Geräten könnten weitere Einblicke in die Mesh-Netzwerkkommunikation bieten.

3. **Analyse des Status-Indikators**: Systematische Tests mit wiederholten Konfigurationen könnten helfen, die Bedeutung des inkrementierenden Bytes zu verstehen.

4. **Erweiterung der CasambiBt-Bibliothek**: Implementierung einer erweiterten Erkennung, die alle Gerätezustände berücksichtigt und die Unit-Adresse als primären Identifikator verwendet.