import React, { useState, useEffect, useRef } from 'react'
import './ValidationDetailPanel.css'
import CriteriaGrid from './CriteriaGrid'
import RequirementDiffView from './RequirementDiffView'

const ValidationDetailPanel = ({ requirement, onValidationComplete, onValidationStart }) => {
  const [activeTab, setActiveTab] = useState('overview')

  // Validation state - inline validation process
  const [isValidating, setIsValidating] = useState(false)
  const [validationEvents, setValidationEvents] = useState([])
  const [validationDiffs, setValidationDiffs] = useState([])
  const [validationResult, setValidationResult] = useState(null)
  const [validationError, setValidationError] = useState(null)
  const eventSourceRef = useRef(null)
  const sessionIdRef = useRef(null)

  // Reset validation state when requirement changes
  useEffect(() => {
    setIsValidating(false)
    setValidationEvents([])
    setValidationDiffs([])
    setValidationResult(null)
    setValidationError(null)
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [requirement?.req_id])

  const addEvent = (type, message, data = null) => {
    const timestamp = new Date().toLocaleTimeString()
    setValidationEvents(prev => [...prev, { type, message, timestamp, data }])
  }

  const addDiff = (diffData) => {
    setValidationDiffs(prev => [...prev, diffData])
  }

  const connectSSE = (sessionId) => {
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`)
    eventSourceRef.current = eventSource

    eventSource.addEventListener('connected', (e) => {
      addEvent('info', 'Connected to validation stream')
    })

    eventSource.addEventListener('evaluation_started', (e) => {
      const data = JSON.parse(e.data)
      addEvent('info', `Evaluating: ${data.requirement_id}`)
    })

    eventSource.addEventListener('evaluation_completed', (e) => {
      const data = JSON.parse(e.data)
      const failingCount = Object.values(data.scores || {}).filter(s => s < 0.7).length
      addEvent('info', `Evaluation complete: ${failingCount} criteria need improvement`)
    })

    eventSource.addEventListener('requirement_updated', (e) => {
      const data = JSON.parse(e.data)
      addEvent('update', `Fixed ${data.criterion}: ${data.score_before.toFixed(2)} -> ${data.score_after.toFixed(2)}`)
      addDiff(data)
    })

    eventSource.addEventListener('requirement_split', (e) => {
      const data = JSON.parse(e.data)
      addEvent('split', `Requirement split into ${data.child_count} atomic requirements`)
    })

    eventSource.addEventListener('validation_complete', (e) => {
      const data = JSON.parse(e.data)
      addEvent('success', `Validation complete: Final score ${data.final_score.toFixed(2)}`)
    })

    eventSource.addEventListener('validation_error', (e) => {
      const data = JSON.parse(e.data)
      addEvent('error', `Error: ${data.error}`)
      setValidationError(data.error)
    })

    eventSource.onerror = (err) => {
      console.error('[ValidationDetailPanel] SSE error:', err)
      addEvent('error', 'Connection error occurred')
    }
  }

  const startValidation = async () => {
    if (!requirement) return

    setIsValidating(true)
    setValidationEvents([])
    setValidationDiffs([])
    setValidationError(null)
    setValidationResult(null)
    setActiveTab('validate') // Switch to validation tab

    const sessionId = `val-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    sessionIdRef.current = sessionId
    addEvent('info', 'Starting validation...')

    // Notify parent
    if (onValidationStart) {
      onValidationStart(requirement.req_id)
    }

    // Connect to SSE stream
    connectSSE(sessionId)

    try {
      const response = await fetch('/api/v1/validate/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement_id: requirement.req_id,
          requirement_text: requirement.title || requirement.text,
          session_id: sessionId,
          threshold: 0.7,
          max_iterations: 3
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || data.message || 'Validation failed')
      }

      setValidationResult(data)
      addEvent('success', 'Validation completed successfully')

      // Notify parent component with result
      if (onValidationComplete) {
        onValidationComplete(requirement.req_id, data)
      }

    } catch (err) {
      console.error('[ValidationDetailPanel] Validation error:', err)
      setValidationError(err.message)
      addEvent('error', `Validation failed: ${err.message}`)
    } finally {
      setIsValidating(false)
      // Cleanup SSE connection
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }

  const getEventIcon = (type) => {
    switch (type) {
      case 'info': return 'i'
      case 'update': return '~'
      case 'split': return '/'
      case 'success': return '+'
      case 'error': return 'x'
      default: return '-'
    }
  }

  if (!requirement) {
    return (
      <div className="validation-detail-panel empty">
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>No Requirement Selected</h3>
          <p>Select a requirement from the list to view validation details</p>
        </div>
      </div>
    )
  }

  const score = requirement.validation_score || 0
  const percentage = Math.round(score * 100)
  const passed = requirement.validation_passed || false

  // Count fixes/improvements if available
  const fixCount = requirement.evaluation
    ? requirement.evaluation.filter(e => !e.isValid && !e.passed).length
    : 0

  // Check if there's a diff between original and corrected text
  const originalText = requirement.original_text || requirement.title || requirement.text || ''
  const correctedText = requirement.corrected_text || requirement.improved_text || ''
  const hasChanges = correctedText && correctedText !== originalText

  // Check if validation has run (events or result exist)
  const hasValidationRun = validationEvents.length > 0 || validationResult !== null

  return (
    <div className="validation-detail-panel">
      {/* Header */}
      <div className="detail-header">
        <div className="header-left">
          <h3 className="req-id">{requirement.req_id}</h3>
          <span className={`status-badge ${passed ? 'pass' : 'fail'}`}>
            {passed ? '+ PASSED' : 'x FAILED'}
          </span>
        </div>
        <div className="header-right">
          <div className="score-display">
            <span className="score-label">Score:</span>
            <span className={`score-value ${passed ? 'pass' : 'fail'}`}>
              {percentage}%
            </span>
          </div>
          {/* Inline Validate Button */}
          <button
            className={`btn-validate-inline ${isValidating ? 'validating' : ''}`}
            onClick={startValidation}
            disabled={isValidating}
          >
            {isValidating ? 'Validating...' : 'Validate'}
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="detail-tabs">
        <button
          className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`tab-btn ${activeTab === 'criteria' ? 'active' : ''}`}
          onClick={() => setActiveTab('criteria')}
        >
          Criteria ({fixCount} failing)
        </button>
        {(hasChanges || hasValidationRun) && (
          <button
            className={`tab-btn ${activeTab === 'changes' ? 'active' : ''}`}
            onClick={() => setActiveTab('changes')}
          >
            Changes
          </button>
        )}
        {hasValidationRun && (
          <button
            className={`tab-btn ${activeTab === 'validate' ? 'active' : ''} ${isValidating ? 'validating' : ''}`}
            onClick={() => setActiveTab('validate')}
          >
            {isValidating ? 'Validating...' : 'Validation'}
          </button>
        )}
      </div>

      {/* Tab Content */}
      <div className="detail-content">
        {activeTab === 'overview' && (
          <div className="overview-tab">
            <div className="section">
              <h4>Requirement Text</h4>
              <div className="text-display original">
                {requirement.title || requirement.text || 'No text available'}
              </div>
            </div>

            <div className="section">
              <h4>Quick Stats</h4>
              <div className="stats-grid">
                <div className="stat-item">
                  <span className="stat-label">Overall Score</span>
                  <span className={`stat-value ${passed ? 'pass' : 'fail'}`}>
                    {percentage}%
                  </span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Status</span>
                  <span className={`stat-value ${passed ? 'pass' : 'fail'}`}>
                    {passed ? 'Passed' : 'Failed'}
                  </span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Failing Criteria</span>
                  <span className="stat-value">
                    {fixCount} / 10
                  </span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Evidence</span>
                  <span className="stat-value">
                    {requirement.evidence_refs?.length || 0} refs
                  </span>
                </div>
              </div>
            </div>

            {requirement.tag && (
              <div className="section">
                <h4>Category</h4>
                <span className="tag-display">{requirement.tag}</span>
              </div>
            )}
          </div>
        )}

        {activeTab === 'criteria' && (
          <div className="criteria-tab">
            <CriteriaGrid requirement={requirement} />
          </div>
        )}

        {activeTab === 'changes' && (hasChanges || validationDiffs.length > 0) && (
          <div className="changes-tab">
            {/* Show validation diffs first if they exist */}
            {validationDiffs.length > 0 && (
              <div className="validation-diffs">
                <h4>Applied Improvements</h4>
                {validationDiffs.map((diff, idx) => (
                  <RequirementDiffView
                    key={idx}
                    oldText={diff.old_text}
                    newText={diff.new_text}
                    criterion={diff.criterion}
                    scoreBefore={diff.score_before}
                    scoreAfter={diff.score_after}
                    suggestion={diff.suggestion}
                    compact={false}
                  />
                ))}
              </div>
            )}

            {/* Show original vs corrected if available */}
            {hasChanges && (
              <RequirementDiffView
                oldText={originalText}
                newText={correctedText}
                criterion="validation"
                scoreBefore={requirement.original_score || 0}
                scoreAfter={score}
                suggestion={requirement.applied_suggestions || ''}
              />
            )}

            {/* Show improvement history if available */}
            {requirement.fix_history && requirement.fix_history.length > 0 && (
              <div className="fix-history">
                <h4>Fix History</h4>
                {requirement.fix_history.map((fix, index) => (
                  <RequirementDiffView
                    key={index}
                    oldText={fix.before}
                    newText={fix.after}
                    criterion={fix.criterion}
                    scoreBefore={fix.score_before}
                    scoreAfter={fix.score_after}
                    suggestion={fix.suggestion}
                    compact={true}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Validation Tab - Inline validation process */}
        {activeTab === 'validate' && (
          <div className="validate-tab">
            {/* Event Log */}
            {validationEvents.length > 0 && (
              <div className="event-log-section">
                <h4>Event Log</h4>
                <div className="event-log">
                  {validationEvents.map((event, idx) => (
                    <div key={idx} className={`event-item event-${event.type}`}>
                      <span className="event-icon">[{getEventIcon(event.type)}]</span>
                      <span className="event-time">{event.timestamp}</span>
                      <span className="event-message">{event.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Validation Result Summary */}
            {validationResult && (
              <div className={`validation-result ${validationResult.passed ? 'pass' : 'fail'}`}>
                <div className="result-header">
                  {validationResult.passed ? '[+] Validation Passed' : '[x] Validation Failed'}
                </div>
                <div className="result-details">
                  <div className="result-item">
                    <span className="result-label">Final Score:</span>
                    <span className="result-value">{(validationResult.final_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Fixes Applied:</span>
                    <span className="result-value">{validationResult.total_fixes || 0}</span>
                  </div>
                  {validationResult.split_occurred && (
                    <div className="result-item">
                      <span className="result-label">Requirement Split:</span>
                      <span className="result-value">Yes (atomicity)</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Error Display */}
            {validationError && (
              <div className="validation-error">
                <div className="error-header">[x] Validation Error</div>
                <div className="error-message">{validationError}</div>
              </div>
            )}

            {/* Loading State */}
            {isValidating && !validationResult && !validationError && (
              <div className="validation-loading">
                <div className="loading-spinner"></div>
                <div className="loading-text">Validating requirement...</div>
              </div>
            )}

            {/* Retry Button */}
            {(validationResult || validationError) && !isValidating && (
              <div className="validation-actions">
                <button
                  className="btn-retry-validation"
                  onClick={startValidation}
                >
                  Retry Validation
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default ValidationDetailPanel
