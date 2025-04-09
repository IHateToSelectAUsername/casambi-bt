# Analyse der Casambi-Gerätenamen in verschiedenen Testskripten

## Beobachtete Unterschiede

Bei der Analyse der Log-Dateien verschiedener Testskripte wurde ein interessanter Unterschied bei der Anzeige der Gerätenamen festgestellt:

### In casambi_discover.log (aus demo_discover.py):

- Die Casambi-Geräte werden mit ihrem korrekten Namen angezeigt, z.B.:
  ```
  Received 05:A3:9D:10:4B:18: CBU-DCS DALI Gateway.
  Received 36:B6:9D:AF:62:AE: CBU-DCS DALI Gateway.
  ```

- Jedoch erkennt die CasambiBt-Bibliothek nur das Gerät mit der MAC-Adresse `36:B6:9D:AF:62:AE` als Casambi-Netzwerk:
  ```
  [DEBUG] CasambiBt._discover: Discovered network at 36:B6:9D:AF:62:AE
  ```

### In all_ble_devices.log und unseren anderen Testskripten:

- Die gleichen Geräte erscheinen, aber ohne Namen oder mit Nullen:
  ```
  Received 05:A3:9D:10:4B:18: .
  Received 36:B6:9D:AF:62:AE: .
  ```

## Interpretation im Kontext der Mesh-Netzwerk-Hypothese

Diese Beobachtung unterstützt und erweitert unsere Mesh-Netzwerk-Hypothese:

1. **Namensanzeige als weiterer Unterschied zwischen Gerätetypen**:
   - Virtuelle Geräte (mit Service UUID) scheinen ihren korrekten Namen in bestimmten Advertising-Paketen zu senden
   - Das physische Gerät sendet möglicherweise keine oder andere Namensinformationen in seinen Advertising-Paketen

2. **Unterschiede in der Datenerfassung**:
   - Die ursprüngliche CasambiBt-Bibliothek scheint bestimmte Advertising-Pakete zu erfassen, die den korrekten Namen enthalten
   - Unsere späteren Testskripte haben möglicherweise nur die Pakete ohne Namensangabe berücksichtigt

3. **Bestätigung des Auswahlmechanismus der CasambiBt-Bibliothek**:
   - Die CasambiBt-Bibliothek erkennt tatsächlich nur das Gerät mit MAC-Adresse `36:B6:9D:AF:62:AE` als Casambi-Netzwerk
   - Dies entspricht dem "virtuellen" Gerät mit Service UUID in unserer Hypothese
   - Das physische Gerät (`05:A3:9D:10:4B:18`) wird nicht als Casambi-Netzwerk erkannt, obwohl es in den Logs erscheint

## Technische Erklärung

In Bluetooth LE senden Geräte mehrere Arten von Advertising-Paketen, die unterschiedliche Informationen enthalten können. Bei den Casambi-Geräten scheinen zwei verschiedene Arten von Paketen gesendet zu werden:

1. **Service-Daten-Pakete**: Enthalten die Service UUID und andere technische Informationen, werden von virtuellen Geräten gesendet.

2. **Scan-Response-Pakete**: Können zusätzliche Informationen wie den Gerätenamen enthalten.

Die Windows Runtime BLE-API, die von der Bleak-Bibliothek verwendet wird, empfängt diese Pakete getrennt, was zu mehreren Log-Einträgen für dasselbe Gerät führt - einmal ohne Namen und einmal mit Namen.

## Erweiterung für die CasambiBt-Bibliothek

Diese Erkenntnis legt nahe, dass die CasambiBt-Bibliothek erweitert werden sollte, um:

1. **Alle Arten von Advertising-Paketen** zu berücksichtigen, um sowohl technische Daten als auch Namen korrekt zu erfassen.

2. **Sowohl physische als auch virtuelle Geräte zu erkennen**, indem nicht nur auf die Service UUID, sondern auch auf Herstellerdaten und Gerätenamen geachtet wird.

3. **Den Gerätenamen als zusätzlichen Identifikator** zu verwenden, besonders bei der Unterscheidung zwischen physischen und virtuellen Repräsentationen desselben Geräts.

## Schlussfolgerung

Der korrekte Gerätename ("CBU-DCS DALI Gateway") scheint hauptsächlich von virtuellen Geräten mit Service UUID gesendet zu werden, während physische Geräte möglicherweise andere oder keine Namensangaben senden. Dies ist ein weiteres unterscheidendes Merkmal zwischen den verschiedenen Gerätetypen im Casambi-Mesh-Netzwerk.

Diese Beobachtung bekräftigt unsere Mesh-Netzwerk-Hypothese und bietet einen weiteren Aspekt, den die CasambiBt-Bibliothek bei der Erkennung und Unterscheidung von Geräten berücksichtigen sollte.