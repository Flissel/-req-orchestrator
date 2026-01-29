import { useState, useRef, useCallback } from 'react'
import './Shuttle.css'

// Pipeline phases
const PHASES = [
  { id: 'mining', label: 'Mining', icon: '⛏️' },
  { id: 'kg', label: 'KG Build', icon: '🕸️' },
  { id: 'validation', label: 'Validation', icon: '✓' },
  { id: 'rewrite', label: 'Rewrite', icon: '✏️' }
]

// Generate unique ID
const generateId = () => `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

/**
 * Shuttle Component - Multi-File Async Processing
 *
 * Features:
 * - Multiple file upload (Drag & Drop)
 * - Async queue processing (file by file)
 * - Each file produces its own profile/graph
 * - 4-phase pipeline per file
 */
export default function Shuttle({
  onFileComplete,      // (fileName, result) => {} - Called per file
  onQueueComplete,     // (allResults) => {} - Called when queue done
  onRequirementsReady, // Legacy: all requirements
  onKgDataReady,       // Legacy: all KG data
  onValidationReady,
  onProcessingStart,
  onProcessingEnd,
  onError,
  backendUrl = ''
}) {
  // File Queue: [{id, file, fileName, status, phases, result}]
  const [fileQueue, setFileQueue] = useState([])
  const [isDragging, setIsDragging] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [currentFileId, setCurrentFileId] = useState(null)
  const [provider] = useState('openrouter')
  const [model] = useState('google/gemini-2.5-flash:nitro')
  const fileInputRef = useRef(null)

  // Update queue item
  const updateQueueItem = (id, updates) => {
    setFileQueue(prev => prev.map(item =>
      item.id === id ? { ...item, ...updates } : item
    ))
  }

  // Update phase for specific file
  const updateFilePhase = (fileId, phaseId, status) => {
    setFileQueue(prev => prev.map(item => {
      if (item.id !== fileId) return item
      return {
        ...item,
        phases: {
          ...item.phases,
          [phaseId]: status
        }
      }
    }))
  }

  // Drag & Drop Handlers
  const handleDragEnter = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const droppedFiles = Array.from(e.dataTransfer.files).filter(file =>
      /\.(md|txt|pdf|docx)$/i.test(file.name)
    )

    if (droppedFiles.length > 0) {
      addFilesToQueue(droppedFiles)
    }
  }, [])

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files)
    addFilesToQueue(selectedFiles)
    e.target.value = '' // Reset input
  }

  const addFilesToQueue = (files) => {
    const newItems = files.map(file => ({
      id: generateId(),
      file,
      fileName: file.name,
      status: 'pending', // pending, processing, done, failed
      phases: {
        mining: 'pending',
        kg: 'pending',
        validation: 'pending',
        rewrite: 'pending'
      },
      result: null
    }))
    setFileQueue(prev => [...prev, ...newItems])
  }

  const handleClick = () => {
    if (!isProcessing) {
      fileInputRef.current?.click()
    }
  }

  // Remove file from queue
  const removeFromQueue = (id) => {
    setFileQueue(prev => prev.filter(item => item.id !== id))
  }

  // Clear completed files
  const clearCompleted = () => {
    setFileQueue(prev => prev.filter(item => item.status !== 'done' && item.status !== 'failed'))
  }

  // Process single file
  const processFile = async (queueItem) => {
    const { id, file, fileName } = queueItem

    setCurrentFileId(id)
    updateQueueItem(id, { status: 'processing' })

    try {
      const formData = new FormData()
      formData.append('files', file)
      formData.append('correlation_id', `shuttle-${id}-${Date.now()}`)
      formData.append('provider', provider)
      formData.append('model', model)
      formData.append('neighbor_refs', '1')
      formData.append('auto_validate', 'true')

      // Phase 1: Mining
      updateFilePhase(id, 'mining', 'running')

      const response = await fetch(`${backendUrl}/api/arch_team/process`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`)
      }

      const data = await response.json()

      if (data.success) {
        // Update phases with visual delays
        updateFilePhase(id, 'mining', 'done')
        updateFilePhase(id, 'kg', 'running')
        await new Promise(r => setTimeout(r, 200))

        updateFilePhase(id, 'kg', 'done')
        updateFilePhase(id, 'validation', 'running')
        await new Promise(r => setTimeout(r, 200))

        updateFilePhase(id, 'validation', 'done')
        updateFilePhase(id, 'rewrite', 'running')
        await new Promise(r => setTimeout(r, 200))

        updateFilePhase(id, 'rewrite', 'done')

        const result = {
          requirements: data.requirements || [],
          kgData: data.kg_data || { nodes: [], edges: [] },
          validation: data.validation_results || {}
        }

        updateQueueItem(id, {
          status: 'done',
          result
        })

        // Callback per file
        onFileComplete?.(fileName, result)

        return result

      } else {
        throw new Error(data.error || 'Processing failed')
      }

    } catch (error) {
      console.error(`[Shuttle] Error processing ${fileName}:`, error)

      // Mark current phase as failed
      const item = fileQueue.find(i => i.id === id)
      if (item) {
        Object.keys(item.phases).forEach(p => {
          if (item.phases[p] === 'running') {
            updateFilePhase(id, p, 'failed')
          }
        })
      }

      updateQueueItem(id, {
        status: 'failed',
        error: error.message
      })

      onError?.(error, fileName)
      return null
    }
  }

  // Process entire queue (file by file)
  const processQueue = async () => {
    if (isProcessing) return

    const pendingFiles = fileQueue.filter(item => item.status === 'pending')
    if (pendingFiles.length === 0) return

    setIsProcessing(true)
    onProcessingStart?.()

    const allResults = []

    for (const item of pendingFiles) {
      const result = await processFile(item)
      if (result) {
        allResults.push({ fileName: item.fileName, ...result })
      }
    }

    setCurrentFileId(null)
    setIsProcessing(false)
    onProcessingEnd?.()

    // Aggregate callbacks
    if (allResults.length > 0) {
      // Legacy callbacks with combined data
      const allRequirements = allResults.flatMap(r => r.requirements)
      const allNodes = allResults.flatMap(r => r.kgData?.nodes || [])
      const allEdges = allResults.flatMap(r => r.kgData?.edges || [])

      onRequirementsReady?.(allRequirements)
      onKgDataReady?.({ nodes: allNodes, edges: allEdges })
      onQueueComplete?.(allResults)
    }
  }

  // View graph for completed file
  const viewGraph = (item) => {
    if (item.result) {
      onFileComplete?.(item.fileName, item.result)
    }
  }

  const pendingCount = fileQueue.filter(i => i.status === 'pending').length
  const doneCount = fileQueue.filter(i => i.status === 'done').length

  return (
    <div className={`shuttle-container ${isProcessing ? 'processing' : ''}`}>
      <div className="shuttle-body">
        {/* Header */}
        <div className="shuttle-header">
          <span className="shuttle-icon">🚀</span>
          <span className="shuttle-title">Arch Platform</span>
          {fileQueue.length > 0 && (
            <span className="queue-badge">{pendingCount}/{fileQueue.length}</span>
          )}
        </div>

        {/* File Queue */}
        {fileQueue.length > 0 && (
          <div className="file-queue">
            {fileQueue.map(item => (
              <div key={item.id} className={`queue-item queue-${item.status}`}>
                <div className="queue-item-info">
                  <span className="queue-status-icon">
                    {item.status === 'pending' && '⏸️'}
                    {item.status === 'processing' && '⏳'}
                    {item.status === 'done' && '✅'}
                    {item.status === 'failed' && '❌'}
                  </span>
                  <span className="queue-filename" title={item.fileName}>
                    {item.fileName.length > 20
                      ? item.fileName.slice(0, 17) + '...'
                      : item.fileName}
                  </span>
                </div>

                {/* Mini phase indicators for processing file */}
                {item.status === 'processing' && (
                  <div className="queue-phases-mini">
                    {PHASES.map(phase => (
                      <span
                        key={phase.id}
                        className={`mini-phase mini-${item.phases[phase.id]}`}
                        title={`${phase.label}: ${item.phases[phase.id]}`}
                      >
                        {item.phases[phase.id] === 'running' ? '◌' :
                         item.phases[phase.id] === 'done' ? '●' : '○'}
                      </span>
                    ))}
                  </div>
                )}

                {/* Actions */}
                <div className="queue-item-actions">
                  {item.status === 'done' && (
                    <button
                      className="btn-view"
                      onClick={() => viewGraph(item)}
                      title="View Graph"
                    >
                      📊
                    </button>
                  )}
                  {(item.status === 'pending' || item.status === 'failed') && (
                    <button
                      className="btn-remove"
                      onClick={() => removeFromQueue(item.id)}
                      title="Remove"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
            ))}

            {doneCount > 0 && (
              <button className="btn-clear-completed" onClick={clearCompleted}>
                Clear completed ({doneCount})
              </button>
            )}
          </div>
        )}

        {/* Drop Zone */}
        <div
          className={`shuttle-dropzone ${isDragging ? 'dragging' : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={handleClick}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.txt,.pdf,.docx"
            multiple
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          <div className="dropzone-content">
            <span className="dropzone-icon">📄</span>
            <span className="dropzone-text">Drop files here</span>
            <span className="dropzone-hint">.md .txt .pdf .docx</span>
          </div>
        </div>

        {/* Launch Button */}
        <div className="shuttle-actions">
          <button
            className={`btn-launch ${isProcessing ? 'processing' : ''}`}
            onClick={processQueue}
            disabled={pendingCount === 0 || isProcessing}
          >
            {isProcessing ? (
              <>
                <span className="spinner">◌</span>
                <span>Processing...</span>
              </>
            ) : (
              <>▶ Launch Queue ({pendingCount})</>
            )}
          </button>
        </div>
      </div>

      {/* Thruster Animation */}
      {isProcessing && (
        <div className="shuttle-thruster">
          <div className="flame flame-1"></div>
          <div className="flame flame-2"></div>
          <div className="flame flame-3"></div>
        </div>
      )}
    </div>
  )
}
