# Good Requirements Examples - Testing Auto-Validation

This file contains well-written requirements that should pass validation. Each requirement follows best practices and adheres to all quality criteria.

## Functional Requirements

REQ-001: Das System muss Benutzer innerhalb von 2 Sekunden nach Eingabe korrekter Anmeldedaten authentifizieren

REQ-002: Die Anwendung muss PDF-Exporte im Format DIN A4 mit maximal 5 MB Dateigröße generieren

REQ-003: Das System muss eingegebene E-Mail-Adressen gegen RFC 5322 Standard validieren

REQ-004: Die Anwendung muss Passwörter mit mindestens 8 Zeichen, einem Großbuchstaben, einer Ziffer und einem Sonderzeichen verlangen

REQ-005: Das System muss nach 3 fehlgeschlagenen Login-Versuchen das Benutzerkonto für 15 Minuten sperren

## Performance Requirements

REQ-006: Das System muss Suchanfragen innerhalb von 500 Millisekunden beantworten

REQ-007: Die Anwendung muss 1000 gleichzeitige Benutzer ohne Leistungsverlust unterstützen

REQ-008: Das System muss Datenbankabfragen mit maximal 200 Millisekunden Latenz ausführen

REQ-009: Die Anwendung muss Dateien bis 50 MB innerhalb von 10 Sekunden hochladen können

REQ-010: Das System muss Cache-Inhalte nach 5 Minuten Inaktivität automatisch löschen

## Data Requirements

REQ-011: Das System muss Benutzerdaten verschlüsselt mit AES-256 speichern

REQ-012: Die Anwendung muss gelöschte Datensätze für 30 Tage in einem Papierkorb aufbewahren

REQ-013: Das System muss alle Änderungen an Stammdaten mit Zeitstempel und Benutzerkennung protokollieren

REQ-014: Die Anwendung muss personenbezogene Daten nach DSGVO-Richtlinien verarbeiten

REQ-015: Das System muss Backups täglich um 02:00 Uhr automatisch erstellen

## Interface Requirements

REQ-016: Das System muss eine REST-API mit JSON-Format für externe Systeme bereitstellen

REQ-017: Die Anwendung muss Fehlermeldungen in deutscher Sprache mit eindeutigen Fehlercodes anzeigen

REQ-018: Das System muss Formularfelder bei ungültiger Eingabe rot markieren und eine Beschreibung des Fehlers anzeigen

REQ-019: Die Anwendung muss eine Breadcrumb-Navigation für mehrstufige Prozesse bereitstellen

REQ-020: Das System muss bei erfolgreichem Speichern eine Bestätigungsmeldung für 3 Sekunden einblenden

## Security Requirements

REQ-021: Das System muss Session-Tokens nach 30 Minuten Inaktivität ungültig machen

REQ-022: Die Anwendung muss alle API-Anfragen mit OAuth 2.0 Bearer Token authentifizieren

REQ-023: Das System muss SQL-Injection-Angriffe durch parametrisierte Abfragen verhindern

REQ-024: Die Anwendung muss alle Passwörter mit bcrypt und einem Salt-Wert hashen

REQ-025: Das System muss fehlgeschlagene Authentifizierungsversuche mit IP-Adresse und Zeitstempel protokollieren
