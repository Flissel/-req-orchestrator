import { useState, useCallback, useEffect, useRef } from 'react'
import './App.css'
import AgentStatus from './components/AgentStatus'
import Configuration from './components/Configuration'
import Requirements from './components/Requirements'
import KnowledgeGraph from './components/KnowledgeGraph'
import ClarificationModal from './components/ClarificationModal'
import ValidationTest from './components/ValidationTest'
import ChatInterface from './components/ChatInterface'
import ManifestViewer from './components/ManifestViewer'
import ValidationModal from './components/ValidationModal'
import ValidationAnalytics from './components/ValidationAnalytics'
import BatchValidationButton from './components/BatchValidationButton'
import BatchValidationModal from './components/BatchValidationModal'
import ToastNotification from './components/ToastNotification'

// Use relative URLs to leverage Vite's proxy (eliminates CORS warnings)
const API_BASE = ''

// Generate session ID once (outside component to prevent duplicates)
const generateSessionId = () => `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

function App() {
  // Use ref to persist session ID across renders (prevents duplicate generation)
  const sessionIdRef = useRef(generateSessionId())
  const sessionId = sessionIdRef.current

  const [agents, setAgents] = useState({
    'chunk-miner': { status: 'waiting', message: 'Warten' },
    kg: { status: 'waiting', message: 'Warten' }
  })

  const [requirements, setRequirements] = useState([])
  const [kgData, setKgData] = useState({ nodes: [], edges: [] })
  const [validationResults, setValidationResults] = useState(null)
  const [logs, setLogs] = useState([])
  const [status, setStatus] = useState({ message: 'Bereit', type: 'info' })
  const [selectedFiles, setSelectedFiles] = useState([])
  const [filePreview, setFilePreview] = useState({ name: '', content: '' })
  const [isLoading, setIsLoading] = useState(false)
  const [selectedRequirementId, setSelectedRequirementId] = useState(null)
  const [validatingRequirement, setValidatingRequirement] = useState(null)
  const [batchValidationQueue, setBatchValidationQueue] = useState(null)
  const [showAutoValidateToast, setShowAutoValidateToast] = useState(false)
  const [pendingAutoValidation, setPendingAutoValidation] = useState(null)

  // Log session ID once on mount
  useEffect(() => {
    console.log(`[App] Session ID: ${sessionId}`)
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
      const { files, model, neighborRefs, useLlm, chunkSize, chunkOverlap, autoValidate } = config

      if (!files || files.length === 0) {
        setStatus({ message: 'Bitte wählen Sie mindestens eine Datei aus.', type: 'err' })
        return
      }

      setIsLoading(true)
      updateAgentStatus('all', 'active', 'Verarbeitung läuft...')
      setStatus({ message: 'Starte Master Workflow...', type: 'warn' })
      addLog('🚀 Starte Master Society of Mind Workflow')

      console.log('[App] Auto-validate preference:', autoValidate)

      const formData = new FormData()
      files.forEach(file => {
        formData.append('files', file)
      })

      // Add session ID for SSE streaming
      formData.append('correlation_id', sessionId)

      // Always send model parameter (don't skip default)
      formData.append('model', model || 'gpt-4o-mini')

      // Add extraction configuration parameters (matching V1)
      formData.append('structured', '1')
      formData.append('chunkMode', 'paragraph')
      formData.append('preserveSources', '1')
      formData.append('configId', 'default')

      // Add neighbor references if enabled
      if (neighborRefs) {
        formData.append('neighbor_refs', '1')
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

      // Debug: Log all parameters being sent
      console.log('[App] FormData parameters:')
      for (let [key, value] of formData.entries()) {
        if (key !== 'files') {  // Skip file objects in log
          console.log(`  ${key}: ${value}`)
        }
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

      // Extract results from HTTP response immediately
      console.log('[App] Workflow result:', result)

      // Declare requirementsWithScores outside the if block so it's accessible for auto-validation
      let requirementsWithScores = []

      if (result.requirements && Array.isArray(result.requirements)) {
        // Merge validation scores into requirements
        requirementsWithScores = result.requirements

        if (result.validation_results && result.validation_results.details) {
          // Create map of validation results by req_id for efficient lookup
          const validationMap = new Map()
          result.validation_results.details.forEach(detail => {
            // Backend returns "verdict": "pass"/"fail", convert to boolean
            const passed = detail.verdict === "pass" || detail.passed === true
            validationMap.set(detail.req_id, {
              score: detail.score,
              passed: passed
            })
          })

          // Merge scores into requirements
          requirementsWithScores = result.requirements.map(req => {
            const validation = validationMap.get(req.req_id)
            return {
              ...req,
              validation_score: validation ? validation.score : 0.0,  // Default: 0.0 (fresh/unmined)
              validation_passed: validation ? validation.passed : false
            }
          })

          console.log('[App] Merged validation scores into requirements')
        } else {
          // No validation results - set all scores to 0.0 (fresh)
          requirementsWithScores = result.requirements.map(req => ({
            ...req,
            validation_score: 0.0,
            validation_passed: false
          }))
          console.log('[App] No validation results - initialized all scores to 0.0')
        }

        setRequirements(requirementsWithScores)
        addLog(`📊 ${requirementsWithScores.length} Requirements extrahiert`)
        console.log('[App] Requirements set:', requirementsWithScores.length)
      }

      if (result.kg_data) {
        setKgData(result.kg_data)
        const nodeCount = result.kg_data.stats?.nodes || result.kg_data.nodes?.length || 0
        const edgeCount = result.kg_data.stats?.edges || result.kg_data.edges?.length || 0
        addLog(`🔗 Knowledge Graph: ${nodeCount} Nodes, ${edgeCount} Edges`)
        console.log('[App] KG data set:', result.kg_data.stats)
      }

      if (result.validation_results) {
        const valResults = result.validation_results
        setValidationResults(valResults)
        addLog(`✅ Validierung: ${valResults.passed} erfolgreich, ❌ ${valResults.failed} fehlgeschlagen`)
        console.log('[App] Validation results:', valResults)
      }

      updateAgentStatus('all', 'completed', 'Workflow abgeschlossen')
      setStatus({
        message: 'Master Workflow erfolgreich abgeschlossen',
        type: 'ok'
      })

      // Trigger auto-validation if enabled and there are failing requirements
      if (autoValidate && result.validation_results && requirementsWithScores && requirementsWithScores.length > 0) {
        const valResults = result.validation_results
        const failedCount = valResults.failed || 0

        console.log('[App] Auto-validate check:', {
          autoValidate,
          failedCount,
          totalReqs: requirementsWithScores.length,
          sampleReq: requirementsWithScores[0]
        })

        if (failedCount > 0) {
          // Filter requirements with score < 0.7 from the merged data (with validation_score)
          const failingReqs = requirementsWithScores.filter(req => {
            const score = req.validation_score
            return score !== undefined && score < 0.7
          })

          console.log('[App] Filtered failing requirements:', failingReqs.length, 'out of', requirementsWithScores.length)

          if (failingReqs.length > 0) {
            console.log('[App] Auto-validate enabled, found', failingReqs.length, 'failing requirements')
            addLog(`⚡ Auto-Validierung aktiviert: ${failingReqs.length} Requirements benötigen Verbesserung`)

            // Store pending requirements and show toast
            setPendingAutoValidation(failingReqs)
            setShowAutoValidateToast(true)
          } else {
            console.log('[App] Auto-validate: No requirements with validation_score < 0.7 found')
            addLog('⚠️ Keine Requirements mit validation_score gefunden - prüfe Backend-Response')
          }
        } else {
          console.log('[App] Auto-validate enabled, but all requirements passed')
          addLog('✅ Alle Requirements haben die Qualitätskriterien erfüllt - keine Validierung nötig')
        }
      }

    } catch (error) {
      updateAgentStatus('all', 'error', 'Fehler aufgetreten')
      setStatus({ message: `Fehler: ${error.message}`, type: 'err' })
      addLog(`❌ Fehler: ${error.message}`, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleReset = () => {
    setRequirements([])
    setKgData({ nodes: [], edges: [] })
    setLogs([])
    updateAgentStatus('all', 'waiting', 'Warten')
    setStatus({ message: 'System zurückgesetzt', type: 'warn' })
    addLog('System zurückgesetzt')
    setSelectedRequirementId(null)
  }

  const handleRequirementClick = (requirementId) => {
    setSelectedRequirementId(requirementId)
    addLog(`📄 Manifest anzeigen: ${requirementId}`)
  }

  const handleCloseManifest = () => {
    setSelectedRequirementId(null)
  }

  const handleValidateRequirement = (requirement) => {
    setValidatingRequirement(requirement)
    addLog(`🔍 Validating requirement: ${requirement.req_id}`)
  }

  const handleCloseValidation = () => {
    setValidatingRequirement(null)
  }

  // Rebuild Knowledge Graph with current requirements
  const rebuildKnowledgeGraph = async (reqs) => {
    if (!reqs || reqs.length === 0) return

    try {
      addLog('Updating Knowledge Graph...')

      const response = await fetch('/api/kg/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: reqs.map(r => ({
            req_id: r.req_id,
            title: r.title || r.text,
            tag: r.tag || 'General',
            evidence_refs: r.evidence_refs || []
          })),
          options: {
            persist: 'qdrant',
            use_llm: false,
            llm_fallback: true,
            persist_async: true
          }
        })
      })

      const data = await response.json()
      if (data.success) {
        setKgData({ nodes: data.nodes || [], edges: data.edges || [] })
        addLog(`KG updated: ${data.nodes?.length || 0} nodes, ${data.edges?.length || 0} edges`)
      } else {
        throw new Error(data.message || 'KG build failed')
      }
    } catch (err) {
      console.error('[App] KG rebuild error:', err)
      addLog(`KG rebuild failed: ${err.message}`)
    }
  }

  const handleValidationComplete = async (requirementId, validationResult) => {
    // Update the requirement with validation results
    const updatedRequirements = requirements.map(req => {
      if (req.req_id === requirementId) {
        return {
          ...req,
          validation_score: validationResult.final_score,
          validation_passed: validationResult.passed,
          validation_fixes: validationResult.total_fixes,
          title: validationResult.final_text || req.title,
          corrected_text: validationResult.final_text
        }
      }
      return req
    })

    setRequirements(updatedRequirements)
    addLog(`Validation complete for ${requirementId}: Score ${(validationResult.final_score * 100).toFixed(0)}%`)

    // Auto-rebuild KG with updated requirements
    await rebuildKnowledgeGraph(updatedRequirements)
  }

  const handleStartBatchValidation = (failingRequirements) => {
    setBatchValidationQueue(failingRequirements)
    addLog(`🔧 Starting batch validation for ${failingRequirements.length} requirements`)
  }

  const handleCloseBatchValidation = () => {
    setBatchValidationQueue(null)
  }

  const handleBatchValidationComplete = async (results) => {
    // Update all requirements with batch validation results
    const updatedRequirements = requirements.map(req => {
      const result = results.find(r => r.req_id === req.req_id)
      if (result) {
        return {
          ...req,
          validation_score: result.score,
          validation_passed: result.passed,
          validation_fixes: result.fixes,
          title: result.final_text || req.title,
          corrected_text: result.final_text
        }
      }
      return req
    })

    setRequirements(updatedRequirements)

    const passedCount = results.filter(r => r.passed).length
    const failedCount = results.filter(r => !r.passed).length
    addLog(`Batch validation complete: ${passedCount} passed, ${failedCount} failed`)

    // Auto-rebuild KG with updated requirements
    await rebuildKnowledgeGraph(updatedRequirements)
  }

  const handleAutoValidateComplete = () => {
    // Toast countdown completed - start batch validation
    console.log('[App] Auto-validate countdown complete, starting batch validation')
    addLog('🚀 Starte automatische Batch-Validierung...')

    if (pendingAutoValidation && pendingAutoValidation.length > 0) {
      setBatchValidationQueue(pendingAutoValidation)
      setPendingAutoValidation(null)
      setShowAutoValidateToast(false)
    }
  }

  const handleAutoValidateCancel = () => {
    // User cancelled auto-validation
    console.log('[App] Auto-validate cancelled by user')
    addLog('⏸ Automatische Validierung abgebrochen')

    setPendingAutoValidation(null)
    setShowAutoValidateToast(false)
  }

  // Calculate failing requirements for batch validation button
  const failingRequirements = requirements.filter(req => {
    const score = req.validation_score
    return score !== undefined && score < 0.7
  })

  return (
    <div className="app">
      <header className="header">
        <h1>🚀 arch_team - Requirements Mining Platform</h1>
        <p className="subtitle">Multi-Agent Requirements Extraction & Knowledge Graph Generation</p>
      </header>

      <AgentStatus agents={agents} />
      <ValidationTest sessionId={sessionId} precomputedResults={validationResults} />
      <ValidationAnalytics days={30} />

      {/* Batch Validation Button - shows when there are failing requirements */}
      <BatchValidationButton
        failingRequirements={failingRequirements}
        onStartBatch={handleStartBatchValidation}
      />

      <div className="main-grid">
        <div className="left-panel">
          <Configuration
            onStart={handleStartMining}
            onReset={handleReset}
            onFilesChange={handleFilesChange}
            status={status}
            logs={logs}
            isLoading={isLoading}
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

      <Requirements
        requirements={requirements}
        onRequirementClick={handleRequirementClick}
        selectedRequirementId={selectedRequirementId}
        onValidateRequirement={handleValidateRequirement}
      />

      {/* Manifest Viewer Panel (conditional) */}
      {selectedRequirementId && (
        <ManifestViewer
          requirementId={selectedRequirementId}
          onClose={handleCloseManifest}
          onNavigate={handleRequirementClick}
        />
      )}

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

      {/* Validation Modal (conditional) */}
      {validatingRequirement && (
        <ValidationModal
          requirement={validatingRequirement}
          onClose={handleCloseValidation}
          onValidationComplete={handleValidationComplete}
        />
      )}

      {/* Batch Validation Modal (conditional) */}
      {batchValidationQueue && (
        <BatchValidationModal
          requirements={batchValidationQueue}
          onClose={handleCloseBatchValidation}
          onBatchComplete={handleBatchValidationComplete}
        />
      )}

      {/* Auto-Validate Toast Notification */}
      <ToastNotification
        show={showAutoValidateToast}
        message={`${pendingAutoValidation?.length || 0} Requirements mit Qualitätsmängeln gefunden`}
        countdown={3}
        onComplete={handleAutoValidateComplete}
        onCancel={handleAutoValidateCancel}
      />
    </div>
  )
}

export default App