# 📋 Desktop App (Electron) - Projekt-Fragebogen
## Template: 03-desktop-electron (Electron + React + Python Backend)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **App Name** | |
| **Zweck der App** | |
| **Ziel-Plattformen** | Windows, macOS, Linux |

---

## A. APP-TYP & ZWECK

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | Was macht die App? | Datei-Manager, Editor, Dashboard | |
| A2 | Offline-First? | Funktioniert ohne Internet | |
| A3 | Single-Instance? | Nur eine Instanz gleichzeitig | |
| A4 | Portable Version? | Ohne Installation nutzbar | |

---

## B. BENUTZEROBERFLÄCHE

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| B1 | Window Style? | [ ] Standard Frame [ ] Frameless [ ] Custom Titlebar | |
| B2 | System Tray? | [ ] Ja [ ] Nein | |
| B3 | Mehrere Fenster? | [ ] Single Window [ ] Multi Window | |
| B4 | Menübar? | [ ] Standard OS Menü [ ] Custom [ ] Keine | |
| B5 | Keyboard Shortcuts? | Global Hotkeys definieren | |

---

## C. NATIVE FEATURES

| # | Frage | Antwort |
|---|-------|---------|
| C1 | Dateisystem-Zugriff? | Lesen, Schreiben, Dialoge | |
| C2 | Clipboard Integration? | Copy/Paste | |
| C3 | Drag & Drop? | Files, Data | |
| C4 | Notifications? | System Notifications | |
| C5 | Auto-Start? | Mit System starten | |
| C6 | Deep Links? | myapp://action | |
| C7 | Protokoll-Handler? | Custom URL Scheme | |

---

## D. DATEN & SPEICHERUNG

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | Lokale Datenbank? | [ ] SQLite (empfohlen) [ ] LevelDB [ ] JSON Files | |
| D2 | Daten-Location? | [ ] App Data [ ] User Documents [ ] Custom | |
| D3 | Datenmigration? | Zwischen App-Versionen | |
| D4 | Backup/Export? | User-Daten exportieren | |
| D5 | Verschlüsselung? | Sensible lokale Daten | |

---

## E. TECH-STACK ENTSCHEIDUNGEN

### Frontend (Electron + React)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | UI Framework? | [ ] React (default) [ ] Vue [ ] Svelte | |
| E2 | Component Library? | [ ] Radix UI [ ] shadcn/ui [ ] Ant Design [ ] Custom | |
| E3 | Styling? | [ ] Tailwind CSS [ ] CSS Modules [ ] Styled Components | |
| E4 | State Management? | [ ] Zustand [ ] Redux [ ] Jotai | |
| E5 | IPC Pattern? | [ ] Preload Scripts [ ] Context Bridge | |

### Backend (Optional Python)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E6 | Python Backend? | [ ] Ja [ ] Nein (Node.js only) | |
| E7 | Python Kommunikation? | [ ] Child Process [ ] Local Server [ ] PyInstaller Bundle | |
| E8 | Python Framework? | [ ] FastAPI [ ] Flask [ ] None | |

### Build & Distribution

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E9 | Build Tool? | [ ] electron-builder (default) [ ] electron-forge | |
| E10 | Auto-Updater? | [ ] Ja (electron-updater) [ ] Nein | |
| E11 | Code Signing? | [ ] Ja [ ] Nein (Dev only) | |
| E12 | Installer Type? | [ ] NSIS (Windows) [ ] DMG (Mac) [ ] AppImage (Linux) | |

---

## F. SICHERHEIT

| # | Frage | Antwort |
|---|-------|---------|
| F1 | Node Integration? | Disabled (empfohlen) | |
| F2 | Context Isolation? | Enabled (empfohlen) | |
| F3 | Remote Content? | Lädt externe Inhalte? | |
| F4 | Sandbox? | Renderer Sandbox | |
| F5 | CSP Header? | Content Security Policy | |

---

## G. PERFORMANCE

| # | Frage | Antwort |
|---|-------|---------|
| G1 | Startup Zeit Ziel? | < 2s, < 5s | |
| G2 | Memory Budget? | Max. RAM Nutzung | |
| G3 | Background Tasks? | Worker Threads | |
| G4 | Lazy Loading? | Module on-demand | |

---

## H. TESTING & DEBUGGING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | E2E Tests? | [ ] Playwright [ ] Spectron [ ] None | |
| H2 | Unit Tests? | [ ] Vitest [ ] Jest | |
| H3 | DevTools? | [ ] Enabled in Dev [ ] Disabled | |
| H4 | Crash Reporting? | [ ] Sentry [ ] Built-in [ ] None | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Electron Main Process
- [ ] Preload Scripts
- [ ] React Components
- [ ] IPC Handlers
- [ ] SQLite Setup
- [ ] Auto-Updater Config
- [ ] Build Scripts
- [ ] Installer Config

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "03-desktop-electron",
  "frontend": {
    "framework": "Electron",
    "ui": "React",
    "bundler": "Vite",
    "language": "TypeScript"
  },
  "backend": {
    "runtime": "Node.js / Python (optional)",
    "ipc": "Electron IPC"
  },
  "database": {
    "type": "SQLite",
    "driver": "better-sqlite3"
  },
  "deployment": {
    "builder": "electron-builder",
    "platforms": ["Windows", "macOS", "Linux"]
  }
}
```
