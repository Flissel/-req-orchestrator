# 📋 Mobile App (Expo) - Projekt-Fragebogen
## Template: 04-mobile-expo (Expo SDK 51 + React Native)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **App Name** | |
| **App Store Name** | |
| **Bundle ID** | com.company.appname |
| **Zielplattformen** | [ ] iOS [ ] Android [ ] Beide |

---

## A. APP-TYP & ZWECK

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | Was macht die App? | Social, E-Commerce, Utility, Game | |
| A2 | Offline-Funktionalität? | Welche Features offline? | |
| A3 | Companion App? | Zu Web-App gehörend? | |
| A4 | Standalone? | Ohne Backend nutzbar? | |

---

## B. NAVIGATION & SCREENS

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| B1 | Navigation Pattern? | Tab Bar, Drawer, Stack | |
| B2 | Haupt-Screens? | Home, Profile, Settings | |
| B3 | Auth Screens? | Login, Register, Forgot PW | |
| B4 | Onboarding? | Tutorial, Intro Slides | |
| B5 | Deep Linking? | myapp://screen/id | |

---

## C. UI/UX

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| C1 | Design System? | [ ] Custom [ ] Paper (MD3) [ ] Tamagui [ ] NativeBase | |
| C2 | Dark Mode? | [ ] Light only [ ] Dark only [ ] Both [ ] System | |
| C3 | Animationen? | [ ] Minimal [ ] Standard [ ] Rich (Reanimated) | |
| C4 | Gestures? | Swipe, Pinch, Pan | |
| C5 | Platform-spezifisch? | iOS/Android unterschiedlich | |

---

## D. NATIVE FEATURES

| # | Frage | Benötigt? | Details |
|---|-------|-----------|---------|
| D1 | Kamera? | [ ] Ja [ ] Nein | Foto, Video, QR Scanner | |
| D2 | Location? | [ ] Ja [ ] Nein | GPS, Background Location | |
| D3 | Push Notifications? | [ ] Ja [ ] Nein | FCM, APNs | |
| D4 | Biometric Auth? | [ ] Ja [ ] Nein | Face ID, Fingerprint | |
| D5 | Contacts Access? | [ ] Ja [ ] Nein | | |
| D6 | File System? | [ ] Ja [ ] Nein | Dokumente, Downloads | |
| D7 | Media Library? | [ ] Ja [ ] Nein | Fotos, Videos | |
| D8 | Haptics? | [ ] Ja [ ] Nein | Vibration Feedback | |
| D9 | In-App Purchases? | [ ] Ja [ ] Nein | Subscriptions, One-time | |
| D10 | Share Extension? | [ ] Ja [ ] Nein | Share to App | |

---

## E. BACKEND & DATEN

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Backend? | [ ] Eigenes API [ ] Supabase [ ] Firebase [ ] Appwrite | |
| E2 | Lokale Datenbank? | [ ] Expo SQLite [ ] MMKV [ ] AsyncStorage | |
| E3 | State Management? | [ ] Zustand [ ] Redux Toolkit [ ] Jotai [ ] React Query | |
| E4 | API Kommunikation? | [ ] React Query [ ] SWR [ ] Axios | |
| E5 | Realtime? | [ ] Nein [ ] WebSocket [ ] Supabase Realtime | |

---

## F. TECH-STACK ENTSCHEIDUNGEN

### Expo Configuration

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| F1 | Expo Workflow? | [ ] Managed (empfohlen) [ ] Bare | |
| F2 | Expo Router? | [ ] Ja (empfohlen) [ ] React Navigation | |
| F3 | EAS Build? | [ ] Ja [ ] Nein (Expo Go only) | |
| F4 | OTA Updates? | [ ] Ja [ ] Nein | |

### Styling & Components

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| F5 | Styling Approach? | [ ] StyleSheet (default) [ ] NativeWind [ ] Tamagui | |
| F6 | Icons? | [ ] Expo Vector Icons [ ] Custom SVG | |
| F7 | Fonts? | [ ] System [ ] Custom Fonts | |

---

## G. AUTH & SICHERHEIT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Auth Methods? | [ ] Email/PW [ ] Social [ ] Phone [ ] Magic Link | |
| G2 | Social Providers? | [ ] Google [ ] Apple [ ] Facebook | |
| G3 | Token Storage? | [ ] Expo SecureStore [ ] MMKV Encrypted | |
| G4 | Session Handling? | Auto-refresh, Logout on expire | |
| G5 | App Lock? | PIN, Biometric | |

---

## H. TESTING & QUALITÄT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Unit Tests? | [ ] Jest [ ] Vitest | |
| H2 | E2E Tests? | [ ] Detox [ ] Maestro [ ] None | |
| H3 | Type Checking? | [ ] TypeScript (empfohlen) [ ] JavaScript | |
| H4 | Linting? | [ ] ESLint + Prettier | |

---

## I. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| I1 | App Store? | [ ] Ja [ ] Nein (intern only) | |
| I2 | TestFlight/Beta? | [ ] Ja [ ] Nein | |
| I3 | CI/CD? | [ ] EAS Build [ ] GitHub Actions [ ] Bitrise | |
| I4 | Environments? | [ ] Dev + Prod [ ] Dev + Staging + Prod | |

---

## J. ANALYTICS & MONITORING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| J1 | Analytics? | [ ] None [ ] Expo Insights [ ] Amplitude [ ] Mixpanel | |
| J2 | Crash Reporting? | [ ] Sentry [ ] Bugsnag [ ] Firebase Crashlytics | |
| J3 | Performance Monitoring? | [ ] None [ ] Firebase Performance | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Expo Router Screens
- [ ] Navigation Setup
- [ ] Auth Flow
- [ ] UI Components
- [ ] API Integration
- [ ] Push Notification Setup
- [ ] EAS Build Config
- [ ] App Store Assets

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "04-mobile-expo",
  "frontend": {
    "framework": "Expo SDK 51",
    "ui": "React Native",
    "navigation": "Expo Router",
    "language": "TypeScript"
  },
  "state": {
    "global": "Zustand",
    "server": "React Query"
  },
  "storage": {
    "local": "Expo SQLite",
    "secure": "Expo SecureStore"
  },
  "deployment": {
    "build": "EAS Build",
    "updates": "EAS Update",
    "stores": ["App Store", "Google Play"]
  }
}
```
