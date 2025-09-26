(() => {
  const API = (window.API_BASE || '').replace(/\/+$/, '');
  const $ = (s) => document.querySelector(s);
  const status = $('#status');
  const reportSelect = $('#reportSelect');
  const reportBox = $('#reportBox');
  const chunkBox = $('#chunkBox');
  const chunkIdx = $('#chunkIdx');
  const goldId = document.getElementById('goldId');
  const goldItems = document.getElementById('goldItems');
  const evalBox = document.getElementById('evalBox');
  const evalThreshold = document.getElementById('evalThreshold');

  function setStatus(t) { if (status) status.textContent = t || ''; }

  async function loadReports() {
    try {
      const resp = await fetch(API + '/api/v1/lx/report/list');
      const data = await resp.json().catch(() => ({}));
      const items = (data && data.items) || [];
      reportSelect.innerHTML = '';
      for (const fn of items) {
        const sid = String(fn).replace(/\.json$/i, '');
        const opt = document.createElement('option');
        opt.value = sid; opt.textContent = sid;
        reportSelect.appendChild(opt);
      }
      setStatus('Reports: ' + items.length);
    } catch (e) {
      setStatus('Fehler: ' + e);
    }
  }

  async function showReport(saveId) {
    try {
      const url = API + '/api/v1/lx/report/get' + (saveId ? ('?saveId=' + encodeURIComponent(saveId)) : '');
      const resp = await fetch(url);
      const data = await resp.json().catch(() => ({}));
      const report = data && data.report;
      reportBox.textContent = JSON.stringify(report || {}, null, 2);
      setStatus('Report angezeigt.');
      return report && (report.saveId || saveId) || null;
    } catch (e) { setStatus('Fehler: ' + e); return null; }
  }

  async function showChunk(saveId, idx) {
    if (!saveId) return;
    try {
      const resp = await fetch(API + '/api/v1/lx/result/chunk?saveId=' + encodeURIComponent(saveId) + '&idx=' + encodeURIComponent(String(idx || 0)));
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) { chunkBox.textContent = JSON.stringify(data, null, 2); return; }
      chunkBox.textContent = String(data.text || '');
      setStatus('Chunk ' + (data.idx ?? idx) + ' angezeigt.');
    } catch (e) { setStatus('Fehler: ' + e); }
  }

  async function goldList() {
    try {
      const resp = await fetch(API + '/api/v1/lx/gold/list');
      const data = await resp.json().catch(() => ({}));
      const items = (data && data.items) || [];
      setStatus('Gold Sets: ' + items.join(', '));
    } catch (e) { setStatus('Fehler: ' + e); }
  }
  async function goldGet() {
    try {
      const id = (goldId?.value || 'default');
      const resp = await fetch(API + '/api/v1/lx/gold/get?id=' + encodeURIComponent(id));
      const data = await resp.json().catch(() => ({}));
      const gold = data && data.gold;
      if (gold && Array.isArray(gold.items)) {
        goldItems.value = gold.items.map(x => (typeof x === 'string' ? x : (x.requirementText || JSON.stringify(x)))).join('\n');
        setStatus('Gold geladen: ' + id);
      } else {
        goldItems.value = '';
        setStatus('Kein Gold vorhanden, ID: ' + id);
      }
    } catch (e) { setStatus('Fehler: ' + e); }
  }
  async function goldSave() {
    try {
      const id = (goldId?.value || 'default');
      let items = [];
      const raw = goldItems?.value || '';
      if (/^\s*\[/.test(raw)) {
        try { items = JSON.parse(raw); } catch { items = []; }
      } else {
        items = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean).map(s => ({ requirementText: s }));
      }
      const body = { goldId: id, gold: { items } };
      const resp = await fetch(API + '/api/v1/lx/gold/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || (data && data.status) !== 'ok') {
        setStatus('Gold speichern fehlgeschlagen'); return;
      }
      setStatus('Gold gespeichert: ' + id);
    } catch (e) { setStatus('Fehler: ' + e); }
  }
  async function evaluateLatest() {
    try {
      const th = parseFloat(evalThreshold?.value || '0.9') || 0.9;
      const id = (goldId?.value || 'default');
      // prefer current textarea gold content; fallback to stored
      let gold = null;
      const raw = goldItems?.value || '';
      if (raw.trim()) {
        let items = [];
        if (/^\s*\[/.test(raw)) {
          try { items = JSON.parse(raw); } catch { items = []; }
        } else {
          items = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean).map(s => ({ requirementText: s }));
        }
        gold = { items };
      }
      const body = gold ? { gold, latest: true, threshold: th } : { goldId: id, latest: true, threshold: th };
      const resp = await fetch(API + '/api/v1/lx/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await resp.json().catch(() => ({}));
      evalBox.textContent = JSON.stringify(data || {}, null, 2);
      setStatus('Evaluation fertig.');
    } catch (e) { setStatus('Fehler: ' + e); }
  }

  document.getElementById('btnLoadReports')?.addEventListener('click', async (e) => { e.preventDefault(); await loadReports(); });
  document.getElementById('btnShowReport')?.addEventListener('click', async (e) => {
    e.preventDefault();
    const sid = reportSelect.value || '';
    const eff = await showReport(sid);
    await showChunk(eff, Number(chunkIdx.value || 0));
  });
  document.getElementById('btnShowLatest')?.addEventListener('click', async (e) => {
    e.preventDefault();
    const eff = await showReport(null);
    await showChunk(eff, Number(chunkIdx.value || 0));
  });
  document.getElementById('btnShowChunk')?.addEventListener('click', async (e) => {
    e.preventDefault();
    const sid = reportSelect.value || '';
    await showChunk(sid, Number(chunkIdx.value || 0));
  });
  document.getElementById('btnGoldList')?.addEventListener('click', (e) => { e.preventDefault(); goldList(); });
  document.getElementById('btnGoldGet')?.addEventListener('click', (e) => { e.preventDefault(); goldGet(); });
  document.getElementById('btnGoldSave')?.addEventListener('click', (e) => { e.preventDefault(); goldSave(); });
  document.getElementById('btnEvaluateLatest')?.addEventListener('click', (e) => { e.preventDefault(); evaluateLatest(); });

  // Auto evaluate (one click): upload file -> auto-gold -> auto-evaluate
  document.getElementById('btnAutoEvaluate')?.addEventListener('click', async (e) => {
    e.preventDefault();
    try {
      const fileInput = document.getElementById('autoFile');
      const f = fileInput?.files?.[0];
      if (!f) { setStatus('Bitte eine Datei wählen.', 'warn'); return; }
      const fd = new FormData();
      fd.append('file', f, f.name);
      const th = parseFloat(evalThreshold?.value || '0.7') || 0.7;
      fd.set('threshold', String(th));
      const resp = await fetch(API + '/api/v1/lx/evaluate/auto', { method: 'POST', body: fd });
      const data = await resp.json().catch(() => ({}));
      evalBox.textContent = JSON.stringify(data || {}, null, 2);
      if (!resp.ok) setStatus('Auto-Evaluate Fehler', 'err'); else setStatus('Auto-Evaluate OK');
    } catch (err) {
      setStatus('Fehler: ' + err, 'err');
    }
  });

  // Initial load
  loadReports();
})();



