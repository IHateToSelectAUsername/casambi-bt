# Casambi Bluetooth Demos

Diese Sammlung von Demo-Skripten zeigt die Verwendung der `CasambiBt`-Bibliothek zur Steuerung von Casambi-Beleuchtungssystemen über Bluetooth Low Energy (BLE).

## Voraussetzungen

- Python 3.7 oder höher
- Installierte `CasambiBt`-Bibliothek
- Aktiviertes Bluetooth auf Ihrem Gerät
- Mindestens ein konfiguriertes Casambi-Netzwerk in Bluetooth-Reichweite

## Übersicht der Demo-Skripte

### 1. Bluetooth-Gerätesuche (`demo_discover.py`)

Dieses Skript demonstriert die automatische Suche nach Casambi-Netzwerken in Bluetooth-Reichweite. Es verwendet die `discover()`-Funktion der Bibliothek.

**Funktionen:**
- Sucht nach Casambi-Netzwerken in Bluetooth-Reichweite
- Zeigt gefundene Netzwerke mit ihrer Bluetooth-Adresse und (falls verfügbar) Namen an

```bash
python demo_discover.py
```

### 2. Netzwerk-Verbindung (`demo_connect.py`)

Dieses Skript zeigt, wie man eine Verbindung zu einem Casambi-Netzwerk herstellt und Netzwerkinformationen wie Geräte, Gruppen und Szenen abruft.

**Funktionen:**
- Sucht nach Netzwerken und stellt eine Verbindung her
- Zeigt umfassende Netzwerkinformationen an:
  - Allgemeine Netzwerkinformationen (Name, ID)
  - Liste aller Geräte mit Details
  - Liste aller Gruppen mit ihren Mitgliedern
  - Liste aller Szenen

```bash
python demo_connect.py
```

### 3. Gerätesteuerung (`demo_control_units.py`)

Demonstriert die Steuerung einzelner Geräte (Units) im Casambi-Netzwerk.

**Funktionen:**
- Einschalten und Ausschalten von Geräten
- Helligkeitssteuerung
- Farbtemperatursteuerung (falls vom Gerät unterstützt)
- RGB-Farbsteuerung (falls vom Gerät unterstützt)
- Anzeige des aktuellen Gerätestatus

```bash
python demo_control_units.py
```

### 4. Gruppensteuerung (`demo_control_groups.py`)

Zeigt, wie man Gruppen von Geräten gemeinsam steuern kann oder alle Geräte auf einmal.

**Funktionen:**
- Steuerung von definierten Gruppen oder aller Geräte gleichzeitig
- Einschalten und Ausschalten von Gruppen
- Helligkeitssteuerung für Gruppen
- Farbtemperatur- und RGB-Farbsteuerung für Gruppen
- Anzeige des aktuellen Status aller Geräte in einer Gruppe

```bash
python demo_control_groups.py
```

### 5. Szenensteuerung (`demo_scenes.py`)

Demonstriert die Verwendung von vorkonfigurierten Szenen in einem Casambi-Netzwerk.

**Funktionen:**
- Aktivierung von Szenen mit Standard-Helligkeit
- Aktivierung von Szenen mit angepasster Helligkeit
- Anzeige des aktuellen Status der Geräte nach Aktivierung einer Szene

```bash
python demo_scenes.py
```

### 6. Ereignisbehandlung (`demo_callbacks.py`)

Zeigt, wie man auf Ereignisse im Casambi-Netzwerk reagiert, wie Statusänderungen von Geräten oder Verbindungstrennungen.

**Funktionen:**
- Registrierung von Callbacks für Statusänderungen
- Registrierung von Callbacks für Verbindungstrennungen
- Interaktive Steuerung von Geräten zur Demonstration der Callbacks
- Simulation einer Verbindungstrennung

```bash
python demo_callbacks.py
```

## Hinweise zur Verwendung

1. **Bluetooth-Aktivierung**: Stellen Sie sicher, dass Bluetooth auf Ihrem Gerät aktiviert ist.
2. **Casambi-App**: Die Demos setzen voraus, dass Sie bereits ein Casambi-Netzwerk eingerichtet haben, vorzugsweise mit der offiziellen Casambi-App.
3. **Passwort**: Sie benötigen das Passwort Ihres Casambi-Netzwerks für alle Demos außer der Gerätesuche.
4. **Logging**: Alle Demos erstellen Log-Dateien im aktuellen Verzeichnis, die für die Fehlersuche nützlich sein können.

## Fehlerbehebung

- **Keine Geräte gefunden**: Überprüfen Sie, ob Bluetooth aktiviert ist und ob sich Casambi-Geräte in Reichweite befinden.
- **Verbindungsfehler**: Stellen Sie sicher, dass das richtige Passwort verwendet wird und dass das Netzwerk erreichbar ist.
- **Authentifizierungsfehler**: Vergewissern Sie sich, dass Sie Zugriff auf das Netzwerk haben und das korrekte Passwort eingeben.