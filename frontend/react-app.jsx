/** @jsx React.createElement */
const { useState } = React;

const API_BASE = (window.API_BASE || "http://localhost:5000").replace(/\/+$/, "");

// Types (JSDoc)
/**
 * @typedef {{id:number,text:string}} InputItem
 */
/**
 * @typedef {{criterion:string,isValid:boolean,reason:string}} EvalItem
 */
/**
 * @typedef {{id:number, originalText:string, correctedText:string, status:'pending'|'processed'|'accepted'|'rejected', evaluation:EvalItem[], open?:boolean}} OutputItem
 */

const CRIT_LABELS = {
  clarity: "Clarity",
  testability: "Testability",
  measurability: "Measurability",
  atomic: "Atomic",
  concise: "Concise",
  unambiguous: "Unambiguous",
  consistent_language: "Consistent Language",
};

function Badge({ status }) {
  const map = {
    accepted: { cls: "ok", text: "Akzeptiert ✅" },
    rejected: { cls: "err", text: "Fehlerhaft ❗" },
    processed: { cls: "ok", text: "Verarbeitet" },
    pending: { cls: "pending", text: "Offen" },
  };
  const v = map[status] || map.pending;
  return React.createElement("span", { className: `badge ${v.cls}` }, v.text);
}

function StatusBar({ text, type }) {
  const color =
    type === "ok" ? { color: "#52c41a" } :
    type === "warn" ? { color: "#faad14" } :
    type === "err" ? { color: "#ff4d4f" } : {};
  return React.createElement("div", { id: "status", className: "status", style: color }, text);
}

function InputList({ items, onAdd, onChange, onRemove }) {
  return React.createElement(
    React.Fragment,
    null,
    React.createElement("h2", null, "Requirements Input"),
    React.createElement(
      "div",
      { className: "list" },
      items.map((item) =>
        React.createElement(
          "div",
          { key: item.id, className: "item" },
          React.createElement(
            "div",
            { className: "item-head" },
            React.createElement("span", { className: "badge pending" }, `Input #${item.id}`),
            React.createElement("input", {
              type: "text",
              value: item.text,
              placeholder: "Anforderungstext eingeben...",
              onChange: (e) => onChange(item.id, e.target.value),
              style: { flex: 1 },
            }),
            React.createElement(
              "div",
              { className: "item-actions" },
              React.createElement(
                "button",
                { className: "btn-del", onClick: () => onRemove(item.id) },
                "Entfernen",
              ),
            ),
          ),
        ),
      ),
    ),
    React.createElement(
      "div",
      { className: "row", style: { marginTop: 12 } },
      React.createElement(
        "button",
        { id: "btnAdd", onClick: onAdd },
        "+ Requirement hinzufügen",
      ),
    ),
  );
}

function OutputItemDetails({ item }) {
  const evalRows = [];
  for (const ev of item.evaluation || []) {
    evalRows.push(
      React.createElement(
        React.Fragment,
        { key: `${item.id}-${ev.criterion}` },
        React.createElement(
          "div",
          { className: "crit" },
          React.createElement("span", { className: `dot ${ev.isValid ? "ok" : "err"}` }),
          React.createElement("span", null, CRIT_LABELS[ev.criterion] || ev.criterion),
        ),
        React.createElement("div", { className: "reason" }, ev.isValid ? "" : (ev.reason || "")),
      ),
    );
  }

  return React.createElement(
    "div",
    { className: "details" },
    React.createElement("h4", null, "Evaluation"),
    React.createElement("div", { className: "criteria" }, evalRows),
    React.createElement("h4", { style: { marginTop: 10 } }, "Correction"),
    React.createElement("textarea", { disabled: true, defaultValue: item.correctedText }),
  );
}

