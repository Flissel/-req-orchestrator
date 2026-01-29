import { useState, useEffect, useRef } from 'react'
import RequirementDiffView from './RequirementDiffView'

/**
 * BatchValidationModal - Validates multiple requirements with SSE streaming
 *
 * Features:
 * - SSE stream for real-time batch validation progress
 * - Live progress: "Validating 3/15... (REQ-003)"
 * - Shows diffs for each fixed requirement
 * - Pausable/cancellable (via session_id)
 * - Auto-refresh requirements list after completion
 */
export default function BatchValidationModal({
  requirements,
  onClose,
  onBatchComplete
}) {
  const [progress, setProgress] = useState({ current: 0, total: requirements.length })
  const [currentRequirement, setCurrentRequirement] = useState(null)
  const [eventLog, setEventLog] = useState([])
  const [diffs, setDiffs] = useState([]) // Array of { req_id, criterion, old, new, score_before, score_after }
  const [results, setResults] = useState([]) // Array of { req_id, passed, score, fixes, split }
  const [status, setStatus] = useState('starting') // starting, running, paused, completed, error
  const [error, setError] = useState(null)
  const [isPaused, setIsPaused] = useState(false)

  const sessionIdRef = useRef(`batch-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`)
  const sessionId = sessionIdRef.current
  const eventSourceRef = useRef(null)
  const currentIndexRef = useRef(0)
  const abortControllerRef = useRef(null)
  const isCancelledRef = useRef(false)

  const addEvent = (type, message) => {
    const timestamp = new Date().toLocaleTimeString()
    setEventLog(prev => [...prev, { timestamp, type, message }])
  }

  const addDiff = (diffData) => {
    setDiffs(prev => [...prev, diffData])
  }

  const addResult = (resultData) => {
    setResults(prev => [...prev, resultData])
  }

  // Connect to SSE stream
  const connectSSE = (sessionId) => {
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`)

    eventSource.addEventListener('requirement_updated', (e) => {
      if (isCancelledRef.current) return
      const data = JSON.parse(e.data)
      addEvent('update', `Fixed ${data.criterion}: ${data.score_before.toFixed(2)} → ${data.score_after.toFixed(2)}`)
      addDiff({
        req_id: data.requirement_id,
        criterion: data.criterion,
        old: data.old_text,
        new: data.new_text,
        score_before: data.score_before,
        score_after: data.score_after
      })
    })

    eventSource.addEventListener('requirement_split', (e) => {
      if (isCancelledRef.current) return
      const data = JSON.parse(e.data)
      const newIds = data.new_requirement_ids || []
      addEvent('split', `Split into ${newIds.length} requirements: ${newIds.join(', ')}`)
    })

    eventSource.addEventListener('validation_complete', (e) => {
      if (isCancelledRef.current) return
      const data = JSON.parse(e.data)
      addEvent('complete', `Completed ${data.requirement_id}: Score ${(data.final_score * 100).toFixed(0)}% (${data.passed ? 'PASS' : 'FAIL'})`)
      addResult({
        req_id: data.requirement_id,
        passed: data.passed,
        score: data.final_score,
        fixes: data.total_fixes,
        split: data.split_occurred,
        final_text: data.final_text  // Include final merged requirement text
      })

      // Move to next requirement
      currentIndexRef.current += 1
      setProgress({ current: currentIndexRef.current, total: requirements.length })

      if (currentIndexRef.current < requirements.length && !isCancelledRef.current) {
        validateNext()
      }
    })

    eventSource.addEventListener('validation_error', (e) => {
      if (isCancelledRef.current) return
      const data = JSON.parse(e.data)
      addEvent('error', `Error: ${data.message}`)
      setError(data.message)
      setStatus('error')
    })

    eventSource.addEventListener('agent_message', (e) => {
      if (isCancelledRef.current) return
      const data = JSON.parse(e.data)
      addEvent('agent', `${data.agent}: ${data.message}`)
    })

    eventSource.onerror = (err) => {
      if (isCancelledRef.current) return
      console.error('[BatchValidationModal] SSE error:', err)
      addEvent('error', 'Connection lost, retrying...')
    }

    eventSourceRef.current = eventSource
    return eventSource
  }

  // Validate next requirement in queue
  const validateNext = async () => {
    // Check if cancelled before proceeding
    if (isCancelledRef.current) {
      return
    }

    if (isPaused) {
      addEvent('info', 'Validation paused')
      return
    }

    if (currentIndexRef.current >= requirements.length) {
      setStatus('completed')
      addEvent('info', `Batch validation completed: ${results.filter(r => r.passed).length}/${requirements.length} passed`)

      // Notify parent to refresh requirements list
      if (onBatchComplete) {
        onBatchComplete(results)
      }
      return
    }

    const req = requirements[currentIndexRef.current]
    setCurrentRequirement(req)
    addEvent('start', `Validating ${req.req_id}: ${req.title?.substring(0, 50) || 'No title'}...`)

    try {
      // Create new AbortController for this request
      abortControllerRef.current = new AbortController()

      const response = await fetch('/api/v1/validate/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement_id: req.req_id,
          requirement_text: req.title || req.description || '',
          session_id: sessionId,
          threshold: 0.7,
          max_iterations: 3
        }),
        signal: abortControllerRef.current.signal
      })

      // Check if cancelled after fetch completes
      if (isCancelledRef.current) {
        return
      }

      const result = await response.json()

      if (!response.ok || !result.success) {
        throw new Error(result.message || 'Validation failed')
      }

      // SSE events will handle the rest (updates, completion)
      setStatus('running')
    } catch (error) {
      // Don't log abort errors as failures
      if (error.name === 'AbortError') {
        addEvent('info', 'Validation request cancelled')
        return
      }

      addEvent('error', `Failed to start validation for ${req.req_id}: ${error.message}`)
      setError(error.message)

      // Check if cancelled before continuing
      if (isCancelledRef.current) {
        return
      }

      // Skip to next requirement
      currentIndexRef.current += 1
      setProgress({ current: currentIndexRef.current, total: requirements.length })

      if (currentIndexRef.current < requirements.length) {
        setTimeout(() => validateNext(), 1000) // Retry after 1 second
      } else {
        setStatus('completed')
      }
    }
  }

  // Start batch validation on mount
  useEffect(() => {
    console.log('[BatchValidationModal] Starting batch validation for', requirements.length, 'requirements')
    connectSSE(sessionId)
    validateNext()

    return () => {
      // Mark as cancelled to stop any ongoing operations
      isCancelledRef.current = true

      // Abort any in-flight fetch
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }

      // Close SSE connection
      if (eventSourceRef.current) {
        console.log('[BatchValidationModal] Closing SSE connection')
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [])

  const handlePause = () => {
    setIsPaused(!isPaused)
    addEvent('info', isPaused ? 'Resuming validation...' : 'Pausing validation...')

    if (isPaused) {
      validateNext() // Resume
    }
  }

  const handleCancel = () => {
    // Set cancelled flag first to stop any ongoing loops
    isCancelledRef.current = true

    // Abort any in-flight fetch request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }

    // Close SSE connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    addEvent('info', 'Batch validation cancelled by user')
    setStatus('completed')
    onClose()
  }

  const getStatusColor = () => {
    switch (status) {
      case 'running': return '#4caf50'
      case 'paused': return '#ff9800'
      case 'completed': return '#2196f3'
      case 'error': return '#f44336'
      default: return '#9e9e9e'
    }
  }

  const getStatusText = () => {
    switch (status) {
      case 'starting': return 'Starting batch validation...'
      case 'running': return `Validating ${progress.current + 1}/${progress.total}...`
      case 'paused': return `Paused at ${progress.current}/${progress.total}`
      case 'completed': return 'Batch validation completed'
      case 'error': return 'Error occurred'
      default: return 'Unknown status'
    }
  }

  const passedCount = results.filter(r => r.passed).length
  const failedCount = results.filter(r => !r.passed).length
  const splitCount = results.filter(r => r.split).length
  const progressPercent = (progress.current / progress.total) * 100

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '12px',
        maxWidth: '900px',
        width: '100%',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
      }}>
        {/* Header */}
        <div style={{
          padding: '24px',
          borderBottom: '2px solid #e0e0e0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h2 style={{ margin: '0 0 8px 0', fontSize: '24px', fontWeight: '600' }}>
              🔧 Batch Validation
            </h2>
            <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>
              {getStatusText()}
            </p>
          </div>
          <button
            onClick={handleCancel}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: '28px',
              cursor: 'pointer',
              color: '#999',
              padding: '4px 8px'
            }}
          >
            ×
          </button>
        </div>

        {/* Progress Bar */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #e0e0e0' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '12px'
          }}>
            <div style={{ fontSize: '14px', fontWeight: '600', color: '#333' }}>
              Progress: {progress.current}/{progress.total}
            </div>
            <div style={{ fontSize: '13px', color: '#666' }}>
              {progressPercent.toFixed(0)}%
            </div>
          </div>

          {/* Progress bar */}
          <div style={{
            width: '100%',
            height: '8px',
            background: '#e0e0e0',
            borderRadius: '4px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${progressPercent}%`,
              height: '100%',
              background: getStatusColor(),
              transition: 'width 0.3s ease'
            }} />
          </div>

          {/* Stats */}
          {results.length > 0 && (
            <div style={{
              display: 'flex',
              gap: '16px',
              marginTop: '12px',
              fontSize: '13px'
            }}>
              <span style={{ color: '#4caf50', fontWeight: '600' }}>
                ✓ Passed: {passedCount}
              </span>
              <span style={{ color: '#f44336', fontWeight: '600' }}>
                ✗ Failed: {failedCount}
              </span>
              {splitCount > 0 && (
                <span style={{ color: '#ff9800', fontWeight: '600' }}>
                  ⚡ Split: {splitCount}
                </span>
              )}
            </div>
          )}

          {/* Current requirement */}
          {currentRequirement && status === 'running' && (
            <div style={{
              marginTop: '12px',
              padding: '12px',
              background: '#f5f5f5',
              borderRadius: '6px',
              fontSize: '13px'
            }}>
              <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                Currently validating:
              </div>
              <div style={{ color: '#666' }}>
                {currentRequirement.req_id} - {currentRequirement.title?.substring(0, 80) || 'No title'}...
              </div>
            </div>
          )}
        </div>

        {/* Event Log & Diffs */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px 24px'
        }}>
          {/* Event Log */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>
              📋 Event Log
            </h3>
            <div style={{
              maxHeight: '200px',
              overflowY: 'auto',
              background: '#f9f9f9',
              borderRadius: '6px',
              padding: '12px',
              fontSize: '12px',
              fontFamily: 'monospace'
            }}>
              {eventLog.length === 0 ? (
                <div style={{ color: '#999' }}>Waiting for events...</div>
              ) : (
                eventLog.map((log, idx) => (
                  <div
                    key={idx}
                    style={{
                      marginBottom: '4px',
                      color: log.type === 'error' ? '#f44336' :
                             log.type === 'complete' ? '#4caf50' :
                             log.type === 'split' ? '#ff9800' :
                             log.type === 'agent' ? '#2196f3' :
                             '#333'
                    }}
                  >
                    <span style={{ color: '#999' }}>[{log.timestamp}]</span> {log.message}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Diffs */}
          {diffs.length > 0 && (
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>
                🔄 Applied Fixes ({diffs.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {diffs.map((diff, idx) => (
                  <div
                    key={idx}
                    style={{
                      border: '1px solid #e0e0e0',
                      borderRadius: '6px',
                      overflow: 'hidden'
                    }}
                  >
                    <div style={{
                      background: '#f5f5f5',
                      padding: '8px 12px',
                      fontSize: '13px',
                      fontWeight: '600',
                      borderBottom: '1px solid #e0e0e0'
                    }}>
                      {diff.req_id} - {diff.criterion}
                      <span style={{
                        marginLeft: '12px',
                        fontSize: '12px',
                        color: diff.score_after > diff.score_before ? '#4caf50' : '#f44336'
                      }}>
                        {(diff.score_before * 100).toFixed(0)}% → {(diff.score_after * 100).toFixed(0)}%
                        {diff.score_after > diff.score_before && ' ✓'}
                      </span>
                    </div>
                    <RequirementDiffView
                      oldText={diff.old}
                      newText={diff.new}
                      criterion={diff.criterion}
                      scoreBefore={diff.score_before}
                      scoreAfter={diff.score_after}
                      compact={false}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div style={{
              marginTop: '16px',
              padding: '12px',
              background: '#ffebee',
              border: '1px solid #f44336',
              borderRadius: '6px',
              color: '#c62828',
              fontSize: '13px'
            }}>
              <strong>Error:</strong> {error}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div style={{
          padding: '16px 24px',
          borderTop: '2px solid #e0e0e0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ fontSize: '13px', color: '#666' }}>
            {status === 'completed' && (
              <span>
                Validation complete: <strong>{passedCount}</strong> passed, <strong>{failedCount}</strong> failed
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            {status === 'running' && (
              <button
                onClick={handlePause}
                style={{
                  padding: '10px 20px',
                  background: isPaused ? '#4caf50' : '#ff9800',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
              >
                {isPaused ? '▶ Resume' : '⏸ Pause'}
              </button>
            )}

            <button
              onClick={handleCancel}
              style={{
                padding: '10px 20px',
                background: status === 'completed' ? '#2196f3' : '#f44336',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer'
              }}
            >
              {status === 'completed' ? 'Close' : 'Cancel'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
