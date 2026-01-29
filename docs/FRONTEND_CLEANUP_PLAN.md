# Frontend Cleanup Plan

## Übersicht

Das Frontend hat zwei Versionen:
- **V1 (App.jsx)**: Legacy Single-Page Layout
- **V2 (AppV2.jsx)**: Neues Tab-basiertes Layout ✅ JETZT DEFAULT

## Aktuelle Situation

### V2 bereits implementierte Features:
- ✅ Tab-Navigation (Mining, Requirements, Validation, Knowledge Graph)
- ✅ RequirementsTable mit Sortierung und Filterung
- ✅ ValidationTab mit Inline-Validierung
- ✅ ValidationDetailPanel mit Live-Progress
- ✅ Batch-Validation mit State-Persistence
- ✅ KnowledgeGraph Visualisierung
- ✅ JSON/DB/KG Data Loading

### V1-only Features (zu migrieren oder entfernen):
- ❓ ChatInterface.jsx - Agent-Konversationen (SSE)
- ❓ ClarificationModal.jsx - User-Clarifications (SSE)
- ❓ EnhancementModal.jsx - WebSocket Enhancement ⚠️ WICHTIG
- ❓ RequirementDetailModal.jsx - Detail-Ansicht
- ❓ EvidencePanel.jsx - Evidence-Anzeige

---

## Phase 1: V2 als Default ✅ ERLEDIGT

```jsx
// src/main.jsx - V2 ist jetzt Standard
const [useV2, setUseV2] = useState(() => {
  const saved = localStorage.getItem('useAppV2')
  return saved === null ? true : saved === 'true'  // Default: true
})
```

**User-Aktion erforderlich**: Browser localStorage löschen oder:
```javascript
localStorage.removeItem('useAppV2')
```

---

## Phase 2: EnhancementModal zu V2 migrieren

### Warum wichtig:
Das EnhancementModal ist das Herzstück der interaktiven Requirement-Verbesserung:
- WebSocket-basierter Flow
- SocietyOfMind Agenten (Purpose, Gap, Question, Rewrite)
- Interaktive Fragen an User

### Migration Steps:
1. Import EnhancementModal in AppV2.jsx
2. State für enhancingRequirement hinzufügen
3. Handler für onEnhance in ValidationTab einbinden
4. Modal am Ende des Components rendern

```jsx
// In AppV2.jsx hinzufügen:
import EnhancementModal from './components/EnhancementModal'

const [enhancingRequirement, setEnhancingRequirement] = useState(null)

// In ValidationTab props:
onEnhanceRequirement={setEnhancingRequirement}

// Am Ende vor </div>:
{enhancingRequirement && (
  <EnhancementModal
    requirement={enhancingRequirement}
    onClose={() => setEnhancingRequirement(null)}
    onEnhancementComplete={handleEnhancementComplete}
  />
)}
```

---

## Phase 3: Components-Kategorisierung

### ✅ BEHALTEN (V2 aktiv):
| Component | Beschreibung |
|-----------|-------------|
| TabNavigation.jsx | Tab-Leiste |
| RequirementsTable.jsx | Requirements-Tabelle |
| ValidationTab.jsx | Validierungs-Tab |
| ValidationDetailPanel.jsx | Inline-Validierung |
| ValidationRequirementCard.jsx | Requirement-Karten |
| KnowledgeGraph.jsx | KG-Visualisierung |
| AgentStatus.jsx | Agent-Statusanzeige |
| Configuration.jsx | Mining-Konfiguration |
| ManifestViewer.jsx | Requirement-Manifest |
| ValidationModal.jsx | Modal-Validierung |
| ToastNotification.jsx | Toast-Benachrichtigungen |
| ErrorBoundary.jsx | Error Handling |

### 🔄 ZU MIGRIEREN:
| Component | Status | Priorität |
|-----------|--------|-----------|
| EnhancementModal.jsx | WebSocket Enhancement | 🔴 HOCH |
| RequirementDetailModal.jsx | Detail-Ansicht | 🟡 MITTEL |
| BatchValidationButton.jsx | Batch-Trigger | 🟢 NIEDRIG (bereits in ValidationTab) |

### ❌ ZU ENTFERNEN (nach Migration):
| Component | Grund |
|-----------|-------|
| ChatInterface.jsx | Nicht mehr benötigt, Agents arbeiten im Hintergrund |
| ChatInterface.css | Zugehöriges CSS |
| ClarificationModal.jsx | Ersetzt durch EnhancementModal |
| QuestionPanel.jsx | Nicht verwendet |
| QuestionPanel.css | Nicht verwendet |
| EvidencePanel.jsx | Nicht verwendet |
| Requirements.jsx | Ersetzt durch RequirementsTable |
| CriteriaGrid.jsx | In ValidationDetailPanel integriert |
| CriteriaGrid.css | Zugehöriges CSS |
| SplitChildrenView.jsx | In ValidationDetailPanel integriert |
| TimelineView.jsx | Nicht verwendet |
| RequirementDiffView.jsx | Nicht verwendet |
| App.css | V1 Styles |

---

## Phase 4: CSS Migration

### Zu behalten:
- `AppV2.css` - Haupt-Styles
- `TabNavigation.css` 
- `RequirementsTable.css`
- `ValidationTab.css`
- `ValidationDetailPanel.css`
- `ValidationRequirementCard.css`
- `ManifestViewer.css`

### Zu konsolidieren:
- `index.css` - Basis-Styles, behalten

### Zu entfernen:
- `App.css` - V1 Styles

---

## Phase 5: Finale Schritte

1. **V1 Code entfernen**:
   - `App.jsx` löschen
   - `App.css` löschen
   - Unbenutzte Components löschen

2. **main.jsx vereinfachen**:
   ```jsx
   // Kein Switch mehr nötig
   import AppV2 from './AppV2.jsx'
   
   ReactDOM.createRoot(document.getElementById('root')).render(
     <React.StrictMode>
       <ErrorBoundary>
         <AppV2 />
       </ErrorBoundary>
     </React.StrictMode>,
   )
   ```

3. **AppV2.jsx umbenennen** zu `App.jsx`

4. **Build & Test**:
   ```bash
   npm run build
   npm run dev
   ```

---

## Zeitschätzung

| Phase | Aufwand |
|-------|---------|
| Phase 1: V2 Default | ✅ Erledigt |
| Phase 2: EnhancementModal | ~30 min |
| Phase 3: Component Cleanup | ~1 Stunde |
| Phase 4: CSS Cleanup | ~30 min |
| Phase 5: Finale Schritte | ~15 min |
| **Gesamt** | **~2.5 Stunden** |

---

## Rückfall-Plan

Falls Probleme auftreten:
1. Git revert zum vorherigen Stand
2. V1 temporär wieder aktivieren über localStorage
3. Issues dokumentieren vor nächstem Versuch