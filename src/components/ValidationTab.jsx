import React, { useState, useRef, useEffect } from 'react'
import './ValidationTab.css'
import ValidationRequirementCard from './ValidationRequirementCard'
import ValidationDetailPanel from './ValidationDetailPanel'

const ValidationTab = ({
  requirements,
  onRequirementClick,
  onValidateAll,
  onValidationComplete
}) => {
  const [selectedReqId, setSelectedReqId] = useState(null)
  const [validatingReqId, setValidatingReqId] = useState(null)

  // Batch validation state
  const [isBatchValidating, setIsBatchValidating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 })
  const [batchEventLog, setBatchEventLog] = useState([])
  const [batchResults, setBatchResults] = useState([]) // { req_id, passed, score, final_text }
  const [batchStatus, setBatchStatus] = useState('idle') // idle, running, paused, completed
  const [currentBatchReqId, setCurrentBatchReqId] = useState(null)

  const batchSessionIdRef = useRef(null)
  const batchEventSourceRef = useRef(null)
  const batchQueueRef = useRef([])
  const batchIndexRef = useRef(0)
  const eventLogRef = useRef(null)

  // Get score for a requirement - check batch results first, then original
  const getUpdatedScore = (reqId) => {
    const batchResult = batchResults.find(r => r.req_id === reqId)
    if (batchResult) {
      return batchResult.score
    }
    const req = requirements.find(r => r.req_id === reqId)
    return req?.validation_score
  }

  // Get updated requirement with merged batch result
  const getMergedRequirement = (req) => {
    const batchResult = batchResults.find(r => r.req_id === req.req_id)
    if (batchResult) {
      return {
        ...req,
        validation_score: batchResult.score,
        validation_passed: batchResult.passed,
        title: batchResult.final_text || req.title
      }
    }
    return req
  }

  // Filter failing requirements - considering batch results
  const failingRequirements = requirements.filter(req => {
    const score = getUpdatedScore(req.req_id)
    return score !== undefined && score < 0.7
  })

  // Requirements that were failing but now pass after batch validation
  const newlyPassingRequirements = batchResults.filter(r => r.passed && r.score >= 0.7)

  const passingRequirements = requirements.filter(req => {
    const score = getUpdatedScore(req.req_id)
    return score !== undefined && score >= 0.7
  })

  // Get selected requirement - also check passing requirements
  const selectedRequirement = requirements.find(r => r.req_id === selectedReqId) || null

  // Get batch validation status for a requirement
  const getBatchStatus = (reqId) => {
    if (currentBatchReqId === reqId) return 'validating'
    const result = batchResults.find(r => r.req_id === reqId)
    if (result) return result.passed ? 'passed' : 'failed'
    return 'pending'
  }

  const handleCardClick = (reqId) => {
    setSelectedReqId(reqId)
  }

  const handleValidationStart = (reqId) => {
    setValidatingReqId(reqId)
  }

  const handleInlineValidationComplete = (reqId, result) => {
    setValidatingReqId(null)
    // Bubble up to parent for state update and KG rebuild
    if (onValidationComplete) {
      onValidationComplete(reqId, result)
    }
  }

  // Auto-scroll event log
  useEffect(() => {
    if (eventLogRef.current) {
      eventLogRef.current.scrollTop = eventLogRef.current.scrollHeight
    }
  }, [batchEventLog])

  // Batch validation functions
  const addBatchEvent = (type, message) => {
    const timestamp = new Date().toLocaleTimeString()
    setBatchEventLog(prev => [...prev, { timestamp, type, message }])
  }

  const connectBatchSSE = (sessionId) => {
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`)
    batchEventSourceRef.current = eventSource

    eventSource.addEventListener('requirement_updated', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('update', `Fixed ${data.criterion}: ${(data.score_before * 100).toFixed(0)}% -> ${(data.score_after * 100).toFixed(0)}%`)
    })

    eventSource.addEventListener('requirement_split', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('split', `Split into ${data.child_count || data.new_requirement_ids?.length || 0} atomic requirements`)
    })

    eventSource.addEventListener('validation_complete', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('complete', `${data.requirement_id}: ${(data.final_score * 100).toFixed(0)}% ${data.passed ? 'PASS' : 'FAIL'}`)
    })

    eventSource.addEventListener('validation_error', (e) => {
      const data = JSON.parse(e.data)
      addBatchEvent('error', data.error || data.message)
    })

    eventSource.onerror = () => {
      // Silent reconnect handled by browser
    }

    return eventSource
  }

  const validateNextInBatch = async () => {
    if (batchIndexRef.current >= batchQueueRef.current.length) {
      // Batch complete
      setBatchStatus('completed')
      setCurrentBatchReqId(null)
      setIsBatchValidating(false)
      addBatchEvent('success', `Batch complete: ${batchResults.filter(r => r.passed).length} passed, ${batchResults.filter(r => !r.passed).length} failed`)

      // Close SSE
      if (batchEventSourceRef.current) {
        batchEventSourceRef.current.close()
        batchEventSourceRef.current = null
      }
      return
    }

    const req = batchQueueRef.current[batchIndexRef.current]
    setCurrentBatchReqId(req.req_id)
    setBatchProgress({ current: batchIndexRef.current + 1, total: batchQueueRef.current.length })
    addBatchEvent('start', `Validating ${req.req_id}: ${(req.title || req.text || '').substring(0, 40)}...`)

    try {
      const response = await fetch('/api/v1/validate/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement_id: req.req_id,
          requirement_text: req.title || req.text || '',
          session_id: batchSessionIdRef.current,
          threshold: 0.7,
          max_iterations: 3
        })
      })

      const data = await response.json()
      console.log('[ValidationTab] API response for', req.req_id, ':', data)

      // Extract score - handle various response formats
      const finalScore = data.final_score ?? data.score ?? 0
      const passed = data.passed ?? (finalScore >= 0.7)
      const finalText = data.final_text || data.corrected_text || req.title || req.text || ''

      console.log('[ValidationTab] Parsed:', { finalScore, passed, finalText: finalText.substring(0, 50) })

      // Add result with all data needed for display
      setBatchResults(prev => [...prev, {
        req_id: req.req_id,
        passed,
        score: finalScore,
        final_text: finalText,
        total_fixes: data.total_fixes || 0
      }])

      // Notify parent to update global state
      if (onValidationComplete) {
        onValidationComplete(req.req_id, {
          ...data,
          final_score: finalScore,
          passed,
          final_text: finalText
        })
      }

      // Move to next
      batchIndexRef.current += 1
      setTimeout(() => validateNextInBatch(), 500) // Small delay between validations

    } catch (err) {
      console.error('[ValidationTab] Validation error for', req.req_id, ':', err)
      addBatchEvent('error', `${req.req_id}: ${err.message}`)
      setBatchResults(prev => [...prev, { req_id: req.req_id, passed: false, score: 0, final_text: req.title || req.text || '' }])

      // Continue to next
      batchIndexRef.current += 1
      setTimeout(() => validateNextInBatch(), 1000)
    }
  }

  const startBatchValidation = () => {
    if (failingRequirements.length === 0) return

    // Reset state
    setIsBatchValidating(true)
    setBatchStatus('running')
    setBatchEventLog([])
    setBatchResults([])
    setBatchProgress({ current: 0, total: failingRequirements.length })
    setSelectedReqId(null) // Clear selection to show batch panel

    // Setup refs
    batchQueueRef.current = [...failingRequirements]
    batchIndexRef.current = 0
    batchSessionIdRef.current = `batch-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    addBatchEvent('info', `Starting batch validation of ${failingRequirements.length} requirements`)

    // Connect SSE
    connectBatchSSE(batchSessionIdRef.current)

    // Start first validation
    validateNextInBatch()
  }

  const cancelBatchValidation = () => {
    setBatchStatus('completed')
    setIsBatchValidating(false)
    setCurrentBatchReqId(null)
    addBatchEvent('info', 'Batch validation cancelled')

    if (batchEventSourceRef.current) {
      batchEventSourceRef.current.close()
      batchEventSourceRef.current = null
    }
  }

  // Calculate batch stats
  const batchPassedCount = batchResults.filter(r => r.passed).length
  const batchFailedCount = batchResults.filter(r => !r.passed).length
  const batchProgressPercent = batchProgress.total > 0
    ? Math.round((batchProgress.current / batchProgress.total) * 100)
    : 0

  return (
    <div className="validation-tab-container">
      {/* Stats Bar */}
      <div className="validation-stats-bar">
        <div className="stats-summary">
          <div className="stat-item">
            <span className="stat-label">Total:</span>
            <span className="stat-value">{requirements.length}</span>
          </div>
          <div className="stat-item pass">
            <span className="stat-label">Passing:</span>
            <span className="stat-value">{passingRequirements.length}</span>
          </div>
          <div className="stat-item fail">
            <span className="stat-label">Failing:</span>
            <span className="stat-value">{failingRequirements.length}</span>
          </div>
        </div>

        {failingRequirements.length > 0 && !isBatchValidating && (
          <button
            className="btn-validate-all"
            onClick={startBatchValidation}
          >
            Validate All Failing ({failingRequirements.length})
          </button>
        )}

        {isBatchValidating && (
          <button
            className="btn-cancel-batch"
            onClick={cancelBatchValidation}
          >
            Cancel Batch
          </button>
        )}
      </div>

      {/* Split Layout */}
      <div className="validation-split-layout">
        {/* Left: Requirements List */}
        <div className="requirements-list-panel">
          <h3 className="panel-title">
            {isBatchValidating ? 'Batch Progress' : `Failing Requirements (${failingRequirements.length})`}
          </h3>

          <div className="requirements-scroll">
            {/* Show newly passing requirements during/after batch */}
            {newlyPassingRequirements.length > 0 && (isBatchValidating || batchStatus === 'completed') && (
              <div className="newly-passing-section">
                <h4 className="section-title passing">✓ Newly Passing ({newlyPassingRequirements.length})</h4>
                {newlyPassingRequirements.map(result => {
                  const req = requirements.find(r => r.req_id === result.req_id)
                  if (!req) return null
                  return (
                    <ValidationRequirementCard
                      key={result.req_id}
                      requirement={getMergedRequirement(req)}
                      isSelected={result.req_id === selectedReqId}
                      onClick={() => handleCardClick(result.req_id)}
                      batchStatus="passed"
                    />
                  )
                })}
              </div>
            )}

            {/* Still failing requirements */}
            {failingRequirements.length === 0 && newlyPassingRequirements.length === 0 ? (
              <div className="no-failing-state">
                <div className="success-icon">✓</div>
                <h4>All Requirements Pass!</h4>
                <p>Great job! All {requirements.length} requirements meet the quality criteria.</p>
              </div>
            ) : failingRequirements.length === 0 && newlyPassingRequirements.length > 0 ? (
              <div className="all-fixed-state">
                <div className="success-icon">🎉</div>
                <h4>All Fixed!</h4>
                <p>All {newlyPassingRequirements.length} requirements now pass validation.</p>
              </div>
            ) : (
              <>
                {(isBatchValidating || batchStatus === 'completed') && newlyPassingRequirements.length > 0 && (
                  <h4 className="section-title failing">✗ Still Failing ({failingRequirements.length})</h4>
                )}
                {failingRequirements.map(req => (
                  <ValidationRequirementCard
                    key={req.req_id}
                    requirement={getMergedRequirement(req)}
                    isSelected={req.req_id === selectedReqId}
                    onClick={() => handleCardClick(req.req_id)}
                    batchStatus={isBatchValidating ? getBatchStatus(req.req_id) : null}
                  />
                ))}
              </>
            )}
          </div>
        </div>

        {/* Right: Detail Panel or Batch Progress */}
        <div className="detail-panel-container">
          {isBatchValidating || batchStatus === 'completed' ? (
            // Inline Batch Validation Panel
            <div className="batch-validation-panel">
              <div className="batch-header">
                <h3>Batch Validation</h3>
                <span className={`batch-status ${batchStatus}`}>
                  {batchStatus === 'running' ? 'Running...' : batchStatus === 'completed' ? 'Completed' : batchStatus}
                </span>
              </div>

              {/* Progress Section */}
              <div className="batch-progress-section">
                <div className="progress-info">
                  <span className="progress-text">
                    Progress: {batchProgress.current}/{batchProgress.total}
                  </span>
                  <span className="progress-percent">{batchProgressPercent}%</span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${batchProgressPercent}%` }}
                  />
                </div>

                {/* Stats Row */}
                <div className="batch-stats-row">
                  <span className="batch-stat pass">Passed: {batchPassedCount}</span>
                  <span className="batch-stat fail">Failed: {batchFailedCount}</span>
                  <span className="batch-stat pending">
                    Pending: {batchProgress.total - batchProgress.current}
                  </span>
                </div>
              </div>

              {/* Event Log */}
              <div className="batch-event-section">
                <h4>Event Log</h4>
                <div className="batch-event-log" ref={eventLogRef}>
                  {batchEventLog.map((event, idx) => (
                    <div key={idx} className={`batch-event-item event-${event.type}`}>
                      <span className="event-time">[{event.timestamp}]</span>
                      <span className="event-msg">{event.message}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              {batchStatus === 'completed' && (
                <div className="batch-actions">
                  <button
                    className="btn-clear-batch"
                    onClick={() => {
                      setBatchStatus('idle')
                      setBatchEventLog([])
                      setBatchResults([])
                    }}
                  >
                    Clear Results
                  </button>
                </div>
              )}
            </div>
          ) : (
            // Normal Detail Panel
            <ValidationDetailPanel
              requirement={selectedRequirement}
              onValidationComplete={handleInlineValidationComplete}
              onValidationStart={handleValidationStart}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default ValidationTab
