import React, { useState, useEffect, useRef, useCallback } from 'react';

// Simple ID generator (no external dependency)
const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

/**
 * EnhancementModal - Real-time WebSocket-based Requirement Enhancement
 * 
 * Uses SocietyOfMind iterative enhancement that:
 * 1. Analyzes requirement PURPOSE
 * 2. Detects information GAPS
 * 3. Generates targeted QUESTIONS
 * 4. Waits for user ANSWERS
 * 5. REWRITES with incorporated answers
 * 6. RE-EVALUATES until quality threshold met
 */

const EnhancementModal = ({ 
  isOpen, 
  onClose, 
  requirement, 
  onEnhancementComplete 
}) => {
  const [messages, setMessages] = useState([]);
  const [answer, setAnswer] = useState('');
  const [status, setStatus] = useState('connecting');
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [currentPurpose, setCurrentPurpose] = useState('');
  const [currentGaps, setCurrentGaps] = useState([]);
  const [currentScore, setCurrentScore] = useState(null);
  const [iteration, setIteration] = useState(0);
  const [enhancedText, setEnhancedText] = useState('');
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const sessionIdRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Add message to chat
  const addMessage = useCallback((type, content, data = {}) => {
    const msg = {
      id: generateId(),
      type,
      content,
      data,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, msg]);
    return msg;
  }, []);

  // Connect and start enhancement
  useEffect(() => {
    if (!isOpen || !requirement) return;

    // Reset state
    setMessages([]);
    setAnswer('');
    setStatus('connecting');
    setCurrentQuestion(null);
    setCurrentPurpose('');
    setCurrentGaps([]);
    setCurrentScore(null);
    setIteration(0);
    setEnhancedText('');
    setError(null);
    
    sessionIdRef.current = generateId();
    const wsUrl = `ws://localhost:8087/enhance/ws/${sessionIdRef.current}`;

    addMessage('system', 'Verbinde mit Enhancement-Service...');
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      addMessage('system', 'Verbunden! Starte iteratives Enhancement...');
      
      // Start enhancement
      ws.send(JSON.stringify({
        type: 'enhancement_start',
        requirement_text: requirement.original_text || requirement.text
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error('Message parse error:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setStatus('error');
      setError('WebSocket-Verbindungsfehler');
      addMessage('error', 'Verbindungsfehler zum Enhancement-Service');
    };

    ws.onclose = () => {
      if (status !== 'complete') {
        setStatus('disconnected');
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [isOpen, requirement]);

  // Handle incoming messages
  const handleMessage = useCallback((data) => {
    const { type } = data;

    switch (type) {
      case 'connected':
        addMessage('system', data.message || 'Verbunden mit iterativem Enhancement');
        break;

      case 'progress':
        addMessage('agent', data.message || data.stage, { stage: data.stage });
        break;

      case 'purpose':
        // Purpose identified
        setCurrentPurpose(data.purpose || '');
        addMessage('purpose', `🎯 PURPOSE identifiziert: ${data.purpose}`, data);
        break;

      case 'gaps':
        // Gaps detected
        const gaps = data.gaps || [];
        setCurrentGaps(gaps);
        if (gaps.length > 0) {
          addMessage('gaps', `🔍 ${gaps.length} Lücken gefunden: ${gaps.join(', ')}`, data);
        } else {
          addMessage('gaps', '✅ Keine kritischen Lücken gefunden', data);
        }
        break;

      case 'evaluation':
        // Evaluation result
        const score = data.score || data.quality_score || 0;
        setCurrentScore(score);
        setIteration(data.iteration || iteration + 1);
        const emoji = score >= 0.7 ? '✅' : score >= 0.5 ? '⚠️' : '❌';
        addMessage('evaluation', `${emoji} Qualität: ${(score * 100).toFixed(0)}% (Iteration ${data.iteration || iteration + 1})`, data);
        break;

      case 'rewritten':
        // Rewritten text
        setEnhancedText(data.text || data.rewritten_text || '');
        addMessage('rewritten', '📝 Anforderung wurde überarbeitet', { text: data.text || data.rewritten_text });
        break;

      case 'clarification_request':
        // Question from agent
        setStatus('awaiting_answer');
        setCurrentQuestion(data.question || data);
        addMessage('question', `❓ ${data.question?.question || data.question || 'Frage vom Agent'}`, data);
        break;

      case 'complete':
        // Enhancement complete
        setStatus('complete');
        setCurrentQuestion(null);
        // Result can be in data.result or data.data (from _send_ws_message)
        const result = data.result || data.data || data;
        setEnhancedText(result.enhanced_text || result.text || enhancedText);
        setCurrentScore(result.final_score || result.score || currentScore);
        
        addMessage('complete', `🎉 Enhancement abgeschlossen! Qualität: ${((result.final_score || result.score || 0) * 100).toFixed(0)}%`, result);
        
        // Notify parent
        if (onEnhancementComplete) {
          onEnhancementComplete({
            original_text: result.original_text || requirement.original_text || requirement.text,
            enhanced_text: result.enhanced_text || result.text || enhancedText,
            final_score: result.final_score || result.score || currentScore,
            iterations: result.iterations_used || iteration,
            questions_asked: result.questions_asked || 0,
            purpose: result.purpose_identified || currentPurpose,
            success: result.success !== false
          });
        }
        break;

      case 'error':
        setStatus('error');
        setError(data.message || 'Unbekannter Fehler');
        addMessage('error', `❌ Fehler: ${data.message || 'Unbekannter Fehler'}`, data);
        break;

      default:
        console.log('Unknown message type:', type, data);
        if (data.message) {
          addMessage('info', data.message, data);
        }
    }
  }, [addMessage, iteration, enhancedText, currentScore, currentPurpose, onEnhancementComplete, requirement]);

  // Submit answer
  const handleSubmitAnswer = () => {
    if (!answer.trim() || !wsRef.current) return;

    // Add user message
    addMessage('user', answer);

    // Send to WebSocket
    wsRef.current.send(JSON.stringify({
      type: 'clarification_response',
      answer: answer.trim()
    }));

    // Clear input and update status
    setAnswer('');
    setCurrentQuestion(null);
    setStatus('processing');
    addMessage('system', 'Antwort wird verarbeitet, neuer Evaluationszyklus startet...');
  };

  // Close handler
  const handleClose = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    onClose();
  };

  // Skip question
  const handleSkip = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'clarification_response',
        answer: 'Keine zusätzlichen Informationen verfügbar.'
      }));
    }
    setCurrentQuestion(null);
    setStatus('processing');
    addMessage('user', '(Übersprungen)');
    addMessage('system', 'Frage übersprungen, Evaluation wird fortgesetzt...');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b flex justify-between items-center bg-gradient-to-r from-purple-700 to-indigo-800 text-white rounded-t-lg">
          <div>
            <h2 className="text-xl font-semibold">🧠 Iteratives Requirement Enhancement</h2>
            <div className="text-sm opacity-90 flex items-center gap-4 mt-1">
              <span>Status: {status === 'complete' ? '✅ Fertig' : status === 'error' ? '❌ Fehler' : status === 'awaiting_answer' ? '⏳ Warte auf Antwort' : '🔄 ' + status}</span>
              {currentScore !== null && <span>Qualität: {(currentScore * 100).toFixed(0)}%</span>}
              {iteration > 0 && <span>Iteration: {iteration}</span>}
            </div>
          </div>
          <button onClick={handleClose} className="text-white hover:text-gray-200">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Purpose & Gaps Summary */}
        {(currentPurpose || currentGaps.length > 0) && (
          <div className="px-6 py-3 bg-gray-50 border-b text-sm">
            {currentPurpose && (
              <div className="mb-1">
                <span className="font-semibold text-purple-700">🎯 Purpose:</span> {currentPurpose}
              </div>
            )}
            {currentGaps.length > 0 && (
              <div>
                <span className="font-semibold text-orange-600">🔍 Offene Gaps:</span> {currentGaps.join(', ')}
              </div>
            )}
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
          {messages.map((msg) => (
            <div 
              key={msg.id}
              className={`p-3 rounded-lg ${
                msg.type === 'user' ? 'bg-blue-100 ml-8' :
                msg.type === 'error' ? 'bg-red-100' :
                msg.type === 'question' ? 'bg-yellow-100' :
                msg.type === 'complete' ? 'bg-green-100' :
                msg.type === 'purpose' ? 'bg-purple-100' :
                msg.type === 'gaps' ? 'bg-orange-100' :
                msg.type === 'evaluation' ? 'bg-indigo-100' :
                msg.type === 'rewritten' ? 'bg-teal-100' :
                'bg-white'
              }`}
            >
              <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
              {msg.type === 'rewritten' && msg.data?.text && (
                <div className="mt-2 p-2 bg-white rounded text-xs border-l-4 border-teal-500">
                  <strong>Neuer Text:</strong><br/>
                  {msg.data.text}
                </div>
              )}
              {msg.type === 'question' && msg.data?.context && (
                <div className="mt-2 text-xs text-gray-600">
                  <strong>Kontext:</strong> {msg.data.context}
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Current Enhanced Text Preview */}
        {enhancedText && status !== 'complete' && (
          <div className="px-4 py-2 bg-teal-50 border-t text-sm">
            <div className="font-semibold text-teal-700">📝 Aktuelle Version:</div>
            <div className="text-gray-700 truncate">{enhancedText.substring(0, 200)}...</div>
          </div>
        )}

        {/* Input Area */}
        {status === 'awaiting_answer' && currentQuestion && (
          <div className="px-4 py-3 border-t bg-yellow-50">
            <div className="mb-2 text-sm font-medium text-gray-700">
              Bitte beantworten Sie die Frage oben:
            </div>
            <div className="flex gap-2">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Ihre Antwort..."
                className="flex-1 p-2 border rounded resize-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                rows={2}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitAnswer();
                  }
                }}
              />
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleSubmitAnswer}
                  disabled={!answer.trim()}
                  className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
                >
                  Senden
                </button>
                <button
                  onClick={handleSkip}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
                >
                  Überspringen
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Completion / Error Footer */}
        {(status === 'complete' || status === 'error') && (
          <div className={`px-4 py-3 border-t ${status === 'complete' ? 'bg-green-50' : 'bg-red-50'}`}>
            <div className="flex justify-between items-center">
              <div>
                {status === 'complete' ? (
                  <span className="text-green-700 font-medium">
                    ✅ Enhancement abgeschlossen! Qualität: {((currentScore || 0) * 100).toFixed(0)}%
                  </span>
                ) : (
                  <span className="text-red-700 font-medium">
                    ❌ {error || 'Fehler beim Enhancement'}
                  </span>
                )}
              </div>
              <button
                onClick={handleClose}
                className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
              >
                Schließen
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EnhancementModal;