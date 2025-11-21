# Mixed Requirements Examples - Testing Auto-Validation

This file contains a realistic mix of good and bad requirements to test the validation system's ability to differentiate quality levels.

## User Authentication (Mixed Quality)

REQ-001: Das System muss Benutzer innerhalb von 2 Sekunden nach Eingabe korrekter Anmeldedaten authentifizieren
*Expected: PASS - Clear, measurable, testable*

REQ-002: Die App soll benutzerfreundlich sein
*Expected: FAIL - Vague, not measurable*

REQ-003: Das System muss nach 3 fehlgeschlagenen Login-Versuchen das Benutzerkonto für 15 Minuten sperren
*Expected: PASS - Clear, specific, testable*

REQ-004: User login should be secure
*Expected: FAIL - Language inconsistency, vague*

REQ-005: Die Anwendung muss Passwörter mit mindestens 8 Zeichen, einem Großbuchstaben, einer Ziffer und einem Sonderzeichen verlangen
*Expected: PASS - Specific, testable, atomic*

## Data Management (Mixed Quality)

REQ-006: Das System muss Benutzerdaten verschlüsselt mit AES-256 speichern
*Expected: PASS - Specific encryption standard*

REQ-007: Die Datenbank soll PostgreSQL sein
*Expected: FAIL - Design-dependent*

REQ-008: Die Anwendung muss gelöschte Datensätze für 30 Tage in einem Papierkorb aufbewahren
*Expected: PASS - Clear retention policy*

REQ-009: Das System speichert die Daten
*Expected: FAIL - Ambiguous, missing context*

REQ-010: Das System muss alle Änderungen an Stammdaten mit Zeitstempel und Benutzerkennung protokollieren
*Expected: PASS - Clear audit requirement*

## Performance (Mixed Quality)

REQ-011: Das System muss Suchanfragen innerhalb von 500 Millisekunden beantworten
*Expected: PASS - Measurable, specific*

REQ-012: Die Ladezeit soll kurz sein
*Expected: FAIL - Not measurable*

REQ-013: Die Anwendung muss 1000 gleichzeitige Benutzer ohne Leistungsverlust unterstützen
*Expected: PASS - Specific load requirement*

REQ-014: Die App muss schnell sein
*Expected: FAIL - Vague, not measurable*

REQ-015: Das System muss Datenbankabfragen mit maximal 200 Millisekunden Latenz ausführen
*Expected: PASS - Clear performance metric*

## Interface & Integration (Mixed Quality)

REQ-016: Das System muss eine REST-API mit JSON-Format für externe Systeme bereitstellen
*Expected: PASS - Clear interface specification*

REQ-017: Die App muss React verwenden
*Expected: FAIL - Design-dependent*

REQ-018: Das System muss Formularfelder bei ungültiger Eingabe rot markieren und eine Beschreibung des Fehlers anzeigen
*Expected: PASS - Clear UX requirement (color is for contrast, not design)*

REQ-019: Der Button muss blau sein und rechts oben platziert werden
*Expected: FAIL - Design-dependent*

REQ-020: Die Anwendung muss Fehlermeldungen in deutscher Sprache mit eindeutigen Fehlercodes anzeigen
*Expected: PASS - Clear localization requirement*

## Complex Requirements (Mixed Quality)

REQ-021: Das System muss Daten speichern, anzeigen, bearbeiten und löschen können
*Expected: FAIL - Non-atomic (multiple concerns)*

REQ-022: Das System muss Session-Tokens nach 30 Minuten Inaktivität ungültig machen
*Expected: PASS - Specific security requirement*

REQ-023: Als ein Benutzer der Anwendung möchte ich in der Lage sein, mich mit meinem Benutzernamen und meinem Passwort anzumelden, wobei das System überprüfen soll, ob meine Anmeldedaten korrekt sind, und wenn ja, dann soll ich Zugang zum System erhalten
*Expected: FAIL - Too verbose*

REQ-024: Die Anwendung muss alle API-Anfragen mit OAuth 2.0 Bearer Token authentifizieren
*Expected: PASS - Clear security standard*

REQ-025: Das System muss für das Marketing-Team Reports generieren
*Expected: FAIL - Purpose-dependent*

## Expected Results Summary
- Total: 25 requirements
- Expected PASS: 13 requirements
- Expected FAIL: 12 requirements
- Pass rate: ~52% (realistic mixed scenario)
