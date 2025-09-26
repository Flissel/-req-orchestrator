# Auto-Refine (Selbstkorrektur) – Funktionsdokumentation

Überblick
- Ziel: Automatisches Verfeinern von Requirements mit iterativen LLM-Änderungen und erneuter Bewertung, bis ein Release-Gate erreicht ist oder ein Eskalationslimit greift.
- Implementierung: Frontend-only Logik in [autoRefineIndex()](frontend/app_optimized.js:1705) und [autoRefineMany()](frontend/app_optimized.js:1775); verwendet vorhandene LLM-Endpoints (Suggest/Apply) und Batch-Validierung.
- UI: Buttons für Einzel-Refine im Detail und Massen-Refine im Header. Respektiert “Use modified”-Arbeitsmodus und verarbeitet nur sichtbare offene Issues.
- Eskalation: Nach max. Iterationen wird das Item auf “Review” gesetzt (Badge), d. h. manuelle Nacharbeit nötig.

Konfiguration und Gates
- UI-Konfiguration: [UI_CONF](frontend/app_optimized.js:41)
  - releaseScore: 0.8
  - maxAutoRefineIter: 5
- Gates/Heuristiken:
  - OK-Erkennung: [computeOk(result)](frontend/app_optimized.js:25)
  - Score-Schwelle: [score(result)](frontend/app_optimized.js:46)
  - Release-Gate: [releaseOk(result)](frontend/app_optimized.js:53) → computeOk ODER Score ≥ releaseScore
  - Offene Issues: [hasOpenIssues(result)](frontend/app_optimized.js:61)

Kern-Helper
- Vorschläge nachladen: [ensureSuggestions(index)](frontend/app_optimized.js:162)
  - POST /api/v1/validate/suggest
  - Robuste Auswertung unterschiedlicher Response-Shapes (Array; { suggestions }; { items: { … } })
- LLM-Apply (Merge): [mergeApply(originalText, atoms)](frontend/app_optimized.js:211)
  - POST /api/v1/corrections/apply (mode=merge)
  - Liefert ‘redefinedRequirement’ (merged Text) für Re-Analyse
- Re-Analyse: [reanalyzeIndex()](frontend/app_optimized.js:1592) / [reanalyzeMany()](frontend/app_optimized.js:1633)
  - POST /api/v1/validate/batch mit items=[text], includeSuggestions=bool
- Adaptive Parallelität: [getAdaptiveConcurrency()](frontend/app_optimized.js:89)
  - 2..5 parallele Worker je nach hardwareConcurrency

Ablauf – Einzel-Item ([autoRefineIndex()](frontend/app_optimized.js:1705))
1. Input: index, optional maxIter (Default: UI_CONF.maxAutoRefineIter)
2. Early Exit: Falls [hasOpenIssues()](frontend/app_optimized.js:61) false, ist das Item bereits freigegeben.
3. Suggestions laden (falls fehlen): [ensureSuggestions(index)](frontend/app_optimized.js:162)
4. Auswahl bestimmen:
   - Wenn der Nutzer in der UI bereits Suggestions selektiert hat (res._selectedSuggestions), verwende nur diese
   - Sonst alle gelieferten Suggestions
5. Merge-Apply: [mergeApply()](frontend/app_optimized.js:211) erzeugt einen neuen “merged” Text
6. Re-Analyse: POST /api/v1/validate/batch mit merged
7. Ergebnis ersetzen: [replaceResultAtIndex()](frontend/app_optimized.js:1562)
8. Gate prüfen: [releaseOk()](frontend/app_optimized.js:53). Wenn erfüllt → Erfolg
9. Wiederholen bis maxIter
10. Eskalation: Falls Gate nicht erreicht wird → res._autoRefine = "manual" und UI-Review-Badge anzeigen

Ablauf – Viele Items ([autoRefineMany()](frontend/app_optimized.js:1775))
- Input: indexes, optional concurrency (Default: [getAdaptiveConcurrency()](frontend/app_optimized.js:89))
- Startet einen kleinen Queue-Workerpool (1..5) und ruft [autoRefineIndex()](frontend/app_optimized.js:1705) für jedes Item
- Fortschritt/Fehler werden via [updateStatus()](frontend/app_optimized.js:1521) angezeigt

UI-Integration
- Detail-Button: “Auto-refine this requirement”
  - Rendering: [displayResults() – Detail Header](frontend/app_optimized.js:808)
  - Handler (delegiert): [results-detail click switch → auto-refine-one](frontend/app_optimized.js:978)
- Header-Button: “Auto-refine open issues”
  - Rendering: [displayResults() – Header, openVisibleCount](frontend/app_optimized.js:827)
  - Handler: [displayResults() – auto-refine-open Click](frontend/app_optimized.js:861)
  - Respektiert “Use modified”: nur sichtbare Indexe werden betrachtet ([getVisibleIndexes()](frontend/app_optimized.js:81)), anschließend Filter auf offene Issues via [hasOpenIssues()](frontend/app_optimized.js:61)
