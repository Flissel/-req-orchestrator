# 📋 Browser Extension - Projekt-Fragebogen
## Template: 10-browser-extension (Manifest V3 + React + TypeScript)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Extension Name** | |
| **Kurzbeschreibung** | |
| **Ziel-Browser** | Chrome, Firefox, Edge |

---

## A. EXTENSION-TYP

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| A1 | Haupt-Funktion? | [ ] Page Modifier [ ] Productivity [ ] DevTools [ ] Data Scraper | |
| A2 | Interaktions-Art? | [ ] Popup [ ] Sidebar [ ] Content Script [ ] Background | |
| A3 | Funktioniert auf? | [ ] Alle Seiten [ ] Bestimmte Domains [ ] Nach Aktivierung | |

---

## B. KOMPONENTEN

| # | Frage | Benötigt? | Details |
|---|-------|-----------|---------|
| B1 | Popup? | [ ] Ja [ ] Nein | Click auf Icon | |
| B2 | Options Page? | [ ] Ja [ ] Nein | Einstellungen | |
| B3 | Content Scripts? | [ ] Ja [ ] Nein | In Webseiten injiziert | |
| B4 | Background Worker? | [ ] Ja [ ] Nein | Service Worker | |
| B5 | DevTools Panel? | [ ] Ja [ ] Nein | Im DevTools | |
| B6 | Side Panel? | [ ] Ja [ ] Nein | Chrome Side Panel | |

---

## C. BERECHTIGUNGEN

| # | Permission | Benötigt? | Grund |
|---|------------|-----------|-------|
| C1 | activeTab | [ ] Ja [ ] Nein | Zugriff auf aktiven Tab | |
| C2 | tabs | [ ] Ja [ ] Nein | Tab-Informationen | |
| C3 | storage | [ ] Ja [ ] Nein | Daten speichern | |
| C4 | cookies | [ ] Ja [ ] Nein | Cookie-Zugriff | |
| C5 | notifications | [ ] Ja [ ] Nein | System-Benachrichtigungen | |
| C6 | contextMenus | [ ] Ja [ ] Nein | Rechtsklick-Menü | |
| C7 | webRequest | [ ] Ja [ ] Nein | Netzwerk-Anfragen | |
| C8 | clipboardRead/Write | [ ] Ja [ ] Nein | Zwischenablage | |
| C9 | Host Permissions | [ ] Alle [ ] Bestimmte | Welche Domains? | |

---

## D. TECH-STACK ENTSCHEIDUNGEN

### Framework & Build

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | UI Framework? | [ ] React (default) [ ] Vue [ ] Svelte [ ] Vanilla | |
| D2 | Build Tool? | [ ] Vite (empfohlen) [ ] Webpack [ ] Rollup | |
| D3 | TypeScript? | [ ] Ja (empfohlen) [ ] JavaScript | |
| D4 | Extension Template? | [ ] CRXJS [ ] Plasmo [ ] Custom | |

### Styling

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D5 | Styling? | [ ] Tailwind CSS [ ] CSS Modules [ ] Styled Components | |
| D6 | Icons? | [ ] Heroicons [ ] Lucide [ ] Custom | |
| D7 | Dark Mode? | [ ] Match Browser [ ] Match System [ ] Toggle | |

### State & Storage

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D8 | State Management? | [ ] Zustand [ ] Redux [ ] React Context | |
| D9 | Storage? | [ ] chrome.storage.local [ ] chrome.storage.sync [ ] IndexedDB | |
| D10 | Message Passing? | Content Script ↔ Background | |

---

## E. CROSS-BROWSER

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Chrome? | [ ] Ja [ ] Nein | |
| E2 | Firefox? | [ ] Ja [ ] Nein | |
| E3 | Edge? | [ ] Ja [ ] Nein | |
| E4 | Safari? | [ ] Ja [ ] Nein | |
| E5 | Polyfill? | [ ] webextension-polyfill | |

---

## F. FEATURES

| # | Frage | Benötigt? |
|---|-------|-----------|
| F1 | Keyboard Shortcuts? | [ ] Ja [ ] Nein |
| F2 | Context Menu? | [ ] Ja [ ] Nein |
| F3 | Badge Counter? | [ ] Ja [ ] Nein |
| F4 | Omnibox Integration? | [ ] Ja [ ] Nein |
| F5 | User Script Injection? | [ ] Ja [ ] Nein |
| F6 | External API Calls? | [ ] Ja [ ] Nein |

---

## G. SICHERHEIT

| # | Frage | Antwort |
|---|-------|---------|
| G1 | CSP konfiguriert? | Content Security Policy |
| G2 | XSS Prevention? | Input Sanitization |
| G3 | Minimal Permissions? | Nur was nötig ist |
| G4 | Audit-bereit? | Store Review |

---

## H. TESTING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Unit Tests? | [ ] Vitest [ ] Jest | |
| H2 | E2E Tests? | [ ] Playwright [ ] Puppeteer | |
| H3 | Extension Testing? | [ ] Manual [ ] Automated | |

---

## I. DISTRIBUTION

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| I1 | Chrome Web Store? | [ ] Ja [ ] Nein | |
| I2 | Firefox Add-ons? | [ ] Ja [ ] Nein | |
| I3 | Self-hosted? | [ ] Ja [ ] Nein | |
| I4 | Auto-Updates? | [ ] Store [ ] Self-managed | |
| I5 | Pricing? | [ ] Free [ ] Freemium [ ] Paid | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Manifest.json
- [ ] Popup UI
- [ ] Options Page
- [ ] Content Scripts
- [ ] Background Worker
- [ ] Message Passing
- [ ] Storage Layer
- [ ] Build Config
- [ ] Tests

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "10-browser-extension",
  "manifest": {
    "version": "V3",
    "browsers": ["Chrome", "Firefox", "Edge"]
  },
  "frontend": {
    "framework": "React",
    "language": "TypeScript",
    "styling": "Tailwind CSS",
    "bundler": "Vite + CRXJS"
  },
  "storage": {
    "local": "chrome.storage.local",
    "sync": "chrome.storage.sync"
  },
  "distribution": {
    "store": "Chrome Web Store",
    "updates": "Store-managed"
  }
}
```
