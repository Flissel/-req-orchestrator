import { useState, useEffect, useRef } from 'react';
import RequirementDiffView from './RequirementDiffView';

/**
 * ValidationTest - Automatic Requirements Validation with Real-Time Updates
 *
 * This component demonstrates the new automatic validation system using:
 * - RequirementOrchestrator with CriterionSpecialistAgents
 * - Server-Sent Events (SSE) for real-time progress updates
 * - RequirementDiffView for showing before/after comparisons
 * - No user interaction required - fully automatic fixes
 */
export default function ValidationTest() {
  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [requirements, setRequirements] = useState([
    { id: 'REQ-001', text: 'Die App muss schnell sein' },
    { id: 'REQ-002', text: 'System soll skalierbar sein' }
  ]);
  const [results, setResults] = useState([]);
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState(null);
  const eventSourceRef = useRef(null);

  // Generate session ID on mount
  useEffect(() => {
    const newSessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    console.log('[ValidationTest] Generated session ID:', newSessionId);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const connectSSE = (sessId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    console.log('[ValidationTest] Connecting to SSE stream:', sessId);
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessId}`);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Connected:', data);
      addEvent('info', 'Connected to validation stream');
    });

    eventSource.addEventListener('evaluation_started', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Evaluation started:', data);
      addEvent('info', `Evaluating ${data.requirement_id} (iteration ${data.iteration})`);
    });

    eventSource.addEventListener('evaluation_completed', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Evaluation completed:', data);
      addEvent('success', `Evaluation complete: score ${data.overall_score.toFixed(2)}`);
    });

    eventSource.addEventListener('requirement_updated', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Requirement updated:', data);
      addEvent('update', `Fixed ${data.criterion}: ${data.score_before.toFixed(2)} → ${data.score_after.toFixed(2)}`);

      // Add diff view to events
      addDiffEvent(data);
    });

    eventSource.addEventListener('requirement_split', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Requirement split:', data);
      addEvent('warning', `Split into ${data.children.length} atomic requirements`);
    });

    eventSource.addEventListener('validation_complete', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Validation complete:', data);
      addEvent(data.passed ? 'success' : 'error',
        `Validation ${data.passed ? 'PASSED' : 'FAILED'}: score ${data.final_score.toFixed(2)}`);
    });

    eventSource.addEventListener('validation_error', (e) => {
      const data = JSON.parse(e.data);
      console.error('[SSE] Validation error:', data);
      addEvent('error', `Error: ${data.error}`);
    });

    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      addEvent('error', 'Connection error - closing stream');
      eventSource.close();
    };
  };

  const addEvent = (type, message) => {
    setEvents(prev => [...prev, {
      type,
      message,
      timestamp: new Date().toLocaleTimeString()
    }]);
  };

  const addDiffEvent = (data) => {
    setEvents(prev => [...prev, {
      type: 'diff',
      data: data,
      timestamp: new Date().toLocaleTimeString()
    }]);
  };

  const runValidation = async () => {
    if (!sessionId) {
      alert('Session ID not available');
      return;
    }

    setIsRunning(true);
    setResults([]);
    setEvents([]);
    setSummary(null);

    // Connect to SSE stream first
    connectSSE(sessionId);

    try {
      console.log('[ValidationTest] Starting automatic validation');
      addEvent('info', 'Starting automatic validation...');

      // Call the new automatic validation endpoint
      const response = await fetch('/api/v1/validate/auto/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirements: requirements,
          session_id: sessionId,
          threshold: 0.7,
          max_iterations: 3
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[ValidationTest] Validation results:', data);

      setResults(data.results || []);
      setSummary(data.summary || null);
      addEvent('success', `Batch validation complete: ${data.summary?.passed || 0}/${data.summary?.total || 0} passed`);

    } catch (error) {
      console.error('[ValidationTest] Error:', error);
      addEvent('error', `Error: ${error.message}`);
    } finally {
      setIsRunning(false);

      // Close SSE connection after a delay
      setTimeout(() => {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      }, 2000);
    }
  };

  const renderEventLog = () => {
    return (
      <div className="event-log">
        <h4>Real-Time Event Log</h4>
        <div className="events-container">
          {events.map((event, index) => {
            if (event.type === 'diff') {
              // Render diff view for requirement updates
              return (
                <div key={index} className="event-item event-diff">
                  <span className="event-timestamp">{event.timestamp}</span>
                  <RequirementDiffView
                    oldText={event.data.old_text}
                    newText={event.data.new_text}
                    criterion={event.data.criterion}
                    scoreBefore={event.data.score_before}
                    scoreAfter={event.data.score_after}
                    compact={true}
                  />
                </div>
              );
            }

            return (
              <div key={index} className={`event-item event-${event.type}`}>
                <span className="event-timestamp">{event.timestamp}</span>
                <span className="event-message">{event.message}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderResults = () => {
    if (results.length === 0) return null;

    return (
      <div className="validation-results">
        <h4>Final Results</h4>

        {summary && (
          <div className="results-summary">
            <div className="summary-item">
              <span>Total:</span> <strong>{summary.total}</strong>
            </div>
            <div className="summary-item success">
              <span>Passed:</span> <strong>{summary.passed}</strong>
            </div>
            <div className="summary-item error">
              <span>Failed:</span> <strong>{summary.failed}</strong>
            </div>
            <div className="summary-item warning">
              <span>Split:</span> <strong>{summary.split}</strong>
            </div>
            <div className="summary-item">
              <span>Total Fixes:</span> <strong>{summary.total_fixes}</strong>
            </div>
          </div>
        )}

        {results.map((result, index) => (
          <div key={index} className="result-card">
            <div className="result-header">
              <span className="result-id">{result.requirement_id}</span>
              <span className={`result-status ${result.passed ? 'passed' : 'failed'}`}>
                {result.passed ? '✓ PASSED' : '✗ FAILED'}
              </span>
              <span className="result-score">
                Score: {result.final_score.toFixed(2)}
              </span>
            </div>

            <div className="result-texts">
              <div className="text-block">
                <strong>Original:</strong>
                <p>{result.original_text}</p>
              </div>
              <div className="text-block">
                <strong>Final:</strong>
                <p>{result.final_text}</p>
              </div>
            </div>

            {result.iterations && result.iterations.length > 0 && (
              <div className="result-iterations">
                <strong>Iterations: {result.iterations.length}</strong>
                <details>
                  <summary>Show details</summary>
                  {result.iterations.map((iter, i) => (
                    <div key={i} className="iteration-item">
                      <div>Iteration {iter.iteration}: Score {iter.overall_score.toFixed(2)}</div>
                      {iter.fixes_applied && iter.fixes_applied.length > 0 && (
                        <ul className="fixes-list">
                          {iter.fixes_applied.map((fix, j) => (
                            <li key={j}>
                              {fix.criterion}: {fix.score_before.toFixed(2)} → {fix.score_after.toFixed(2)}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </details>
              </div>
            )}

            {result.split_occurred && (
              <div className="result-split">
                <strong>⚠ Split into {result.split_children.length} atomic requirements:</strong>
                <ul>
                  {result.split_children.map((child, i) => (
                    <li key={i}>{child}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="validation-test">
      <div className="test-header">
        <h3>🧪 Automatic Validation Test</h3>
        <p className="text-sm text-gray-600">
          Fully automatic requirement validation with real-time updates - no user interaction required
        </p>
        {sessionId && (
          <p className="text-xs text-gray-400 mt-1">
            Session: {sessionId}
          </p>
        )}
      </div>

      <div className="test-requirements">
        <h4>Test Requirements:</h4>
        <ul>
          {requirements.map((req, index) => (
            <li key={index}>
              <strong>{req.id}:</strong> {req.text}
            </li>
          ))}
        </ul>
      </div>

      <button
        onClick={runValidation}
        disabled={isRunning || !sessionId}
        className={`test-button ${isRunning ? 'running' : ''}`}
      >
        {isRunning ? '⏳ Validation läuft...' : '▶️ Start Automatic Validation'}
      </button>

      {events.length > 0 && renderEventLog()}
      {results.length > 0 && renderResults()}

      <div className="test-info">
        <p className="text-xs text-gray-500 mt-4">
          ℹ️ Expected Flow:
        </p>
        <ol className="text-xs text-gray-500 ml-4">
          <li>1. Connect to SSE stream for real-time updates</li>
          <li>2. Orchestrator evaluates all 10 quality criteria</li>
          <li>3. For each failing criterion, specialist agent applies fix automatically</li>
          <li>4. Show before/after diff for each fix</li>
          <li>5. Atomic violations trigger automatic requirement splitting</li>
          <li>6. Maximum 3 iteration rounds to reach quality threshold</li>
          <li>7. Display final results with scores and iteration history</li>
        </ol>
      </div>

      <style>{`
        .validation-test {
          padding: 20px;
          max-width: 1200px;
          margin: 0 auto;
        }

        .test-header {
          margin-bottom: 24px;
        }

        .test-header h3 {
          font-size: 24px;
          font-weight: 600;
          margin-bottom: 8px;
        }

        .test-requirements {
          background: #f8f9fa;
          border: 1px solid #e0e0e0;
          border-radius: 6px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .test-requirements h4 {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 12px;
        }

        .test-requirements ul {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .test-requirements li {
          padding: 8px 0;
          border-bottom: 1px solid #e0e0e0;
        }

        .test-requirements li:last-child {
          border-bottom: none;
        }

        .test-button {
          background: #2196f3;
          color: white;
          border: none;
          border-radius: 6px;
          padding: 12px 24px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.2s;
          margin-bottom: 24px;
        }

        .test-button:hover:not(:disabled) {
          background: #1976d2;
        }

        .test-button:disabled {
          background: #ccc;
          cursor: not-allowed;
        }

        .test-button.running {
          background: #ff9800;
        }

        .event-log {
          margin: 24px 0;
          background: #fff;
          border: 1px solid #e0e0e0;
          border-radius: 6px;
          padding: 16px;
        }

        .event-log h4 {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 16px;
        }

        .events-container {
          max-height: 400px;
          overflow-y: auto;
        }

        .event-item {
          padding: 8px 12px;
          margin-bottom: 8px;
          border-radius: 4px;
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }

        .event-item.event-info {
          background: #e3f2fd;
          border-left: 3px solid #2196f3;
        }

        .event-item.event-success {
          background: #e8f5e9;
          border-left: 3px solid #4caf50;
        }

        .event-item.event-error {
          background: #ffebee;
          border-left: 3px solid #f44336;
        }

        .event-item.event-warning {
          background: #fff3e0;
          border-left: 3px solid #ff9800;
        }

        .event-item.event-update {
          background: #f3e5f5;
          border-left: 3px solid #9c27b0;
        }

        .event-item.event-diff {
          background: transparent;
          border: none;
          flex-direction: column;
          padding: 0;
        }

        .event-timestamp {
          font-family: monospace;
          font-size: 11px;
          color: #666;
          min-width: 80px;
        }

        .event-message {
          flex: 1;
          font-size: 13px;
        }

        .validation-results {
          margin: 24px 0;
        }

        .validation-results h4 {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 16px;
        }

        .results-summary {
          display: flex;
          gap: 16px;
          margin-bottom: 24px;
          padding: 16px;
          background: #f8f9fa;
          border-radius: 6px;
        }

        .summary-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .summary-item span {
          font-size: 12px;
          color: #666;
        }

        .summary-item strong {
          font-size: 24px;
          font-weight: 600;
        }

        .summary-item.success strong {
          color: #4caf50;
        }

        .summary-item.error strong {
          color: #f44336;
        }

        .summary-item.warning strong {
          color: #ff9800;
        }

        .result-card {
          background: white;
          border: 1px solid #e0e0e0;
          border-radius: 6px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .result-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid #e0e0e0;
        }

        .result-id {
          font-weight: 600;
          color: #333;
        }

        .result-status {
          padding: 4px 10px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }

        .result-status.passed {
          background: #c8e6c9;
          color: #2e7d32;
        }

        .result-status.failed {
          background: #ffcdd2;
          color: #c62828;
        }

        .result-score {
          margin-left: auto;
          font-family: monospace;
          font-weight: 600;
        }

        .result-texts {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
          margin-bottom: 16px;
        }

        .text-block {
          background: #f8f9fa;
          padding: 12px;
          border-radius: 4px;
        }

        .text-block strong {
          display: block;
          margin-bottom: 8px;
          font-size: 12px;
          color: #666;
        }

        .text-block p {
          margin: 0;
          font-size: 14px;
          line-height: 1.5;
        }

        .result-iterations {
          margin-top: 12px;
          font-size: 13px;
        }

        .result-iterations details {
          margin-top: 8px;
        }

        .iteration-item {
          padding: 8px 0;
          border-bottom: 1px solid #e0e0e0;
        }

        .fixes-list {
          margin: 8px 0 0 20px;
          font-size: 12px;
          color: #666;
        }

        .result-split {
          background: #fff3e0;
          padding: 12px;
          border-radius: 4px;
          margin-top: 12px;
        }

        .result-split ul {
          margin: 8px 0 0 20px;
        }

        .test-info {
          margin-top: 32px;
          padding-top: 24px;
          border-top: 1px solid #e0e0e0;
        }

        @media (max-width: 768px) {
          .result-texts {
            grid-template-columns: 1fr;
          }

          .results-summary {
            flex-wrap: wrap;
          }
        }
      `}</style>
    </div>
  );
}
