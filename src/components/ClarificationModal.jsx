import { useEffect, useState } from 'react';

/**
 * ClarificationModal - Real-time user clarification via SSE
 *
 * Connects to SSE stream and displays agent questions as modals.
 * User answers are sent back via REST API.
 *
 * Props:
 *   - sessionId: Unique session identifier (correlation_id)
 *   - enabled: Whether to connect to SSE stream
 */
export default function ClarificationModal({ sessionId, enabled = true }) {
  const [question, setQuestion] = useState(null);
  const [answer, setAnswer] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!enabled || !sessionId) {
      return;
    }

    console.log(`[ClarificationModal] Connecting to SSE for session: ${sessionId}`);

    // Establish SSE connection
    const eventSource = new EventSource(
      `http://localhost:8000/api/clarification/stream?session_id=${sessionId}`
    );

    eventSource.onopen = () => {
      console.log('[ClarificationModal] SSE connection established');
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[ClarificationModal] Received event:', data);

        if (data.type === 'connected') {
          console.log(`[ClarificationModal] Connected to session: ${data.session_id}`);
        } else if (data.type === 'question') {
          console.log('[ClarificationModal] Displaying question:', data.question);
          setQuestion(data);
          setAnswer(''); // Reset answer field
        }
      } catch (error) {
        console.error('[ClarificationModal] Failed to parse SSE message:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[ClarificationModal] SSE error:', error);
      eventSource.close();
    };

    // Cleanup on unmount
    return () => {
      console.log('[ClarificationModal] Closing SSE connection');
      eventSource.close();
    };
  }, [sessionId, enabled]);

  const handleSubmit = async (e) => {
    e?.preventDefault();

    if (!answer.trim()) {
      alert('Bitte geben Sie eine Antwort ein');
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/api/clarification/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          correlation_id: sessionId,
          answer: answer.trim()
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('[ClarificationModal] Answer submitted:', result);

      // Close modal after successful submission
      setQuestion(null);
      setAnswer('');
    } catch (error) {
      console.error('[ClarificationModal] Failed to submit answer:', error);
      alert(`Fehler beim Senden der Antwort: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSuggestedAnswer = (suggested) => {
    setAnswer(suggested);
  };

  // Don't render anything if no question
  if (!question) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6">
        <h3 className="text-xl font-semibold mb-4 text-gray-800">
          🤖 Agent fragt:
        </h3>

        <p className="text-gray-700 mb-6 text-lg leading-relaxed">
          {question.question}
        </p>

        {/* Suggested answers (if provided) */}
        {question.suggested_answers && question.suggested_answers.length > 0 && (
          <div className="mb-4">
            <p className="text-sm text-gray-600 mb-2">Vorschläge:</p>
            <div className="flex flex-wrap gap-2">
              {question.suggested_answers.map((suggested, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSuggestedAnswer(suggested)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    answer === suggested
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {suggested}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Answer input */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Ihre Antwort:
            </label>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Geben Sie Ihre Antwort hier ein..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={4}
              disabled={isSubmitting}
            />
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="submit"
              disabled={isSubmitting || !answer.trim()}
              className={`px-6 py-2 rounded-md font-medium transition-colors ${
                isSubmitting || !answer.trim()
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {isSubmitting ? 'Sende...' : 'Antworten'}
            </button>
          </div>
        </form>

        {/* Question ID (debug info) */}
        <p className="text-xs text-gray-400 mt-4">
          Question ID: {question.question_id}
        </p>
      </div>
    </div>
  );
}
