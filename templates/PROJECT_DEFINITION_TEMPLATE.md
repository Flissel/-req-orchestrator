# 📘 Projekt-Definition Template
## Kontextreiche Anforderungserfassung für Software-Projekte

> **Zweck**: Dieses Template hilft, alle relevanten Informationen für ein Software-Projekt strukturiert zu erfassen. Die Antworten bilden die Grundlage für präzise Requirements, die von KI-Systemen oder Entwicklungsteams verarbeitet werden können.

---

## 🚀 QUICK-START: Projekt-Steckbrief

*Fülle zuerst diese 5 Kernfragen aus, bevor du in die Details gehst:*

| Feld | Deine Antwort |
|------|---------------|
| **Projektname** | |
| **Elevator Pitch** (1-2 Sätze: Was macht die App?) | |
| **Zielgruppe** (Wer nutzt es primär?) | |
| **Hauptproblem** (Welches Problem wird gelöst?) | |
| **Erfolgsmetrik** (Woran misst du Erfolg?) | |

---

# 📋 VOLLSTÄNDIGER FRAGEN-KATALOG

## Legende
- 🔴 **MUST** = Kritisch für MVP
- 🟡 **SHOULD** = Wichtig für v1.0
- 🟢 **NICE** = Kann später kommen
- 💡 = Beispiel/Hinweis

---

## A. BUSINESS & DOMAIN KONTEXT
*Warum wichtig: Ohne klaren Business-Kontext werden technische Entscheidungen im Vakuum getroffen.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| A1 | 🔴 | Was ist der Hauptzweck der Anwendung? | 💡 "Verkürzung der Bestellzeit um 50%" statt "Online-Shop" | |
| A2 | 🔴 | Wer ist der Auftraggeber/Stakeholder? | 💡 Intern (Marketing-Team) oder Extern (Kunde XY GmbH) | |
| A3 | 🔴 | In welcher Branche/Domäne? | 💡 E-Commerce, HealthTech, FinTech, Logistik, HR, Education | |
| A4 | 🟡 | Bestehende Systeme zum Ersetzen/Integrieren? | 💡 "Ablösung von Excel-Listen" oder "Integration mit SAP" | |
| A5 | 🟡 | Was ist das USP (Alleinstellungsmerkmal)? | 💡 Was macht es anders als Konkurrenzprodukte? | |
| A6 | 🔴 | Welche Geschäftsprozesse werden unterstützt? | 💡 Bestellung → Zahlung → Versand → Retoure | |
| A7 | 🔴 | Regulatorische Anforderungen? | 💡 DSGVO, HIPAA, PCI-DSS, ISO 27001, GoBD | |
| A8 | 🟡 | Geplanter Go-Live Zeitraum? | 💡 MVP in 3 Monaten, Full-Release in 6 Monaten | |
| A9 | 🟡 | Budget-Constraints (Hosting/Infra)? | 💡 Max. 500€/Monat für Cloud, oder "kosten-sensitiv" | |
| A10 | 🔴 | Erfolgsmetriken (KPIs)? | 💡 DAU, Conversion Rate, NPS, Time-to-Value | |

---

## B. BENUTZER & ROLLEN
*Warum wichtig: Jede Funktion sollte einem konkreten Benutzer dienen.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| B1 | 🔴 | Welche Benutzertypen/Rollen gibt es? | 💡 Admin, Manager, Mitarbeiter, Kunde, Gast | |
| B2 | 🔴 | Erwartete Benutzeranzahl (initial)? | 💡 10, 100, 1.000, 10.000+ | |
| B3 | 🟡 | Erwartete Benutzeranzahl (12 Monate)? | 💡 Wachstumsfaktor 2x, 5x, 10x? | |
| B4 | 🔴 | Berechtigungen pro Rolle? | 💡 Admin: CRUD all, User: Read own, Manager: Read team | |
| B5 | 🟡 | Rollen-Hierarchie? | 💡 CEO > Manager > Team Lead > Mitarbeiter | |
| B6 | 🟢 | Mehrere Rollen pro Benutzer? | 💡 Ja: User ist gleichzeitig Admin in Projekt A | |
| B7 | 🔴 | Wie erfolgt Registrierung? | 💡 Self-Service, Einladung per Email, CSV-Import, SSO | |
| B8 | 🟡 | Gibt es Gastbenutzer/öffentliche Bereiche? | 💡 Produkte ohne Login ansehen, aber Warenkorb braucht Account | |
| B9 | 🟡 | Welche Profildaten werden erfasst? | 💡 Name, Email, Avatar, Abteilung, Telefon, Adresse | |
| B10 | 🟡 | Multi-Tenancy (Mandantenfähigkeit)? | 💡 Jede Firma sieht nur eigene Daten, getrennte DBs/Schemas | |
| B11 | 🟢 | Behandlung inaktiver Benutzer? | 💡 Auto-Logout nach 30 Tagen, Account-Deaktivierung | |
| B12 | 🟡 | Benutzergruppen oder Teams? | 💡 Marketing-Team, Entwicklung, Sales | |