function OutputList({ items, onAccept, onReject, onToggleOpen, onAcceptAll, onRejectAll }) {
  return React.createElement(
    React.Fragment,
    null,
    React.createElement("h2", null, "Requirements Output"),
    React.createElement(
      "div",
      { className: "row", style: { marginBottom: 8 } },
      React.createElement("button", { onClick: onAcceptAll }, "Accept All"),
      React.createElement("button", { onClick: onRejectAll, className: "danger" }, "Reject All"),
    ),
    React.createElement(
      "div",
      { className: "list" },
      items.map((item) => {
        const chevron = item.open ? "▼" : "▶";
        return React.createElement(
          "div",
          { key: item.id, className: "item" },
          React.createElement(
            "div",
            { className: "item-head", onClick: () => onToggleOpen(item.id) },
            React.createElement(Badge, { status: item.status }),
            React.createElement(
              "span",
              { className: "chevron", onClick: (e) => { e.stopPropagation(); onToggleOpen(item.id); }, title: "Details umschalten" },
              chevron,
            ),
            React.createElement("input", { type: "text", value: item.originalText, disabled: true, style: { flex: 1 } }),
            React.createElement(
              "div",
              { className: "item-actions" },
              React.createElement("button", { className: "btn-accept", onClick: (e) => { e.stopPropagation(); onAccept(item.id); } }, "Accept"),
              React.createElement("button", { className: "btn-reject danger", onClick: (e) => { e.stopPropagation(); onReject(item.id); } }, "Reject"),
            ),
          ),
          item.open ? React.createElement(OutputItemDetails, { item }) : null,
        );
      }),
    ),
  );
}

