(() => {
  // Robust ermitteln:
  // - bevorzugt window.API_BASE (aus index.html → Default http://localhost:8081)
  // - Fallback: wenn location.origin eine http/https Origin ist, diese verwenden
  // - letzter Fallback: http://localhost:8081
  (function() {
    const isHttpOrigin = typeof location !== 'undefined' && /^https?:\/\//i.test(location.origin || '');
    const fallback = 'http://localhost:8081';
    const chosen = window.API_BASE || (isHttpOrigin ? location.origin : fallback);
    window.API_BASE = chosen; // sichtbar im DevTools
  })();
  const API_BASE = String(window.API_BASE || 'http://localhost:8081').replace(/\/+$/, "");

  // Globale Variablen für Zustandsverwaltung
  let requirements = [];
  // Batch-only Modus (keine anderen Modi mehr)
  const CURRENT_MODE = 'incremental';
  let isProcessing = false;

  // Ergebnis-Status-Zähler (UI-Only)
  let acceptedCount = 0;
  let rejectedCount = 0;

  // Zentralisierte OK/Test-Logik
  function computeOk(result) {
    try {
      if (!result || typeof result !== 'object') return false;
      if (result.verdict === 'pass') return true;
      const evalArr = Array.isArray(result.evaluation) ? result.evaluation : [];
      if (evalArr.length === 0) return false;
      for (let i = 0; i < evalArr.length; i++) {
        if (!evalArr[i]?.isValid) return false;
      }
      return true;
    } catch {
      return false;
    }
  }

  // Auto-Refine Konfiguration und Gates
  const UI_CONF = {
    releaseScore: 0.8,
    maxAutoRefineIter: 5
  };

  function score(result) {
    try {
      const s = Number(result?.score);
      return Number.isFinite(s) ? s : 0;
    } catch { return 0; }
  }

  function releaseOk(result) {
    try {
      if (computeOk(result)) return true;
      if (score(result) >= (UI_CONF?.releaseScore ?? 0.8)) return true;
      return false;
    } catch { return false; }
  }

  function hasOpenIssues(result) {
    try { return !releaseOk(result); } catch { return true; }
  }



// Modified-Filter Helpers
function isModified(result) {
  try { return !!(result && result._modified); } catch { return false; }
}
function getModifiedIndexes() {
  try {
    if (!Array.isArray(currentResults)) return [];
    const out = [];
    for (let i = 0; i < currentResults.length; i++) {
      if (isModified(currentResults[i])) out.push(i);
    }
    return out;
  } catch { return []; }
}
function getVisibleIndexes() {
  try {
    if (!Array.isArray(currentResults)) return [];
    if (ui && ui.showModifiedOnly) return getModifiedIndexes();
    return currentResults.map((_, i) => i);
  } catch { return []; }
}
// Adaptive Parallelität (Option B): 2..5 Worker basierend auf hardwareConcurrency
function getAdaptiveConcurrency() {
  try {
    const cpuRaw = (typeof navigator !== 'undefined' && navigator.hardwareConcurrency) ? Number(navigator.hardwareConcurrency) : 4;
    const cpu = Number.isFinite(cpuRaw) && cpuRaw > 0 ? cpuRaw : 4;
    const conc = Math.floor(cpu / 2) || 2;
    return Math.max(2, Math.min(5, conc));
  } catch {
    return 2;
  }
}

  // Hilfsfunktion: Editor-/State-Sync nach Übernahme eines neuen Textes
  function ensureEditorSync(index, newText) {
    try {
      if (typeof index !== 'number' || index < 0) return;
      const text = String(newText ?? '');
      // Datenmodell
      if (Array.isArray(requirements)) {
        requirements[index] = text;
      }
      if (Array.isArray(currentResults) && currentResults[index]) {
        currentResults[index].originalText = text;
        currentResults[index].correctedText = '';
      }

      // Linke Liste spiegeln
      const list = document.getElementById('req-list');
      if (list) {
        const collapsed = list.querySelector(`.req-collapsed[data-idx="${index}"] .editable-input`);
        const expanded = list.querySelector(`.req-expanded[data-idx="${index}"] .expand-textarea`);
        if (collapsed) collapsed.value = text;
        if (expanded) expanded.value = text;
      }

      // Rechte Detail-Korrektur leeren und neu zeichnen
      try {
        const ta = document.getElementById('correction-textarea');
        if (ta) ta.value = '';
      } catch {}
      renderDetailOnly();
    } catch (e) {
      console.error('ensureEditorSync() Fehler', e);
    }
  }

  // Sofort-Persistenz: POST /api/v1/corrections/text
  async function saveTextImmediate(oldOriginal, newText) {
    const url = `${API_BASE}/api/v1/corrections/text`;
    const payload = {
      originalText: String(oldOriginal ?? ''),
      text: String(newText ?? '')
    };
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        const msg = `HTTP ${resp.status}: ${t || resp.statusText}`;
        updateStatus(`Fehler beim Speichern: ${msg}`);
        return false;
      }
      updateStatus('Suggestion übernommen und gespeichert.');
      return true;
    } catch (err) {
      const msg = err?.message || String(err);
      updateStatus(`Fehler beim Speichern: ${msg}`);
      return false;
    }
  }

  // Suggestions sicherstellen (lädt bei Bedarf)
  async function ensureSuggestions(index) {
    try {
      const idx = Number(index);
      if (!Number.isInteger(idx) || idx < 0) return [];
      const res = currentResults?.[idx];
      if (!res) return [];
      if (Array.isArray(res.suggestions) && res.suggestions.length > 0) {
        return res.suggestions;
      }
      const original = String(res.originalText || res.text || res.requirement || '');
      const url = `${API_BASE}/api/v1/validate/suggest`;
      const payload = [ original ];
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload),
        mode: 'cors'
      });
      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        updateStatus(`Suggestions-Fehler: ${resp.status} ${resp.statusText}`);
        console.error('ensureSuggestions → HTTP Fehler', { status: resp.status, statusText: resp.statusText, sample: t.slice(0, 400) });
        return [];
      }
      const ct = resp.headers.get('content-type') || '';
      let data;
      if (ct.includes('application/json')) data = await resp.json();
      else {
        const t = await resp.text();
        try { data = JSON.parse(t); } catch { data = {}; }
      }
      let atoms = [];
      if (Array.isArray(data)) atoms = data;
      else if (Array.isArray(data?.suggestions)) atoms = data.suggestions;
      else if (data && data.items && typeof data.items === 'object') {
        const key = Object.keys(data.items || {})[0];
        atoms = data.items?.[key]?.suggestions || [];
      }
      res.suggestions = Array.isArray(atoms) ? atoms : [];
      res._suggestionsOpen = res._suggestionsOpen || {};
      res._selectedSuggestions = res._selectedSuggestions || {};
      return res.suggestions;
    } catch (e) {
      console.error('ensureSuggestions() Fehler', e);
      return [];
    }
  }

  // LLM Merge-Apply: liefert zusammengeführten Text oder ''
  async function mergeApply(originalText, atoms) {
    try {
      const original = String(originalText || '');
      const selected = Array.isArray(atoms) ? atoms : [];
      if (!original) return '';
      const resp = await fetch(`${API_BASE}/api/v1/corrections/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          originalText: original,
          selectedSuggestions: selected,
          mode: 'merge',
          context: {}
        })
      });
      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        updateStatus(`Apply-Fehler: ${resp.status} ${resp.statusText}`);
        console.error('mergeApply → HTTP Fehler', { status: resp.status, statusText: resp.statusText, sample: t.slice(0, 400) });
        return '';
      }
      const data = await resp.json();
      const items = Array.isArray(data?.items) ? data.items : [];
      const merged = String(items?.[0]?.redefinedRequirement || items?.[0]?.redefined || items?.[0]?.redefined_req || '');
      return merged;
    } catch (e) {
      console.error('mergeApply() Fehler', e);
      return '';
    }
  }

  // Master/Detail UI-Status
  let currentResults = [];
  let selectedIndex = -1; // wird auf 0 gesetzt, wenn Ergebnisse vorhanden sind
  let detailsCollapsed = false;

  // UI-Globalzustand (Filter/Arbeitsmodus)
  const ui = {
    showModifiedOnly: false
  };

  // DOM-Elemente
  const loadBtn = document.getElementById("load-btn");
  const processBtn = document.getElementById("process-btn");
  const modeSelect = null; // kein Modus-Selector mehr (Batch-only)
  const statusDiv = document.getElementById("status");
  const resultsDiv = document.getElementById("results");

  // RAG/Upload UI
  const uploadBtn = document.getElementById('upload-btn');
  const uploadInput = document.getElementById('upload-input');
  const ragSearchBtn = document.getElementById('rag-search-btn');
  const ragQueryInput = document.getElementById('rag-query');
  const ragResultsDiv = document.getElementById('rag-results');
  const ragUseAgent = document.getElementById('rag-use-agent');
  const ragMineBtn = document.getElementById('rag-mine-btn');
  const resetIndexBtn = document.getElementById('reset-index-btn');

  // Event Listeners
  loadBtn.addEventListener("click", loadRequirements);
  processBtn.addEventListener("click", processRequirements);

  // Upload: Button öffnet Dateidialog
  if (uploadBtn && uploadInput) {
    uploadBtn.addEventListener('click', () => {
      try { uploadInput.value = ''; } catch {}
      uploadInput.click();
    });
    uploadInput.addEventListener('change', async (e) => {
      try {
        const files = Array.from(uploadInput.files || []);
        if (!files.length) { updateStatus('Kein File ausgewählt.'); return; }
        await ingestFiles(files);
      } catch (err) {
        updateStatus(`Upload-Fehler: ${err?.message || String(err)}`);
      }
    });
  }

  // RAG Search
  if (ragSearchBtn && ragQueryInput) {
    ragSearchBtn.addEventListener('click', async () => {
      const q = String(ragQueryInput.value || '').trim();
      if (!q) { updateStatus('Bitte eine Query eingeben.'); return; }
      await runRagSearch(q);
    });
  }
  if (ragMineBtn) {
    ragMineBtn.addEventListener('click', async () => {
      const q = String(ragQueryInput?.value || '').trim();
      if (!q) { updateStatus('Bitte eine Query eingeben.'); return; }
      await runMineRequirements(q);
    });
  }

  // Reset Index (Qdrant collection)
  if (resetIndexBtn) {
    resetIndexBtn.addEventListener('click', async () => {
      await resetIndex();
    });
  }
  
  // Modus-Auswahl wird nicht mehr angezeigt/genutzt – Standard ist Batch

  /**
   * Lädt Requirements aus der Markdown-Datei
   */
  async function loadRequirements() {
    try {
      updateStatus("Lade Requirements...");
      const response = await fetch(`${API_BASE}/api/v1/demo/requirements`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log("Load requirements data:", data);
      
      // Backend gibt {items: [...]} zurück, extrahiere die requirement texts
      const items = data.items || [];
      requirements = items.map(item => item.requirementText || item.requirement || item.text || "");
      
      console.log("Loaded requirements:", requirements);
      console.log("Requirements count:", requirements.length);
      
      // Mache requirements global verfügbar für Debugging
      window.requirements = requirements;
      
      updateStatus(`${requirements.length} Requirements geladen`);
      displayRequirements();
      processBtn.disabled = false;
      
    } catch (error) {
      console.error("Fehler beim Laden:", error);
      updateStatus(`Fehler beim Laden: ${error.message}`);
    }
  }

  /**
   * Verarbeitet Requirements basierend auf dem gewählten Modus
   */
  async function processRequirements() {
    if (isProcessing || requirements.length === 0) return;

    isProcessing = true;
    processBtn.disabled = true;

    try {
      // Nutzerwunsch: erstes Ergebnis schnell anzeigen → inkrementell/sequentiell
      updateStatus(`Starte inkrementelle Verarbeitung (gesamt: ${requirements.length})...`);
      const conc = (typeof getAdaptiveConcurrency === 'function' ? getAdaptiveConcurrency() : 3);
      await processIncremental({ concurrency: conc, includeSuggestions: true });
    } catch (error) {
      console.error("Verarbeitungsfehler:", error);
      updateStatus(`Fehler: ${error.message}`);
    } finally {
      isProcessing = false;
      processBtn.disabled = false;
    }
  }

  /**
   * Sequenzielle Verarbeitung (Original-Methode)
   */
  // entfernt (Batch-only)
  function processSequential() {
    throw new Error("Sequenzielle Verarbeitung ist deaktiviert (Batch-only).");
  }

  /**
   * Parallele Verarbeitung (Optimiert)
   */
  // entfernt (Batch-only)
  function processParallel() {
    throw new Error("Parallele Verarbeitung ist deaktiviert (Batch-only).");
  }

  // ------------ RAG / Ingest Helpers ------------
  async function ingestFiles(files) {
    try {
      updateStatus(`Sende ${files.length} Datei(en) an Ingest...`);
      const fd = new FormData();
      for (const f of files) fd.append('files', f, f.name);
      // Optionale Chunk-Parameter (Defaults serverseitig)
      // fd.append('chunkMin', '200'); fd.append('chunkMax', '400'); fd.append('chunkOverlap', '50');

      const resp = await fetch(`${API_BASE}/api/v1/files/ingest`, {
        method: 'POST',
        body: fd
      });
      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
      }
      const data = await resp.json();
      const msg = `Ingest OK: files=${data.countFiles}, blocks=${data.countBlocks}, chunks=${data.countChunks}, upserted=${data.upserted} → collection=${data.collection} (qdrant:${data.qdrantPort})`;
      updateStatus(msg);
      // Optional: RAG-Ergebnisbereich updaten
      try {
        const colsResp = await fetch(`${API_BASE}/api/v1/vector/collections`);
        if (colsResp.ok) {
          const cols = await colsResp.json();
          console.log('Qdrant Collections:', cols);
        }
      } catch {}
    } catch (e) {
      console.error('ingestFiles error', e);
      updateStatus(`Fehler beim Ingest: ${e?.message || String(e)}`);
    }
  }

  // Drop & recreate current Qdrant collection
  async function resetIndex() {
    try {
      const confirmed = window.confirm('Achtung: Der Index (Qdrant-Collection) wird vollständig geleert und neu angelegt. Fortfahren?');
      if (!confirmed) return;
      updateStatus('Resette Vektor-Index (Qdrant)…');
      // Nur POST ohne Header/Body, um Preflight zu vermeiden
      let resp = await fetch(`${API_BASE}/api/v1/vector/reset`, { method: 'POST' });
      // Fallback 1: Wenn POST 405 → GET mit confirm=1 (vermeidet Preflight)
      if (!resp || resp.status === 405) {
        try {
          resp = await fetch(`${API_BASE}/api/v1/vector/reset?confirm=1`, { method: 'GET' });
        } catch (e) {
          // lasse Fehler in der nachfolgenden Prüfung hochlaufen
        }
      }
      if (!resp || !resp.ok) {
        const t = resp ? (await resp.text().catch(() => '')) : '';
        throw new Error(`HTTP ${resp ? resp.status : 'n/a'}: ${t || 'Reset fehlgeschlagen'}`);
      }
      const data = await resp.json().catch(() => ({}));
      // UI Feedback
      if (ragResultsDiv) {
        const pretty = JSON.stringify(data, null, 2);
        ragResultsDiv.innerHTML = `<div class="small"><pre style="white-space:pre-wrap;max-height:220px;overflow:auto;">${escapeHtml(pretty)}</pre></div>`;
      }
      updateStatus('Index-Reset abgeschlossen.');
      // Optional: Collections anzeigen (nur Log)
      try {
        const cols = await fetch(`${API_BASE}/api/v1/vector/collections`).then(r => r.ok ? r.json() : null).catch(() => null);
        if (cols) console.log('Qdrant Collections nach Reset:', cols);
      } catch {}
    } catch (err) {
      console.error('resetIndex error', err);
      updateStatus(`Fehler beim Index-Reset: ${err?.message || String(err)}`);
    }
  }

  async function runRagSearch(query) {
    try {
      const useAgent = !ragUseAgent || ragUseAgent.checked === true;
      updateStatus(`Starte ${useAgent ? 'Agent-RAG' : 'RAG'}: "${query}" ...`);
      if (ragResultsDiv) ragResultsDiv.textContent = 'Suche...';

      let data;
      if (useAgent) {
        const resp = await fetch(`${API_BASE}/api/v1/agent/answer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query })
        });
        if (!resp.ok) {
          const t = await resp.text().catch(() => '');
          throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
        }
        data = await resp.json();
      } else {
        const url = `${API_BASE}/api/v1/rag/search?` + new URLSearchParams({ query: String(query || '') });
        const resp = await fetch(url, { method: 'GET' });
        if (!resp.ok) {
          const t = await resp.text().catch(() => '');
          throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
        }
        data = await resp.json();
      }

      const hits = Array.isArray(data?.hits) ? data.hits : [];
      const normalized = hits.map((h, i) => {
        const p = h?.payload || {};
        const scoreNum = typeof h?.score === 'number' ? h.score : null;
        const score = scoreNum !== null ? Number(scoreNum).toFixed(4) : String(h?.score ?? '');
        const src = String(p.sourceFile || p.source || 'unknown');
        const idx = (typeof p.chunkIndex === 'number') ? p.chunkIndex : null;
        const snippet = String(p.text || '').slice(0, 300).replace(/\s+/g, ' ').trim();
        return { rank: i + 1, id: h?.id ?? null, score, source: src, chunkIndex: idx, snippet };
      });

      const triggeredPolicies = useAgent && Array.isArray(data?.triggeredPolicies) ? data.triggeredPolicies : [];
      const agentNotes = useAgent && Array.isArray(data?.agentNotes) ? data.agentNotes : [];
      const resultObj = {
        query: data?.query ?? query,
        effectiveQuery: data?.effectiveQuery ?? query,
        topK: data?.topK ?? hits.length,
        referenceCount: useAgent ? (data?.referenceCount ?? null) : null,
        triggeredPolicies,
        items: normalized,
        agentNotes
      };

      if (ragResultsDiv) {
        if (!normalized.length) {
          ragResultsDiv.textContent = 'Keine Treffer.';
        } else {
          const jsonPretty = JSON.stringify(resultObj, null, 2);
          const htmlList = normalized.map(n => {
            const idx = (n.chunkIndex !== null && n.chunkIndex !== undefined) ? ` #${n.chunkIndex}` : '';
            return `<li><strong>[${escapeHtml(String(n.score))}]</strong> ${escapeHtml(n.snippet)} <em>(${escapeHtml(String(n.source))}${idx})</em></li>`;
          }).join('');
          const policiesHtml = triggeredPolicies.length ? `<div class="small" style="margin-top:6px;">Policies: ${triggeredPolicies.map(p => `<span class="badge" title="Triggered policy">${escapeHtml(String(p))}</span>`).join(' ')}</div>` : '';
          const notesHtml = agentNotes.length ? `<div class="small" style="margin-top:6px;color:#9ad;">Agent notes: ${agentNotes.map(escapeHtml).join(' | ')}</div>` : '';
          ragResultsDiv.innerHTML =
            `<div class="small"><pre style="white-space:pre-wrap;max-height:220px;overflow:auto;">${escapeHtml(jsonPretty)}</pre></div>` +
            policiesHtml +
            `<ol class="small" style="margin-top:8px">${htmlList}</ol>` +
            notesHtml;
        }
      }
      updateStatus(`${useAgent ? 'Agent-RAG' : 'RAG'} abgeschlossen: ${normalized.length} Treffer.`);
    } catch (e) {
      console.error('runRagSearch error', e);
      if (ragResultsDiv) ragResultsDiv.textContent = `Fehler: ${e?.message || String(e)}`;
      updateStatus(`Fehler bei RAG-Suche: ${e?.message || String(e)}`);
    }
  }

  async function runMineRequirements(query) {
    try {
      const q = String(query || '').trim();
      if (!q) { updateStatus('Bitte eine Query eingeben.'); return; }
      updateStatus(`Starte Requirements-Mining (Multi-Hop) …`);
      const resp = await fetch(`${API_BASE}/api/v1/agent/mine_requirements`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ query: q })
      });
      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
      }
      const data = await resp.json();
      const items = Array.isArray(data?.items) ? data.items : [];

      // Anforderungen in die linke Liste aufnehmen (anhängen, ohne Duplikate)
      let added = 0;
      for (const it of items) {
        const txt = String(it?.requirementText || '').trim();
        if (!txt) continue;
        if (!requirements.includes(txt)) {
          requirements.push(txt);
          added++;
        }
      }
      if (added > 0) {
        displayRequirements();
      }
      // Ergebnis im RAG-Panel anzeigen
      if (ragResultsDiv) {
        const pretty = JSON.stringify(data, null, 2);
        ragResultsDiv.innerHTML = `<div class="small"><pre style="white-space:pre-wrap;max-height:220px;overflow:auto;">${escapeHtml(pretty)}</pre></div>`;
      }
      updateStatus(`Mining abgeschlossen. ${added} Requirement(s) hinzugefügt.`);
    } catch (e) {
      console.error('runMineRequirements error', e);
      if (ragResultsDiv) ragResultsDiv.textContent = `Fehler: ${e?.message || String(e)}`;
      updateStatus(`Fehler beim Mining: ${e?.message || String(e)}`);
    }
  }

  /**
   * Batch-Verarbeitung (Schnellste)
   */
  async function processBatch() {
    // Beibehaltung als Fallback (kompletter Batch in einem Request)
    updateStatus("Starte Batch-Verarbeitung (komplett)...");
    try {
      const response = await fetch(`${API_BASE}/api/v1/validate/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: requirements, includeSuggestions: true })
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      const results = Array.isArray(data) ? data : [];
      updateStatus(`Batch-Verarbeitung abgeschlossen: ${results.length} Requirements verarbeitet.`);
      displayResults(results);
    } catch (error) {
      throw new Error(`Batch-Verarbeitung fehlgeschlagen: ${error.message}`);
    }
  }

  /**
   * Inkrementelle Verarbeitung: schickt pro Requirement einen Request,
   * hängt Ergebnisse sofort an und hält den Nutzer "am Ball".
   * Optional einfache Parallelität via concurrency (Standard: 1).
   */
  async function processIncremental({ concurrency = 1, includeSuggestions = true } = {}) {
    const total = requirements.length;
    currentResults = [];
    const indexQueue = requirements.map((_, i) => i);
    let processed = 0;
    let active = 0;
    let errorCount = 0;

    updateStatus(`Starte inkrementelle Verarbeitung (gesamt: ${total})...`);
    try { window.__processingMode = 'incremental'; } catch {}
    console.log('Mode=incremental, total=%d', total);

    async function runNext() {
      const nextIdx = indexQueue.shift();
      if (nextIdx === undefined) return;

      active += 1;
      const reqText = String(requirements[nextIdx] || "");

      try {
        const resp = await fetch(`${API_BASE}/api/v1/validate/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items: [reqText], includeSuggestions })
        });

        if (!resp.ok) {
          const t = await resp.text().catch(() => "");
          throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
        }

        const data = await resp.json();
        const arr = Array.isArray(data) ? data : [];
        const result = arr[0] || {
          originalText: reqText,
          status: "rejected",
          evaluation: [],
          error: "Leere Antwort vom Server"
        };

        // Sicherstellen, dass originalText gesetzt ist (für UI rechts)
        if (!result.originalText) result.originalText = reqText;

        // anhängen und UI sofort aktualisieren
        currentResults.push(result);
        processed += 1;
        updateStatus(`Verarbeitet: ${processed}/${total} (Fehler: ${errorCount})`);
        // neue Array-Referenz übergeben, damit displayResults "neue Ergebnisse" erkennt
        displayResults(currentResults.slice());
      } catch (err) {
        console.error("Incremental-Fehler bei Index", nextIdx, err);
        errorCount += 1;
        currentResults.push({
          originalText: reqText,
          status: "rejected",
          evaluation: [],
          error: String(err?.message || err || "Unbekannter Fehler")
        });
        processed += 1;
        updateStatus(`Verarbeitet: ${processed}/${total} (Fehler: ${errorCount})`);
        displayResults(currentResults.slice());
      } finally {
        active -= 1;
        // weitere Items starten
        if (indexQueue.length > 0) {
          await runNext();
        }
      }
    }

    // Starte bis zu "concurrency" Worker
    const workers = [];
    const cap = Math.max(1, Math.min(5, Number(concurrency) || 1));
    for (let i = 0; i < cap; i++) {
      workers.push(runNext());
    }
    await Promise.all(workers);

    updateStatus(`Inkrementelle Verarbeitung abgeschlossen: ${processed}/${total} (Fehler: ${errorCount}).`);
  }

  /**
   * Zeigt die geladenen Requirements an - jetzt editierbar mit Item-Actions
   */
  function displayRequirements() {
    const requirementsSection = document.getElementById('requirements-section');
    const requirementsDisplay = document.getElementById('requirements-display');
    
    if (!requirements.length) {
      if (requirementsSection) requirementsSection.style.display = 'none';
      return;
    }
    
    let html = `
      <div class="list" id="req-list">
        <p style="margin-bottom: 12px;"><strong>Geladene Requirements (${requirements.length}):</strong></p>
    `;

    requirements.forEach((req, index) => {
      const safe = escapeHtml(String(req));
      html += `
        <div class="item" data-req-index="${index}">
          <div class="item-head">
            <span class="badge pending">${index + 1}</span>

            <div class="req-collapsed" data-idx="${index}" style="flex:1;min-width:0;">
              <input class="editable-input" type="text" value="${safe}" aria-label="Requirement ${index+1}">
            </div>

            <div class="req-expanded hidden" data-idx="${index}" style="flex:1;min-width:0;">
              <textarea class="editable-textarea expand-textarea" data-idx="${index}">${safe}</textarea>
            </div>

            <button class="item-action-btn toggle-view-btn" title="Expand/Collapse" aria-label="Expand requirement" data-idx="${index}" data-mode="collapsed">Expand</button>
            <button class="item-action-btn delete-btn" title="Remove requirement" aria-label="Remove requirement" data-idx="${index}">🗑️</button>
          </div>
        </div>
      `;
    });

    html += `
      <button class="add-requirement-btn" id="add-requirement-btn">+ Requirement hinzufügen</button>
      </div>`;
    
    if (requirementsDisplay) {
      requirementsDisplay.innerHTML = html;
      bindRequirementInputEvents();
    }
    if (requirementsSection) {
      requirementsSection.style.display = 'block';
    }
  }

  // Bindet Events für editierbare Inputs und Add-Button
  function bindRequirementInputEvents() {
    const list = document.getElementById('req-list');
    if (!list) return;

    // Update local state on collapsed input change
    list.querySelectorAll('.editable-input').forEach((input, idx) => {
      input.addEventListener('input', (e) => {
        requirements[idx] = e.target.value;
        // Markiere als modifiziert, falls ein entsprechendes Result existiert
        try {
          if (Array.isArray(currentResults) && currentResults[idx]) {
            currentResults[idx]._modified = true;
          }
        } catch {}
        // Spiegel in geöffneter Textarea (falls sichtbar)
        const ta = list.querySelector(`.req-expanded[data-idx="${idx}"] .expand-textarea`);
        if (ta) ta.value = e.target.value;
      });
    });

    // Update local state on expanded textarea change
    list.querySelectorAll('.expand-textarea').forEach((ta) => {
      const idx = parseInt(ta.getAttribute('data-idx'), 10);
      ta.addEventListener('input', (e) => {
        requirements[idx] = e.target.value;
        // Markiere als modifiziert, falls ein entsprechendes Result existiert
        try {
          if (Array.isArray(currentResults) && currentResults[idx]) {
            currentResults[idx]._modified = true;
          }
        } catch {}
        // Spiegeln in das Input-Feld (falls sichtbar)
        const inp = list.querySelector(`.req-collapsed[data-idx="${idx}"] .editable-input`);
        if (inp) inp.value = e.target.value;
      });
    });

    // Delegierter Click-Handler für Toggle/Remove
    list.addEventListener('click', (e) => {
      const del = e.target.closest?.('.delete-btn');
      if (del) {
        e.stopPropagation();
        const idx = parseInt(del.getAttribute('data-idx'), 10);
        if (!Number.isNaN(idx)) {
          requirements.splice(idx, 1);
          displayRequirements();
        }
        return;
      }
      const toggle = e.target.closest?.('.toggle-view-btn');
      if (toggle) {
        e.stopPropagation();
        const idx = parseInt(toggle.getAttribute('data-idx'), 10);
        const mode = String(toggle.getAttribute('data-mode') || 'collapsed');
        const collapsed = list.querySelector(`.req-collapsed[data-idx="${idx}"]`);
        const expanded = list.querySelector(`.req-expanded[data-idx="${idx}"]`);
        if (!collapsed || !expanded) return;

        if (mode === 'collapsed') {
          // Expand: Input -> Textarea
          const inp = collapsed.querySelector('.editable-input');
          const ta = expanded.querySelector('.expand-textarea');
          if (ta && inp) ta.value = inp.value;
          collapsed.classList.add('hidden');
          expanded.classList.remove('hidden');
          toggle.setAttribute('data-mode', 'expanded');
          toggle.textContent = 'Collapse';
        } else {
          // Collapse: Textarea -> Input
          const inp = collapsed.querySelector('.editable-input');
          const ta = expanded.querySelector('.expand-textarea');
          if (ta && inp) inp.value = ta.value;
          expanded.classList.add('hidden');
          collapsed.classList.remove('hidden');
          toggle.setAttribute('data-mode', 'collapsed');
          toggle.textContent = 'Expand';
        }
        return;
      }
    });

    // Add Requirement
    const addBtn = document.getElementById('add-requirement-btn');
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        requirements.push("");
        displayRequirements();
      });
    }
  }

  /**
   * Zeigt Verarbeitungsergebnisse an – Master/Detail Layout mit rechtsseitiger, einklappbarer Detail-Ansicht
   */
  function displayResults(results) {
    if (!results || !results.length) {
      resultsDiv.innerHTML = "<h2>📊 Ergebnisse</h2><p>Keine Ergebnisse verfügbar.</p>";
      return;
    }

    // Ergebnisse in globalem UI-State speichern und Auswahl initialisieren
    const isNewResults = currentResults !== results;
    currentResults = results;
    if (isNewResults) { detailsCollapsed = false; }
    if (selectedIndex < 0 || selectedIndex >= currentResults.length) {
      selectedIndex = currentResults.length > 0 ? 0 : -1;
    }

    // Zähler aktualisieren (accepted/rejected)
    const accepted = currentResults.filter(r => r.status === "accepted" || r.verdict === "pass").length;
    const rejected = currentResults.length - accepted;
    acceptedCount = accepted;
    rejectedCount = rejected;

    // Modified/Visible-Counts und Auswahl-Anpassung
    const modifiedCount = Array.isArray(currentResults) ? currentResults.filter(isModified).length : 0;
    const totalCount = Array.isArray(currentResults) ? currentResults.length : 0;
    const visibleIndexes = (function() {
      if (ui && ui.showModifiedOnly) {
        const arr = [];
        for (let i = 0; i < currentResults.length; i++) if (isModified(currentResults[i])) arr.push(i);
        return arr;
      }
      return currentResults.map((_, i) => i);
    })();
    if (ui && ui.showModifiedOnly) {
      if (visibleIndexes.length === 0) {
        selectedIndex = -1;
      } else if (!visibleIndexes.includes(selectedIndex)) {
        selectedIndex = visibleIndexes[0];
      }
    }

    // Header-Actions (Accept all / Reject all + Zähler-Pills)
    const filterHtml = `
      <div class="results-actions">
        <button class="action-btn accept" id="accept-all-btn" ${ui && ui.showModifiedOnly && visibleIndexes.length === 0 ? 'disabled' : ''}>Accept all</button>
        <button class="action-btn reject" id="reject-all-btn" ${ui && ui.showModifiedOnly && visibleIndexes.length === 0 ? 'disabled' : ''}>Reject all</button>
        <div class="counter-pills">
          <span class="pill accepted" id="pill-accepted">✅ ${acceptedCount}</span>
          <span class="pill rejected" id="pill-rejected">❗ ${rejectedCount}</span>
        </div>
      </div>`;

    // Linke Spalte: Master-Liste mit Summary-Rows
    let masterHtml = `<div class="results-master" id="results-master">`;
    if (ui && ui.showModifiedOnly && visibleIndexes.length === 0) {
      masterHtml += `<div class="detail-placeholder" style="padding:12px;">Keine geänderten Items.</div>`;
    } else {
      const listIndexes = (Array.isArray(visibleIndexes) ? visibleIndexes : currentResults.map((_, i) => i));
      listIndexes.forEach((index) => {
        const result = currentResults[index];
        const isOk = computeOk(result);
        const statusBadgeClass = isOk ? "badge ok" : "badge err";
        const text = String(result.originalText || result.requirement || 'Unbekannt');
        const scoreHtml = result.score !== undefined ? `<span class="badge score">Score: ${Number(result.score).toFixed(2)}</span>` : '';
        const modBadge = isModified(result) ? `<span class="badge modified">Modified</span>` : '';
        const reviewBadge = result._autoRefine === 'manual' ? `<span class="badge review">Review</span>` : '';

        masterHtml += `
          <div class="summary-row ${index === selectedIndex ? 'selected' : ''}" data-index="${index}" data-status="${isOk ? 'accepted' : 'rejected'}" data-modified="${isModified(result) ? 'true' : 'false'}">
            <div class="summary-main">
              <span class="badge">${index + 1}</span>
              <div class="summary-text">${escapeHtml(text)}</div>
              <span class="${statusBadgeClass}" data-role="status-badge">${isOk ? 'OK' : 'Fehler'}</span>
              ${scoreHtml}
              ${modBadge}
              ${reviewBadge}
            </div>
            <div class="summary-actions">
              <button class="item-action-btn accept" data-action="accept" data-idx="${index}" title="Accept item" aria-label="Accept item">Accept</button>
              <button class="item-action-btn reject" data-action="reject" data-idx="${index}" title="Reject item" aria-label="Reject item">Reject</button>
            </div>
          </div>
        `;
      });
    }
    masterHtml += `</div>`;

    // Rechte Spalte: Detail-Ansicht (collapsible)
    let detailInner = '';
    if (selectedIndex === -1) {
      detailInner = `<div class="detail-placeholder">Bitte links ein Ergebnis auswählen</div>`;
    } else {
      const res = currentResults[selectedIndex];
      const originalText = String(res.originalText || res.requirement || '');
      const corrected = res.correctedText && res.correctedText !== res.originalText ? res.correctedText : '';

      // Kriterien-Tabelle rendern
      const rows = Array.isArray(res.evaluation) ? res.evaluation.map(ev => {
        const criterion = escapeHtml(ev.criterion || ev.key || '');
        const passed = !!ev.isValid;
        const reasonCell = !passed ? `<div class="criteria-reason">${escapeHtml(ev.reason || 'Keine Begründung vorhanden')}</div>` : '';
        return `
          <tr>
            <td class="crit-col"><span class="mono">${criterion}</span></td>
            <td class="passed-col">${passed ? '✅' : '❌'}</td>
            <td class="reason-col">${reasonCell}</td>
          </tr>
        `;
      }).join('') : '';

      const criteriaTable = `
        <table class="criteria-table">
          <thead>
            <tr>
              <th>Criterion</th>
              <th>Passed</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;

      // Suggestions-Abschnitt vorbereiten
      const suggestions = Array.isArray(res.suggestions) ? res.suggestions : null;
      let suggestionsSection = '';
      if (suggestions && suggestions.length > 0) {
        res._suggestionsOpen = res._suggestionsOpen || {};
        const itemsHtml = suggestions.map((atom, sIdx) => {
          const corr = String(atom?.correction || '');
          const isOpen = !!res._suggestionsOpen[sIdx];
          res._selectedSuggestions = res._selectedSuggestions || {};
          const isSelected = !!res._selectedSuggestions[sIdx];
          const ac = Array.isArray(atom?.acceptance_criteria) ? atom.acceptance_criteria : [];
          const metrics = Array.isArray(atom?.metrics) ? atom.metrics : (atom && typeof atom === 'object' && Array.isArray(atom.metrics) ? atom.metrics : []);
          const acList = ac.length ? `<ul class="suggestion-criteria">${ac.map(c => `<li>${escapeHtml(String(c))}</li>`).join('')}</ul>` : '';
          const metricsList = metrics && metrics.length ? `<ul class="suggestion-metrics">${metrics.map(m => {
            const name = escapeHtml(String(m?.name || m?.metric || ''));
            const op = escapeHtml(String(m?.op || m?.operator || ':'));
            const val = escapeHtml(String(m?.value ?? m?.val ?? ''));
            const ctx = m?.context ? ` - ${escapeHtml(String(m.context))}` : '';
            return `<li><span class="mono">${name}</span> ${op} ${val}${ctx}</li>`;
          }).join('')}</ul>` : '';
          const detailsInner = `${acList}${metricsList}`;
          return `
            <div class="suggestion-card ${isSelected ? 'selected' : ''}" data-r-index="${selectedIndex}" data-s-index="${sIdx}">
              <div class="suggestion-head">
                <div style="flex:1;min-width:0;display:flex;align-items:center;gap:8px;">
                  <input type="checkbox" class="suggestion-select" data-action="toggle-select" data-sidx="${sIdx}" ${isSelected ? 'checked' : ''} aria-label="Select suggestion ${sIdx + 1}">
                  <div>
                    <div><strong>Suggestion #${sIdx + 1}</strong></div>
                    <div class="suggestion-correction" title="${escapeHtml(corr)}">${escapeHtml(corr)}</div>
                  </div>
                </div>
                <div class="suggestion-actions">
                  <button class="item-action-btn" data-action="apply-suggestion" data-sidx="${sIdx}" title="Apply suggestion" aria-label="Apply suggestion">Apply</button>
                  <button class="item-action-btn accept" data-action="accept-suggestion" data-sidx="${sIdx}" title="Accept suggestion" aria-label="Accept suggestion">Accept</button>
                  <button class="item-action-btn accept" data-action="promote-suggestion" data-sidx="${sIdx}" title="Promote suggestion" aria-label="Promote suggestion">Promote</button>
                  <button class="item-action-btn" data-action="toggle-suggestion" data-sidx="${sIdx}" title="Toggle details" aria-label="Toggle details">${isOpen ? 'Details ▾' : 'Details ▸'}</button>
                </div>
              </div>
              ${detailsInner ? `<div class="suggestion-details" style="display:${isOpen ? 'block' : 'none'}">${detailsInner}</div>` : ''}
            </div>
          `;
        }).join('');
        suggestionsSection = `
          <section class="detail-section suggestions">
            <div class="suggestions-header">
              <h4 style="margin:0;">Suggestions</h4>
              <div class="suggestions-actions">
                <button class="action-btn" data-action="apply-selected" title="Apply selected suggestions" aria-label="Apply selected suggestions">Apply selected</button>
                <button class="action-btn accept" data-action="promote-selected" title="Promote selected suggestions" aria-label="Promote selected suggestions">Promote selected</button>
              </div>
            </div>
            ${itemsHtml}
            <div class="small" id="suggestions-status"></div>
          </section>
        `;
      } else {
        suggestionsSection = `
          <section class="detail-section suggestions">
            <h4>Suggestions</h4>
            <button class="action-btn" data-action="load-suggestions" id="load-suggestions-btn" title="Load suggestions" aria-label="Load suggestions">Load suggestions</button>
            <div class="small" id="suggestions-status">Keine Suggestions geladen.</div>
          </section>
        `;
      }

      detailInner = `
        <section class="detail-section">
          <h4>Requirement</h4>
          <div class="mono-container">${escapeHtml(originalText)}</div>
        </section>

        <section class="detail-section">
          <h4>Correction</h4>
          <textarea class="editable-textarea" id="correction-textarea" data-role="correction">${escapeHtml(corrected)}</textarea>
          <button class="save-btn" id="save-correction-btn" data-action="save-correction">Speichern</button>
        </section>

        <section class="detail-section">
          <h4>Criteria</h4>
          ${criteriaTable}
        </section>

        ${suggestionsSection}

        ${res.error ? `<div class="criteria-reason" style="color:#ffb1b1;">${escapeHtml(res.error)}</div>` : ''}
      `;
    }

    const detailBodyStyle = detailsCollapsed ? 'style="display:none;"' : '';
    const detailHtml = `
      <div class="results-detail" id="results-detail">
        <div class="results-detail-header">
          <button class="detail-toggle" id="detail-toggle">${detailsCollapsed ? 'Details ▸' : 'Details ▾'}</button>
          <button class="action-btn" data-action="reanalyze-one" title="Dieses Requirement erneut analysieren" aria-label="Re-analyze this requirement">Re-analyze this requirement</button>
          <button class="action-btn" data-action="auto-refine-one" title="Dieses Requirement automatisch verfeinern" aria-label="Auto-refine this requirement">Auto-refine this requirement</button>
        </div>
        <div class="results-detail-body" id="detail-body" ${detailBodyStyle}>
          ${detailInner}
        </div>
      </div>
    `;

    // Gesamtes Layout rendern (Header + Split)
    const issuesCount = currentResults.filter(r => hasOpenIssues(r)).length;
    const okIndicatorHtml = issuesCount === 0
      ? `<span class="badge ok" id="ok-indicator">All OK</span>`
      : `<span class="badge err" id="ok-indicator">Open issues: ${issuesCount}</span>`;
    const openVisibleCount = (Array.isArray(visibleIndexes) ? visibleIndexes : []).filter(i => hasOpenIssues(currentResults[i])).length;
    const html = `
      <div class="results-header">
        <div class="results-title">
          <h2 style="margin:0">📊 Ergebnisse</h2>
          <span class="badge">Modus: ${CURRENT_MODE}</span>
          <button class="action-btn toggle-modified" data-action="toggle-modified" aria-pressed="${ui && ui.showModifiedOnly ? 'true' : 'false'}" title="Nur geänderte anzeigen">Use modified (${modifiedCount}/${totalCount})</button>
          <div class="reanalyze-group" style="display:flex; gap:8px; align-items:center; margin-left:8px;">
            <button class="action-btn" data-action="reanalyze-modified" title="Nur geänderte erneut analysieren" aria-label="Re-analyze modified" ${modifiedCount === 0 ? 'disabled' : ''}>Re-analyze modified</button>
            <button class="action-btn" data-action="reanalyze-all" title="Alle erneut analysieren" aria-label="Re-analyze all">Re-analyze all</button>
            <button class="action-btn" data-action="auto-refine-open" title="Nur sichtbare offene Issues automatisch verfeinern" aria-label="Auto-refine open issues" ${openVisibleCount === 0 ? 'disabled' : ''}>Auto-refine open issues</button>
          </div>
          ${okIndicatorHtml}
        </div>
        ${filterHtml}
      </div>
      <div class="results-split">
        ${masterHtml}
        <div class="results-resizer" id="results-resizer"></div>
        ${detailHtml}
      </div>
    `;
    resultsDiv.innerHTML = html;

    // Re-Analyze Header Buttons
    document.querySelector('[data-action="reanalyze-modified"]')?.addEventListener('click', async () => {
      const idxs = (ui && ui.showModifiedOnly) ? (visibleIndexes.slice()) : getModifiedIndexes();
      if (!idxs.length) { updateStatus('Keine modifizierten Items gefunden.'); return; }
      const conc = (typeof getAdaptiveConcurrency === 'function' ? getAdaptiveConcurrency() : 3);
      await reanalyzeMany(idxs, { concurrency: conc, includeSuggestions: true });
    });
    document.querySelector('[data-action="reanalyze-all"]')?.addEventListener('click', async () => {
      const idxs = currentResults.map((_, i) => i);
      const conc = (typeof getAdaptiveConcurrency === 'function' ? getAdaptiveConcurrency() : 3);
      await reanalyzeMany(idxs, { concurrency: conc, includeSuggestions: true });
    });
    document.querySelector('[data-action="auto-refine-open"]')?.addEventListener('click', async () => {
      const base = (ui && ui.showModifiedOnly) ? (visibleIndexes.slice()) : currentResults.map((_, i) => i);
      const idxs = base.filter(i => hasOpenIssues(currentResults[i]));
      if (!idxs.length) { updateStatus('Keine offenen sichtbaren Issues.'); return; }
      const conc = (typeof getAdaptiveConcurrency === 'function' ? getAdaptiveConcurrency() : 2);
      await autoRefineMany(idxs, { concurrency: conc });
    });
    // Toggle modified working mode
    document.querySelector('[data-action="toggle-modified"]')?.addEventListener('click', () => {
      ui.showModifiedOnly = !ui.showModifiedOnly;
      displayResults(currentResults);
    });

    // Resizable Split: Initiale Wiederherstellung + Drag-Handling (persistiert)
    (() => {
      const container = resultsDiv.querySelector('.results-split');
      if (!container) return;

      // Initiale Breite aus localStorage lesen (Clamp 20..60), sonst Default 30
      const saved = Number(localStorage.getItem('resultsSplit.master'));
      let masterPercent = (!Number.isNaN(saved) && saved >= 20 && saved <= 60) ? saved : 30;
      container.style.setProperty('--master-col', masterPercent + '%');
      container.style.setProperty('--detail-col', (100 - masterPercent) + '%');

      const resizer = document.getElementById('results-resizer');
      if (!resizer) return;

      resizer.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const rect = container.getBoundingClientRect();

        function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

        function onMove(ev) {
          const x = clamp(ev.clientX - rect.left, 0, rect.width);
          let percent = clamp((x / rect.width) * 100, 20, 60);
          percent = Math.round(percent);
          container.style.setProperty('--master-col', percent + '%');
          container.style.setProperty('--detail-col', (100 - percent) + '%');
        }

        function onUp() {
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          // Persistieren (Clamp 20..60)
          const valStr = container.style.getPropertyValue('--master-col');
          const m = /([\d.]+)/.exec(valStr);
          if (m) {
            const val = Math.round(parseFloat(m[1]));
            if (!Number.isNaN(val)) {
              try { localStorage.setItem('resultsSplit.master', String(clamp(val, 20, 60))); } catch {}
            }
          }
        }

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      });
    })();

    // Events: Accept all / Reject all
    document.getElementById('accept-all-btn')?.addEventListener('click', () => {
      if (ui && ui.showModifiedOnly) setStatusesForIndexes(visibleIndexes, 'accepted');
      else setAllStatuses('accepted');
    });
    document.getElementById('reject-all-btn')?.addEventListener('click', () => {
      if (ui && ui.showModifiedOnly) setStatusesForIndexes(visibleIndexes, 'rejected');
      else setAllStatuses('rejected');
    });

    // Events: Summary-Row Auswahl
    document.querySelectorAll('#results-master .summary-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('.summary-actions') || e.target.closest('button')) return;
        const idx = parseInt(row.getAttribute('data-index'), 10);
        if (!Number.isNaN(idx)) {
          selectedIndex = idx;
          displayResults(currentResults); // vollständiges Re-Rendern ist ausreichend
        }
      });
    });

    // Events: Accept/Reject pro Row
    document.querySelectorAll('#results-master .summary-row .item-action-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.getAttribute('data-action');
        const row = btn.closest('.summary-row');
        if (!row) return;

        const newStatus = action === 'accept' ? 'accepted' : 'rejected';
        setItemStatus(row, newStatus);

        const idx = parseInt(row.getAttribute('data-index'), 10);
        if (!Number.isNaN(idx) && currentResults[idx]) {
          currentResults[idx].status = newStatus;
        }

        if (idx === selectedIndex) {
          displayResults(currentResults);
        } else {
          updateHeaderPills();
        }
      });
    });

    // Toggle: Detail einklappen/ausklappen
    document.getElementById('detail-toggle')?.addEventListener('click', (e) => {
      e.preventDefault();
      detailsCollapsed = !detailsCollapsed;
      displayResults(currentResults);
    });

    // Correction speichern (rechte Spalte)
    attachSaveCorrectionListener();

    // Suggestions: delegierter Click-Handler (rechte Detailspalte)
    document.getElementById('results-detail')?.addEventListener('click', async (e) => {
      const btn = e.target?.closest?.('[data-action]');
      if (!btn) return;
      const action = btn.getAttribute('data-action');
      if (!action) return;
      if (selectedIndex === -1) return;
      const res = currentResults[selectedIndex];

      if (action === 'reanalyze-one') {
        await reanalyzeIndex(selectedIndex, { includeSuggestions: true });
        return;
      } else if (action === 'auto-refine-one') {
        await autoRefineIndex(selectedIndex, {});
        return;
      }

      if (action === 'apply-suggestion') {
        const sIdx = parseInt(btn.getAttribute('data-sidx'), 10);
        if (Number.isNaN(sIdx)) return;
        const atom = res?.suggestions?.[sIdx];
        if (!atom) return;
        const ta = document.getElementById('correction-textarea');
        if (ta) {
          ta.value = String(atom.correction || '');
          try { ta.focus(); } catch {}
        }
      } else if (action === 'promote-suggestion') {
        const sIdx = parseInt(btn.getAttribute('data-sidx'), 10);
        if (Number.isNaN(sIdx)) return;
        const atom = res?.suggestions?.[sIdx];
        if (!atom) return;

        try {
          const original = String(res.originalText || res.text || res.requirement || '');
          updateStatus('Wende Suggestion via LLM Apply an...');
          const resp = await fetch(`${API_BASE}/api/v1/corrections/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              originalText: original,
              selectedSuggestions: [atom],
              mode: 'merge',
              context: {}
            })
          });
          if (!resp.ok) {
            const t = await resp.text().catch(() => '');
            throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
          }
          const data = await resp.json();
          const items = Array.isArray(data?.items) ? data.items : [];
          if (items.length) {
            const txt = String(items[0]?.redefinedRequirement || '');
            const ta = document.getElementById('correction-textarea');
            if (ta) { ta.value = txt; }
            res.correctedText = txt;
            updateStatus('Correction erzeugt (LLM Apply). Speichern optional mit "Speichern"-Button.');
            renderDetailOnly();
            try { document.getElementById('correction-textarea')?.focus(); } catch {}
          } else {
            updateStatus('Keine Correction vom Server erhalten.');
          }
        } catch (err) {
          console.error('Apply Suggestion → Fehler', err);
          updateStatus(`Fehler bei Apply: ${err?.message || String(err)}`);
        }
      } else if (action === 'accept-suggestion') {
        const sIdx = parseInt(btn.getAttribute('data-sidx'), 10);
        if (Number.isNaN(sIdx)) return;
        const atom = res?.suggestions?.[sIdx];
        if (!atom) return;

        const oldOriginal = String(res.originalText || res.text || res.requirement || '');
        const newText = String(atom.correction || atom.text || atom.redefinedRequirement || '');
        ensureEditorSync(selectedIndex, newText);
        res._modified = true;

        const ok = await saveTextImmediate(oldOriginal, newText);
        const statusEl = document.getElementById('suggestions-status');
        if (statusEl) {
          statusEl.textContent = ok ? 'Suggestion übernommen und gespeichert.' : 'Fehler beim Übernehmen.';
          statusEl.classList.remove('status-success','status-error','status-info');
          statusEl.classList.add(ok ? 'status-success' : 'status-error');
        }
        try {
          const ta = document.getElementById('correction-textarea');
          if (ta) ta.focus();
          else {
            const exp = document.querySelector(`.req-expanded[data-idx="${selectedIndex}"] .expand-textarea`);
            const col = document.querySelector(`.req-collapsed[data-idx="${selectedIndex}"] .editable-input`);
            (exp || col)?.focus?.();
          }
        } catch {}
      } else if (action === 'toggle-suggestion') {
        const sIdx = parseInt(btn.getAttribute('data-sidx'), 10);
        if (Number.isNaN(sIdx)) return;
        res._suggestionsOpen = res._suggestionsOpen || {};
        res._suggestionsOpen[sIdx] = !res._suggestionsOpen[sIdx];
        renderDetailOnly();
      } else if (action === 'toggle-select') {
        const sIdx = parseInt(btn.getAttribute('data-sidx'), 10);
        if (Number.isNaN(sIdx)) return;
        res._selectedSuggestions = res._selectedSuggestions || {};
        res._selectedSuggestions[sIdx] = !res._selectedSuggestions[sIdx];
        // UI aktualisieren, um .selected Klasse der Karte zu reflektieren
        renderDetailOnly();
      } else if (action === 'apply-selected') {
        const sel = res._selectedSuggestions || {};
        const atoms = (res.suggestions || []).filter((_, i) => !!sel[i]);
        const text = atoms.map(a => String(a?.correction || '')).filter(Boolean).join('\n');
        const ta = document.getElementById('correction-textarea');
        if (ta) { ta.value = text; try { ta.focus(); } catch {} }
      } else if (action === 'promote-selected') {
        const sel = res._selectedSuggestions || {};
        const atoms = (res.suggestions || []).filter((_, i) => !!sel[i]);
        if (!atoms.length) { updateStatus('Keine Auswahl getroffen.'); return; }
        try {
          const original = String(res.originalText || res.text || res.requirement || '');
          updateStatus('Wende ausgewählte Suggestions via LLM Apply (merge) an...');
          const resp = await fetch(`${API_BASE}/api/v1/corrections/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              originalText: original,
              selectedSuggestions: atoms,
              mode: 'merge',
              context: {}
            })
          });
          if (!resp.ok) {
            const t = await resp.text().catch(() => '');
            throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
          }
          const data = await resp.json();
          const items = Array.isArray(data?.items) ? data.items : [];
          if (items.length) {
            const txt = String(items[0]?.redefinedRequirement || '');
            const ta = document.getElementById('correction-textarea');
            if (ta) { ta.value = txt; }
            res.correctedText = txt;
            updateStatus('Correction erzeugt (LLM Apply, Merge).');
            renderDetailOnly();
          } else {
            updateStatus('Keine Correction vom Server erhalten.');
          }
        } catch (err) {
          console.error('Apply Selected → Fehler', err);
          updateStatus(`Fehler bei Apply Selected: ${err?.message || String(err)}`);
        }
      } else if (action === 'load-suggestions') {
        const loadBtn = btn;
        loadBtn.disabled = true;
        const statusEl = document.getElementById('suggestions-status');
        if (statusEl) { statusEl.textContent = 'Lade Suggestions...'; statusEl.style.color = ''; }

        try {
          const currentResult = res;
          const original = String(currentResult.originalText || currentResult.text || currentResult.requirement || '');
          const url = `${API_BASE}/api/v1/validate/suggest`;
          const payload = [ original ];

          // Request-Logging (gezielt)
          console.debug('Load suggestions → Request', {
            url,
            method: 'POST',
            bodyLength: payload.length,
            origin: location.origin,
            apiBase: API_BASE
          });
          updateStatus(`Suggestions laden: POST ${url} (items=${payload.length})`);
          if (statusEl) {
            statusEl.textContent = `Request POST ${url} (items=${payload.length}) …`;
            statusEl.style.color = '';
          }

          const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(payload),
            mode: 'cors'
          });

          const ct = resp.headers.get('content-type') || '';

          // Response-Logging (gezielt)
          try {
            console.debug('Load suggestions → Response', {
              ok: resp.ok,
              status: resp.status,
              statusText: resp.statusText,
              contentType: ct
            });
          } catch {}

          if (!resp.ok) {
            updateStatus(`Fehler: ${resp.status} ${resp.statusText}`);
            const t = await resp.text().catch(() => '');
            console.error('Load suggestions → HTTP Fehler', { status: resp.status, statusText: resp.statusText, sample: t.slice(0, 500) });
            if (statusEl) {
              statusEl.textContent = `Fehler: ${resp.status} ${resp.statusText}`;
              statusEl.style.color = '#ffb1b1';
            }
            return;
          }

          // Content-Type prüfen + Fallback
          let data;
          if (ct.includes('application/json')) {
            data = await resp.json();
          } else {
            const t = await resp.text();
            try {
              data = JSON.parse(t);
            } catch (e) {
              updateStatus(`Fehler: Unerwarteter Content-Type (${ct}); kein gültiges JSON`);
              console.error('Load suggestions → Parsefehler', { contentType: ct, error: e, sample: t.slice(0, 500) });
              if (statusEl) {
                statusEl.textContent = `Fehler: Unerwarteter Content-Type (${ct}); kein gültiges JSON`;
                statusEl.style.color = '#ffb1b1';
              }
              return;
            }
          }

          // Response-Shape robust auswerten
          let atoms = [];
          if (Array.isArray(data)) {
            // Direktes Array = bereits Suggestions-Array
            atoms = data;
          } else if (data && Array.isArray(data.suggestions)) {
            atoms = data.suggestions;
          } else if (data && data.items && typeof data.items === 'object') {
            const key = Object.keys(data.items || {})[0];
            atoms = data.items?.[key]?.suggestions || [];
          }

          if (!atoms || atoms.length === 0) {
            if (statusEl) {
              statusEl.textContent = 'Keine Suggestions verfügbar.';
              statusEl.style.color = '#ffb1b1';
            }
            return;
          }

          // Erfolg: Zustand aktualisieren und NUR Detailspalte neu rendern
          currentResult.suggestions = atoms;
          currentResult._suggestionsOpen = {};
          currentResult._selectedSuggestions = {};
          
          if (statusEl) {
            statusEl.textContent = `Suggestions geladen (${atoms.length}).`;
            statusEl.style.color = '';
          }

          renderDetailOnly();
        } catch (err) {
          const errName = err?.name ? `${err.name}: ` : '';
          const msg = `${errName}${err?.message || String(err)}`;
          console.error('Load suggestions → Fehler', err);
          const url = `${API_BASE}/api/v1/validate/suggest`;
          const hint = (err && (err.name === 'TypeError' || String(err.message || '').includes('Failed to fetch')))
            ? 'Hinweis: Möglicher CORS/Preflight- oder Mixed-Content-Fehler (https Seite → http API) bzw. Netzwerkfehler.'
            : '';
          if (statusEl) {
            statusEl.textContent = `Fehler: ${msg}. ${hint} URL=${url}, method=POST, bodyLen=1`;
            statusEl.style.color = '#ffb1b1';
          }
          updateStatus(`Fehler beim Laden der Suggestions: ${msg}. ${hint} URL=${url}`);
        } finally {
          loadBtn.disabled = false;
        }
      }
    });
    // Initiale Zähler setzen
    updateHeaderPills();
  }

  // Hotfix helpers: render only detail panel and attach save listener
  function attachSaveCorrectionListener() {
    const btn = document.getElementById('save-correction-btn');
    if (!btn) return;
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (selectedIndex === -1) return;
      const res = currentResults[selectedIndex];
      const ta = document.getElementById('correction-textarea');
      const corrected = ta?.value || '';
      if (!corrected.trim()) {
        console.warn('Leere Correction – nichts zu speichern.');
        return;
      }
      try {
        const original = String(res.originalText || res.requirement || '');
        const resp = await fetch(`${API_BASE}/api/v1/corrections/text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ originalText: original, text: corrected })
        });
        if (!resp.ok) {
          const t = await resp.text().catch(() => '');
          throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
        }
        updateStatus('Correction gespeichert.');
        res.correctedText = corrected; // lokalen Zustand aktualisieren
      } catch (err) {
        console.error('Fehler beim Speichern der Correction:', err);
        updateStatus(`Fehler beim Speichern der Correction: ${err.message}`);
      }
    });
  }

  function renderDetailOnly() {
    const detailBody = document.getElementById('detail-body');
    if (!detailBody) return;
    let detailInner = '';
    if (selectedIndex === -1) {
      detailInner = `<div class="detail-placeholder">Bitte links ein Ergebnis auswählen</div>`;
    } else {
      const res = currentResults[selectedIndex];
      const originalText = String(res.originalText || res.requirement || '');
      const corrected = res.correctedText && res.correctedText !== res.originalText ? res.correctedText : '';
      const rows = Array.isArray(res.evaluation) ? res.evaluation.map(ev => {
        const criterion = escapeHtml(ev.criterion || ev.key || '');
        const passed = !!ev.isValid;
        const reasonCell = !passed ? `<div class="criteria-reason">${escapeHtml(ev.reason || 'Keine Begründung vorhanden')}</div>` : '';
        return `
          <tr>
            <td class="crit-col"><span class="mono">${criterion}</span></td>
            <td class="passed-col">${passed ? '✅' : '❌'}</td>
            <td class="reason-col">${reasonCell}</td>
          </tr>
        `;
      }).join('') : '';
      const criteriaTable = `
        <table class="criteria-table">
          <thead>
            <tr>
              <th>Criterion</th>
              <th>Passed</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      const suggestions = Array.isArray(res.suggestions) ? res.suggestions : null;
      let suggestionsSection = '';
      if (suggestions && suggestions.length > 0) {
        res._suggestionsOpen = res._suggestionsOpen || {};
        res._selectedSuggestions = res._selectedSuggestions || {};
        const itemsHtml = suggestions.map((atom, sIdx) => {
          const corr = String(atom?.correction || '');
          const isOpen = !!res._suggestionsOpen[sIdx];
          const isSelected = !!res._selectedSuggestions[sIdx];
          const ac = Array.isArray(atom?.acceptance_criteria) ? atom.acceptance_criteria : [];
          const metrics = Array.isArray(atom?.metrics) ? atom.metrics : (atom && typeof atom === 'object' && Array.isArray(atom.metrics) ? atom.metrics : []);
          const acList = ac.length ? `<ul class="suggestion-criteria">${ac.map(c => `<li>${escapeHtml(String(c))}</li>`).join('')}</ul>` : '';
          const metricsList = metrics && metrics.length ? `<ul class="suggestion-metrics">${metrics.map(m => {
            const name = escapeHtml(String(m?.name || m?.metric || ''));
            const op = escapeHtml(String(m?.op || m?.operator || ':'));
            const val = escapeHtml(String(m?.value ?? m?.val ?? ''));
            const ctx = m?.context ? ` - ${escapeHtml(String(m.context))}` : '';
            return `<li><span class="mono">${name}</span> ${op} ${val}${ctx}</li>`;
          }).join('')}</ul>` : '';
          const detailsInner = `${acList}${metricsList}`;
          return `
            <div class="suggestion-card ${isSelected ? 'selected' : ''}" data-r-index="${selectedIndex}" data-s-index="${sIdx}">
              <div class="suggestion-head">
                <div style="flex:1;min-width:0;display:flex;align-items:center;gap:8px;">
                  <input type="checkbox" class="suggestion-select" data-action="toggle-select" data-sidx="${sIdx}" ${isSelected ? 'checked' : ''} aria-label="Select suggestion ${sIdx + 1}">
                  <div>
                    <div><strong>Suggestion #${sIdx + 1}</strong></div>
                    <div class="suggestion-correction" title="${escapeHtml(corr)}">${escapeHtml(corr)}</div>
                  </div>
                </div>
                <div class="suggestion-actions">
                  <button class="item-action-btn" data-action="apply-suggestion" data-sidx="${sIdx}" title="Apply suggestion" aria-label="Apply suggestion">Apply</button>
                  <button class="item-action-btn accept" data-action="accept-suggestion" data-sidx="${sIdx}" title="Accept suggestion" aria-label="Accept suggestion">Accept</button>
                  <button class="item-action-btn accept" data-action="promote-suggestion" data-sidx="${sIdx}" title="Promote suggestion" aria-label="Promote suggestion">Promote</button>
                  <button class="item-action-btn" data-action="toggle-suggestion" data-sidx="${sIdx}" title="Toggle details" aria-label="Toggle details">${isOpen ? 'Details ▾' : 'Details ▸'}</button>
                </div>
              </div>
              ${detailsInner ? `<div class="suggestion-details" style="display:${isOpen ? 'block' : 'none'}">${detailsInner}</div>` : ''}
            </div>
          `;
        }).join('');
        suggestionsSection = `
          <section class="detail-section suggestions">
            <div class="suggestions-header">
              <h4 style="margin:0;">Suggestions</h4>
              <div class="suggestions-actions">
                <button class="action-btn" data-action="apply-selected" title="Apply selected suggestions" aria-label="Apply selected suggestions">Apply selected</button>
                <button class="action-btn accept" data-action="promote-selected" title="Promote selected suggestions" aria-label="Promote selected suggestions">Promote selected</button>
              </div>
            </div>
            ${itemsHtml}
            <div class="small" id="suggestions-status"></div>
          </section>
        `;
      } else {
        suggestionsSection = `
          <section class="detail-section suggestions">
            <h4>Suggestions</h4>
            <button class="action-btn" data-action="load-suggestions" id="load-suggestions-btn" title="Load suggestions" aria-label="Load suggestions">Load suggestions</button>
            <div class="small" id="suggestions-status">Keine Suggestions geladen.</div>
          </section>
        `;
      }
      detailInner = `
        <section class="detail-section">
          <h4>Requirement</h4>
          <div class="mono-container">${escapeHtml(originalText)}</div>
        </section>

        <section class="detail-section">
          <h4>Correction</h4>
          <textarea class="editable-textarea" id="correction-textarea" data-role="correction">${escapeHtml(corrected)}</textarea>
          <button class="save-btn" id="save-correction-btn" data-action="save-correction">Speichern</button>
        </section>

        <section class="detail-section">
          <h4>Criteria</h4>
          ${criteriaTable}
        </section>

        ${suggestionsSection}

        ${res.error ? `<div class="criteria-reason" style="color:#ffb1b1;">${escapeHtml(res.error)}</div>` : ''}
      `;
    }
    detailBody.innerHTML = detailInner;
    attachSaveCorrectionListener();
  }

  // Setzt den Status eines einzelnen Ergebnis-Items und aktualisiert Header-Zähler
  function setItemStatus(itemEl, status) {
    const current = itemEl.getAttribute('data-status');
    if (current === status) return;
    
    // Badge aktualisieren
    const badge = itemEl.querySelector('[data-role="status-badge"]');
    if (badge) {
      if (status === 'accepted') {
        badge.classList.remove('err');
        badge.classList.add('ok');
        badge.textContent = 'OK';
      } else {
        badge.classList.remove('ok');
        badge.classList.add('err');
        badge.textContent = 'Fehler';
      }
    }

    // Zähler anpassen
    if (current === 'accepted') acceptedCount--; else rejectedCount--;
    if (status === 'accepted') acceptedCount++; else rejectedCount++;

    itemEl.setAttribute('data-status', status);
    updateHeaderPills();
  }

  // Setzt alle Items auf einen Status (Accept all / Reject all)
  function setAllStatuses(status) {
    // UI aktualisieren
    document.querySelectorAll('#results-master .summary-row').forEach(item => setItemStatus(item, status));
    // Datenmodell synchronisieren
    if (Array.isArray(currentResults) && currentResults.length) {
      for (let i = 0; i < currentResults.length; i++) {
        currentResults[i].status = status;
      }
    }
    updateHeaderPills();
  }

  // Setzt Status für eine definierte Indexmenge (sichtbare/gefilteter Scope)
  function setStatusesForIndexes(indexes, status) {
    try {
      const arr = Array.isArray(indexes) ? indexes : [];
      for (let i = 0; i < arr.length; i++) {
        const idx = Number(arr[i]);
        if (!Number.isInteger(idx)) continue;
        const row = document.querySelector(`#results-master .summary-row[data-index="${idx}"]`);
        if (row) setItemStatus(row, status);
        if (Array.isArray(currentResults) && currentResults[idx]) {
          currentResults[idx].status = status;
        }
      }
      updateHeaderPills();
    } catch (e) {
      console.error('setStatusesForIndexes() Fehler', e);
    }
  }

  // Aktualisiert die Header-Pills
  function updateHeaderPills() {
    const acc = document.getElementById('pill-accepted');
    const rej = document.getElementById('pill-rejected');
    if (acc) acc.textContent = `✅ ${acceptedCount}`;
    if (rej) rej.textContent = `❗ ${rejectedCount}`;
  }

  // Einfaches Filter-Feature (UI-Only)
  function filterResults(mode) {
    const items = document.querySelectorAll('#results-list .item');
    items.forEach(el => {
      const st = el.getAttribute('data-status');
      if (mode === 'all') el.style.display = '';
      else if (mode === 'accepted') el.style.display = st === 'accepted' ? '' : 'none';
      else if (mode === 'rejected') el.style.display = st === 'rejected' ? '' : 'none';
    });
  }

  /**
   * Fügt Event Listener für kollabierbare Result Cards hinzu (legacy, nicht mehr verwendet)
   */
  function addCollapsibleEventListeners() {
    const resultHeaders = document.querySelectorAll('.result-header');
    
    resultHeaders.forEach(header => {
      header.addEventListener('click', function() {
        const resultItem = this.closest('.result-item');
        if (resultItem) {
          resultItem.classList.toggle('expanded');
        }
      });
    });
  }

  /**
   * Utility: HTML escapen zur sicheren Ausgabe in Inputs/HTML
   */
  function escapeHtml(str) {
    return String(str)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  /**
   * Aktualisiert den Status-Text
   */
  function updateStatus(message) {
    statusDiv.textContent = message;
    console.log("Status:", message);
  }

  /**
   * Liefert den aktuellsten Text für einen Index (Detail-Korrektur > Result.originalText > Editor links)
   */
  function getCurrentTextForIndex(index) {
    try {
      const idx = Number(index);
      if (!Number.isInteger(idx) || idx < 0) return '';
      // 1) Aktive Detail-Korrektur (wenn ausgewählt und nicht leer)
      if (selectedIndex === idx) {
        const ta = document.getElementById('correction-textarea');
        const val = (ta && typeof ta.value === 'string') ? ta.value.trim() : '';
        if (val) return val;
      }
      // 2) Result-Originaltext
      const fromResult = currentResults?.[idx]?.originalText;
      if (fromResult && String(fromResult).trim()) {
        return String(fromResult).trim();
      }
      // 3) Fallback: linker Editor (collapsed/expanded)
      const collapsed = document.querySelector(`.req-collapsed[data-idx="${idx}"] .editable-input`);
      if (collapsed && typeof collapsed.value === 'string' && collapsed.value.trim()) {
        return String(collapsed.value).trim();
      }
      const expanded = document.querySelector(`.req-expanded[data-idx="${idx}"] .expand-textarea`);
      if (expanded && typeof expanded.value === 'string' && expanded.value.trim()) {
        return String(expanded.value).trim();
      }
      return '';
    } catch {
      return '';
    }
  }

  /**
   * Ersetzt das Ergebnis an einem Index und rendert die UI neu
   */
  function replaceResultAtIndex(index, newResult) {
    try {
      const idx = Number(index);
      if (!Number.isInteger(idx) || idx < 0) return;
      const nr = { ...(newResult || {}) };
      if (!nr.originalText || !String(nr.originalText).trim()) {
        const fallbackText = getCurrentTextForIndex(idx) || currentResults?.[idx]?.originalText || '';
        nr.originalText = String(fallbackText);
      }
      const next = Array.isArray(currentResults) ? currentResults.slice() : [];
      next[idx] = nr;
      currentResults = next;

      // Auswahl beibehalten, bei Out-of-Range auf 0 clampen
      if (currentResults.length > 0) {
        if (selectedIndex < 0 || selectedIndex >= currentResults.length) selectedIndex = 0;
      } else {
        selectedIndex = -1;
      }

      // Komplettes Re-Rendern für Konsistenz
      displayResults(currentResults);
    } catch (e) {
      console.error('replaceResultAtIndex() Fehler', e);
    }
  }

  /**
   * Re-Analyse eines einzelnen Index
   */
  async function reanalyzeIndex(index, { includeSuggestions = true } = {}) {
    const idx = Number(index);
    const text = getCurrentTextForIndex(idx);
    updateStatus('Re-Analyse gestartet…');
    try {
      const resp = await fetch(`${API_BASE}/api/v1/validate/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: [text], includeSuggestions })
      });
      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
      }
      const data = await resp.json();
      const arr = Array.isArray(data) ? data : [];
      const result = arr[0] || {
        originalText: text,
        status: 'rejected',
        evaluation: [],
        error: 'Leere Antwort'
      };
      if (!result.originalText) result.originalText = text;
      replaceResultAtIndex(idx, result);
      updateStatus('Re-Analyse abgeschlossen (1/1).');
    } catch (err) {
      const msg = String(err?.message || err || 'Unbekannter Fehler');
      const fail = {
        originalText: text,
        status: 'rejected',
        evaluation: [],
        error: msg
      };
      replaceResultAtIndex(idx, fail);
      updateStatus('Fehler bei Re-Analyse: ' + msg);
    }
  }

  /**
   * Re-Analyse vieler Indexe mit einfacher Nebenläufigkeit
   */
  async function reanalyzeMany(indexes, { concurrency = 1, includeSuggestions = true } = {}) {
    try {
      const norm = Array.isArray(indexes)
        ? indexes.map(i => Number(i)).filter(i => Number.isInteger(i) && i >= 0 && i < (currentResults?.length || 0))
        : [];
      const uniq = Array.from(new Set(norm));
      const queue = uniq.slice();
      const total = queue.length;
      let processed = 0;
      let errorCount = 0;
      let active = 0;

      updateStatus(`Starte Re-Analyse (gesamt: ${total})…`);
      if (total === 0) return;

      async function runNext() {
        const nextIdx = queue.shift();
        if (nextIdx === undefined) return;
        active++;
        const text = getCurrentTextForIndex(nextIdx);
        try {
          const resp = await fetch(`${API_BASE}/api/v1/validate/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: [text], includeSuggestions })
          });
          if (!resp.ok) {
            const t = await resp.text().catch(() => '');
            throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
          }
          const data = await resp.json();
          const arr = Array.isArray(data) ? data : [];
          const result = arr[0] || {
            originalText: text,
            status: 'rejected',
            evaluation: [],
            error: 'Leere Antwort'
          };
          if (!result.originalText) result.originalText = text;
          replaceResultAtIndex(nextIdx, result);
        } catch (err) {
          errorCount += 1;
          const msg = String(err?.message || err || 'Unbekannter Fehler');
          replaceResultAtIndex(nextIdx, {
            originalText: text,
            status: 'rejected',
            evaluation: [],
            error: msg
          });
        } finally {
          processed += 1;
          updateStatus(`Re-analyzed: ${processed}/${total} (Fehler: ${errorCount})`);
          active--;
          if (queue.length > 0) {
            await runNext();
          }
        }
      }

      const cap = Math.max(1, Math.min(5, Number(concurrency) || 1));
      const workers = [];
      for (let i = 0; i < cap; i++) workers.push(runNext());
      await Promise.all(workers);

      updateStatus(`Re-Analyse abgeschlossen: ${processed}/${total} (Fehler: ${errorCount}).`);
    } catch (e) {
      const msg = String(e?.message || e || 'Unbekannter Fehler');
      updateStatus(`Fehler im Re-Analyse-Loop: ${msg}`);
    }
  }

  // Auto-Refine Funktionen
  async function autoRefineIndex(index, opts = {}) {
    try {
      const idx = Number(index);
      if (!Number.isInteger(idx) || idx < 0 || idx >= (currentResults?.length || 0)) return false;
      const maxIter = Number(opts?.maxIter ?? UI_CONF?.maxAutoRefineIter ?? 5);
      for (let iter = 1; iter <= maxIter; iter++) {
        updateStatus(`Auto-refine (${iter}/${maxIter}) für #${idx + 1}…`);
        try {
          const res = currentResults[idx];
          if (!res) break;
          if (!hasOpenIssues(res)) {
            updateStatus(`Auto-refine: #${idx + 1} ist bereits freigegeben.`);
            return true;
          }
          // Suggestions laden (falls nötig)
          const suggestions = await ensureSuggestions(idx);
          const sel = res._selectedSuggestions || {};
          const selectedAtoms = (Array.isArray(suggestions) ? suggestions : []).filter((_, i) => !!sel[i]);
          const atoms = selectedAtoms.length ? selectedAtoms : (Array.isArray(suggestions) ? suggestions : []);
          const baseText = String(res.originalText || res.text || res.requirement || getCurrentTextForIndex(idx) || '');
          const merged = await mergeApply(baseText, atoms);
          if (!merged) {
            updateStatus(`Auto-refine (#${idx + 1}): Kein Merge-Ergebnis erhalten.`);
            break;
          }
          // Re-Analyse mit dem gemergeten Text durchführen
          const resp = await fetch(`${API_BASE}/api/v1/validate/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: [merged], includeSuggestions: true })
          });
          if (!resp.ok) {
            const t = await resp.text().catch(() => '');
            throw new Error(`HTTP ${resp.status}: ${t || resp.statusText}`);
          }
          const data = await resp.json();
          const arr = Array.isArray(data) ? data : [];
          const nextRes = arr[0] || {
            originalText: merged,
            status: 'rejected',
            evaluation: [],
            error: 'Leere Antwort'
          };
          if (!nextRes.originalText) nextRes.originalText = merged;
          replaceResultAtIndex(idx, nextRes);
          if (!hasOpenIssues(nextRes)) {
            updateStatus(`Auto-refine erfolgreich (#${idx + 1}) in ${iter} Iteration(en).`);
            return true;
          }
        } catch (e) {
          console.error('autoRefineIndex() Iterationsfehler', e);
          updateStatus(`Auto-refine Fehler (#${idx + 1}): ${e?.message || String(e)}`);
        }
      }
      // Eskalation zur manuellen Prüfung
      try {
        if (Array.isArray(currentResults) && currentResults[idx]) {
          currentResults[idx]._autoRefine = 'manual';
        }
      } catch {}
      displayResults(currentResults);
      updateStatus(`Auto-refine beendet (#${idx + 1}): manuelle Review erforderlich.`);
      return false;
    } catch (e) {
      console.error('autoRefineIndex() Fehler', e);
      updateStatus(`Auto-refine Fehler: ${e?.message || String(e)}`);
      return false;
    }
  }

  async function autoRefineMany(indexes, { concurrency = (typeof getAdaptiveConcurrency === 'function' ? getAdaptiveConcurrency() : 2) } = {}) {
    try {
      const norm = Array.isArray(indexes)
        ? indexes.map(i => Number(i)).filter(i => Number.isInteger(i) && i >= 0 && i < (currentResults?.length || 0))
        : [];
      const uniq = Array.from(new Set(norm));
      const queue = uniq.slice();
      const total = queue.length;
      let processed = 0;
      let errorCount = 0;
      let active = 0;

      updateStatus(`Starte Auto-refine (gesamt: ${total})…`);
      if (total === 0) return;

      async function runNext() {
        const nextIdx = queue.shift();
        if (nextIdx === undefined) return;
        active++;
        try {
          const ok = await autoRefineIndex(nextIdx, {});
          if (!ok) errorCount += 1;
        } catch (e) {
          errorCount += 1;
          console.error('autoRefineMany → Fehler', e);
        } finally {
          processed += 1;
          updateStatus(`Auto-refined: ${processed}/${total} (Fehler: ${errorCount})`);
          active--;
          if (queue.length > 0) {
            await runNext();
          }
        }
      }

      const cap = Math.max(1, Math.min(5, Number(concurrency) || 1));
      const workers = [];
      for (let i = 0; i < cap; i++) workers.push(runNext());
      await Promise.all(workers);

      updateStatus(`Auto-refine abgeschlossen: ${processed}/${total} (Fehler: ${errorCount}).`);
    } catch (e) {
      const msg = String(e?.message || e || 'Unbekannter Fehler');
      updateStatus(`Fehler im Auto-refine-Loop: ${msg}`);
    }
  }

  // Initialisierung
  updateStatus("Bereit. Klicken Sie 'Load MD' um zu beginnen.");
})();