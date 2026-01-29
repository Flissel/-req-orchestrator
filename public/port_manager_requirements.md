# Port & PID Manager - Requirements Specification

Eine webbasierte Anwendung zur Verwaltung und Überwachung von System-Ports und Prozess-IDs (PIDs).

## 1. Functional Requirements

### 1.1 Process Management

- **REQ-PM-001**: Das System soll alle laufenden Prozesse in einer tabellarischen Übersicht anzeigen, inklusive PID, Prozessname, Status, CPU-Auslastung in Prozent und Speicherverbrauch in MB.

- **REQ-PM-002**: Der Benutzer soll Prozesse nach PID oder Prozessname durchsuchen können, mit Autovervollständigung nach Eingabe von mindestens 2 Zeichen und Filterung der Ergebnisse in Echtzeit.

- **REQ-PM-003**: Das System ermöglicht das Beenden eines Prozesses durch Angabe der PID. Vor der Ausführung zeigt das System eine Bestätigungsabfrage mit Prozessname, PID und aktuellem Status an.

- **REQ-PM-004**: Die Prozessliste aktualisiert sich automatisch alle 5 Sekunden und hebt geänderte Einträge für 3 Sekunden visuell durch Hintergrundfarbe hervor.

- **REQ-PM-005**: Das System zeigt für jeden Prozess einen Verlaufsgrafen der CPU-Auslastung der letzten 60 Sekunden mit Datenpunkten im 5-Sekunden-Intervall an.

### 1.2 Port Management

- **REQ-PT-001**: Das System listet alle belegten TCP- und UDP-Ports auf, mit zugehörigem Prozessnamen, PID, Protokoll, lokalem Endpunkt und Remote-Adresse.

- **REQ-PT-002**: Benutzer können die Port-Liste nach Status filtern: LISTENING, ESTABLISHED, TIME_WAIT, CLOSE_WAIT. Mehrfachauswahl ist möglich.

- **REQ-PT-003**: Das System gibt eine Warnmeldung aus, wenn ein Systemport im Bereich 1-1024 von einem nicht signierten Prozess belegt wird. Die Warnung enthält Port-Nummer, Protokoll, Prozessname und PID.

- **REQ-PT-004**: Der Benutzer kann nach einzelnen Port-Nummern oder Port-Bereichen im Format min-max suchen. Die Ergebnisse werden gefiltert und nach Port-Nummer sortiert angezeigt.

- **REQ-PT-005**: Das System zeigt für jeden offenen Port die Anzahl aktiver Verbindungen, übertragene Bytes pro Sekunde und Verbindungsdauer in Minuten an.

### 1.3 Dashboard und Visualisierung

- **REQ-DASH-001**: Das Dashboard zeigt eine Übersicht mit: Anzahl aktiver Prozesse, Anzahl belegter Ports, Anzahl freier Standard-Ports (1-1024), CPU-Auslastung in Prozent und RAM-Nutzung in Prozent.

- **REQ-DASH-002**: Ein Kreisdiagramm visualisiert die Port-Verteilung nach Kategorien: System-Ports mit Bereich 1-1024, Registrierte Ports mit Bereich 1025-49151 und Dynamische Ports mit Bereich 49152-65535.

- **REQ-DASH-003**: Bei Klick auf ein Segment im Port-Diagramm öffnet sich eine gefilterte Liste mit allen Ports dieser Kategorie, sortiert nach Aktivität.

- **REQ-DASH-004**: Das Dashboard zeigt eine Echtzeit-Timeline der letzten 100 Verbindungsereignisse mit Zeitstempel, Eventtyp und betroffener Ressource.

## 2. Non-Functional Requirements

### 2.1 Performance

- **REQ-PERF-001**: Die initiale Ladezeit des Dashboards beträgt maximal 2 Sekunden bei bis zu 500 aktiven Prozessen, gemessen vom Request bis zum vollständigen Rendering.

- **REQ-PERF-002**: Die Echtzeit-Aktualisierung der Prozessliste erfolgt mit einer Latenz von maximal 200ms zwischen Backend-Event und UI-Update, gemessen via Performance API.

- **REQ-PERF-003**: Die Suchfunktion liefert Ergebnisse innerhalb von 100ms nach Eingabe, auch bei einer Datenbasis von 10.000 Prozess-Einträgen.