function App() {
  /** @type [InputItem[], Function] */
  const [inputs, setInputs] = useState([
    { id: 1, text: "The vehicle attendant must have the ability to monitor the status of the shuttle." },
    { id: 2, text: "Das Shuttle muss manuell rückwärts fahren können." },
  ]);
  /** @type [OutputItem[], Function] */
  const [outputs, setOutputs] = useState([]);
  const [status, setStatus] = useState({ text: "Bereit. Fügen Sie Anforderungen hinzu und klicken Sie auf Process.", type: "info" });

  function setStatusInfo(text) { setStatus({ text, type: "info" }); }
  function setStatusOk(text) { setStatus({ text, type: "ok" }); }
  function setStatusWarn(text) { setStatus({ text, type: "warn" }); }
  function setStatusErr(text) { setStatus({ text, type: "err" }); }

  async function loadFromMd() {
    try {
      setStatusInfo("Lade Requirements aus Markdown...");
      const res = await fetch(API_BASE + "/api/demo/requirements");
      const data = await res.json();
      if (!res.ok) throw new Error(data?.message || res.statusText);
      const items = Array.isArray(data.items) ? data.items : [];
      if (!items.length) {
        setStatusWarn("Keine Requirements in der Markdown-Datei gefunden.");
        return;
      }
      const next = items.map((it, idx) => ({
        id: idx + 1,
        text: it.requirementText || "",
      }));
      setInputs(next);
      setStatusOk(`Geladen: ${next.length} Einträge aus Markdown.`);
    } catch (e) {
      setStatusErr("Fehler beim Laden der Markdown-Datei: " + (e?.message || String(e)));
    }
  }

  function addInput() {
    const id = inputs.length ? Math.max(...inputs.map(i => i.id)) + 1 : 1;
    setInputs([...inputs, { id, text: "" }]);
  }

  function removeInput(id) {
    setInputs(inputs.filter(i => i.id !== id));
  }

  function changeInput(id, text) {
    setInputs(inputs.map(i => (i.id === id ? { ...i, text } : i)));
  }

  function toggleOpen(id) {
    setOutputs(outputs.map(o => (o.id === id ? { ...o, open: !o.open } : o)));
  }

  function acceptOne(id) {
    setOutputs(outputs.map(o => (o.id === id ? { ...o, status: "accepted", originalText: o.correctedText || o.originalText, open: false } : o)));
  }

  function rejectOne(id) {
    setOutputs(outputs.map(o => (o.id === id ? { ...o, status: "rejected", open: false } : o)));
  }

  function acceptAll() {
    setOutputs(outputs.map(o => ({ ...o, status: "accepted", originalText: o.correctedText || o.originalText, open: false })));
  }

  function rejectAll() {
    setOutputs(outputs.map(o => ({ ...o, status: "rejected", open: false })));
  }

  function statusFromEvaluation(evaluation) {
    const allOk = (evaluation || []).every(e => !!e.isValid);
    return allOk ? "processed" : "rejected";
  }

  async function processAll() {
    try {
      // Nur Requirements mit Text
      const validInputs = inputs.filter(input => input.text && input.text.trim());
      if (!validInputs.length) {
        setStatusWarn("Keine Requirements zum Verarbeiten gefunden.");
        return;
      }
  
      const payload = validInputs.map(i => i.text.trim());
      setStatusInfo(`Verarbeite ${payload.length} Requirements (parallel, ein Request)...`);
      console.time && console.time("processAll");
      performance && performance.mark && performance.mark("processAll:start");
  
      let results = [];
  
      // 1) Schnellster Pfad: paralleler Endpoint
      try {
        const res = await fetch(API_BASE + "/api/validate/parallel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.message || res.statusText);
        results = Array.isArray(data) ? data : [];
      } catch (e1) {
        // 2) Fallback: Batch-Endpoint
        try {
          const res = await fetch(API_BASE + "/api/validate/batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data?.message || res.statusText);
          results = Array.isArray(data) ? data : [];
        } catch (e2) {
          // 3) Letzter Fallback: sequentielle Einzel-Requests (wie vorher)
          setStatusInfo(`Fallback aktiv: Sequentielle Verarbeitung von ${payload.length} Requirements...`);
          const seqOut = [];
          for (let i = 0; i < payload.length; i++) {
            const txt = payload[i];
            setStatusInfo(`Verarbeite Requirement ${i + 1}/${payload.length}: ${txt.substring(0, 50)}...`);
            try {
              const res = await fetch(API_BASE + "/api/validate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify([txt]),
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data?.message || res.statusText);
              seqOut.push(data[0]);
            } catch (e3) {
              seqOut.push({
                id: i + 1,
                originalText: validInputs[i].text,
                correctedText: validInputs[i].text,
                status: "rejected",
                evaluation: [{ criterion: "error", isValid: false, reason: `Fehler: ${e3.message}` }],
              });
            }
          }
          results = seqOut;
        }
      }
  
      const processedOutputs = (results || []).map((result) => ({
        id: result.id,
        originalText: result.originalText,
        correctedText: result.correctedText,
        status: result.status, // "accepted" | "rejected"
        evaluation: result.evaluation, // Array von {criterion, isValid, reason}
        open: false,
      }));
  
      setOutputs(processedOutputs);
      console.time && console.timeEnd("processAll");
      performance && performance.mark && performance.mark("processAll:end");
      try { performance && performance.measure && performance.measure("processAll", "processAll:start", "processAll:end"); } catch {}
      setStatusOk(`Processing abgeschlossen: ${processedOutputs.length} Requirements verarbeitet.`);
    } catch (e) {
      setStatusErr("Fehler: " + (e?.message || String(e)));
    }
  }

  return React.createElement(
    React.Fragment,
    null,
    React.createElement(StatusBar, { text: status.text, type: status.type }),
    React.createElement(
      "section",
      { className: "card" },
      React.createElement("h2", null, "Steuerung"),
      React.createElement(
        "div",
        { className: "row" },
        React.createElement("button", { onClick: addInput }, "+ Requirement hinzufügen"),
        React.createElement("button", { onClick: processAll }, "Process (POST /api/validate)"),
        React.createElement("button", { onClick: loadFromMd }, "Load MD (GET /api/demo/requirements)"),
        React.createElement("button", { onClick: acceptAll }, "Accept All"),
        React.createElement("button", { onClick: rejectAll, className: "danger" }, "Reject All"),
      ),
    ),
    React.createElement(
      "section",
      { className: "card" },
      React.createElement(
        "div",
        { className: "columns" },
        React.createElement("div", null, React.createElement(InputList, { items: inputs, onAdd: addInput, onChange: changeInput, onRemove: removeInput })),
        React.createElement("div", null, React.createElement(OutputList, { items: outputs, onAccept: acceptOne, onReject: rejectOne, onToggleOpen: toggleOpen, onAcceptAll: acceptAll, onRejectAll: rejectAll })),
      ),
    ),
  );
}

// Bootstrap React into current HTML
const rootEl = document.getElementById("root");
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(React.createElement(App));
}