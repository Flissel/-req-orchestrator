import { useState, useEffect, useRef } from 'react'
import RequirementDiffView from './RequirementDiffView'

export default function ValidationModal({ requirement, onClose, onValidationComplete }) {
  const [isValidating, setIsValidating] = useState(false)
  const [events, setEvents] = useState([])
  const [diffs, setDiffs] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const eventSourceRef = useRef(null)
  const sessionIdRef = useRef(`val-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`)

  const addEvent = (type, message, data = null) => {
    const timestamp = new Date().toLocaleTimeString()
    setEvents(prev => [...prev, { type, message, timestamp, data }])
  }

  const addDiff = (diffData) => {
    setDiffs(prev => [...prev, diffData])
  }

  const connectSSE = (sessionId) => {
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`)
    eventSourceRef.current = eventSource

    eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data)
      addEvent('info', 'Connected to validation stream')
      console.log('[ValidationModal] SSE connected:', data)
    })

    eventSource.addEventListener('evaluation_started', (e) => {
      const data = JSON.parse(e.data)
      addEvent('info', `Evaluating requirement: ${data.requirement_id}`)
    })

    eventSource.addEventListener('evaluation_completed', (e) => {
      const data = JSON.parse(e.data)
      const failingCount = Object.values(data.scores || {}).filter(s => s < 0.7).length
      addEvent('info', `Evaluation complete: ${failingCount} criteria need improvement`)
    })

    eventSource.addEventListener('requirement_updated', (e) => {
      const data = JSON.parse(e.data)
      addEvent('update', `Fixed ${data.criterion}: ${data.score_before.toFixed(2)} → ${data.score_after.toFixed(2)}`)
      addDiff(data)
    })

    eventSource.addEventListener('requirement_split', (e) => {
      const data = JSON.parse(e.data)
      addEvent('split', `Requirement split into ${data.child_count} atomic requirements`)
    })

    eventSource.addEventListener('validation_complete', (e) => {
      const data = JSON.parse(e.data)
      addEvent('success', `Validation complete: Final score ${data.final_score.toFixed(2)}`)
      console.log('[ValidationModal] Validation complete:', data)
    })

    eventSource.addEventListener('validation_error', (e) => {
      const data = JSON.parse(e.data)
      addEvent('error', `Error: ${data.error}`)
      setError(data.error)
    })

    eventSource.onerror = (err) => {
      console.error('[ValidationModal] SSE error:', err)
      addEvent('error', 'Connection error occurred')
    }
  }

  const startValidation = async () => {
    setIsValidating(true)
    setEvents([])
    setDiffs([])
    setError(null)
    setResult(null)

    const sessionId = sessionIdRef.current
    addEvent('info', 'Starting validation...')

    // Connect to SSE stream
    connectSSE(sessionId)

    try {
      const response = await fetch('/api/v1/validate/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement_id: requirement.req_id,
          requirement_text: requirement.title,
          session_id: sessionId,
          threshold: 0.7,
          max_iterations: 3
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || data.message || 'Validation failed')
      }

      setResult(data)
      addEvent('success', 'Validation completed successfully')

      // Notify parent component
      if (onValidationComplete) {
        onValidationComplete(requirement.req_id, data)
      }

    } catch (err) {
      console.error('[ValidationModal] Validation error:', err)
      setError(err.message)
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

  useEffect(() => {
    // Start validation automatically when modal opens
    startValidation()

    // Cleanup on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  const getEventIcon = (type) => {
    switch (type) {
      case 'info': return 'ℹ️'
      case 'update': return '🔄'
      case 'split': return '✂️'
      case 'success': return '✅'
      case 'error': return '❌'
      default: return '•'
    }
  }

  const getEventColor = (type) => {
    switch (type) {
      case 'info': return '#2196f3'
      case 'update': return '#ff9800'
      case 'split': return '#9c27b0'
      case 'success': return '#4caf50'
      case 'error': return '#f44336'
      default: return 'var(--text)'
    }
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        background: 'var(--bg)',
        borderRadius: '8px',
        maxWidth: '900px',
        width: '100%',
        maxHeight: '90vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h2 style={{ margin: 0 }}>🔍 Requirement Validation</h2>
            <div style={{ fontSize: '14px', color: 'var(--muted)', marginTop: '4px' }}>
              {requirement.req_id}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              cursor: 'pointer',
              color: 'var(--text)',
              padding: '0 8px'
            }}
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '20px'
        }}>
          {/* Original Requirement */}
          <div style={{
            marginBottom: '20px',
            padding: '15px',
            background: 'var(--bg-secondary)',
            borderRadius: '6px',
            border: '1px solid var(--border)'
          }}>
            <div style={{ fontWeight: '600', marginBottom: '8px', fontSize: '13px', color: 'var(--muted)' }}>
              Original Text
            </div>
            <div style={{ fontSize: '14px' }}>
              {requirement.title}
            </div>
          </div>

          {/* Event Log */}
          {events.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '10px' }}>
                📝 Event Log
              </h3>
              <div style={{
                background: 'var(--bg-secondary)',
                borderRadius: '6px',
                border: '1px solid var(--border)',
                maxHeight: '200px',
                overflow: 'auto'
              }}>
                {events.map((event, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '8px 12px',
                      borderBottom: idx < events.length - 1 ? '1px solid var(--border)' : 'none',
                      fontSize: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <span style={{ fontSize: '14px' }}>{getEventIcon(event.type)}</span>
                    <span style={{ fontSize: '11px', color: 'var(--muted)', minWidth: '60px' }}>
                      {event.timestamp}
                    </span>
                    <span style={{ color: getEventColor(event.type) }}>
                      {event.message}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Diff Views */}
          {diffs.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '10px' }}>
                🔄 Applied Improvements
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {diffs.map((diff, idx) => (
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
            </div>
          )}

          {/* Result Summary */}
          {result && (
            <div style={{
              padding: '15px',
              background: result.passed ? '#c8e6c9' : '#ffcdd2',
              borderRadius: '6px',
              border: `1px solid ${result.passed ? '#4caf50' : '#f44336'}`
            }}>
              <div style={{ fontWeight: '600', marginBottom: '8px', color: result.passed ? '#2e7d32' : '#c62828' }}>
                {result.passed ? '✅ Validation Passed' : '❌ Validation Failed'}
              </div>
              <div style={{ fontSize: '13px', color: result.passed ? '#2e7d32' : '#c62828' }}>
                Final Score: {(result.final_score * 100).toFixed(0)}%
              </div>
              <div style={{ fontSize: '12px', color: result.passed ? '#2e7d32' : '#c62828', marginTop: '4px' }}>
                Total Fixes Applied: {result.total_fixes}
              </div>
              {result.split_occurred && (
                <div style={{ fontSize: '12px', color: result.passed ? '#2e7d32' : '#c62828', marginTop: '4px' }}>
                  ✂️ Requirement was split into atomic components
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{
              padding: '15px',
              background: '#ffcdd2',
              borderRadius: '6px',
              border: '1px solid #f44336',
              color: '#c62828'
            }}>
              <div style={{ fontWeight: '600', marginBottom: '4px' }}>❌ Error</div>
              <div style={{ fontSize: '13px' }}>{error}</div>
            </div>
          )}

          {/* Loading State */}
          {isValidating && !result && !error && (
            <div style={{
              textAlign: 'center',
              padding: '40px',
              color: 'var(--muted)'
            }}>
              <div style={{ fontSize: '32px', marginBottom: '10px' }}>⏳</div>
              <div>Validating requirement...</div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '15px 20px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '10px'
        }}>
          {result && (
            <button
              onClick={() => startValidation()}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: '1px solid var(--primary)',
                background: 'var(--bg)',
                color: 'var(--primary)',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              🔄 Retry Validation
            </button>
          )}
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              background: 'var(--primary)',
              color: 'white',
              cursor: 'pointer',
              fontWeight: '500'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
