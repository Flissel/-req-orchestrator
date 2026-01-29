import { useState, useCallback, useEffect, useRef } from 'react'
import './AppV2.css'
import TabNavigation from './components/TabNavigation'
import AgentStatus from './components/AgentStatus'
import Configuration from './components/Configuration'
import RequirementsTable from './components/RequirementsTable'
import KnowledgeGraph from './components/KnowledgeGraph'
import ManifestViewer from './components/ManifestViewer'
import ValidationModal from './components/ValidationModal'
import ToastNotification from './components/ToastNotification'
import ValidationTab from './components/ValidationTab'
import EnhancementModal from './components/EnhancementModal'
import TechStackTab from './components/TechStackTab'
import ProjectSelectorModal from './components/ProjectSelectorModal'
import Shuttle from './components/Shuttle'

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
  const [enhancingRequirement, setEnhancingRequirement] = useState(null)
  const [showTechStackTab, setShowTechStackTab] = useState(false)
  const [showProjectSelector, setShowProjectSelector] = useState(false)

  // Lifted batch validation state - persists across tab switches
  const [batchValidationState, setBatchValidationState] = useState({
    isValidating: false,
    progress: { current: 0, total: 0 },
    eventLog: [],
    results: [],
    status: 'idle', // idle, running, paused, completed
    currentReqId: null,
    // Human-in-the-loop: requirements needing user input
    pendingQuestions: [], // [{req_id, requirement_text, questions: [{id, question, suggested_answers, criterion, context_hint}], status: 'awaiting_input'}]
    needsInputCount: 0
  })

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
    const { files, model, provider, neighborRefs, useLlm, chunkSize, chunkOverlap, autoValidate } = config

    const filesToUse = files || selectedFiles
    if (!filesToUse || filesToUse.length === 0) {
      setStatus({ message: 'Please select files first', type: 'err' })
      addLog('❌ No files selected', 'error')
      return
    }

    setIsLoading(true)
    setStatus({ message: 'Starting Master Workflow...', type: 'info' })
    addLog(`🚀 Starting mining with ${filesToUse.length} file(s)`)

    console.log('[AppV2] LLM Provider:', provider || 'openai')
    console.log('[AppV2] Model:', model || 'gpt-4o-mini')

    updateAgentStatus('all', 'running', 'Processing...')

    try {
      const formData = new FormData()
      Array.from(filesToUse).forEach(file => {
        formData.append('files', file)
      })

      formData.append('correlation_id', sessionId)

      // Always send provider and model parameters (don't skip defaults)
      formData.append('provider', provider || 'openai')
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

          requirementsWithScores = requirementsWithScores.map(req => {
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

  // Enhancement handlers
  const handleEnhanceRequirement = (requirement) => {
    setEnhancingRequirement(requirement)
    addLog(`🧠 Starting SocietyOfMind enhancement: ${requirement.req_id}`)
  }

  const handleEnhancementComplete = async (reqId, enhancementResult) => {
    // Update requirement with enhanced text
    let updatedRequirements = requirements.map(req => {
      if (req.req_id === reqId) {
        return ({
          ...req,
          title: enhancementResult.enhanced_text || req.title,
          validation_score: enhancementResult.final_score || req.validation_score,
          validation_passed: (enhancementResult.final_score || 0) >= 0.7,
          _enhanced: true,
          _enhancement_changes: enhancementResult.changes_made
        })
      }
      return req
    })

    // If splits were created, add them as new requirements
    if (enhancementResult.splits && enhancementResult.splits.length > 0) {
      const newReqs = enhancementResult.splits.map((splitText, idx) => ({
        req_id: `${reqId}-split-${idx + 1}`,
        title: splitText,
        tag: requirements.find(r => r.req_id === reqId)?.tag || 'split',
        validation_score: null,
        validation_passed: false,
        _split_from: reqId
      }))
      updatedRequirements.push(...newReqs)
      addLog(`📋 Created ${newReqs.length} split requirements from ${reqId}`)
    }

    setRequirements(updatedRequirements)
    addLog(`✨ Enhancement complete for ${reqId}: Score ${((enhancementResult.final_score || 0) * 100).toFixed(0)}%`)
    setEnhancingRequirement(null)

    // Fire-and-forget: KG rebuild in background
    rebuildKnowledgeGraph(updatedRequirements).catch(err => {
      console.error('[AppV2] Background KG rebuild failed:', err)
    })
  }

  // Rebuild Knowledge Graph with current requirements
  const rebuildKnowledgeGraph = async (reqs) => {
    if (!reqs || reqs.length === 0) return

    try {
      addLog('🔄 Updating Knowledge Graph...')
      updateAgentStatus('kg', 'active', 'Rebuilding KG')

      const response = await fetch(`${API_BASE}/api/kg/build`, {
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

      // Check response status before parsing
      if (!response.ok) {
        console.warn(`[AppV2] KG rebuild service unavailable: ${response.status}`)
        addLog('⚠️ KG service unavailable (skipped)')
        updateAgentStatus('kg', 'idle', 'KG service unavailable')
        return  // Silently fail - KG is optional
      }

      // Check if response has content
      const text = await response.text()
      if (!text) {
        console.warn('[AppV2] KG rebuild returned empty response')
        addLog('⚠️ KG service returned empty response (skipped)')
        updateAgentStatus('kg', 'idle', 'KG service unavailable')
        return
      }

      const data = JSON.parse(text)
      if (data.success) {
        setKgData({ nodes: data.nodes || [], edges: data.edges || [] })
        addLog(`✅ Knowledge Graph updated: ${data.nodes?.length || 0} nodes, ${data.edges?.length || 0} edges`)
        updateAgentStatus('kg', 'complete', 'KG updated')
      } else {
        console.warn('[AppV2] KG rebuild failed:', data.message)
        addLog('⚠️ KG rebuild incomplete (non-critical)')
        updateAgentStatus('kg', 'idle', 'KG build incomplete')
      }
    } catch (err) {
      // Downgrade to warning - KG is optional background feature
      console.warn('[AppV2] KG rebuild unavailable:', err.message)
      // Don't spam user logs for optional feature
      updateAgentStatus('kg', 'idle', 'KG unavailable')
    }
  }

  // Handle inline validation complete from ValidationDetailPanel
  const handleInlineValidationComplete = async (reqId, result) => {
    // Update the specific requirement
    let updatedRequirements = requirements.map(req => {
      if (req.req_id === reqId) {
        return {
          ...req,
          validation_score: result.final_score,
          validation_passed: result.passed,
          validation_fixes: result.total_fixes,
          title: result.final_text || req.title,
          corrected_text: result.final_text,
          split_occurred: result.split_occurred || false
        }
      }
      return req
    })

    // Handle split children - insert after parent
    if (result.split_children && result.split_children.length > 0) {
      const parentIndex = updatedRequirements.findIndex(r => r.req_id === reqId)
      if (parentIndex !== -1) {
        // Insert children after parent
        updatedRequirements = [
          ...updatedRequirements.slice(0, parentIndex + 1),
          ...result.split_children,
          ...updatedRequirements.slice(parentIndex + 1)
        ]
        addLog(`📋 Split ${reqId} into ${result.split_children.length} atomic requirements`)
      }
    }

    setRequirements(updatedRequirements)
    addLog(`✅ Validation complete for ${reqId}: Score ${(result.final_score * 100).toFixed(0)}%`)

    // Fire-and-forget: KG rebuild in background, doesn't block UI
    rebuildKnowledgeGraph(updatedRequirements).catch(err => {
      console.error('[AppV2] Background KG rebuild failed:', err)
    })
  }

  const handleBatchValidationComplete = async (results) => {
    // Update requirements with new validation scores
    const updatedRequirements = requirements.map(req => {
      const updated = results.find(r => r.req_id === req.req_id)
      return updated ? { ...req, ...updated } : req
    })

    setRequirements(updatedRequirements)
    setBatchValidationQueue(null)
    addLog(`✅ Batch validation completed`)

    // Fire-and-forget: KG rebuild in background, doesn't block UI
    rebuildKnowledgeGraph(updatedRequirements).catch(err => {
      console.error('[AppV2] Background KG rebuild failed:', err)
    })
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
    return score !== undefined && score !== null && score < 0.7
  })

  // Load requirements from external sources
  const handleLoadData = async (action) => {
    if (action === 'json') {
      document.getElementById('loadReqsInputV2')?.click()
    } else if (action === 'db') {
      // Open project selector modal
      setShowProjectSelector(true)
    } else if (action === 'kg') {
      // Load KG from Qdrant
      try {
        setStatus({ message: 'Loading Knowledge Graph from Qdrant...', type: 'info' })
        addLog('📂 Loading Knowledge Graph from Qdrant...')
        const res = await fetch(`${API_BASE}/api/kg/export`)
        const data = await res.json()
        if (data.success && (data.nodes?.length > 0 || data.edges?.length > 0)) {
          setKgData({ nodes: data.nodes || [], edges: data.edges || [] })
          addLog(`✅ Loaded KG: ${data.stats?.node_count || 0} nodes, ${data.stats?.edge_count || 0} edges`)
          setStatus({ message: `KG loaded: ${data.stats?.node_count || 0} Nodes, ${data.stats?.edge_count || 0} Edges`, type: 'ok' })
          setActiveTab('knowledge-graph')
        } else {
          setStatus({ message: 'KG is empty or error', type: 'warn' })
          addLog('⚠️ Knowledge Graph is empty')
        }
      } catch (err) {
        console.error('[AppV2] KG load failed:', err)
        setStatus({ message: 'KG load failed', type: 'err' })
        addLog(`❌ KG load failed: ${err.message}`)
      }
    }
  }

  // Handle project selection from modal
  const handleProjectSelect = async (source) => {
    try {
      setStatus({ message: 'Loading requirements from DB...', type: 'info' })
      
      // Build URL with optional source_file filter
      let url = `${API_BASE}/api/v1/manifest?limit=500`
      if (source && source.source_file) {
        url += `&source_file=${encodeURIComponent(source.source_file)}`
        addLog(`📂 Loading requirements from: ${source.source_file}`)
      } else {
        addLog('📂 Loading all requirements from database...')
      }
      
      const res = await fetch(url)
      const data = await res.json()
      
      // API returns array directly, not {manifests: []}
      const manifests = Array.isArray(data) ? data : (data.manifests || [])
      
      if (manifests.length > 0) {
        // Transform manifest format to requirements format for validation
        const reqs = manifests.map(m => {
          // Use validation_score directly from manifest (persisted by Phase 3c in master_agent)
          const validationScore = m.validation_score ?? null
          const validationPassed = m.validation_verdict === 'pass' ||
            (validationScore !== null && validationScore >= 0.7) || false

          return {
            req_id: m.requirement_id,
            title: m.current_text || m.original_text,
            tag: m.metadata?.tag || m.source_type || 'imported',
            evidence_refs: m.evidence_refs || [],
            validation_score: validationScore,
            validation_passed: validationPassed,
            source_file: m.source_file,
            original_text: m.original_text,
            current_text: m.current_text,
            current_stage: m.current_stage,
            evaluation: m.evaluation || []
          }
        })

        // Count validated vs not validated
        const validatedCount = reqs.filter(r => r.validation_score !== null).length
        setRequirements(reqs)
        
        const sourceInfo = source?.source_file ? ` from "${source.source_file}"` : ''
        addLog(`✅ Loaded ${reqs.length} requirements${sourceInfo} (${validatedCount} validated)`)
        setStatus({ message: `${reqs.length} Requirements loaded (${validatedCount} validated)`, type: 'ok' })
        setActiveTab('requirements')
      } else {
        setStatus({ message: 'No requirements found', type: 'warn' })
        addLog('⚠️ No requirements found in database')
      }
    } catch (err) {
      console.error('[AppV2] DB load failed:', err)
      setStatus({ message: 'DB load failed', type: 'err' })
      addLog(`❌ DB load failed: ${err.message}`)
    }
  }

  const handleJsonFileLoad = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      const reqs = data.requirements || data

      // Build validation lookup from validation_results.details if present
      const validationMap = new Map()
      if (data.validation_results?.details) {
        data.validation_results.details.forEach(detail => {
          validationMap.set(detail.req_id, detail)
        })
      }

      if (Array.isArray(reqs) && reqs.length > 0) {
        // Normalize requirements format - merge with validation_results if separate
        const normalizedReqs = reqs.map((r, idx) => {
          // Get validation data from either the requirement itself or validation_results.details
          const validation = validationMap.get(r.req_id) || {}

          // Handle score: prefer validation_score, then score from validation, then from req
          const validationScore = r.validation_score ?? validation.score ?? r.score ?? undefined

          // Handle passed: prefer validation_passed, then verdict from validation
          const validationPassed = r.validation_passed ?? (validation.verdict === 'pass') ?? (r.verdict === 'pass') ?? false

          // Get evaluation from validation or requirement
          const rawEvaluation = validation.evaluation || r.evaluation || []

          // Normalize evaluation array: map passed→isValid, feedback→reason
          const normalizedEvaluation = rawEvaluation.map(e => ({
            criterion: e.criterion,
            isValid: e.isValid ?? e.passed ?? false,  // Support both formats
            reason: e.reason || e.feedback || '',      // Support both formats
            score: e.score
          }))

          return {
            req_id: r.req_id || r.requirement_id || `REQ-${idx + 1}`,
            title: r.title || r.current_text || r.original_text || r.text || '',
            tag: r.tag || r.metadata?.tag || 'imported',
            evidence_refs: r.evidence_refs || [],
            validation_score: validationScore,
            validation_passed: validationPassed,
            evaluation: normalizedEvaluation
          }
        })

        // Count validated vs not validated
        const validatedCount = normalizedReqs.filter(r => r.validation_score !== undefined).length
        setRequirements(normalizedReqs)
        addLog(`✅ Loaded ${normalizedReqs.length} requirements from ${file.name} (${validatedCount} validated)`)
        setStatus({ message: `${normalizedReqs.length} Requirements loaded (${validatedCount} validated)`, type: 'ok' })
        setActiveTab('requirements')
      }
    } catch (err) {
      console.error('[AppV2] JSON load failed:', err)
      setStatus({ message: 'JSON load failed', type: 'err' })
      addLog(`❌ JSON load failed: ${err.message}`)
    }
    e.target.value = ''
  }

  return (
    <div className="app-v2">
      <header className="header-v2">
        <h1>🚀 arch_team - Requirements Mining Platform</h1>
        <p className="subtitle">Multi-Agent Requirements Extraction & Knowledge Graph Generation</p>

        {/* Data Loading Buttons */}
        <div style={{ marginTop: '10px', display: 'flex', gap: '10px', alignItems: 'center' }}>
          <input
            type="file"
            id="loadReqsInputV2"
            onChange={handleJsonFileLoad}
            accept=".json"
            style={{ display: 'none' }}
          />
          <label
            htmlFor="loadReqsInputV2"
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: '1px solid #3b82f6',
              background: '#1e293b',
              color: '#3b82f6',
              cursor: 'pointer',
              fontWeight: '500',
              fontSize: '13px'
            }}
          >
            📁 JSON File
          </label>
          <button
            onClick={() => handleLoadData('db')}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: '1px solid #10b981',
              background: '#1e293b',
              color: '#10b981',
              cursor: 'pointer',
              fontWeight: '500',
              fontSize: '13px'
            }}
          >
            🗄️ From DB
          </button>
          <button
            onClick={() => handleLoadData('kg')}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: '1px solid #8b5cf6',
              background: '#1e293b',
              color: '#8b5cf6',
              cursor: 'pointer',
              fontWeight: '500',
              fontSize: '13px'
            }}
          >
            🔗 From KG
          </button>

          {requirements.length > 0 && (
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>
              {requirements.length} Requirements loaded
            </span>
          )}
        </div>
      </header>

      <AgentStatus agents={agents} />

      <TabNavigation activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="tab-content">
        {/* Tab 1: Mining */}
        {activeTab === 'mining' && (
          <div className="tab-panel mining-panel">
            <div className="mining-grid">
              {/* Shuttle Component - Arch Platform Interface */}
              <div className="shuttle-section" style={{
                position: 'absolute',
                top: '20px',
                right: '20px',
                zIndex: 100
              }}>
                <Shuttle
                  backendUrl={API_BASE}
                  onRequirementsReady={(reqs) => {
                    setRequirements(reqs)
                    addLog(`Shuttle: ${reqs.length} Requirements empfangen`)
                    setActiveTab('requirements')
                  }}
                  onKgDataReady={(kg) => {
                    setKgData(kg)
                    addLog(`Shuttle: KG mit ${kg.nodes?.length || 0} Nodes empfangen`)
                  }}
                  onProcessingStart={() => {
                    setIsLoading(true)
                    updateAgentStatus('chunk-miner', 'running', 'Processing...')
                  }}
                  onProcessingEnd={() => {
                    setIsLoading(false)
                    updateAgentStatus('chunk-miner', 'done', 'Complete')
                  }}
                  onError={(err) => {
                    setStatus({ message: `Error: ${err.message}`, type: 'err' })
                    addLog(`Shuttle Error: ${err.message}`, 'error')
                  }}
                />
              </div>

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
              onEnhanceRequirement={handleEnhanceRequirement}
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
              onValidationComplete={handleInlineValidationComplete}
              onEnhanceRequirement={handleEnhanceRequirement}
              batchValidationState={batchValidationState}
              setBatchValidationState={setBatchValidationState}
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
                  onEnhanceRequirement={handleEnhanceRequirement}
                />
              </div>
              <div className="kg-right-panel">
                <KnowledgeGraph data={kgData} requirements={requirements} />
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: TechStack */}
        {activeTab === 'techstack' && (
          <div className="tab-panel techstack-panel">
            <TechStackTab
              requirements={requirements}
              onTemplateSelect={(template, result) => {
                addLog(`🛠️ Template selected: ${template.name}`)
                if (result?.success) {
                  addLog(`✅ Project created: ${result.path}`)
                }
              }}
            />
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

      {showAutoValidateToast && (
        <ToastNotification
          message={`${pendingAutoValidation?.length || 0} requirements failed validation. Start auto-validation?`}
          countdown={10}
          onComplete={handleAutoValidateConfirm}
          onCancel={handleAutoValidateCancel}
        />
      )}

      {/* Enhancement Modal */}
      {enhancingRequirement && (
        <EnhancementModal
          requirement={enhancingRequirement}
          onClose={() => setEnhancingRequirement(null)}
          onEnhancementComplete={handleEnhancementComplete}
        />
      )}

      {/* Project Selector Modal */}
      <ProjectSelectorModal
        isOpen={showProjectSelector}
        onClose={() => setShowProjectSelector(false)}
        onSelect={handleProjectSelect}
      />
    </div>
  )
}

export default AppV2