- **REQ-PERF-004**: Der Speicherverbrauch des Frontend-Clients überschreitet nicht 150MB RAM bei Anzeige von bis zu 1000 Prozessen, gemessen via Chrome DevTools Memory Profiler.

### 2.2 Security

- **REQ-SEC-001**: Sensible Aktionen wie Prozess beenden und Port schließen erfordern eine Re-Authentifizierung per Passwort oder 6-stelligem TOTP-Code.

- **REQ-SEC-002**: Alle API-Aufrufe werden über HTTPS mit TLS 1.3 oder höher verschlüsselt. HTTP-Anfragen werden mit Status 301 auf HTTPS umgeleitet.

- **REQ-SEC-003**: Benutzeraktionen werden in einem Audit-Log protokolliert mit: Zeitstempel im ISO 8601 Format, Benutzer-ID, Aktionstyp, betroffene Ressource und Client-IP-Adresse.

- **REQ-SEC-004**: API-Tokens haben eine maximale Gültigkeit von 24 Stunden und werden bei Inaktivität von mehr als 30 Minuten automatisch invalidiert.

### 2.3 Usability

- **REQ-UX-001**: Die Benutzeroberfläche unterstützt vollständige Tastaturnavigation: Tab für Elementwechsel, Enter für Aktionsausführung, Escape für Dialog schließen, Strg+F für globale Suche.

- **REQ-UX-002**: Fehlermeldungen zeigen den konkreten Fehlergrund, die betroffene Ressource und mindestens einen Lösungsvorschlag mit Handlungsanweisung an.

- **REQ-UX-003**: Responsive Design gewährleistet Bedienbarkeit auf Bildschirmen ab 1024x768 Pixel, mit angepasstem Layout für Tablet ab 768px Breite und Mobile ab 375px Breite.

- **REQ-UX-004**: Tabellenköpfe sind fixiert und bleiben beim Scrollen sichtbar. Die Sortierrichtung wird durch Pfeilsymbole angezeigt.

### 2.4 Reliability

- **REQ-REL-001**: Bei Unterbrechung der Backend-Verbindung startet das System automatisch alle 10 Sekunden einen Reconnect-Versuch und zeigt den Verbindungsstatus in der Statusleiste an.

- **REQ-REL-002**: Prozessdaten werden im Browser-LocalStorage gecached mit einem Zeitstempel. Bei Verbindungsabbruch zeigt das System den letzten bekannten Stand mit Altersangabe an.

- **REQ-REL-003**: Das System protokolliert Client-Fehler mit Stacktrace, Browser-Info und Session-ID und sendet diese an das Backend-Logging alle 30 Sekunden gesammelt.

## 3. Technical Requirements

### 3.1 Integration

- **REQ-TECH-001**: Das Backend stellt eine RESTful API gemäß OpenAPI 3.0 Spezifikation bereit. Die API-Dokumentation wird automatisch aus Code-Annotationen generiert und ist unter /api/docs erreichbar.

- **REQ-TECH-002**: Die WebSocket-Verbindung für Echtzeit-Updates verwendet das JSON-RPC 2.0 Protokoll mit Heartbeat-Messages alle 30 Sekunden zur Verbindungsüberwachung.

- **REQ-TECH-003**: Die Export-Funktion ermöglicht Download der aktuellen Ansicht als CSV mit Kommatrennung und UTF-8-BOM Encoding oder als JSON mit Schema-Validierung und Pretty-Print Formatierung.

- **REQ-TECH-004**: Das System unterstützt den Import von Prozess-Whitelists im JSON-Format mit Schema-Validierung und zeigt bei Importfehlern die fehlerhaften Einträge mit Zeilennummer an.

### 3.2 Compatibility

- **REQ-COMP-001**: Das Frontend unterstützt die jeweils zwei neuesten Major-Versionen von Chrome, Firefox, Safari und Edge zum Zeitpunkt des Releases.

- **REQ-COMP-002**: Der Backend-Agent unterstützt Windows 10 und 11 auf x64-Architektur, Ubuntu 20.04 und 22.04 auf x64-Architektur sowie macOS 12 und 13 auf x64- und ARM-Architektur.

- **REQ-COMP-003**: Die Anwendung funktioniert korrekt bei Systemuhren mit einer Abweichung von bis zu 5 Minuten von der tatsächlichen Zeit durch Verwendung von Server-Zeitstempeln für alle zeitkritischen Operationen.