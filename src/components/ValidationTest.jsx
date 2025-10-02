import { useState } from 'react';

/**
 * ValidationTest - Test component for Society of Mind validation with user clarification
 */
export default function ValidationTest({ sessionId }) {
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState(null);

  const runValidationTest = async () => {
    if (!sessionId) {
      alert('Session ID nicht verfügbar');
      return;
    }

    setIsRunning(true);
    setResult(null);

    try {
      console.log('[ValidationTest] Starting validation with session:', sessionId);

      // Call validation API with correlation_id = sessionId
      const response = await fetch('http://localhost:8000/api/validation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirements: [
            'Die App muss schnell sein',
            'System soll skalierbar sein'
          ],
          correlation_id: sessionId,
          criteria_keys: ['clarity', 'testability', 'measurability'],
          threshold: 0.7
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[ValidationTest] Validation result:', data);

      setResult(data);
    } catch (error) {
      console.error('[ValidationTest] Error:', error);
      setResult({ error: error.message });
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="validation-test">
      <div className="test-header">
        <h3>🧪 Validation Test (Society of Mind)</h3>
        <p className="text-sm text-gray-600">
          Testet Requirements Validation mit User Clarification
        </p>
        {sessionId && (
          <p className="text-xs text-gray-400 mt-1">
            Session: {sessionId}
          </p>
        )}
      </div>

      <button
        onClick={runValidationTest}
        disabled={isRunning || !sessionId}
        className={`test-button ${isRunning ? 'running' : ''}`}
      >
        {isRunning ? '⏳ Validation läuft...' : '▶️ Validation Test starten'}
      </button>

      {result && (
        <div className="test-result">
          <h4>Ergebnis:</h4>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}

      <div className="test-info">
        <p className="text-xs text-gray-500 mt-2">
          ℹ️ Erwarteter Flow:
        </p>
        <ol className="text-xs text-gray-500 ml-4">
          <li>1. Agent evaluiert Requirements</li>
          <li>2. Agent stellt Clarification-Frage im Modal</li>
          <li>3. Sie antworten im Modal</li>
          <li>4. Agent verarbeitet Antwort und fährt fort</li>
        </ol>
      </div>
    </div>
  );
}