---

## C. AUTHENTIFIZIERUNG & AUTORISIERUNG
*Warum wichtig: Sicherheit beginnt beim Login.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| C1 | 🔴 | Login-Methoden? | 💡 Email/Passwort, Google OAuth, Microsoft SSO, Magic Link | |
| C2 | 🟡 | Multi-Faktor-Authentifizierung (MFA)? | 💡 SMS, Authenticator App, Hardware Key | |
| C3 | 🟡 | Identity Provider Integration? | 💡 Azure AD, Okta, Auth0, Keycloak | |
| C4 | 🟡 | Session-Dauer? | 💡 15 Min (Bank), 24h (App), 30 Tage (Social) | |
| C5 | 🟢 | "Remember Me" Funktionalität? | 💡 Persistenter Login auf vertrautem Gerät | |
| C6 | 🔴 | Passwort-Reset Prozess? | 💡 Email-Link, Security Questions, Admin-Reset | |
| C7 | 🟡 | Passwort-Richtlinien? | 💡 Min. 8 Zeichen, 1 Großbuchstabe, 1 Sonderzeichen | |
| C8 | 🟡 | Login-Versuch-Limitierung? | 💡 5 Versuche, dann 15 Min Sperre | |
| C9 | 🟢 | IP-Whitelisting/Geo-Blocking? | 💡 Nur aus Deutschland, nur aus Firmennetz | |
| C10 | 🟡 | API-Token Management? | 💡 JWT, API Keys mit Ablaufdatum, OAuth2 Client Credentials | |

---

## D. KERN-FUNKTIONALITÄT
*Warum wichtig: Das Herzstück der Anwendung - hier entsteht der Mehrwert.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| D1 | 🔴 | Top 5 Features/Use Cases? | 💡 1. Produkt suchen 2. In Warenkorb 3. Bestellen 4. Bezahlen 5. Tracken | |
| D2 | 🔴 | CRUD-Operationen pro Entität? | 💡 Produkt: Create(Admin), Read(All), Update(Admin), Delete(Admin) | |
| D3 | 🟡 | Workflows/Prozesse? | 💡 Antrag → Genehmigung → Freigabe → Abschluss | |
| D4 | 🟡 | Suchfunktionen? | 💡 Volltext mit Elasticsearch, Facetten-Filter, Autocomplete | |
| D5 | 🟡 | Import/Export? | 💡 CSV-Import für Produkte, Excel-Export für Reports, PDF-Rechnungen | |
| D6 | 🟡 | Berichte/Dashboards? | 💡 Umsatz-Dashboard, User-Aktivität, Performance-Metriken | |
| D7 | 🟢 | Batch-Operationen? | 💡 Alle ausgewählten Produkte auf "inaktiv" setzen | |
| D8 | 🟡 | Sortierung & Filterung? | 💡 Nach Datum, Preis, Relevanz; Filter: Kategorie, Status, Preisspanne | |
| D9 | 🟢 | Versionierung/History? | 💡 Änderungshistorie für Dokumente, Audit-Trail | |
| D10 | 🟢 | Kommentare/Annotationen? | 💡 Kommentare an Aufgaben, Notizen an Kunden | |
| D11 | 🟢 | Favoriten/Bookmarks? | 💡 Produkte merken, häufig genutzte Reports pinnen | |
| D12 | 🟢 | Drag-and-Drop? | 💡 Kanban-Board, Sortierung per Drag, Datei-Upload | |
| D13 | 🟡 | Kalender/Termine? | 💡 Terminbuchung, Verfügbarkeitskalender, Erinnerungen | |
| D14 | 🟡 | Tags/Kategorien? | 💡 Produkt-Tags, Ticket-Labels, hierarchische Kategorien | |
| D15 | 🟢 | Vorlagen/Templates? | 💡 Email-Templates, Projekt-Vorlagen, Report-Templates | |

