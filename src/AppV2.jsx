import { useState, useCallback, useEffect, useRef } from 'react'
import './AppV2.css'
import TabNavigation from './components/TabNavigation'
import AgentStatus from './components/AgentStatus'
import Configuration from './components/Configuration'
import RequirementsTable from './components/RequirementsTable'
import KnowledgeGraph from './components/KnowledgeGraph'
import ManifestViewer from './components/ManifestViewer'
import ValidationModal from './components/ValidationModal'
import BatchValidationModal from './components/BatchValidationModal'
import ToastNotification from './components/ToastNotification'
import ValidationTab from './components/ValidationTab'

// Use relative URLs to leverage Vite's proxy
const API_BASE = ''

const generateSessionId = () => `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

function AppV2() {
  const sessionIdRef = useRef(generateSessionId())
  const sessionId = sessionIdRef.current

  // Tab state
  const [activeTab, setActiveTab] = useState('mining')

  // Core state
  const [agents, setAgents] = useState({
    'chunk-miner': { status: 'waiting', message: 'Waiting' },
    kg: { status: 'waiting', message: 'Waiting' }
  })

  const [requirements, setRequirements] = useState([])
  const [kgData, setKgData] = useState({ nodes: [], edges: [] })
  const [validationResults, setValidationResults] = useState(null)
  const [logs, setLogs] = useState([])
  const [status, setStatus] = useState({ message: 'Ready', type: 'info' })
  const [selectedFiles, setSelectedFiles] = useState([])
  const [filePreview, setFilePreview] = useState({ name: '', content: '' })
  const [isLoading, setIsLoading] = useState(false)
  const [selectedRequirementId, setSelectedRequirementId] = useState(null)
  const [validatingRequirement, setValidatingRequirement] = useState(null)
  const [batchValidationQueue, setBatchValidationQueue] = useState(null)
  const [showAutoValidateToast, setShowAutoValidateToast] = useState(false)
  const [pendingAutoValidation, setPendingAutoValidation] = useState(null)

  useEffect(() => {
    console.log(`[AppV2] Session ID: ${sessionId}`)
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

      const isBinary = fileName.endsWith('.docx') ||
                       fileName.endsWith('.pdf') ||
                       fileName.endsWith('.doc') ||
                       fileName.endsWith('.xlsx')

      if (isBinary) {
        const sizeKB = (file.size / 1024).toFixed(2)
        setFilePreview({
          name: file.name,
          content: `📄 Binary File\n\nType: ${file.type || 'Unknown'}\nSize: ${sizeKB} KB\n\n✓ File ready for mining\n\nNote: Preview is only available for text files (.md, .txt).\nThe file will be processed automatically during mining.`
        })
      } else {
        try {
          const text = await file.text()
          setFilePreview({ name: file.name, content: text.slice(0, 5000) })
        } catch (err) {
          setFilePreview({ name: file.name, content: 'Preview not available' })
        }
      }
    }
  }, [])

  const handleStartMining = async (config) => {
    const { files, model, neighborRefs, useLlm, chunkSize, chunkOverlap, autoValidate } = config

    const filesToUse = files || selectedFiles
    if (!filesToUse || filesToUse.length === 0) {
      setStatus({ message: 'Please select files first', type: 'err' })
      addLog('❌ No files selected', 'error')
      return
    }

    setIsLoading(true)
    setStatus({ message: 'Starting Master Workflow...', type: 'info' })
    addLog(`🚀 Starting mining with ${filesToUse.length} file(s)`)

    updateAgentStatus('all', 'running', 'Processing...')

    try {
      const formData = new FormData()
      Array.from(filesToUse).forEach(file => {
        formData.append('files', file)
      })

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

      formData.append('validation_threshold', '0.7')

      // Debug: Log all parameters being sent
      console.log('[AppV2] FormData parameters:')
      for (let [key, value] of formData.entries()) {
        if (key !== 'files') {  // Skip file objects in log
          console.log(`  ${key}: ${value}`)
        }
      }

      const response = await fetch(`${API_BASE}/api/arch_team/process`, {
        method: 'POST',
        body: formData,
      })

      const result = await response.json()

      if (!response.ok || !result.success) {
        throw new Error(result.error || result.message || 'Workflow failed')
      }

      addLog(`✅ Master Workflow completed`)

      let requirementsWithScores = []

      if (result.requirements && Array.isArray(result.requirements)) {
        requirementsWithScores = result.requirements

        if (result.validation_results && result.validation_results.details) {
          const validationMap = new Map()
          result.validation_results.details.forEach(detail => {
            const passed = detail.verdict === "pass" || detail.passed === true

            // Transform backend format to frontend format
            const evaluation = detail.evaluation?.map(e => ({
              criterion: e.criterion,
              isValid: e.passed,        // Map "passed" → "isValid"
              reason: e.feedback || '',  // Map "feedback" → "reason"
              score: e.score
            })) || []

            validationMap.set(detail.req_id, {
              score: detail.score,
              passed: passed,
              evaluation: evaluation  // Include transformed evaluation array
            })
          })

          requirementsWithScores = result.requirements.map(req => {
            const validation = validationMap.get(req.req_id)
            return {
              ...req,
              validation_score: validation ? validation.score : 0.0,
              validation_passed: validation ? validation.passed : false,
              evaluation: validation ? validation.evaluation : []  // Attach evaluation array
            }
          })
        } else {
          requirementsWithScores = result.requirements.map(req => ({
            ...req,
            validation_score: 0.0,
            validation_passed: false
          }))
        }

        setRequirements(requirementsWithScores)
        addLog(`📊 ${requirementsWithScores.length} Requirements extracted`)

        // Auto-switch to Requirements tab after mining
        setActiveTab('requirements')
      }

      if (result.kg_data) {
        setKgData(result.kg_data)
        const nodeCount = result.kg_data.stats?.nodes || result.kg_data.nodes?.length || 0
        const edgeCount = result.kg_data.stats?.edges || result.kg_data.edges?.length || 0
        addLog(`🔗 Knowledge Graph: ${nodeCount} Nodes, ${edgeCount} Edges`)
      }

      if (result.validation_results) {
        const valResults = result.validation_results
        setValidationResults(valResults)
        addLog(`✅ Validation: ${valResults.passed} successful, ❌ ${valResults.failed} failed`)
      }

      updateAgentStatus('all', 'completed', 'Workflow completed')
      setStatus({
        message: 'Master Workflow successfully completed',
        type: 'ok'
      })

      // Trigger auto-validation if enabled
      if (autoValidate && result.validation_results && requirementsWithScores && requirementsWithScores.length > 0) {
        const failedCount = result.validation_results.failed || 0

        if (failedCount > 0) {
          const failingReqs = requirementsWithScores.filter(req => {
            const score = req.validation_score
            return score !== undefined && score < 0.7
          })

          if (failingReqs.length > 0) {
            addLog(`⚡ Auto-validation activated: ${failingReqs.length} requirements need improvement`)
            setPendingAutoValidation(failingReqs)
            setShowAutoValidateToast(true)
          }
        }
      }

    } catch (error) {
      updateAgentStatus('all', 'error', 'Error occurred')
      setStatus({ message: `Error: ${error.message}`, type: 'err' })
      addLog(`❌ Error: ${error.message}`, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleReset = () => {
    setRequirements([])
    setKgData({ nodes: [], edges: [] })
    setValidationResults(null)
    setSelectedFiles([])
    setFilePreview({ name: '', content: '' })
    setLogs([])
    setStatus({ message: 'Ready', type: 'info' })
    updateAgentStatus('all', 'waiting', 'Waiting')
    addLog('🔄 System reset')
  }

  const handleRequirementClick = (reqId) => {
    setSelectedRequirementId(reqId)
  }

  const handleValidate = (requirement) => {
    setValidatingRequirement(requirement)
  }

  const handleStartBatchValidation = (failingReqs) => {
    setBatchValidationQueue(failingReqs)
  }

  const handleBatchValidationComplete = (results) => {
    // Update requirements with new validation scores
    setRequirements(prev => prev.map(req => {
      const updated = results.find(r => r.req_id === req.req_id)
      return updated ? { ...req, ...updated } : req
    }))

    setBatchValidationQueue(null)
    addLog(`✅ Batch validation completed`)
  }

  const handleAutoValidateConfirm = () => {
    if (pendingAutoValidation && pendingAutoValidation.length > 0) {
      handleStartBatchValidation(pendingAutoValidation)
      setShowAutoValidateToast(false)
      setPendingAutoValidation(null)
    }
  }

  const handleAutoValidateCancel = () => {
    setShowAutoValidateToast(false)
    setPendingAutoValidation(null)
  }

  // Calculate failing requirements for validation tab
  const failingRequirements = requirements.filter(req => {
    const score = req.validation_score
    return score !== undefined && score < 0.7
  })

  return (
    <div className="app-v2">
      <header className="header-v2">
        <h1>🚀 arch_team - Requirements Mining Platform</h1>
        <p className="subtitle">Multi-Agent Requirements Extraction & Knowledge Graph Generation</p>
      </header>

      <AgentStatus agents={agents} />

      <TabNavigation activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="tab-content">
        {/* Tab 1: Mining */}
        {activeTab === 'mining' && (
          <div className="tab-panel mining-panel">
            <div className="mining-grid">
              <div className="config-section">
                <Configuration
                  onStart={handleStartMining}
                  onReset={handleReset}
                  onFilesChange={handleFilesChange}
                  status={status}
                  logs={logs}
                  isLoading={isLoading}
                />
              </div>

              <div className="preview-section">
                <div className="file-preview">
                  <h3>📄 File Preview</h3>
                  {filePreview.name ? (
                    <>
                      <div className="preview-header">{filePreview.name}</div>
                      <pre className="preview-content">{filePreview.content}</pre>
                    </>
                  ) : (
                    <div className="preview-empty">No file selected</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Requirements */}
        {activeTab === 'requirements' && (
          <div className="tab-panel requirements-panel">
            <RequirementsTable
              requirements={requirements}
              onRequirementClick={handleRequirementClick}
            />
          </div>
        )}

        {/* Tab 3: Validation */}
        {activeTab === 'validation' && (
          <div className="tab-panel validation-panel">
            <ValidationTab
              requirements={requirements}
              onRequirementClick={handleRequirementClick}
              onValidateAll={handleStartBatchValidation}
            />
          </div>
        )}

        {/* Tab 4: Knowledge Graph */}
        {activeTab === 'knowledge-graph' && (
          <div className="tab-panel kg-panel">
            <div className="kg-split-layout">
              <div className="kg-left-panel">
                <h3 className="panel-title">📋 Requirements</h3>
                <RequirementsTable
                  requirements={requirements}
                  onRequirementClick={handleRequirementClick}
                />
              </div>
              <div className="kg-right-panel">
                <h3 className="panel-title">🕸️ Knowledge Graph</h3>
                <div className="kg-container">
                  <KnowledgeGraph data={kgData} requirements={requirements} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      {selectedRequirementId && (
        <ManifestViewer
          requirementId={selectedRequirementId}
          onClose={() => setSelectedRequirementId(null)}
        />
      )}

      {validatingRequirement && (
        <ValidationModal
          requirement={validatingRequirement}
          sessionId={`val-${Date.now()}`}
          onClose={() => setValidatingRequirement(null)}
        />
      )}

      {batchValidationQueue && (
        <BatchValidationModal
          requirements={batchValidationQueue}
          sessionId={`batch-${Date.now()}`}
          onClose={() => setBatchValidationQueue(null)}
          onComplete={handleBatchValidationComplete}
        />
      )}

      {showAutoValidateToast && (
        <ToastNotification
          message={`${pendingAutoValidation?.length || 0} requirements failed validation. Start auto-validation?`}
          countdown={10}
          onComplete={handleAutoValidateConfirm}
          onCancel={handleAutoValidateCancel}
        />
      )}
    </div>
  )
}

export default AppV2
