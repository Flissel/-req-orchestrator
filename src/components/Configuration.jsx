import { useState, useEffect } from 'react'
import { getAutoValidatePreference, setAutoValidatePreference, getProviderPreference, setProviderPreference, getModelPreference, setModelPreference } from '../utils/preferences'

export default function Configuration({ onStart, onReset, onFilesChange, status, logs, isLoading = false }) {
  const [files, setFiles] = useState(null)
  const [provider, setProvider] = useState('openai')
  const [model, setModel] = useState('gpt-4o-mini')
  const [neighborRefs, setNeighborRefs] = useState(true)
  const [useLlm, setUseLlm] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [chunkSize, setChunkSize] = useState(4000)  // Match V1's effective chunk size
  const [chunkOverlap, setChunkOverlap] = useState(300)  // Match V1's overlap
  const [isLoadingSample, setIsLoadingSample] = useState(false)
  const [autoValidate, setAutoValidate] = useState(false)
  const [selectedExample, setSelectedExample] = useState('')

  // Load preferences from LocalStorage on mount
  useEffect(() => {
    const savedAutoValidate = getAutoValidatePreference()
    setAutoValidate(savedAutoValidate)

    const savedProvider = getProviderPreference()
    if (savedProvider) {
      setProvider(savedProvider)
    }

    const savedModel = getModelPreference()
    if (savedModel) {
      setModel(savedModel)
    }

    console.log('[Configuration] Loaded preferences:', {
      autoValidate: savedAutoValidate,
      provider: savedProvider || 'openai',
      model: savedModel || 'gpt-4o-mini'
    })
  }, [])

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files)
    setFiles(selectedFiles)
    if (onFilesChange) {
      onFilesChange(selectedFiles)
    }
  }

  const loadSampleFile = async () => {
    try {
      setIsLoadingSample(true)
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
    } finally {
      setIsLoadingSample(false)
    }
  }

  const loadExampleFile = async (exampleType) => {
    if (!exampleType) return

    try {
      setIsLoadingSample(true)
      const response = await fetch(`/${exampleType}`)
      if (!response.ok) throw new Error('Example file not found')
      const text = await response.text()
      const blob = new Blob([text], { type: 'text/markdown' })
      const file = new File([blob], exampleType, { type: 'text/markdown' })
      const fileList = [file]
      setFiles(fileList)
      if (onFilesChange) {
        onFilesChange(fileList)
      }
      console.log(`[Configuration] Loaded example: ${exampleType}`)
    } catch (err) {
      console.error('Failed to load example:', err)
      alert('Example file could not be loaded. Make sure the Vite dev server is running.')
    } finally {
      setIsLoadingSample(false)
    }
  }

  const handleExampleChange = (e) => {
    const exampleType = e.target.value
    setSelectedExample(exampleType)
    if (exampleType) {
      loadExampleFile(exampleType)
    }
  }

  const handleAutoValidateChange = (e) => {
    const enabled = e.target.checked
    setAutoValidate(enabled)
    setAutoValidatePreference(enabled)
    console.log('[Configuration] Auto-validate preference changed:', enabled)
  }

  const handleProviderChange = (e) => {
    const newProvider = e.target.value
    setProvider(newProvider)
    setProviderPreference(newProvider)

    // Reset model to appropriate default when switching providers
    if (newProvider === 'openrouter') {
      setModel('anthropic/claude-haiku-4.5')
      setModelPreference('anthropic/claude-haiku-4.5')
    } else {
      setModel('gpt-4o-mini')
      setModelPreference('gpt-4o-mini')
    }

    console.log('[Configuration] Provider changed:', newProvider)
  }

  const handleModelChange = (e) => {
    const newModel = e.target.value
    setModel(newModel)
    setModelPreference(newModel)
    console.log('[Configuration] Model changed:', newModel)
  }

  const handleStart = () => {
    onStart({
      files,
      provider,
      model,
      neighborRefs,
      useLlm,
      chunkSize,
      chunkOverlap,
      autoValidate  // Pass preference to parent
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
        <label htmlFor="examples">🧪 Test-Beispiele:</label>
        <select
          id="examples"
          value={selectedExample}
          onChange={handleExampleChange}
          disabled={isLoadingSample || isLoading}
        >
          <option value="">-- Beispiel auswählen --</option>
          <option value="bad_requirements_example.md">❌ Schlechte Requirements (alle Fehler)</option>
          <option value="good_requirements_example.md">✅ Gute Requirements (sollten passen)</option>
          <option value="mixed_requirements_example.md">🔀 Gemischte Requirements (~50% Pass-Rate)</option>
          <option value="port_manager_requirements.md">🔌 Port Manager App (33 Reqs, High Quality)</option>
        </select>
        <small className="hint" style={{ display: 'block', marginTop: '4px', color: '#666' }}>
          Vordefinierte Beispiele zum Testen der Auto-Validierung
        </small>
      </div>

      <div className="form-group">
        <button
          className="btn btn-sample"
          onClick={loadSampleFile}
          disabled={isLoadingSample || isLoading}
        >
          {isLoadingSample ? '⏳ Lade...' : '📝 Beispieldatei laden (Moiré Mouse Tracking)'}
        </button>
      </div>

      <div className="form-group">
        <label htmlFor="provider">🔌 LLM Provider:</label>
        <select id="provider" value={provider} onChange={handleProviderChange}>
          <option value="openai">OpenAI</option>
          <option value="openrouter">OpenRouter</option>
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="model">🧠 Modell:</label>
        <select id="model" value={model} onChange={handleModelChange}>
          {provider === 'openai' && (
            <>
              <option value="gpt-4o-mini">gpt-4o-mini (schnell & günstig)</option>
              <option value="gpt-4o">gpt-4o (präzise)</option>
              <option value="gpt-4">gpt-4 (high-end)</option>
            </>
          )}
          {provider === 'openrouter' && (
            <>
              <option value="anthropic/claude-haiku-4.5">Claude Haiku 4.5 (schnell, SWE-bench 73%+)</option>
              <option value="anthropic/claude-sonnet-4-5-20250929">Claude Sonnet 4.5 (ausgewogen)</option>
              <option value="anthropic/claude-opus-4-20250805">Claude Opus 4 (premium)</option>
            </>
          )}
        </select>
        <small className="hint" style={{ display: 'block', marginTop: '4px', color: '#666' }}>
          {provider === 'openai' && 'OpenAI API (direkt)'}
          {provider === 'openrouter' && 'OpenRouter Proxy - Zugang zu Claude, Llama, etc.'}
        </small>
      </div>

      <div className="form-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={autoValidate}
            onChange={handleAutoValidateChange}
          />
          <span>⚡ Automatisch validieren nach Mining</span>
        </label>
        <small className="hint" style={{ display: 'block', marginTop: '4px', marginLeft: '24px', color: '#666' }}>
          Startet Batch-Validierung automatisch nach erfolgreicher Requirements-Extraktion
        </small>
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
              onChange={(e) => setChunkSize(parseInt(e.target.value) || 800)}
            />
            <small className="hint">Standard: 4000 | Größer = mehr Kontext pro Chunk</small>
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
              onChange={(e) => setChunkOverlap(parseInt(e.target.value) || 200)}
            />
            <small className="hint">Standard: 300 | Überlappung zwischen Chunks</small>
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
        <button
          className="btn btn-primary"
          onClick={handleStart}
          disabled={!files || isLoading}
        >
          {isLoading ? '⏳ Verarbeitung läuft...' : '🚀 Mining starten'}
        </button>
        <button
          className="btn btn-secondary"
          onClick={onReset}
          disabled={isLoading}
        >
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