---

## E. DATENMODELL & ENTITÄTEN
*Warum wichtig: Ein gutes Datenmodell ist das Fundament für Erweiterbarkeit.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| E1 | 🔴 | Hauptentitäten? | 💡 User, Product, Order, Invoice, Category | |
| E2 | 🔴 | Beziehungen zwischen Entitäten? | 💡 User 1:n Orders, Product n:m Categories, Order 1:n OrderItems | |
| E3 | 🔴 | Pflichtfelder pro Entität? | 💡 User: email (unique), Product: name, price | |
| E4 | 🟡 | Berechnete/abgeleitete Felder? | 💡 Order.total = SUM(items.price * items.quantity) | |
| E5 | 🟡 | Datentypen? | 💡 String, Integer, Decimal(10,2), DateTime, JSON, BLOB | |
| E6 | 🟡 | Soft-Delete vs Hard-Delete? | 💡 Soft: deleted_at Timestamp, Hard: Physisch löschen | |
| E7 | 🟡 | Unique Constraints? | 💡 User.email, Product.sku, Order.number | |
| E8 | 🟢 | Hierarchische Daten? | 💡 Kategorien mit Parent-Child, Org-Chart, Kommentar-Threads | |
| E9 | 🔴 | Verschlüsselte Felder? | 💡 Passwörter (Hash), Kreditkarten, Gesundheitsdaten | |
| E10 | 🟢 | Daten mit TTL (Ablaufdatum)? | 💡 Session-Tokens, Verification-Links, temporäre Uploads | |

---

## F. API & BACKEND
*Warum wichtig: Die API definiert, wie Frontend und externe Systeme kommunizieren.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| F1 | 🔴 | API-Stil? | 💡 REST, GraphQL, gRPC, oder Hybrid (REST + GraphQL) | |
| F2 | 🟡 | API-Versionierung? | 💡 URL (/api/v1/), Header (Accept-Version), Query (?v=1) | |
| F3 | 🟡 | Rate Limiting? | 💡 100 req/min für Free, 1000 req/min für Premium | |
| F4 | 🔴 | Response-Format? | 💡 JSON (Standard), XML (Legacy), Protocol Buffers (Performance) | |
| F5 | 🔴 | Pagination? | 💡 Offset-based (?page=2&limit=20), Cursor-based (after=xyz) | |
| F6 | 🟡 | HTTP-Statuscodes? | 💡 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found | |
| F7 | 🟡 | Webhooks? | 💡 Bei Bestellung, bei Zahlung, bei Statusänderung | |
| F8 | 🟡 | API-Dokumentation? | 💡 OpenAPI/Swagger, Postman Collection, GraphQL Playground | |
| F9 | 🟡 | Async Operations? | 💡 Report-Generierung, Email-Versand, Video-Konvertierung | |
| F10 | 🟡 | Caching-Strategie? | 💡 Redis für Sessions, CDN für Assets, HTTP Cache-Headers | |

---

## G. FRONTEND & UI
*Warum wichtig: Die UI bestimmt die User Experience und Akzeptanz.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| G1 | 🔴 | Plattform(en)? | 💡 Web-Only, Web + iOS + Android, Desktop (Electron) | |
| G2 | 🟡 | Browser-Support? | 💡 Evergreen (Chrome, Firefox, Edge), IE11 (Legacy), Safari | |
| G3 | 🔴 | Responsive Design? | 💡 Mobile-First, Desktop-First, oder Fixed-Width | |
| G4 | 🟡 | Design System vorhanden? | 💡 Material UI, Ant Design, Custom, Figma-Files | |
| G5 | 🔴 | Benötigte UI-Komponenten? | 💡 DataTable, Forms, Modal, Sidebar, Charts, Calendar | |
| G6 | 🟢 | Dark Mode? | 💡 Automatisch (System), Toggle, oder nur Light | |
| G7 | 🟡 | Mehrsprachigkeit (i18n)? | 💡 DE + EN, dynamisch erweiterbar, RTL-Support (Arabisch) | |
| G8 | 🟡 | Barrierefreiheit (a11y)? | 💡 WCAG 2.1 AA, Screen-Reader Support, Keyboard Navigation | |
| G9 | 🟢 | Animationen? | 💡 Subtle (Hover, Transitions), Rich (Lottie), oder keine | |
| G10 | 🟢 | Offline-Funktionalität? | 💡 Service Worker, lokaler Cache, Sync bei Reconnect | |
| G11 | 🟡 | Real-Time Updates? | 💡 WebSocket für Chat, SSE für Notifications, Polling als Fallback | |
| G12 | 🟡 | Print/PDF Export? | 💡 Print-CSS, Server-side PDF (Puppeteer), Client-side (jsPDF) | |

