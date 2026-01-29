# {{PROJECT_NAME}} - Setup Guide

## Electron Desktop App mit Python Backend

Diese Anleitung führt durch die Einrichtung einer Cross-Platform Desktop-Anwendung.

---

## 📋 Voraussetzungen

- [ ] Node.js 20+ installiert
- [ ] Python 3.12+ installiert (für Backend)
- [ ] npm oder yarn
- [ ] VS Code mit Extensions: ESLint, Prettier, Python

---

## 🚀 Schritt-für-Schritt Einrichtung

### Schritt 1: Projekt initialisieren

```bash
cd {{PROJECT_NAME_KEBAB}}
npm install
```

### Schritt 2: Python Backend (optional)

```bash
cd python-backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
pip install -r requirements.txt
```

### Schritt 3: Development-Modus starten

```bash
# Terminal 1 - Electron App
npm run dev

# Terminal 2 - Python Backend (optional)
cd python-backend
python main.py
```

### Schritt 4: Electron App testen

Die App öffnet sich automatisch im Development-Modus.

### Schritt 5: Production Build erstellen

```bash
# Windows
npm run build:win

# macOS
npm run build:mac

# Linux
npm run build:linux

# Alle Plattformen
npm run build:all
```

---

## 📁 Projektstruktur

```
{{PROJECT_NAME_KEBAB}}/
├── electron/              # Electron Main Process
│   ├── main.ts           # Main entry point
│   ├── preload.ts        # Preload script
│   └── ipc/              # IPC handlers
├── src/                   # React Frontend
│   ├── App.tsx           # Main App component
│   ├── components/       # UI Components
│   └── lib/              # Utilities
├── python-backend/        # Python Backend (optional)
│   ├── main.py           # Backend entry
│   └── api/              # API routes
├── electron-builder.yml  # Build configuration
└── package.json
```

---

## 🧪 Tests

```bash
# Unit Tests
npm run test

# E2E Tests
npm run test:e2e
```

---

## 📦 Build-Artefakte

Nach dem Build findest du die Installer in:

- Windows: `dist/{{PROJECT_NAME_KEBAB}} Setup.exe`
- macOS: `dist/{{PROJECT_NAME_KEBAB}}.dmg`
- Linux: `dist/{{PROJECT_NAME_KEBAB}}.AppImage`

---

## ✅ Checkliste

- [ ] Dependencies installiert
- [ ] App startet im Dev-Modus
- [ ] IPC Kommunikation funktioniert
- [ ] SQLite Datenbank funktioniert
- [ ] Production Build erstellt
- [ ] Auto-Updater konfiguriert (optional)