- Review-Badge:
  - Anzeige in Summary-Row, wenn res._autoRefine === "manual": [displayResults() – reviewBadge](frontend/app_optimized.js:660)
  - Style: [.badge.review](frontend/styles.css:580)

Scope-Logik und “Use modified”
- Sichtbarer Indexsatz: [getVisibleIndexes()](frontend/app_optimized.js:81) (bei aktivem Filter nur geänderte Items)
- Header-Aktion “Auto-refine open issues”:
  - Basis: visibleIndexes (wenn Filter aktiv) sonst alle Indexe
  - Filter: nur Items mit [hasOpenIssues()](frontend/app_optimized.js:61)
- Einzel-Aktion im Detail ignoriert den Filter (immer das selektierte Item)

Fehler- und Status-Handling
- Einheitliche Status-Updates: [updateStatus()](frontend/app_optimized.js:1521)
- Zusätzliche Try/Catch-Blöcke in:
  - [ensureSuggestions()](frontend/app_optimized.js:162)
  - [mergeApply()](frontend/app_optimized.js:211)
  - [autoRefineIndex()](frontend/app_optimized.js:1705)
- HTTP-Fehler: Response-Text wird geloggt; UI erhält klare Fehlermeldungen

API-Verträge (vereinfachter Überblick)
- POST /api/v1/validate/suggest
  - Request: JSON-Array mit 1 String (Original Requirement)
  - Response: 
    - Entweder Array von Suggestion-Atomen
    - oder { suggestions: [...] }
    - oder { items: { [id]: { suggestions: [...] } } }
  - Suggestion-Atom Felder (Beispiele): correction, acceptance_criteria[], metrics[]
- POST /api/v1/corrections/apply
  - Request: { originalText, selectedSuggestions: Atom[], mode: "merge", context: {} }
  - Response: { items: [ { redefinedRequirement: string } ] }
- POST /api/v1/validate/batch
  - Request: { items: [text], includeSuggestions: boolean }
  - Response: Array von Result-Objekten (mit evaluation[], score, verdict, ggf. suggestions)

Performance/Parallelität
- Concurrency default:
  - [autoRefineMany()](frontend/app_optimized.js:1775): getAdaptiveConcurrency() (2..5)
  - [reanalyzeMany()](frontend/app_optimized.js:1633): konfigurierbar, Standard analog
- Hardening:
  - Fallbacks via typeof-Checks, wenn Helper durch Caching noch nicht verfügbar sind

Cache & Laden
- Cache-Buster auf [index.html](frontend/index.html:57) gesetzt: v=inc-4
- Bei Frontend-Änderungen ggf. Hard-Reload im Browser (Cache leeren), um ReferenceErrors zu vermeiden

Tests (Playwright)
- Single-Item Erfolg: [tests/ui/auto-refine.spec.ts](tests/ui/auto-refine.spec.ts:1)
  - “auto-refine this requirement” erreicht Release-Gate (OK oder Score ≥ 0.8)
- Sichtbarkeits-Scope mit “Use modified”: [tests/ui/auto-refine.spec.ts](tests/ui/auto-refine.spec.ts:36)
  - Header-Button verarbeitet nur sichtbare offene Items
- Eskalation auf Review: [tests/ui/auto-refine.spec.ts](tests/ui/auto-refine.spec.ts:110)
  - Nach maxIter erscheint “Review”-Badge, Status bleibt Fehler
- Vorhandene Specs:
  - Modified-Filter: [tests/ui/modified-filter.spec.ts](tests/ui/modified-filter.spec.ts:1)
  - Apply Suggestion / LLM-Apply: [tests/ui/apply-suggestion.spec.ts](tests/ui/apply-suggestion.spec.ts:1)

Bekannte Einschränkungen
- Abhängigkeit von Backend-Qualität: Suggest/Apply/Bewertung müssen stabil antworten; Tests mocken diese Endpoints.
- Merge-Strategie: “merge” ist bewusst konservativ; bei komplexen Konflikten kann manuell nachgearbeitet werden (Review-Badge).
- Quotas/Rate Limits: Bei großen Mengen ggf. Concurrency reduzieren.

Bedienhinweise
- Einzel-Refine: Detail öffnen → “Auto-refine this requirement”
- Batch-Refine offener Issues: Header → “Auto-refine open issues”
- “Use modified” aktivieren, um nur geänderte Items zu bearbeiten und Batch-Operationen darauf zu beschränken.

Änderungsverweise (wichtige Stellen)
- Gates/Konfig: [UI_CONF / releaseOk / hasOpenIssues](frontend/app_optimized.js:41)
- Auto-Refine Kern: [autoRefineIndex()](frontend/app_optimized.js:1705), [autoRefineMany()](frontend/app_optimized.js:1775)
- UI-Buttons/Events: [displayResults() – Header/Detail/Handler](frontend/app_optimized.js:827)
- Review-Badge: [displayResults() – reviewBadge](frontend/app_optimized.js:660) und [.badge.review](frontend/styles.css:580)