---

## H. DATEI- & MEDIEN-HANDLING
*Warum wichtig: Dateien sind oft größter Speicher- und Performance-Faktor.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| H1 | 🟡 | Erlaubte Dateitypen? | 💡 Bilder (jpg, png, webp), Dokumente (pdf, docx), Videos (mp4) | |
| H2 | 🟡 | Größenbeschränkungen? | 💡 Bilder max. 5MB, Dokumente max. 20MB, Videos max. 500MB | |
| H3 | 🟢 | Bildverarbeitung? | 💡 Auto-Resize, Thumbnail-Generierung, WebP-Konvertierung | |
| H4 | 🟡 | Speicherort? | 💡 AWS S3, Azure Blob, Google Cloud Storage, lokal + CDN | |
| H5 | 🟢 | Virus-Scanning? | 💡 ClamAV, CloudFlare, VirusTotal API | |
| H6 | 🟢 | Aufbewahrungsdauer? | 💡 User-Uploads: unbegrenzt, Temp-Files: 24h, Logs: 90 Tage | |

---

## I. BENACHRICHTIGUNGEN & KOMMUNIKATION
*Warum wichtig: Gute Benachrichtigungen erhöhen Engagement und Retention.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| I1 | 🔴 | Email-Benachrichtigungen? | 💡 Willkommen, Passwort-Reset, Bestellbestätigung, Wöchentlicher Digest | |
| I2 | 🟡 | Push-Notifications? | 💡 Web Push (Service Worker), Mobile Push (FCM/APNs) | |
| I3 | 🟡 | In-App Notifications? | 💡 Bell-Icon mit Counter, Toast-Messages, Notification Center | |
| I4 | 🟢 | SMS-Benachrichtigungen? | 💡 2FA-Codes, kritische Alerts, Lieferstatus | |
| I5 | 🟡 | Notification-Präferenzen? | 💡 User kann pro Kanal und Typ an/aus schalten | |
| I6 | 🟢 | Newsletter/Marketing? | 💡 Mailchimp, SendGrid, eigenes System | |
| I7 | 🟡 | User-to-User Messaging? | 💡 Direct Messages, Kommentare, @Mentions | |
| I8 | 🟢 | Team-Tool Integration? | 💡 Slack, Microsoft Teams, Discord Webhooks | |

---

## J. EXTERNE INTEGRATIONEN
*Warum wichtig: Selten existiert Software isoliert - Integrationen schaffen Mehrwert.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| J1 | 🟡 | Externe APIs? | 💡 Maps (Google, Mapbox), Weather, Currency Exchange | |
| J2 | 🟡 | Payment-Integration? | 💡 Stripe, PayPal, Klarna, SEPA-Lastschrift | |
| J3 | 🟢 | Kalender-Integration? | 💡 Google Calendar, Outlook/Exchange, CalDAV | |
| J4 | 🟡 | CRM/ERP-Integration? | 💡 Salesforce, HubSpot, SAP, Microsoft Dynamics | |
| J5 | 🟡 | Analytics? | 💡 Google Analytics, Mixpanel, Amplitude, Plausible | |
| J6 | 🟢 | Social Media? | 💡 Facebook Login, Twitter Share, Instagram Feed | |

---

## K. PERFORMANCE & SKALIERUNG
*Warum wichtig: Langsame Apps werden nicht genutzt.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| K1 | 🟡 | Requests/Sekunde (initial)? | 💡 10 (intern), 100 (B2B), 1000+ (B2C) | |
| K2 | 🟡 | Requests/Sekunde (Peak)? | 💡 Black Friday: 10x normal, Newsletter: 5x normal | |
| K3 | 🔴 | Max. akzeptable Latenz? | 💡 API: <200ms, Page Load: <3s, Search: <500ms | |
| K4 | 🟡 | Erwartete DB-Größe? | 💡 1GB (klein), 100GB (mittel), 1TB+ (groß) | |
| K5 | 🟢 | Saisonale Spitzen? | 💡 Weihnachten, Schulanfang, Quartalsende | |
| K6 | 🟡 | Horizontale Skalierung? | 💡 Auto-Scaling bei >80% CPU, min 2 - max 10 Instanzen | |
| K7 | 🟢 | Geografische Verteilung? | 💡 Single Region (EU), Multi-Region (EU + US), Global (CDN) | |
| K8 | 🟡 | Verfügbarkeits-SLA? | 💡 99% (3.6 Tage/Jahr Down), 99.9% (8.7h), 99.99% (52min) | |

