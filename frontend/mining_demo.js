(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const btn = $("#btnMine");
  const fileInput = $("#files");
  const modelInput = { value: "" };
  const neighborsInput = document.getElementById("neighbors") || { checked: false };
  const useLlmInput = { checked: false };
  const cfgSelect = document.getElementById("cfgSelect");
  const goldSelect = document.getElementById("goldSelect");
  const btnReloadGold = document.getElementById("btnReloadGold");
  const useGoldFewshot = document.getElementById("useGoldFewshot");
  const autoGoldChk = document.getElementById("autoGold");
  const fastModeChk = document.getElementById("fastMode");
  const tempInput = document.getElementById("temperature");
  const btnLoadCfg = document.getElementById("btnLoadCfg");
  const btnPreviewCfg = document.getElementById("btnPreviewCfg");
  const cfgIdInput = null;
  const cfgJson = null;
  const btnSaveCfg = null;
  const cfgFileInput = null;
  const btnLoadCfgFile = null;
  const btnInsertCfgTemplate = null;
  const schemaIdInput = null;
  const schemaFileInput = null;
  const btnSaveSchema = null;
  const reportSelect = null;
  const btnLoadReports = null;
  const btnShowReport = null;
  const btnShowLatestReport = null;
  let currentConfigId = "default";
  const statusEl = $("#status");
  const resultsEl = $("#results");
  const btnSaveReqs = document.getElementById("btnSaveReqs") || null;

  // Preview-Elemente rechts
  const previewMeta = $("#previewMeta");
  const previewText = $("#previewText");
  const previewBox = $("#previewBox");

  // Graph (Cytoscape) in der Mitte
  let cy = null; let cyModal = null;
  function _cyStyles() {
    return [
      // Basistexte mit dunklem Text-Hintergrund statt weißem Highlight
      { selector: 'node', style: {
        'label':'data(name)',
        'color':'#e6e6e6',
        'background-color':'#4cc9f0',
        'font-size':'10px',
        'min-zoomed-font-size': 6,
        'text-wrap':'wrap',
        'text-max-width':'160px',
        'text-background-color':'transparent',
        'text-background-opacity': 0,
        'text-background-padding':'3px',
        'text-background-shape':'roundrectangle',
        'text-outline-width': 0,
        'text-outline-color': 'transparent'
      }},
      { selector: 'node[type = "Requirement"]', style: { 'shape':'round-rectangle', 'background-color':'#38bdf8' } },
      { selector: 'node[type = "Actor"]', style: { 'shape':'ellipse', 'background-color':'#a78bfa' } },
      { selector: 'node[type = "Action"]', style: { 'shape':'diamond', 'background-color':'#22c55e' } },
      { selector: 'node[type = "Entity"]', style: { 'shape':'rectangle', 'background-color':'#f97316' } },
      // Tag-Knoten: heller Hintergrund, dunkle Schrift, KEIN dunkler Text-Hintergrund
      { selector: 'node[type = "Tag"]', style: {
        'shape':'hexagon',
        'background-color':'#60a5fa',
        'color':'#061018',
        'border-width':2,
        'border-color':'#93c5fd',
        'text-background-opacity': 0
      }},
      { selector: 'edge', style: {
        'width':1.5,
        'line-color':'#94a3b8',
        'target-arrow-color':'#94a3b8',
        'target-arrow-shape':'triangle',
        'curve-style':'bezier',
        'label':'data(rel)',
        'color':'#ffd700',
        'font-size':'9px',
        'text-background-color':'transparent',
        'text-background-opacity':0,
        'text-background-padding':'2px',
        'text-rotation':'autorotate',
        'text-outline-width': 0,
        'text-outline-color': 'transparent'
      }},
      // Auswahl-Overlay deaktivieren (kein weißes Markieren)
      { selector: 'node:selected', style: { 'overlay-opacity': 0 } },
      { selector: 'edge:selected', style: { 'overlay-opacity': 0 } }
    ];
  }
  function _layoutOpts() {
    const hasFcose = (typeof window !== 'undefined' && window.fcose);
    if (hasFcose) {
      return {
        name: 'fcose',
        quality: 'proof',
        randomize: true,
        animate: false,
        fit: true,
        // Mehr Distanz/Platz zwischen Komponenten
        idealEdgeLength: 300,
        nodeSeparation: 360,
        componentSpacing: 480,
        gravity: 0.12,
        nodeRepulsion: 900000,
        nestingFactor: 0.8,
        packComponents: true,
        padding: 120,
        nodeDimensionsIncludeLabels: true,
        tile: true
      };
    }
    // Fallback: etwas mehr Padding auch bei cose
    return { name: 'cose', animate: false, padding: 120 };
  }
  function ensureGraph() {
    if (cy) return cy;
    const el = document.getElementById("cy");
    if (!el || typeof cytoscape === "undefined") return null;
    cy = cytoscape({ container: el, elements: [], style: _cyStyles(), layout: _layoutOpts() });
    // Vollbild-Resize unterstützen
    try {
      window.addEventListener('resize', () => {
        try { cy.resize(); cy.fit(); } catch (e) {}
      });
    } catch (e) {}
    return cy;
  }
  function ensureModalGraph() {
    if (cyModal) return cyModal;
    const el = document.getElementById("cyModal");
    if (!el || typeof cytoscape === "undefined") return null;
    cyModal = cytoscape({ container: el, elements: [], style: _cyStyles(), layout: _layoutOpts() });
    try {
      window.addEventListener('resize', () => {
        try { cyModal.resize(); cyModal.fit(); } catch (e) {}
      });
    } catch (e) {}
    return cyModal;
  }
  function resetGraph() { const c = ensureGraph(); if (c) c.elements().remove(); }
  function upsertNodeCy(payload) {
    const id = (payload && (payload.node_id || payload.id));
    if (!id) return;
    if (cy.getElementById(id).length) return;
    const name = payload.name || id;
    const type = payload.type || "Unknown";
    cy.add({ group: "nodes", data: { id, name, type } });
  }
  function upsertEdgeCy(payload) {
    const from = payload && payload.from_node_id;
    const to = payload && payload.to_node_id;
    const rel = (payload && payload.rel) || "RELATES_TO";
    if (!from || !to) return;
    const id = (payload && payload.edge_id) || (from + "#" + rel + "#" + to);
    if (cy.getElementById(id).length) return;
    if (!cy.getElementById(from).length) cy.add({ group:"nodes", data:{ id: from, name: from, type: "Unknown" } });
    if (!cy.getElementById(to).length) cy.add({ group:"nodes", data:{ id: to, name: to, type: "Unknown" } });
    cy.add({ group:"edges", data:{ id, source: from, target: to, rel } });
  }
  function renderGraph(nodes, edges) {
    const c = ensureGraph();
    if (!c) return;
    c.elements().remove();
    (nodes || []).forEach((n) => {
      const p = n && (n.payload || { node_id: n.id, name: n.name, type: n.type });
      if (p) upsertNodeCy(p);
    });
    (edges || []).forEach((e) => {
      const p = e && (e.payload || { edge_id: e.id, from_node_id: e.from, to_node_id: e.to, rel: e.rel });
      if (p) upsertEdgeCy(p);
    });
    c.layout(_layoutOpts()).run();
    try { c.resize(); c.fit(); } catch (e) {}
  }

  // Export-Helper
  function _ts() { return new Date().toISOString().replace(/[:.]/g, "-"); }
  function _downloadUrl(url, filename, revoke=false) {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    if (revoke) setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportCyToPng(cyInst, filename) {
    if (!cyInst) return;
    const dataUrl = cyInst.png({ full: true, scale: 2, bg: "#0d1220" });
    _downloadUrl(dataUrl, filename || ("kg-" + _ts() + ".png"));
  }
  function exportGraphJson(nodes, edges, filename) {
    const data = { nodes: nodes || [], edges: edges || [] };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    _downloadUrl(url, filename || ("kg-" + _ts() + ".json"), true);
  }

  function renderGraphModal(nodes, edges) {
    const c = ensureModalGraph();
    if (!c) return;
    c.elements().remove();
    (nodes || []).forEach((n) => {
      const p = n && (n.payload || { node_id: n.id, name: n.name, type: n.type });
      if (p) {
        if (!c.getElementById(p.node_id || p.id).length) {
          c.add({ group:'nodes', data:{ id: p.node_id || p.id, name: p.name || p.node_id, type: p.type || 'Unknown' } });
        }
      }
    });
    (edges || []).forEach((e) => {
      const p = e && (e.payload || { edge_id: e.id, from_node_id: e.from, to_node_id: e.to, rel: e.rel });
      if (p) {
        const id = p.edge_id || ((p.from_node_id||'') + '#' + (p.rel||'RELATES_TO') + '#' + (p.to_node_id||''));
        if (!c.getElementById(p.from_node_id||'').length) c.add({ group:'nodes', data:{ id: p.from_node_id, name: p.from_node_id, type:'Unknown' } });
        if (!c.getElementById(p.to_node_id||'').length) c.add({ group:'nodes', data:{ id: p.to_node_id, name: p.to_node_id, type:'Unknown' } });
        if (!c.getElementById(id).length) c.add({ group:'edges', data:{ id, source:p.from_node_id, target:p.to_node_id, rel:(p.rel||'RELATES_TO') } });
      }
    });
    c.layout(_layoutOpts()).run();
    try { window.__kg_last_nodes = Array.isArray(nodes) ? nodes : []; window.__kg_last_edges = Array.isArray(edges) ? edges : []; } catch (e) {}
    try { c.resize(); c.fit(); } catch (e) {}
  }
  function focusReqInGraph(reqId) {
    if (cy) {
      const el = cy.getElementById(reqId);
      if (el && el.length) { try { cy.elements().unselect(); el.select(); cy.center(el); } catch(e){} }
    }
    if (cyModal) {
      const el2 = cyModal.getElementById(reqId);
      if (el2 && el2.length) { try { cyModal.elements().unselect(); el2.select(); cyModal.center(el2); } catch(e){} }
    }
  }

  // Zustand für Preview/Selektion
  let previewRawEscaped = "";
  let activeCard = null;

  // Utils
  function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

  function setPreview(name, text) {
    if (!previewMeta || !previewText || !previewBox) return;
    const maxPreview = 20000;
    const shown = text.length > maxPreview ? (text.slice(0, maxPreview) + "\n\n… [gekürzt]") : text;
    const looksJson = /^\s*[\[{]/.test(shown);
    if (looksJson) {
      try {
        const parsed = JSON.parse(text);
        previewText.textContent = JSON.stringify(parsed, null, 2);
        previewRawEscaped = escapeHtml(JSON.stringify(parsed, null, 2));
      } catch (_) {
        const escaped = escapeHtml(shown);
        previewRawEscaped = escapeHtml(text);
        previewText.innerHTML = escaped;
      }
    } else {
    const escaped = escapeHtml(shown);
      previewRawEscaped = escapeHtml(text);
    previewText.innerHTML = escaped;
    }
    previewMeta.textContent = name ? `Datei: ${name}` : "Keine Datei geladen.";
    try { previewBox.scrollTop = 0; } catch(e){}
  }

  function clearPreview() {
    if (!previewMeta || !previewText) return;
    previewRawEscaped = "";
    previewText.textContent = "";
    previewMeta.textContent = "Keine Datei geladen.";
  }

  function highlightInPreview(query) {
    if (!previewRawEscaped || !previewText) return;
    const q = (query || "").trim();
    if (!q) { previewText.innerHTML = previewRawEscaped; return; }
    const words = Array.from(new Set(q.split(/[^A-Za-zÄÖÜäöü0-9]+/g).filter(w => w && w.length >= 3)));
    if (!words.length) { previewText.innerHTML = previewRawEscaped; return; }
    let html = previewRawEscaped;
    for (const w of words) {
      const re = new RegExp(`\\b(${w.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")})\\b`, "gi");
      html = html.replace(re, "<mark>$1</mark>");
    }
    previewText.innerHTML = html;
  }

  function setStatus(text, cls = "") {
    statusEl.className = "status " + (cls || "");
    statusEl.textContent = text;
  }

  function clearResults() {
    resultsEl.innerHTML = "";
  }

  function renderItems(items) {
    clearResults();
    if (!items || !items.length) {
      resultsEl.innerHTML = `
        <div class="card">
          <div class="status warn">Keine Requirements gefunden.</div>
        </div>
      `;
      return;
    }

    const frag = document.createDocumentFragment();

    items.forEach((it, idx) => {
      const card = document.createElement("div");
      card.className = "card";

      const reqId = it.req_id || it.id || `REQ-${idx + 1}`;
      const titleText = it.title || it.requirementText || it.text || reqId;
      const tag = it.tag || (it.extraction_class || it.type || "n/a");
      const evs = Array.isArray(it.evidence_refs) ? it.evidence_refs : [];

      const evLis = evs.map((e) => {
        if (typeof e === "string") return `<li>${escapeHtml(e)}</li>`;
        try { return `<li><code>${escapeHtml(JSON.stringify(e))}</code></li>`; }
        catch { return `<li>n/a</li>`; }
      }).join("");

      card.innerHTML = `
        <div class="card-header" style="display:flex;justify-content:space-between;gap:8px;margin-bottom:4px;font-size:13px;">
          <div class="req-id" style="font-weight:600;">${escapeHtml(reqId)}</div>
          <div class="req-tag" style="color:#60a5fa;">${escapeHtml(tag)}</div>
        </div>
        <h3 class="req-title">${escapeHtml(titleText)}</h3>
        <details class="req-details" open>
          <summary>Details</summary>
          <div class="req-block" style="margin-top:6px;">
            <div class="req-label" style="font-size:12px;color:#9aa5b1;margin-bottom:4px;">Evidenz (${evs.length}):</div>
            <ul class="req-evidence">${evLis}</ul>
          </div>
          <div class="req-block" style="margin-top:6px;">
            <div class="req-label" style="font-size:12px;color:#9aa5b1;margin-bottom:4px;">Rohdaten:</div>
            <pre class="req-json" style="margin:0;font-size:11px;white-space:pre-wrap;">${escapeHtml(JSON.stringify(it, null, 2))}</pre>
          </div>
        </details>
      `;

      // Klick: Auswahl + Preview-Highlight + Graph-Fokus
      card.addEventListener("click", () => {
        if (activeCard) activeCard.classList.remove("active");
        activeCard = card;
        card.classList.add("active");
        highlightInPreview(titleText);
        try { focusReqInGraph(reqId); } catch {}
      });

      frag.appendChild(card);
    });

    resultsEl.appendChild(frag);
    // Merke die letzte Liste global für Speichern
    try { window.__last_mined_items = items; } catch(e){}
  }

  async function postForm(fd) {
    // v2.1: direkte LangExtract-Route nutzen (kein Vector-Ingest nötig)
    const resp = await fetch((window.API_BASE || "") + "/api/v1/lx/extract", { method: "POST", body: fd });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data || data.success === false) {
      const msg = (data && data.message) ? data.message : `HTTP ${resp.status}`;
      setStatus(`Fehler: ${msg}`, "err");
      return null;
    }
    // Statustext generisch halten (lx/extract liefert keine countFiles/countChunks)
    const chunks = Array.isArray(data.lxPreview) ? data.lxPreview.length : (typeof data.chunks === 'number' ? data.chunks : 0);
    setStatus(`Extraktion OK${chunks ? `: ${chunks} Extrakte` : ''}.`, "ok");
    return data;
  }

  function itemsFromLx(lxPreview) {
    if (!Array.isArray(lxPreview)) return [];
    const reqs = lxPreview.filter(e => String((e && e.extraction_class) || '').toLowerCase() === 'requirement');
    function autoTagForText(text, attrs) {
      // Prefer explicit category/area if present
      const explicit = (attrs && (attrs.category || attrs.area));
      if (explicit) return String(explicit).toLowerCase();
      const s = String(text || '').toLowerCase();
      if (/\bbatch\b|\/api\/v1\/batch/.test(s)) return 'batch';
      if (/\bcors\b|\bendpoint\b|\/api\/v1\//.test(s)) return 'api';
      if (/\bllm\b|openai_model|\bmock_mode\b/.test(s)) return 'llm';
      if (/\bdocker\b|\bcompose\b|\bgunicorn\b|\bwsgi\b|\bops\b/.test(s)) return 'ops';
      if (/datenbank|database|schema|foreign key|index|sqlite/i.test(s)) return 'db';
      if (/\bp95\b|latenz|latency|throughput|parallel|max_parallel|batch_size/.test(s)) return 'performance';
      if (/config|umgebungsvariablen|\.env\b/.test(s)) return 'config';
      if (/security|sensitiv|sensitive|logs|auth/.test(s)) return 'security';
      if (/deploy|gunicorn|wsgi|compose/.test(s)) return 'deployment';
      return 'requirement';
    }
    return reqs.map((e, i) => {
      const title = e.extraction_text || `Requirement ${i + 1}`;
      const tag = autoTagForText(title, e.attributes || {});
      return {
        req_id: `REQ-${i + 1}`,
        title,
        tag,
        evidence_refs: [
          `${e.sourceFile || 'unknown'}#${(e.chunkIndex != null ? e.chunkIndex : '0')}`
        ],
        raw: e
      };
    });
  }

  function sortItemsByCharPos(items) {
    const parseChunkFromRef = (it) => {
      try {
        const ref = Array.isArray(it.evidence_refs) ? it.evidence_refs[0] : null;
        if (!ref) return 0;
        const idx = String(ref).split('#')[1];
        const n = parseInt(idx, 10);
        return Number.isFinite(n) ? n : 0;
      } catch { return 0; }
    };
    const getSource = (it) => (it?.raw?.sourceFile) || (Array.isArray(it.evidence_refs) ? String(it.evidence_refs[0]).split('#')[0] : '');
    const getChunk = (it) => (it?.raw?.chunkIndex != null ? it.raw.chunkIndex : parseChunkFromRef(it));
    const getStart = (it) => (it?.raw?.char_interval?.start_pos != null ? Number(it.raw.char_interval.start_pos) : Number.POSITIVE_INFINITY);
    return (items || []).sort((a, b) => {
      const sa = getSource(a) || '';
      const sb = getSource(b) || '';
      if (sa !== sb) return sa < sb ? -1 : 1;
      const ca = getChunk(a);
      const cb = getChunk(b);
      if (ca !== cb) return ca - cb;
      const pa = getStart(a);
      const pb = getStart(b);
      return pa - pb;
    });
  }

  function normalizeTextForCompare(s) {
    return String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function dedupeByIdThenText(items) {
    const seenByText = new Set();
    const seenId = new Map(); // id -> firstText
    const deduped = [];
    const idConflicts = []; // { id, firstText, otherText }
    let removedCount = 0;

    for (const it of items || []) {
      const id = it.id || it.req_id || null;
      const text = it.title || it.requirementText || "";
      const normText = normalizeTextForCompare(text);
      const textKey = normText;

      // duplicate by text → drop
      if (textKey && seenByText.has(textKey)) { removedCount++; continue; }

      if (id) {
        if (seenId.has(id)) {
          const firstText = seenId.get(id);
          const firstNorm = normalizeTextForCompare(firstText);
          if (firstNorm === normText) {
            // same id and same text → drop later one
            removedCount++;
            continue;
          } else {
            // same id, different content → conflict notification
            idConflicts.push({ id, firstText, otherText: text });
            // keep both but ensure text-based dedupe still applies
          }
        } else {
          seenId.set(id, text);
        }
      }

      seenByText.add(textKey);
      deduped.push(it);
    }

    return { deduped, removedCount, idConflicts };
  }

  async function loadConfigList() {
    try {
      const resp = await fetch((window.API_BASE || "") + "/api/v1/lx/config/list");
      const data = await resp.json().catch(() => ({}));
      const items = (data && data.items) || ["default"];
      if (cfgSelect) {
        cfgSelect.innerHTML = "";
        items.forEach((id) => {
          const opt = document.createElement("option");
          opt.value = id; opt.textContent = id;
          if (id === currentConfigId) opt.selected = true;
          cfgSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn("loadConfigList", e);
    }
  }

  async function loadGoldList() {
    try {
      const resp = await fetch((window.API_BASE || "") + "/api/v1/lx/gold/list");
      const data = await resp.json().catch(() => ({}));
      const items = (data && data.items) || [];
      if (goldSelect) {
        goldSelect.innerHTML = "";
        const opt0 = document.createElement("option");
        opt0.value = ""; opt0.textContent = "(kein)";
        goldSelect.appendChild(opt0);
        items.forEach((id) => {
          const opt = document.createElement("option");
          opt.value = id; opt.textContent = id;
          goldSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn("loadGoldList", e);
    }
  }

  async function previewConfig(id) {
    try {
      const resp = await fetch((window.API_BASE || "") + "/api/v1/lx/config/preview?id=" + encodeURIComponent(id || currentConfigId));
      const data = await resp.json().catch(() => ({}));
      const cfg = (data && data.config) || null;
      if (!cfg) { setStatus("Keine Config gefunden.", "warn"); }
      setStatus("Config geladen: " + (data.configId || id), "ok");
      try {
        const meta = document.getElementById("previewMeta");
        const txt = document.getElementById("previewText");
        meta.textContent = "Config Preview: " + (data.configId || id);
        const toShow = cfg || data || {};
        txt.textContent = JSON.stringify(toShow, null, 2);
      } catch (e) {}
    } catch (e) {
      setStatus("Config Preview Fehler: " + e, "err");
    }
  }

  async function saveConfigFromTextarea() { /* removed in slim UI */ }

  function insertConfigTemplate() {
    const template = {
      prompt_description: "Extrahiere Anforderungen (Requirement), Akteure (Actor), Fähigkeiten (Capability), Constraints, Tags. Gebe für Requirements prägnante Sätze zurück.",
      examples: [
        {
          text: "Der Benutzer kann sich mit Benutzername und Passwort anmelden.",
          extractions: [
            { extraction_class: "Requirement", extraction_text: "Login mit Benutzername und Passwort muss möglich sein", attributes: { category: "authentication" } },
            { extraction_class: "Actor", extraction_text: "Benutzer" },
            { extraction_class: "Capability", extraction_text: "Anmelden" },
            { extraction_class: "Tag", extraction_text: "auth" }
          ]
        }
      ]
    };
    if (cfgJson) cfgJson.value = JSON.stringify(template, null, 2);
  }

  async function loadConfigFromFile() {
    const f = cfgFileInput?.files?.[0];
    if (!f) { setStatus("Bitte Config-JSON wählen.", "warn"); return; }
    const txt = await readBlobAsText(f);
    try {
      const parsed = JSON.parse(txt);
      cfgJson.value = JSON.stringify(parsed, null, 2);
      setStatus("Config aus Datei geladen.", "ok");
    } catch (e) {
      setStatus("Ungültiges JSON in Datei.", "err");
    }
  }

  async function saveSchemaFromFile() { /* moved to reports page */ }

  async function loadReportList() {
    try {
      const resp = await fetch((window.API_BASE || "") + "/api/v1/lx/report/list");
      const data = await resp.json().catch(() => ({}));
      const items = (data && data.items) || [];
      if (reportSelect) {
        reportSelect.innerHTML = "";
        items.forEach((fn) => {
          const sid = String(fn).replace(/\.json$/i, "");
          const opt = document.createElement("option");
          opt.value = sid; opt.textContent = sid;
          reportSelect.appendChild(opt);
        });
      }
      setStatus("Reports geladen: " + items.length, "ok");
    } catch (e) {
      setStatus("Reports laden Fehler: " + e, "err");
    }
  }

  async function showReport(saveId) {
    try {
      const url = (window.API_BASE || "") + "/api/v1/lx/report/get" + (saveId ? ("?saveId=" + encodeURIComponent(saveId)) : "");
      const resp = await fetch(url);
      const data = await resp.json().catch(() => ({}));
      const report = data && data.report;
      if (!report) { setStatus("Kein Report gefunden.", "warn"); return; }
      try {
        const meta = document.getElementById("previewMeta");
        const txt = document.getElementById("previewText");
        meta.textContent = "Report: " + (saveId || "latest");
        txt.textContent = JSON.stringify(report, null, 2);
      } catch (e) {}
      setStatus("Report angezeigt.", "ok");

      // Lade zusätzlich das zugrunde liegende Ergebnis und zeige ersten Chunk-Inhalt
      const sid = report && (report.saveId || saveId);
      if (sid) {
        try {
          const r2 = await fetch((window.API_BASE || "") + "/api/v1/lx/result/chunk?saveId=" + encodeURIComponent(sid) + "&idx=0");
          const d2 = await r2.json().catch(() => ({}));
          if (r2.ok && d2 && typeof d2.text === "string") {
            // Dokument-Vorschau überschreibt Meta und zeigt Dateiname/ChunkIndex
            const payload = d2.payload || {};
            const source = payload.sourceFile || "unknown";
            const cidx = (payload.chunkIndex != null ? payload.chunkIndex : d2.idx);
            setPreview(`Report: ${sid} – ${source}#${cidx}`, d2.text);
          }
        } catch (_) {}
      }
    } catch (e) {
      setStatus("Report laden Fehler: " + e, "err");
    }
  }

  async function readBlobAsText(blob) {
    if (!blob) return "";
    // Bevorzugt Response(Text)-Dekodierung (utf-8), robuste Fallbacks inklusive FileReader
    try {
      return await new Response(blob).text();
    } catch (_) {
      try {
        return await blob.text();
      } catch (_) {
        // Finaler Fallback mit FileReader
        try {
          const txt = await new Promise((resolve, reject) => {
            const fr = new FileReader();
            fr.onerror = () => reject(fr.error);
            fr.onload = () => resolve(String(fr.result || ""));
            fr.readAsText(blob);
          });
          return txt;
        } catch (e3) {
          console.warn("readBlobAsText: konnte Blob nicht als Text lesen:", e3);
          return "";
        }
      }
    }
  }

  const lxResultsMsg = { type: "LX_MINE_RESULTS", lxPreview: []}; const lxReportsMsg = { type: "LX_REPORT_RESULTS", lxPreview: [] };
  // Öffnet den Vollbild‑TAG‑Viewer in neuem Tab und sendet lxPreview via postMessage
  let __tag_win = null;
  let __tag_ready = false;
  let __last_lx_preview = [];
  function ensureTagWindow() {
    try {
      if (!__tag_win || __tag_win.closed) {
        const url = (location && location.origin ? location.origin : "") + "/tag_view.html";
        // WICHTIG: ohne 'noopener', damit window.opener im Viewer gesetzt ist (Handshake)
        __tag_win = window.open(url, "_blank");
      }
    } catch (e) {
      console.warn("ensureTagWindow failed:", e);
    }
    return __tag_win;
  }
  function openTagView(lxPreview) {
    try {
      if (!Array.isArray(lxPreview) || !lxPreview.length) return;
      __last_lx_preview = lxPreview.slice(); // letzte Vorschau puffern
      try { localStorage.setItem("tag:last_lx_preview", JSON.stringify(__last_lx_preview)); } catch(_){}
      ensureTagWindow();
      const payload = { type: "TAG_VIEW_LOAD", lxPreview: lxPreview };
      // Erst nach READY senden, aber zusätzlich mit Retry absichern
      const maxTries = 60; // ~12s bei 200ms Intervall
      let n = 0;
      const t = setInterval(() => {
        try {
          if (!__tag_win || __tag_win.closed) { clearInterval(t); return; }
          if (__tag_ready) {
            __tag_win.postMessage(payload, "*");
            clearInterval(t);
            return;
          }
          // Bis READY eintrifft, dennoch periodisch senden (best-effort)
          __tag_win.postMessage(payload, "*");
          n++;
          if (n >= maxTries) clearInterval(t);
        } catch (_) {
          n++;
          if (n >= maxTries) clearInterval(t);
        }
      }, 200);
    } catch (e) {
      console.warn("openTagView failed:", e);
    }
  }
  // Fallback: Wenn LangExtract keine Vorschau liefert, versuche Mining über Agent-/RAG-Endpoint
  async function mineFallback() {
    try {
      setStatus("LangExtract leer – versuche Mining aus letzter LX-Session…", "warn");
      const resp = await fetch((window.API_BASE || "") + "/api/v1/lx/mine?latest=1", { method: "GET" });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data || !Array.isArray(data.items)) {
        const msg = (data && data.message) ? data.message : `HTTP ${resp.status}`;
        setStatus(`Mining Fallback fehlgeschlagen: ${msg}`, "err");
        return;
      }
      const items = data.items || [];
      if (items.length === 0) {
        setStatus("Mining Fallback lieferte 0 Items.", "warn");
        clearResults();
        resultsEl.innerHTML = `<div class="card"><div class="status warn">Keine Requirements gefunden.</div></div>`;
        return;
      }
      setStatus(`Mining (Fallback) OK: ${items.length} Items.`, "ok");
      renderItems(items);
    } catch (e) {
      console.error(e);
      setStatus(`Mining Fallback Fehler: ${e}`, "err");
    }
  }


  // KG-Build nach Mining-Response
  async function buildKG(items) {
    try {
      setStatus("KG wird gebaut…", "warn");
      const resp = await fetch((window.API_BASE || "") + "/api/kg/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: items, options: { persist: "qdrant", use_llm: !!(useLlmInput && useLlmInput.checked) } })
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data || data.success === false) {
        const msg = (data && data.message) ? data.message : `HTTP ${resp.status}`;
        setStatus(`KG Fehler: ${msg}`, "err");
        return;
      }
      const nodes = data.nodes || [];
      const edges = data.edges || [];
      // Nur im Vollbild rendern (Center-Render überspringen für bessere Performance)
      openKgModal(nodes, edges);
      setStatus(`Graph erstellt: ${nodes.length} Knoten, ${edges.length} Kanten.`, "ok");
    } catch (e) {
      console.error(e);
      setStatus(`KG Fehler: ${e}`, "err");
    }
  }

  // Baue Graph aus der LangExtract-Vorschau (response.lxPreview)
  function buildKGFromLx(lxPreview) {
    try {
      if (!Array.isArray(lxPreview) || lxPreview.length === 0) {
        setStatus("Keine LangExtract-Vorschau erhalten.", "warn");
        return;
      }
      // Gruppiere je Chunk, verbinde Entities mit Requirements aus demselben Chunk
      const groups = new Map();
      for (const e of lxPreview) {
        const key = (e.sourceFile || "unknown") + "::" + String(e.chunkIndex ?? "0");
        const arr = groups.get(key) || [];
        arr.push(e);
        groups.set(key, arr);
      }
      const nodes = [];
      const edges = [];
      let reqCounter = 0;
      for (const arr of groups.values()) {
        const reqs = arr.filter(x => (x.extraction_class || "").toLowerCase() === "requirement");
        const others = arr.filter(x => (x.extraction_class || "").toLowerCase() !== "requirement");
        // Erzeuge pro Requirement einen Knoten
        const reqIds = [];
        for (const r of reqs) {
          const rid = "REQ-" + (++reqCounter);
          nodes.push({ id: rid, type: "Requirement", name: r.extraction_text || rid, payload: { node_id: rid, type: "Requirement", name: r.extraction_text || rid } });
          reqIds.push(rid);
        }
        // Falls kein explizites Requirement existiert: einen Platzhalter anlegen
        if (reqIds.length === 0 && others.length > 0) {
          const rid = "REQ-" + (++reqCounter);
          nodes.push({ id: rid, type: "Requirement", name: "Requirement (auto)", payload: { node_id: rid, type: "Requirement", name: "Requirement (auto)" } });
          reqIds.push(rid);
        }
        // Mappe andere Klassen auf Entity-Typen
        const mapType = (cls) => {
          const c = String(cls || "").toLowerCase();
          if (c === "actor") return "Actor";
          if (c === "capability") return "Action";
          if (c === "constraint") return "Entity";
          if (c === "acceptance_criterion") return "Entity";
          if (c === "relation") return "Entity";
          if (c === "tag") return "Tag";
          return "Entity";
        };
        const mapRel = (cls) => {
          const c = String(cls || "").toLowerCase();
          if (c === "actor") return "HAS_ACTOR";
          if (c === "capability") return "HAS_CAPABILITY";
          if (c === "constraint") return "HAS_CONSTRAINT";
          if (c === "acceptance_criterion") return "HAS_CRITERION";
          if (c === "tag") return "HAS_TAG";
          return "RELATES_TO";
        };
        // Entities erzeugen und mit allen reqIds im gleichen Chunk verbinden
        for (const o of others) {
          const nid = (mapType(o.extraction_class) + ":" + (o.extraction_text || Math.random().toString(36).slice(2))).slice(0, 128);
          if (!nodes.find(n => n.id === nid)) {
            nodes.push({ id: nid, type: mapType(o.extraction_class), name: o.extraction_text || nid, payload: { node_id: nid, type: mapType(o.extraction_class), name: o.extraction_text || nid } });
          }
          for (const rid of reqIds) {
            const eid = rid + "#" + mapRel(o.extraction_class) + "#" + nid;
            if (!edges.find(e => e.id === eid)) {
              edges.push({ id: eid, from: rid, to: nid, rel: mapRel(o.extraction_class), payload: { edge_id: eid, from_node_id: rid, to_node_id: nid, rel: mapRel(o.extraction_class) } });
            }
          }
        }
      }
      // Graph im Vollbild-Modal anzeigen
      openKgModal(nodes, edges);
      setStatus(`Graph erstellt aus LangExtract: ${nodes.length} Knoten, ${edges.length} Kanten.`, "ok");
    } catch (e) {
      console.error(e);
      setStatus(`KG Fehler (LX): ${e}`, "err");
    }
  }

  function sortLxPreviewByPos(lxPreview) {
    const getSource = (e) => (e && e.sourceFile) || 'unknown';
    const getChunk = (e) => (e && e.chunkIndex != null ? e.chunkIndex : 0);
    const getStart = (e) => {
      const ci = e && e.char_interval;
      const sp = ci && (ci.start_pos != null ? Number(ci.start_pos) : Number.POSITIVE_INFINITY);
      return Number.isFinite(sp) ? sp : Number.POSITIVE_INFINITY;
    };
    return (Array.isArray(lxPreview) ? lxPreview.slice() : []).sort((a,b) => {
      const sa = getSource(a), sb = getSource(b);
      if (sa !== sb) return sa < sb ? -1 : 1;
      const ca = getChunk(a), cb = getChunk(b);
      if (ca !== cb) return ca - cb;
      return getStart(a) - getStart(b);
    });
  }

  async function doUpload() {
    try {
      const files = fileInput.files;
      if (!files || !files.length) {
        setStatus("Bitte mindestens eine Datei wählen.", "warn");
        return;
      }

      let aggregated = [];
      let allPreview = [];
      btn.disabled = true;
      setStatus("Mining läuft…", "warn");
      clearResults();
      // Popup-freundlich: Viewer synchron öffnen
      ensureTagWindow();

      const fd = new FormData();
      for (const f of files) fd.append("files", f, f.name);
      fd.set("structured", "1");
      // v2.1 Optionen standardmäßig aktivieren (anpassbar):
      fd.set("chunkMode", "paragraph");
      // Quellen beibehalten für präzisere Evidenz-Zuordnung
      fd.set("preserveSources", "1");
      if (currentConfigId) fd.set("configId", currentConfigId);
      // Guided mining options
      if (useGoldFewshot && useGoldFewshot.checked) fd.set("useGoldAsFewshot", "1");
      if (autoGoldChk && autoGoldChk.checked) fd.set("autoGold", "1");
      const gidSel = (goldSelect && goldSelect.value) ? goldSelect.value.trim() : "";
      if (gidSel) fd.set("goldId", gidSel);
      if (fastModeChk && fastModeChk.checked) fd.set("fast", "1");
      const tval = (tempInput && tempInput.value) ? tempInput.value : "";
      if (tval) fd.set("temperature", String(tval));
 
      // preview: zeige erste Datei
      const first = files[0];
      if (first) {
        try {
          const text = await readBlobAsText(first);
          setPreview(first.name, text);
        } catch (e) {
          console.warn("Preview lesen fehlgeschlagen:", e);
          clearPreview();
        }
      } else {
        clearPreview();
      }
 
      const model = (modelInput.value || "").trim();
      const neighbors = neighborsInput.checked;
      if (model) fd.set("model", model);
      if (neighbors) fd.set("neighbor_refs", "1");

      // Multi-Pass Mining: groß, mittel, klein (Fast Mode: nur ein Pass)
      const passParagraph = (document.getElementById('passParagraph')?.checked) || false;
      const useCustom = (document.getElementById('useCustomChunks')?.checked) || false;
      const uiSize = parseInt(document.getElementById('chunkSize')?.value || '4000', 10) || 4000;
      const uiOverlap = parseInt(document.getElementById('chunkOverlap')?.value || '300', 10) || 300;
      const configs = (fastModeChk && fastModeChk.checked)
        ? [{ mode: passParagraph ? 'paragraph' : 'token', chunkMin: uiSize, chunkMax: uiSize, chunkOverlap: uiOverlap }]
        : (useCustom
        ? [{ mode: passParagraph ? 'paragraph' : 'token', chunkMin: uiSize, chunkMax: uiSize, chunkOverlap: uiOverlap }]
        : [
            { mode: 'token', chunkMin: 8000, chunkMax: 8000, chunkOverlap: 300 },
            { mode: passParagraph ? 'paragraph' : 'token', chunkMin: 4000, chunkMax: 4000, chunkOverlap: 300 },
            { mode: 'token', chunkMin: 1500, chunkMax: 1500, chunkOverlap: 200 }
          ]);
      for (const passConfig of configs) {
        const passFd = new FormData();
        for (const f of files) passFd.append("files", f, f.name);
        passFd.set("structured", "1");
        passFd.set("chunkMode", passConfig.mode);
        passFd.set("preserveSources", "1");
        passFd.set("chunkMin", String(passConfig.chunkMin));
        passFd.set("chunkMax", String(passConfig.chunkMax));
        passFd.set("chunkOverlap", String(passConfig.chunkOverlap));
        if (neighborsInput && neighborsInput.checked) passFd.set("neighbor_refs", "1");
        if (currentConfigId) passFd.set("configId", currentConfigId);
        if (useGoldFewshot && useGoldFewshot.checked) passFd.set("useGoldAsFewshot", "1");
        if (autoGoldChk && autoGoldChk.checked) passFd.set("autoGold", "1");
        const gidSel2 = (goldSelect && goldSelect.value) ? goldSelect.value.trim() : "";
        if (gidSel2) passFd.set("goldId", gidSel2);
        if (fastModeChk && fastModeChk.checked) passFd.set("fast", "1");
        const tval2 = (tempInput && tempInput.value) ? tempInput.value : "";
        if (tval2) passFd.set("temperature", String(tval2));
        const passResp = await postForm(passFd);
        if (passResp && Array.isArray(passResp.lxPreview)) {
          aggregated = aggregated.concat(passResp.lxPreview);
          allPreview = allPreview.concat((passResp.lxPreview || []).map(p => ({ ...p, chunkIndex: p.chunkIndex || passResp.structured_chunks, sourceFile: p.sourceFile || passResp.file_name })));
        } else {
          setStatus("Pass Fehler oder leer.", "err"); // Messages were robust since renaming WIT_API = API_BASE
        }
      }
      // Dedupe: first by id then by normalized text
      const { deduped, removedCount, idConflicts } = dedupeByIdThenText(aggregated);
      if (deduped.length) {
        if (idConflicts && idConflicts.length) {
          setStatus(`Konflikte: ${idConflicts.length} gleiche IDs mit unterschiedlichem Inhalt. Entfernte Duplikate: ${removedCount}.`, "warn");
          try { window.__last_id_conflicts = idConflicts; } catch(e){}
        }
        renderItems(sortItemsByCharPos(deduped));
        // Build KG from full merged lxPreview to include entities/edges
        try {
          const sortedPreview = sortLxPreviewByPos(allPreview);
          __last_lx_preview = sortedPreview.slice();
          try { localStorage.setItem("tag:last_lx_preview", JSON.stringify(__last_lx_preview)); } catch(_){}
          openTagView(sortedPreview);
        } catch (e) { console.warn("TAG viewer open failed", e); }
      } else {
        setStatus("Keine Requirements extrahiert.", "warn");
      }
    } catch (err) {
      console.error(err);
      setStatus(`Fehler: ${err}`, "err");
    } finally {
      btn.disabled = false;
    }
  }

  async function doUploadSample() {
    try {
      btn.disabled = true;
      setStatus("Mining (Beispiel) läuft…", "warn");
      clearResults();
      // Popup-freundlich: Viewer synchron öffnen
      ensureTagWindow();

      const resp = await fetch("./sample_requirements.md");
      if (!resp.ok) {
        setStatus(`Fehler: Beispiel nicht gefunden (HTTP ${resp.status})`, "err");
        return;
      }
      const blob = await resp.blob();
      const file = new File([blob], "sample_requirements.md", { type: blob.type || "text/markdown" });

      // preview: zeige Beispieltext
      try {
        const text = await readBlobAsText(blob);
        setPreview(file.name, text);
      } catch (e) {
        console.warn("Preview Beispiel lesen fehlgeschlagen:", e);
        clearPreview();
      }

      const fd = new FormData();
      fd.append("files", file, file.name);
      fd.set("structured", "1");
      // v2.1 Optionen (gleich wie oben)
      fd.set("chunkMode", "paragraph");
      fd.set("preserveSources", "1");
      if (currentConfigId) fd.set("configId", currentConfigId);
 
      const model = (modelInput.value || "").trim();
      const neighbors = neighborsInput.checked;
      if (model) fd.set("model", model);
      if (neighbors) fd.set("neighbor_refs", "1");
 
      const data = await postForm(fd);
      if (data && Array.isArray(data.lxPreview) && data.lxPreview.length) {
        try { renderItems(itemsFromLx(data.lxPreview)); } catch (e) { console.warn(e); }
        buildKGFromLx(data.lxPreview);
        // Öffne automatisch den TAG‑Viewer für die Sample‑Vorschau
        try {
          const sortedPreview = sortLxPreviewByPos(data.lxPreview);
          __last_lx_preview = sortedPreview.slice();
          try { localStorage.setItem("tag:last_lx_preview", JSON.stringify(__last_lx_preview)); } catch(_){}
          openTagView(sortedPreview);
        } catch (_) {}
      } else {
        await mineFallback();
      }
    } catch (err) {
      console.error(err);
      setStatus(`Fehler: ${err}`, "err");
    } finally {
      btn.disabled = false;
    }
  }

  // Vollbild-Graph Modal helpers
  function openKgModal(nodes, edges) {
    const modal = document.getElementById("kgModal");
    if (!modal) return;
    modal.classList.add("show");
    setTimeout(() => {
      try { renderGraphModal(nodes, edges); } catch (e) { console.warn(e); }
    }, 0);
  }
  function closeKgModal() {
    const modal = document.getElementById("kgModal");
    if (!modal) return;
    modal.classList.remove("show");
  }

  document.getElementById("btnKgClose")?.addEventListener("click", (e) => { e.preventDefault(); closeKgModal(); });
  document.getElementById("btnKgRelayout")?.addEventListener("click", (e) => {
    e.preventDefault();
    try { cyModal && cyModal.layout(_layoutOpts()).run(); } catch(e){}
  });
  document.getElementById("btnKgFit")?.addEventListener("click", (e) => {
    e.preventDefault();
    try { cyModal && cyModal.fit(); } catch(e){}
  });
  document.getElementById("btnKgExportPng")?.addEventListener("click", (e) => {
    e.preventDefault();
    try { exportCyToPng(cyModal, "kg-" + _ts() + ".png"); } catch(e){ console.warn(e); }
  });
  document.getElementById("btnKgExportJson")?.addEventListener("click", (e) => {
    e.preventDefault();
    try {
      const n = window.__kg_last_nodes || [];
      const ed = window.__kg_last_edges || [];
      exportGraphJson(n, ed, "kg-" + _ts() + ".json");
    } catch(e){ console.warn(e); }
  });

  btn?.addEventListener("click", (e) => {
    e.preventDefault();
    doUpload();
  });

  document.getElementById("btnSample")?.addEventListener("click", (e) => {
    e.preventDefault();
    doUploadSample();
  });

  cfgSelect?.addEventListener("change", (e) => {
    const val = (cfgSelect.value || "").trim();
    currentConfigId = val || "default";
    setStatus("Config gewählt: " + currentConfigId);
  });

  btnLoadCfg?.addEventListener("click", async (e) => {
    e.preventDefault();
    await loadConfigList();
  });

  btnPreviewCfg?.addEventListener("click", async (e) => {
    e.preventDefault();
    await previewConfig(currentConfigId);
  });

  // Removed config editing listeners in slim UI

  btnReloadGold?.addEventListener("click", async (e) => {
    e.preventDefault();
    await loadGoldList();
    setStatus("Gold-Liste aktualisiert.", "ok");
  });

  btnSaveSchema?.addEventListener("click", async (e) => {
    e.preventDefault();
    await saveSchemaFromFile();
  });

  // Reports moved to dedicated page

  async function saveRequirements(items) {
    try {
      const body = { items: (items || []), path: "./data/requirements.out.json" };
      const resp = await fetch((window.API_BASE || "") + "/api/v1/lx/save_requirements", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data || data.status !== "ok") {
        const msg = (data && data.message) ? data.message : `HTTP ${resp.status}`;
        setStatus(`Speichern fehlgeschlagen: ${msg}`, "err");
        return;
      }
      setStatus(`Gespeichert: ${data.count} Items → ${data.path}`, "ok");
    } catch (e) {
      console.error(e);
      setStatus(`Speichern Fehler: ${e}`, "err");
    }
  }

  btnSaveReqs?.addEventListener("click", async (e) => {
    e.preventDefault();
    const items = Array.isArray(window.__last_mined_items) ? window.__last_mined_items : [];
    if (!items.length) {
      setStatus("Keine Items zum Speichern vorhanden.", "warn");
      return;
    }
    await saveRequirements(items.map((it, i) => ({
      id: it.id || it.req_id || `R${i + 1}`,
      requirementText: it.requirementText || it.title || "",
      context: it.context || {}
    })));
  });

  // TAG Viewer Handshake: READY/RENDERED/NEED_DATA Events verarbeiten
  window.addEventListener("message", (ev) => {
    try {
      const d = ev && ev.data;
      if (!d || !d.type) return;
      if (d.type === "TAG_VIEW_READY") {
        __tag_ready = true;
        setStatus("TAG Viewer bereit.", "ok");
        // Persistiere letzte Vorschau für den Viewer-Fallback
        if (Array.isArray(__last_lx_preview) && __last_lx_preview.length) {
          try { localStorage.setItem("tag:last_lx_preview", JSON.stringify(__last_lx_preview)); } catch(_){}
          try { __tag_win && __tag_win.postMessage({ type: "TAG_VIEW_LOAD", lxPreview: __last_lx_preview }, "*"); } catch(_){}
        }
      } else if (d.type === "TAG_VIEW_RENDERED") {
        const m = (typeof d.mentions === "number") ? d.mentions : "?";
        setStatus(`TAG Viewer gerendert (${m} Mentions).`, "ok");
      } else if (d.type === "TAG_VIEW_NEED_DATA") {
        // Proaktiv nachreichen und persistieren
        if (Array.isArray(__last_lx_preview) && __last_lx_preview.length) {
          try { localStorage.setItem("tag:last_lx_preview", JSON.stringify(__last_lx_preview)); } catch(_){}
          try { __tag_win && __tag_win.postMessage({ type: "TAG_VIEW_LOAD", lxPreview: __last_lx_preview }, "*"); } catch(_){}
        }
      }
    } catch (_) {}
  });

  // Initial config list fetch
  loadConfigList();
  loadGoldList();
  // Optional: initial reports
  // loadReportList();
})();