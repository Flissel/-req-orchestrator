# 📋 Web Application - Projekt-Fragebogen
## Template: 01-web-app (Next.js 14 + Prisma + PostgreSQL)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Projektname** | |
| **Elevator Pitch** | |
| **Zielgruppe** | |

---

## A. BUSINESS KONTEXT

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | Was ist der Hauptzweck der App? | z.B. "E-Commerce für Kunstwerke", "SaaS Dashboard" | |
| A2 | Welche Branche/Domäne? | E-Commerce, FinTech, HealthTech, HR, Education | |
| A3 | Regulatorische Anforderungen? | DSGVO, PCI-DSS, HIPAA | |
| A4 | Erfolgsmetriken (KPIs)? | DAU, Conversion Rate, Revenue | |

---

## B. BENUTZER & ROLLEN

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| B1 | Welche Benutzerrollen gibt es? | Admin, User, Moderator, Guest | |
| B2 | Erwartete Benutzerzahl? | 10, 100, 1.000, 10.000+ | |
| B3 | Berechtigungen pro Rolle? | Admin: CRUD all, User: Read own | |
| B4 | Registrierung wie? | Self-Service, Einladung, SSO | |
| B5 | Multi-Tenancy nötig? | Jede Firma sieht nur eigene Daten | |

---

## C. AUTHENTIFIZIERUNG

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| C1 | Login-Methoden? | [ ] Email/Passwort [ ] Google OAuth [ ] GitHub [ ] Microsoft SSO [ ] Magic Link | |
| C2 | MFA erforderlich? | [ ] Nein [ ] Optional [ ] Pflicht | |
| C3 | Session-Dauer? | 15min / 24h / 30 Tage | |
| C4 | Passwort-Richtlinien? | Min. Länge, Sonderzeichen | |

---

## D. KERN-FEATURES

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| D1 | Top 5 Features? | 1. ... 2. ... 3. ... 4. ... 5. ... | |
| D2 | Haupt-Entitäten? | User, Product, Order, etc. | |
| D3 | Welche CRUD-Operationen? | Pro Entität: Create/Read/Update/Delete | |
| D4 | Suchfunktion benötigt? | Volltext, Filter, Autocomplete | |
| D5 | Dashboard/Reports? | Welche Metriken visualisieren? | |
| D6 | Import/Export? | CSV, Excel, PDF | |

---

## E. DATENMODELL

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| E1 | Hauptentitäten auflisten | Mit Feldern und Typen | |
| E2 | Beziehungen? | 1:n, n:m zwischen Entitäten | |
| E3 | Sensible Daten? | Passwörter, Zahlungsdaten, PII | |
| E4 | Soft-Delete oder Hard-Delete? | Daten behalten oder löschen | |

---

## F. TECH-STACK ENTSCHEIDUNGEN

### Frontend (Next.js)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| F1 | UI Component Library? | [ ] shadcn/ui (empfohlen) [ ] Radix UI [ ] Chakra UI [ ] Material UI [ ] Custom | |
| F2 | Styling? | [ ] Tailwind CSS (default) [ ] CSS Modules [ ] Styled Components | |
| F3 | State Management? | [ ] React Query (empfohlen) [ ] Zustand [ ] Redux [ ] Context only | |
| F4 | Form Library? | [ ] React Hook Form (empfohlen) [ ] Formik [ ] Native | |
| F5 | Dark Mode? | [ ] Ja [ ] Nein [ ] System-basiert | |

### Backend (Next.js API Routes + Prisma)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| F6 | API Stil? | [ ] tRPC (empfohlen) [ ] REST API Routes [ ] GraphQL | |
| F7 | Validierung? | [ ] Zod (empfohlen) [ ] Yup [ ] Joi | |
| F8 | Auth Provider? | [ ] NextAuth.js (default) [ ] Clerk [ ] Auth0 [ ] Supabase Auth | |
| F9 | File Uploads? | [ ] Nein [ ] UploadThing [ ] AWS S3 [ ] Cloudinary | |
| F10 | Email Service? | [ ] Keiner [ ] Resend [ ] SendGrid [ ] Postmark | |

### Datenbank (PostgreSQL + Prisma)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| F11 | Hosting? | [ ] Docker local (default) [ ] Supabase [ ] Neon [ ] PlanetScale [ ] Railway | |
| F12 | Caching? | [ ] Keins [ ] Redis [ ] Upstash | |
| F13 | Full-Text Search? | [ ] Prisma native [ ] Algolia [ ] Meilisearch [ ] pg_trgm | |

---

## G. UI/UX REQUIREMENTS

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| G1 | Responsive Design? | Mobile-First, Desktop-First | |
| G2 | Welche Seiten/Views? | Landing, Dashboard, Settings, etc. | |
| G3 | Navigation Style? | Sidebar, Topbar, Tabs | |
| G4 | Benötigte Komponenten? | DataTable, Modal, Charts, Calendar | |
| G5 | Mehrsprachigkeit? | DE, EN, weitere? | |
| G6 | Barrierefreiheit (a11y)? | WCAG Level AA | |

---

## H. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Hosting Platform? | [ ] Vercel (empfohlen) [ ] Railway [ ] Render [ ] AWS [ ] Self-hosted | |
| H2 | CI/CD? | [ ] GitHub Actions [ ] Vercel Auto [ ] GitLab CI | |
| H3 | Environments? | [ ] Dev + Prod [ ] Dev + Staging + Prod | |
| H4 | Domain vorhanden? | Eigene Domain oder Subdomain | |

---

## I. INTEGRATIONEN

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| I1 | Payment? | Stripe, PayPal, Klarna | |
| I2 | Analytics? | Vercel Analytics, PostHog, Mixpanel | |
| I3 | Monitoring? | Sentry, LogRocket | |
| I4 | Externe APIs? | Maps, Weather, etc. | |

---

## J. SICHERHEIT

| # | Frage | Antwort |
|---|-------|---------|
| J1 | Rate Limiting nötig? | |
| J2 | CORS-Einschränkungen? | |
| J3 | Audit-Logging? | |
| J4 | Backup-Strategie? | |

---

# 📊 GENERIERUNGSOPTIONEN

Nach Beantwortung der Fragen können folgende Artefakte generiert werden:

- [ ] Prisma Schema (`prisma/schema.prisma`)
- [ ] API Routes / tRPC Router
- [ ] Authentifizierung Setup
- [ ] UI Komponenten
- [ ] Seiten/Views
- [ ] Docker Compose
- [ ] Environment Config
- [ ] README mit Setup-Anleitung

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "01-web-app",
  "frontend": {
    "framework": "Next.js 14",
    "ui": "React 18",
    "styling": "Tailwind CSS",
    "components": "shadcn/ui",
    "state": "React Query",
    "forms": "React Hook Form + Zod"
  },
  "backend": {
    "runtime": "Next.js API Routes",
    "api": "tRPC",
    "auth": "NextAuth.js",
    "validation": "Zod"
  },
  "database": {
    "type": "PostgreSQL",
    "orm": "Prisma",
    "hosting": "Docker / Supabase"
  },
  "deployment": {
    "platform": "Vercel",
    "ci": "GitHub Actions"
  }
}
```