---

## L. SICHERHEIT
*Warum wichtig: Ein Sicherheitsvorfall kann das Projekt zerstören.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| L1 | 🟢 | Penetration Testing? | 💡 Jährlich extern, vor jedem Major Release, Bug Bounty | |
| L2 | 🔴 | Besonders schützenswerte Daten? | 💡 PII, Finanzdaten, Gesundheitsdaten, Geschäftsgeheimnisse | |
| L3 | 🟡 | Audit-Logging? | 💡 Wer hat wann was geändert, Login-History, Admin-Aktionen | |
| L4 | 🔴 | HTTPS-Only? | 💡 Ja, mit HSTS, inkl. Redirect von HTTP | |
| L5 | 🟡 | CORS-Einschränkungen? | 💡 Nur eigene Domain, oder auch partner.example.com | |
| L6 | 🟡 | Security Headers? | 💡 CSP, X-Frame-Options, X-Content-Type-Options | |
| L7 | 🟢 | DDoS-Protection? | 💡 Cloudflare, AWS Shield, Rate Limiting | |
| L8 | 🔴 | Secrets Management? | 💡 HashiCorp Vault, AWS Secrets Manager, Environment Variables | |

---

## M. DEPLOYMENT & INFRASTRUKTUR
*Warum wichtig: Gutes DevOps ermöglicht schnelle, sichere Releases.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| M1 | 🔴 | Cloud Provider? | 💡 AWS, Azure, GCP, Hetzner, On-Premise, Hybrid | |
| M2 | 🟡 | Container-Orchestrierung? | 💡 Kubernetes, Docker Compose, ECS, Cloud Run | |
| M3 | 🔴 | CI/CD? | 💡 GitHub Actions, GitLab CI, Jenkins, CircleCI | |
| M4 | 🟡 | Environments? | 💡 Dev, Staging, Production; oder auch QA, UAT | |
| M5 | 🟢 | Deployment-Strategie? | 💡 Rolling Update, Blue/Green, Canary, Feature Flags | |
| M6 | 🟡 | Konfigurations-Management? | 💡 .env Files, Secrets Manager, ConfigMaps | |
| M7 | 🟢 | Infrastructure-as-Code? | 💡 Terraform, Pulumi, CloudFormation, Ansible | |
| M8 | 🔴 | Backup-Strategie? | 💡 Täglich automatisch, 30 Tage Retention, Cross-Region | |
| M9 | 🟡 | Disaster Recovery? | 💡 RTO: 4h, RPO: 1h, Failover-Region | |
| M10 | 🟡 | Monitoring/Alerting? | 💡 Prometheus + Grafana, Datadog, New Relic, PagerDuty | |

---

## N. TESTING & QUALITÄT
*Warum wichtig: Tests sind die Versicherung gegen Regressions.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| N1 | 🟡 | Test-Coverage Ziel? | 💡 70% Unit, 50% Integration, kritische Pfade 100% | |
| N2 | 🟡 | E2E-Tests? | 💡 Cypress, Playwright, Selenium für Happy Paths | |
| N3 | 🟢 | Performance-Tests? | 💡 k6, JMeter, Artillery vor Major Releases | |
| N4 | 🟡 | Security-Tests? | 💡 OWASP ZAP, SonarQube, Snyk für Dependencies | |
| N5 | 🟡 | UAT-Prozess? | 💡 Staging-Umgebung, Test-Accounts, Feedback-Formular | |
| N6 | 🔴 | Code Review? | 💡 PR-Reviews, mindestens 1 Approval, keine self-merges | |

---

## O. DOKUMENTATION & SUPPORT
*Warum wichtig: Dokumentation reduziert Support-Aufwand und Onboarding-Zeit.*

