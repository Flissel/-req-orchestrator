import { useState, useCallback, useEffect } from 'react'
import './App.css'
import AgentStatus from './components/AgentStatus'
import Configuration from './components/Configuration'
import Requirements from './components/Requirements'
import KnowledgeGraph from './components/KnowledgeGraph'
import ClarificationModal from './components/ClarificationModal'
import ValidationTest from './components/ValidationTest'
import ChatInterface from './components/ChatInterface'

const API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : ''

function App() {
  const [agents, setAgents] = useState({
    'chunk-miner': { status: 'waiting', message: 'Warten' },
    kg: { status: 'waiting', message: 'Warten' }
  })

  const [requirements, setRequirements] = useState([])
  const [kgData, setKgData] = useState({ nodes: [], edges: [] })
  const [logs, setLogs] = useState([])
  const [status, setStatus] = useState({ message: 'Bereit', type: 'info' })
  const [selectedFiles, setSelectedFiles] = useState([])
  const [filePreview, setFilePreview] = useState({ name: '', content: '' })
  const [sessionId, setSessionId] = useState(null)

  // Generate unique session ID on mount
  useEffect(() => {
    const id = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    setSessionId(id)
    console.log(`[App] Session ID generated: ${id}`)
  }, [])

  const updateAgentStatus = (agent, status, message) => {
    if (agent === 'all') {
      const allAgents = {}
      Object.keys(agents).forEach(key => {
        allAgents[key] = { status, message }
      })
      setAgents(allAgents)
    } else {
      setAgents(prev => ({
        ...prev,
        [agent]: { status, message }
      }))
    }
  }

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev].slice(0, 100))
  }

  const handleFilesChange = useCallback(async (files) => {
    setSelectedFiles(files)
    if (files && files.length > 0) {
      const file = files[0]
      const fileName = file.name.toLowerCase()

      // Check if file is binary format
      const isBinary = fileName.endsWith('.docx') ||
                       fileName.endsWith('.pdf') ||
                       fileName.endsWith('.doc') ||
                       fileName.endsWith('.xlsx')

      if (isBinary) {
        const sizeKB = (file.size / 1024).toFixed(2)
        setFilePreview({
          name: file.name,
          content: `📄 Binäre Datei\n\nTyp: ${file.type || 'Unbekannt'}\nGröße: ${sizeKB} KB\n\n✓ Datei bereit für Mining\n\nHinweis: Vorschau ist nur für Textdateien (.md, .txt) verfügbar.\nDie Datei wird beim Mining automatisch verarbeitet.`
        })
      } else {
        try {
          const text = await file.text()
          setFilePreview({ name: file.name, content: text.slice(0, 5000) })
        } catch (err) {
          setFilePreview({ name: file.name, content: 'Vorschau nicht verfügbar' })
        }
      }
    }
  }, [])

  const handleStartMining = async (config) => {
    try {
      const { files, model, neighborRefs, useLlm, chunkSize, chunkOverlap } = config

      if (!files || files.length === 0) {
        setStatus({ message: 'Bitte wählen Sie mindestens eine Datei aus.', type: 'err' })
        return
      }

      updateAgentStatus('all', 'active', 'Verarbeitung läuft...')
      setStatus({ message: 'Starte Master Workflow...', type: 'warn' })
      addLog('🚀 Starte Master Society of Mind Workflow')

      const formData = new FormData()
      files.forEach(file => {
        formData.append('files', file)
      })

      // Add session ID for SSE streaming
      formData.append('correlation_id', sessionId)

      if (model && model !== 'gpt-4o-mini') {
        formData.append('model', model)
      }

      // Add custom chunk parameters
      if (chunkSize) {
        formData.append('chunk_size', chunkSize.toString())
      }

      if (chunkOverlap) {
        formData.append('chunk_overlap', chunkOverlap.toString())
      }

      // Add LLM KG option
      if (useLlm !== undefined) {
        formData.append('use_llm_kg', useLlm ? 'true' : 'false')
      }

      addLog(`Sende Anfrage an Master Workflow (Session: ${sessionId})...`)
      addLog('💬 Agent-Konversation erscheint im Chat unten')

      const response = await fetch(`${API_BASE}/api/arch_team/process`, {
        method: 'POST',
        body: formData
      })

      const result = await response.json()

      if (!response.ok || !result.success) {
        throw new Error(result.error || result.message || 'Workflow fehlgeschlagen')
      }

      addLog(`✅ Master Workflow abgeschlossen`)

      // Extract results if available
      if (result.result) {
        addLog('📊 Verarbeite Workflow-Ergebnisse...')
        // Results will be updated via SSE and onWorkflowComplete callback
      }

      updateAgentStatus('all', 'completed', 'Workflow abgeschlossen')
      setStatus({
        message: 'Master Workflow erfolgreich abgeschlossen',
        type: 'ok'
      })

    } catch (error) {
      updateAgentStatus('all', 'error', 'Fehler aufgetreten')
      setStatus({ message: `Fehler: ${error.message}`, type: 'err' })
      addLog(`❌ Fehler: ${error.message}`, 'error')
    }
  }

  const handleReset = () => {
    setRequirements([])
    setKgData({ nodes: [], edges: [] })
    setLogs([])
    updateAgentStatus('all', 'waiting', 'Warten')
    setStatus({ message: 'System zurückgesetzt', type: 'warn' })
    addLog('System zurückgesetzt')
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🚀 arch_team - Requirements Mining Platform</h1>
        <p className="subtitle">Multi-Agent Requirements Extraction & Knowledge Graph Generation</p>
      </header>

      <AgentStatus agents={agents} />
      <ValidationTest sessionId={sessionId} />

      <div className="main-grid">
        <div className="left-panel">
          <Configuration
            onStart={handleStartMining}
            onReset={handleReset}
            onFilesChange={handleFilesChange}
            status={status}
            logs={logs}
          />
        </div>

        <div className="center-panel">
          <KnowledgeGraph data={kgData} requirements={requirements} />
        </div>

        <div className="right-panel">
          <div className="file-preview">
            <h3>📄 Dateivorschau</h3>
            {filePreview.name ? (
              <>
                <div className="preview-header">{filePreview.name}</div>
                <pre className="preview-content">{filePreview.content}</pre>
              </>
            ) : (
              <div className="preview-empty">Keine Datei ausgewählt</div>
            )}
          </div>
        </div>
      </div>

      <Requirements requirements={requirements} />

      {/* User Clarification Modal (SSE-based) */}
      <ClarificationModal
        sessionId={sessionId}
        enabled={true}
      />

      {/* Chat Interface for Master Workflow */}
      <ChatInterface
        sessionId={sessionId}
        onWorkflowComplete={(result) => {
          console.log('[App] Workflow completed:', result)
          if (result.requirements) {
            setRequirements(result.requirements)
          }
          if (result.kg_data) {
            setKgData(result.kg_data)
          }
        }}
      />
    </div>
  )
}

export default App