# 📋 VR Experience (WebXR) - Projekt-Fragebogen
## Template: 14-vr-webxr (Three.js / A-Frame + WebXR)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Experience Name** | |
| **VR-Typ** | Immersive, AR, Mixed Reality |
| **Zielgeräte** | Quest, Pico, Browser |

---

## A. EXPERIENCE-TYP

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| A1 | Primärer Modus? | [ ] VR Immersive [ ] AR [ ] Mixed Reality [ ] 360° Video | |
| A2 | Use Case? | [ ] Gaming [ ] Training [ ] Visualization [ ] Social [ ] Art | |
| A3 | Interaktivität? | [ ] Passiv (Viewer) [ ] Aktiv (Interaktion) [ ] Multiplayer | |
| A4 | Session-Dauer? | Minuten, Stunden | |

---

## B. HARDWARE & PLATTFORM

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| B1 | Zielgeräte? | [ ] Quest 2/3 [ ] Pico 4 [ ] Apple Vision Pro [ ] Browser-only | |
| B2 | Controller? | [ ] 6DoF Controllers [ ] Hand Tracking [ ] Gaze only | |
| B3 | Room Scale? | [ ] Seated [ ] Standing [ ] Room Scale | |
| B4 | Fallback? | [ ] 3D Mouse [ ] Magic Window [ ] None | |

---

## C. 3D CONTENT

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| C1 | 3D Modelle? | GLB, GLTF, Blender | |
| C2 | Szenen-Komplexität? | Low (Mobile), Medium, High (PC) | |
| C3 | Texturen? | Auflösung, Anzahl | |
| C4 | Animationen? | Skeletal, Morph, Procedural | |
| C5 | Lighting? | Baked, Realtime, Mixed | |

---

## D. INTERACTION DESIGN

| # | Frage | Benötigt? |
|---|-------|-----------|
| D1 | Teleportation? | [ ] Ja [ ] Nein |
| D2 | Smooth Locomotion? | [ ] Ja [ ] Nein |
| D3 | Object Grabbing? | [ ] Ja [ ] Nein |
| D4 | UI Panels? | [ ] Ja [ ] Nein |
| D5 | Pointer/Ray? | [ ] Ja [ ] Nein |
| D6 | Haptic Feedback? | [ ] Ja [ ] Nein |
| D7 | Voice Input? | [ ] Ja [ ] Nein |

---

## E. TECH-STACK ENTSCHEIDUNGEN

### 3D Framework

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Framework? | [ ] Three.js (empfohlen) [ ] A-Frame [ ] Babylon.js [ ] React Three Fiber | |
| E2 | WebXR Library? | [ ] Native WebXR [ ] @react-three/xr [ ] A-Frame VR | |
| E3 | Physics? | [ ] Keine [ ] Rapier [ ] Cannon.js [ ] Ammo.js | |
| E4 | Audio? | [ ] Web Audio [ ] Howler.js [ ] Three.js Audio | |

### Build & Development

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E5 | Build Tool? | [ ] Vite (empfohlen) [ ] Webpack | |
| E6 | TypeScript? | [ ] Ja [ ] JavaScript | |
| E7 | React? | [ ] Ja (R3F) [ ] Vanilla | |
| E8 | Asset Pipeline? | [ ] Manual [ ] Blender Scripts | |

### Optimization

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E9 | LOD System? | [ ] Ja [ ] Nein | |
| E10 | Instancing? | [ ] Ja [ ] Nein | |
| E11 | Texture Compression? | [ ] Basis [ ] KTX2 [ ] None | |
| E12 | Occlusion Culling? | [ ] Ja [ ] Nein | |

---

## F. AUDIO

| # | Frage | Benötigt? |
|---|-------|-----------|
| F1 | Spatial Audio? | [ ] Ja [ ] Nein |
| F2 | Ambient Sounds? | [ ] Ja [ ] Nein |
| F3 | Voice Chat? | [ ] Ja [ ] Nein |
| F4 | Music? | [ ] Ja [ ] Nein |

---

## G. MULTIPLAYER (falls nötig)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Multiplayer? | [ ] Nein [ ] Ja | |
| G2 | Max Players? | 2, 8, 16+ | |
| G3 | Networking? | [ ] WebSocket [ ] WebRTC [ ] Photon | |
| G4 | Avatar Sync? | Position, Hands, Full Body | |

---

## H. PERFORMANCE TARGETS

| # | Frage | Antwort |
|---|-------|---------|
| H1 | Target FPS? | 72 (Quest), 90 (PC) |
| H2 | Draw Calls? | <100 (Mobile), <500 (PC) |
| H3 | Triangle Budget? | 100k, 500k, 1M+ |
| H4 | Texture Memory? | MB |
| H5 | Load Time? | <5s, <10s |

---

## I. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| I1 | Hosting? | [ ] Vercel [ ] Netlify [ ] Self-hosted | |
| I2 | HTTPS? | [ ] Ja (WebXR Required) | |
| I3 | PWA? | [ ] Ja [ ] Nein | |
| I4 | Native Build? | [ ] Nein [ ] Quest App (PWA) | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Scene Setup
- [ ] XR Session Manager
- [ ] Controller Handlers
- [ ] Teleportation System
- [ ] Grab System
- [ ] UI Panels
- [ ] Audio Manager
- [ ] Loading Screen
- [ ] Performance Monitor
- [ ] Build Config

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "14-vr-webxr",
  "3d": {
    "framework": "Three.js / A-Frame",
    "xr": "WebXR API",
    "physics": "Rapier (optional)"
  },
  "frontend": {
    "bundler": "Vite",
    "language": "TypeScript",
    "react": "React Three Fiber (optional)"
  },
  "audio": {
    "library": "Web Audio API",
    "spatial": true
  },
  "deployment": {
    "platform": "Any Static Host",
    "devices": ["Quest", "Pico", "Browser"]
  }
}
```
