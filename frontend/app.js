(() => {
  const API_BASE = (window.API_BASE || "http://localhost:5000").replace(/\/+$/, "");

  // Elements
  const el = {
    mdInput: document.getElementById("mdInput"),
    fileInput: document.getElementById("fileInput"),
    useServerMD: document.getElementById("useServerMD"),
    btnEvaluate: document.getElementById("btnEvaluate"),
    btnSuggest: document.getElementById("btnSuggest"),
    btnRewrite: document.getElementById("btnRewrite"),
    status: document.getElementById("status"),
    mergedOutput: document.getElementById("mergedOutput"),
    btnDownload: document.getElementById("btnDownload"),
    btnRefreshFromServer: document.getElementById("btnRefreshFromServer"),
    evalId: document.getElementById("evalId"),
    decidedBy: document.getElementById("decidedBy"),
    btnAccept: document.getElementById("btnAccept"),
    btnReject: document.getElementById("btnReject"),
    decisionOutput: document.getElementById("decisionOutput"),
  };

  // State
  let useServerFile = true; // Standard: Server nutzt REQUIREMENTS_MD_PATH=/data/requirements.md
  let lastMerged = "";

  // Utils
  function setStatus(text, type = "info") {
    const colors = {
      info: "",
      ok: "color:#52c41a;",
      warn: "color:#faad14;",
      err: "color:#ff4d4f;",
    };
    el.status.textContent = text;
    el.status.setAttribute("style", colors[type] || "");
  }

  async function httpPost(path, body) {
    const res = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : "{}",
    });
    const txt = await res.text();
    try {
      const data = JSON.parse(txt);
      if (!res.ok) throw new Error(data.message || JSON.stringify(data));
      return data;
    } catch (e) {
      if (!res.ok) throw new Error(txt || res.statusText);
      throw e;
    }
  }

  function downloadText(filename, text) {
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.download = filename;
    a.href = url;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function enableUi(en) {
    [el.btnEvaluate, el.btnSuggest, el.btnRewrite, el.btnDownload, el.btnRefreshFromServer, el.btnAccept, el.btnReject].forEach(b => {
      if (b) b.disabled = !en;
    });
  }

  // File input → load into textarea
  el.fileInput.addEventListener("change", () => {
    const f = el.fileInput.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      el.mdInput.value = String(reader.result || "");
      useServerFile = false;
      setStatus("Markdown aus Datei geladen. Hinweis: Server verarbeitet standardmäßig die Datei auf dem Server (REQUIREMENTS_MD_PATH).", "info");
    };
    reader.readAsText(f, "utf-8");
  });

  // Use server MD flag
  el.useServerMD.addEventListener("click", () => {
    useServerFile = true;
    setStatus("Serverdatei wird verwendet (REQUIREMENTS_MD_PATH). Lokaler Editor wird ignoriert.", "info");
  });

  // Core actions: Evaluate, Suggest, Rewrite
  async function runBatch(which) {
    try {
      setStatus("Sende Anfrage...", "info");
      enableUi(false);

      // Hinweis: Das Backend liest IMMER REQUIREMENTS_MD_PATH serverseitig.
      // Dieses Frontend bietet nur Anzeige/Download der Ergebnisse.
      // Optional: Nutzer kann die lokale Datei als requirements.md in ./data ablegen.
      const path = which === "evaluate" ? "/api/v1/batch/evaluate"
                 : which === "suggest"  ? "/api/v1/batch/suggest"
                 : which === "rewrite"  ? "/api/v1/batch/rewrite"
                 : null;
      if (!path) throw new Error("Unbekannte Operation");

      const resp = await httpPost(path);
      lastMerged = String(resp.mergedMarkdown || "");
      el.mergedOutput.textContent = lastMerged || "(kein Inhalt)";
      setStatus(`Erfolg: ${which}`, "ok");
    } catch (err) {
      console.error(err);
      setStatus("Fehler: " + (err?.message || String(err)), "err");
    } finally {
      enableUi(true);
    }
  }

  el.btnEvaluate.addEventListener("click", () => runBatch("evaluate"));
  el.btnSuggest.addEventListener("click", () => runBatch("suggest"));
  el.btnRewrite.addEventListener("click", () => runBatch("rewrite"));

  // Download merged
  el.btnDownload.addEventListener("click", () => {
    if (!lastMerged) {
      setStatus("Kein Ergebnis zum Download vorhanden. Bitte zuerst eine Aktion ausführen.", "warn");
      return;
    }
    downloadText("requirements.out.md", lastMerged);
  });

  // "Refresh" → holt aktuellsten Merge durch Evaluate-Aufruf (ohne Dateiänderung)
  el.btnRefreshFromServer.addEventListener("click", () => runBatch("evaluate"));

  // Correction Decision
  async function sendDecision(decision) {
    try {
      const evaluationId = (el.evalId.value || "").trim();
      const decidedBy = (el.decidedBy.value || "").trim() || undefined;
      if (!evaluationId) {
        setStatus("evaluationId ist erforderlich.", "warn");
        return;
      }
      setStatus(`Sende Decision: ${decision}...`, "info");
      enableUi(false);
      const body = { evaluationId, decision, decidedBy };
      const resp = await httpPost("/api/v1/corrections/decision", body);
      el.decisionOutput.textContent = JSON.stringify(resp, null, 2);
      setStatus("Decision gespeichert.", "ok");
    } catch (err) {
      console.error(err);
      setStatus("Fehler: " + (err?.message || String(err)), "err");
    } finally {
      enableUi(true);
    }
  }

  el.btnAccept.addEventListener("click", () => sendDecision("accepted"));
  el.btnReject.addEventListener("click", () => sendDecision("rejected"));

  // Init
  setStatus("Bereit. Tipp: Legen Sie Ihre Markdown unter ./data/requirements.md ab. Der Server liest REQUIREMENTS_MD_PATH.", "info");
})();