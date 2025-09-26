# Demo Requirements Dokument

## Einleitung
Dieses Dokument enthält einige klare, kurze Requirements, die der Mining-Agent erkennen soll.

## Funktionale Anforderungen
- Das System MUSS Benutzer-Login via E-Mail und Passwort unterstützen.
- Das System SOLL eine Passwort-Zurücksetzen-Funktion per E-Mail bereitstellen.
- Das System MUSS Rollen (admin, editor, viewer) unterscheiden und Berechtigungen prüfen.
- Beim Upload von Dateien MUSS ein Fortschrittsbalken angezeigt werden.
- Die Anwendung SOLL Suchergebnisse in unter 200 ms für 90% der Anfragen liefern.

## Nicht-funktionale Anforderungen
- Die Plattform MUSS mindestens 10.000 gleichzeitige Sitzungen unterstützen.
- Das System MUSS TLS 1.2+ erzwingen und HSTS aktivieren.
- Logs DÜRFEN KEINE personenbezogenen Daten im Klartext enthalten.
- Fehler SOLLEN strukturiert im JSON-Format geloggt werden (level, message, traceId, timestamp).

## Sicherheit
- Nach 5 fehlgeschlagenen Login-Versuchen MUSS der Account 15 Minuten gesperrt werden.
- Passwörter MÜSSEN mit Argon2id gehasht werden.
- Alle Tokens SOLLEN eine maximale Lebensdauer von 1 Stunde haben.

## UX
- Formulare MÜSSEN Inline-Validierung anzeigen (rot markierte Felder + Fehlermeldung).
- Die Anwendung SOLL Dark/Light Theme umschaltbar machen.

## Betrieb
- Deployments MÜSSEN Blue-Green unterstützen mit unter 1 Minute Downtime.
- Metriken SOLLEN via OpenTelemetry (OTLP) exportiert werden.

## Abschluss
Diese Liste dient als Testkorpus für das Requirements-Mining.