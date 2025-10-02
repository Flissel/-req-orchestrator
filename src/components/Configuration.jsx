import { useState } from 'react'

export default function Configuration({ onStart, onReset, onFilesChange, status, logs }) {
  const [files, setFiles] = useState(null)
  const [model, setModel] = useState('gpt-4o-mini')
  const [neighborRefs, setNeighborRefs] = useState(true)
  const [useLlm, setUseLlm] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [chunkSize, setChunkSize] = useState(800)
  const [chunkOverlap, setChunkOverlap] = useState(200)

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files)
    setFiles(selectedFiles)
    if (onFilesChange) {
      onFilesChange(selectedFiles)
    }
  }

  const loadSampleFile = async () => {
    try {
      const response = await fetch('/moire_mouse_tracking_requirements.md')
      if (!response.ok) throw new Error('Sample file not found')
      const text = await response.text()
      const blob = new Blob([text], { type: 'text/markdown' })
      const file = new File([blob], 'moire_mouse_tracking_requirements.md', { type: 'text/markdown' })
      const fileList = [file]
      setFiles(fileList)
      if (onFilesChange) {
        onFilesChange(fileList)
      }
    } catch (err) {
      console.error('Failed to load sample:', err)
      alert('Sample file could not be loaded. Make sure the Vite dev server is running.')
    }
  }

  const handleStart = () => {
    onStart({
      files,
      model,
      neighborRefs,
      useLlm,
      chunkSize,
      chunkOverlap
    })
  }

  return (
    <div className="config-panel">
      <h2>⚙️ Konfiguration</h2>

      <div className={`status-bar status-${status.type}`}>
        {status.message}
      </div>

      <div className="form-group">
        <label htmlFor="files">📁 Dokument(e) auswählen:</label>
        <input
          id="files"
          type="file"
          accept=".md,.txt,.pdf,.docx"
          multiple
          onChange={handleFileChange}
        />
        {files && <div className="file-count">{files.length} Datei(en) ausgewählt</div>}
      </div>

      <div className="form-group">
        <button className="btn btn-sample" onClick={loadSampleFile}>
          📝 Beispieldatei laden (Moiré Mouse Tracking)
        </button>
      </div>

      <div className="form-group">
        <label htmlFor="model">🧠 Modell:</label>
        <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="gpt-4o-mini">gpt-4o-mini (schnell & günstig)</option>
          <option value="gpt-4o">gpt-4o (präzise)</option>
          <option value="gpt-4">gpt-4</option>
        </select>
      </div>

      <div className="form-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={neighborRefs}
            onChange={(e) => setNeighborRefs(e.target.checked)}
          />
          <span>Nachbarschafts-Evidenz (±1 Chunk)</span>
        </label>
      </div>

      <div className="form-group">
        <button
          className="btn btn-link"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? '▼' : '▶'} Erweiterte Optionen
        </button>
      </div>

      {showAdvanced && (
        <div className="advanced-options">
          <div className="form-group">
            <label htmlFor="chunkSize">📏 Chunk-Größe (Tokens):</label>
            <input
              type="number"
              id="chunkSize"
              min="200"
              max="2000"
              step="100"
              value={chunkSize}
              onChange={(e) => setChunkSize(parseInt(e.target.value))}
            />
            <small className="hint">Standard: 800 | Größer = mehr Kontext pro Chunk</small>
          </div>

          <div className="form-group">
            <label htmlFor="chunkOverlap">🔄 Chunk-Überlappung (Tokens):</label>
            <input
              type="number"
              id="chunkOverlap"
              min="0"
              max="500"
              step="50"
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(parseInt(e.target.value))}
            />
            <small className="hint">Standard: 200 | Überlappung zwischen Chunks</small>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
              />
              <span>LLM für KG-Expansion nutzen</span>
            </label>
            <small className="hint">Heuristik + optionale LLM-Verfeinerung</small>
          </div>
        </div>
      )}

      <div className="button-group">
        <button className="btn btn-primary" onClick={handleStart} disabled={!files}>
          🚀 Mining starten
        </button>
        <button className="btn btn-secondary" onClick={onReset}>
          🔄 Zurücksetzen
        </button>
      </div>

      <div className="logs-section">
        <h3>📋 Logs</h3>
        <div className="logs">
          {logs.length === 0 ? (
            <div className="log-empty">Keine Logs verfügbar</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="log-entry">{log}</div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