| # | Prio | Frage | Hinweis/Beispiel | Antwort |
|---|------|-------|------------------|---------|
| O1 | 🟡 | Benötigte Dokumentation? | 💡 User Guide, API Docs, Admin-Handbuch, Entwickler-Setup | |
| O2 | 🟢 | In-App Hilfe? | 💡 Tooltips, Guided Tours, Context-sensitive Help | |
| O3 | 🟡 | Support-Kanal? | 💡 Email, Ticket-System (Zendesk, Freshdesk), Live-Chat | |
| O4 | 🟢 | Schulungen? | 💡 Video-Tutorials, Webinare, Vor-Ort-Schulung | |

---

# 📊 ZUSAMMENFASSUNG

| Kategorie | Fragen | 🔴 MUST | 🟡 SHOULD | 🟢 NICE |
|-----------|--------|---------|-----------|---------|
| A. Business & Domain | 10 | 5 | 4 | 1 |
| B. Benutzer & Rollen | 12 | 4 | 6 | 2 |
| C. Authentifizierung | 10 | 2 | 6 | 2 |
| D. Kern-Funktionalität | 15 | 2 | 7 | 6 |
| E. Datenmodell | 10 | 4 | 4 | 2 |
| F. API & Backend | 10 | 3 | 7 | 0 |
| G. Frontend & UI | 12 | 3 | 6 | 3 |
| H. Datei-Handling | 6 | 0 | 3 | 3 |
| I. Benachrichtigungen | 8 | 1 | 4 | 3 |
| J. Externe Integrationen | 6 | 0 | 4 | 2 |
| K. Performance | 8 | 1 | 5 | 2 |
| L. Sicherheit | 8 | 3 | 3 | 2 |
| M. Deployment | 10 | 3 | 5 | 2 |
| N. Testing | 6 | 1 | 4 | 1 |
| O. Dokumentation | 4 | 0 | 2 | 2 |
| **TOTAL** | **135** | **32** | **70** | **33** |

---

# 📖 GLOSSAR

| Begriff | Erklärung |
|---------|-----------|
| **MVP** | Minimum Viable Product - kleinste Version mit Kernfunktion |
| **CRUD** | Create, Read, Update, Delete - Basis-Operationen |
| **SSO** | Single Sign-On - einmal einloggen, überall angemeldet |
| **MFA/2FA** | Multi-Factor / Two-Factor Authentication |
| **REST** | Representational State Transfer - API-Architekturstil |
| **GraphQL** | Query-Sprache für APIs mit flexiblen Abfragen |
| **JWT** | JSON Web Token - Token-basierte Authentifizierung |
| **CDN** | Content Delivery Network - geografisch verteilte Caches |
| **CI/CD** | Continuous Integration / Continuous Deployment |
| **SLA** | Service Level Agreement - garantierte Verfügbarkeit |
| **RTO** | Recovery Time Objective - max. Ausfallzeit |
| **RPO** | Recovery Point Objective - max. Datenverlust |
| **CORS** | Cross-Origin Resource Sharing - Browser-Sicherheit |
| **a11y** | Accessibility - Barrierefreiheit |
| **i18n** | Internationalization - Mehrsprachigkeit |

---

# 🎯 NUTZUNGSHINWEISE

## Für MVP (Minimum Viable Product)
Fokussiere auf alle 🔴 MUST Fragen (32 Stück). Das ergibt ein solides Grundgerüst.

## Für v1.0 Release
Beantworte zusätzlich alle 🟡 SHOULD Fragen (70 Stück). Das deckt 90% der typischen Anforderungen ab.

## Für Enterprise/Vollversion
Gehe auch alle 🟢 NICE Fragen durch (33 Stück). Das ergibt ein vollständiges Bild.

## Tipps für gute Antworten
1. **Konkret statt vage**: "max. 200ms" statt "schnell"
2. **Zahlen nennen**: "100 User, 1000 in 12 Monaten" statt "einige"
3. **Beispiele geben**: "wie bei Amazon" oder "ähnlich Trello"
4. **Bei Unsicherheit**: "Noch unklar - muss recherchiert werden" ist besser als raten

---

# 📝 PROJEKT AUSFÜLLEN

**Projektname**: _______________________________________________

**Kurzbeschreibung**: _______________________________________________

**Projekttyp**: [ ] Web-App [ ] Mobile-App [ ] API-Service [ ] Desktop-App [ ] Andere: _______

**Timeline**: MVP bis _______ | v1.0 bis _______

---

*Beginne mit dem Quick-Start Steckbrief oben und arbeite dich dann durch die Kategorien A-O.*
