# {{PROJECT_NAME}} - Setup Guide

## Mobile App mit Expo (iOS + Android)

Diese Anleitung führt durch die Einrichtung einer Cross-Platform Mobile App.

---

## 📋 Voraussetzungen

- [ ] Node.js 20+ installiert
- [ ] Expo Go App auf Smartphone installiert
  - [iOS App Store](https://apps.apple.com/app/expo-go/id982107779)
  - [Google Play Store](https://play.google.com/store/apps/details?id=host.exp.exponent)
- [ ] npm oder yarn

---

## 🚀 Schritt-für-Schritt Einrichtung

### Schritt 1: Projekt initialisieren

```bash
cd {{PROJECT_NAME_KEBAB}}
npm install
```

### Schritt 2: Development-Server starten

```bash
npx expo start
```

Ein QR-Code erscheint im Terminal.

### Schritt 3: App auf Smartphone testen

1. Öffne die **Expo Go** App
2. Scanne den QR-Code
3. Die App wird automatisch geladen

### Schritt 4: Live-Testing

- Änderungen im Code werden automatisch auf dem Gerät aktualisiert
- Shake das Gerät für das Developer Menu
- `r` im Terminal für Reload

### Schritt 5: Production Build (optional)

```bash
# EAS CLI installieren
npm install -g eas-cli

# Build konfigurieren
eas build:configure

# iOS Build (App Store)
eas build --platform ios

# Android Build (Play Store)
eas build --platform android
```

---

## 📁 Projektstruktur

```
{{PROJECT_NAME_KEBAB}}/
├── app/                   # Expo Router (File-based routing)
│   ├── _layout.tsx       # Root layout
│   ├── index.tsx         # Home screen (/)
│   ├── (tabs)/           # Tab navigation group
│   │   ├── _layout.tsx   # Tab layout
│   │   ├── index.tsx     # First tab
│   │   └── settings.tsx  # Settings tab
│   └── [id].tsx          # Dynamic route
├── components/            # Reusable components
├── hooks/                 # Custom hooks
├── lib/                   # Utilities
├── assets/               # Images, fonts
├── app.json              # Expo configuration
└── package.json
```

---

## 🧭 Navigation (Expo Router)

```typescript
// app/(tabs)/_layout.tsx
import { Tabs } from 'expo-router';

export default function TabLayout() {
  return (
    <Tabs>
      <Tabs.Screen name="index" options={{ title: 'Home' }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
    </Tabs>
  );
}
```

---

## 📱 Native Features

```typescript
// Kamera-Zugriff
import { Camera } from 'expo-camera';

// Push Notifications
import * as Notifications from 'expo-notifications';

// Lokale Datenbank
import * as SQLite from 'expo-sqlite';

// Secure Storage
import * as SecureStore from 'expo-secure-store';
```

---

## 🧪 Tests

```bash
# Unit Tests
npm run test

# Component Tests
npm run test:components
```

---

## ✅ Checkliste

- [ ] Dependencies installiert
- [ ] Expo Go App installiert
- [ ] App läuft auf Simulator/Gerät
- [ ] Navigation funktioniert
- [ ] API-Verbindung getestet
- [ ] Icons und Splash Screen konfiguriert