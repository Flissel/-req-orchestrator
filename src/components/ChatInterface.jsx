import { useState, useEffect, useRef } from 'react'
import './ChatInterface.css'
import { debugSSE, exposeSSEForTesting } from '../utils/sse-debug'
import { createReconnectingEventSource } from '../utils/sse-reconnection'

// Use relative URLs to leverage Vite's proxy (eliminates CORS warnings)
const API_BASE = ''

function ChatInterface({ sessionId, onWorkflowComplete }) {
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false)
  const [workflowId, setWorkflowId] = useState(null)
  const messagesEndRef = useRef(null)
  const pollingInterval = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Add system message
  const addSystemMessage = (content) => {
    setMessages(prev => [...prev, {
      id: Date.now(),
      sender: 'system',
      content,
      timestamp: new Date().toLocaleTimeString()
    }])
  }

  // Add agent message
  const addAgentMessage = (agent, content) => {
    setMessages(prev => [...prev, {
      id: Date.now(),
      sender: agent,
      content,
      timestamp: new Date().toLocaleTimeString()
    }])
  }

  // Add user message
  const addUserMessage = (content) => {
    setMessages(prev => [...prev, {
      id: Date.now(),
      sender: 'user',
      content,
      timestamp: new Date().toLocaleTimeString()
    }])
  }

  // Send user message
  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return

    const userMsg = inputMessage.trim()
    addUserMessage(userMsg)
    setInputMessage('')

    if (isWorkflowRunning) {
      // Send as clarification answer
      try {
        await fetch(`${API_BASE}/api/clarification/answer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            answer: userMsg
          })
        })
        addSystemMessage('✓ Antwort gesendet')
      } catch (err) {
        addSystemMessage(`✗ Fehler beim Senden: ${err.message}`)
      }
    } else {
      // Start new workflow with this message as initial input
      startWorkflow(userMsg)
    }
  }

  // Start workflow
  const startWorkflow = async (initialMessage) => {
    try {
      setIsWorkflowRunning(true)
      addSystemMessage(`🚀 Starte Master Workflow...`)

      // For now, we'll trigger with uploaded files
      // The master workflow expects files, not just messages
      addSystemMessage('⚠️ Bitte Dateien über "Start Mining" hochladen')
      setIsWorkflowRunning(false)

    } catch (err) {
      addSystemMessage(`✗ Workflow-Start fehlgeschlagen: ${err.message}`)
      setIsWorkflowRunning(false)
    }
  }

  // Poll for workflow messages (if we had a message stream endpoint)
  useEffect(() => {
    if (!isWorkflowRunning || !workflowId) return

    pollingInterval.current = setInterval(async () => {
      try {
        // This would poll for new messages from the workflow
        // For now, we'll rely on SSE from ClarificationModal
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 2000)

    return () => {
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current)
      }
    }
  }, [isWorkflowRunning, workflowId])

  // Listen for workflow messages via SSE (with automatic reconnection)
  useEffect(() => {
    if (!sessionId) return

    const workflowConnection = createReconnectingEventSource(
      `${API_BASE}/api/workflow/stream?session_id=${sessionId}`,
      {
        onOpen: (e) => {
          if (import.meta.env.DEV) {
            console.log('[Chat] Workflow SSE connection opened')
          }
        },
        onMessage: (event) => {
          try {
            const data = JSON.parse(event.data)

            if (data.type === 'connected') {
              if (import.meta.env.DEV) {
                console.log('[Chat] Workflow SSE connected:', data.session_id)
              }
            } else if (data.type === 'agent_message') {
              addAgentMessage(data.agent, data.message)
            } else if (data.type === 'workflow_status') {
              if (data.status === 'running') {
                setIsWorkflowRunning(true)
                addSystemMessage('🔄 Workflow gestartet')
              } else if (data.status === 'completed') {
                setIsWorkflowRunning(false)
                addSystemMessage('✅ Workflow abgeschlossen')
              } else if (data.status === 'failed') {
                setIsWorkflowRunning(false)
                addSystemMessage(`❌ Workflow fehlgeschlagen: ${data.error || 'Unbekannter Fehler'}`)
              }
            } else if (data.type === 'workflow_result') {
              if (onWorkflowComplete) {
                onWorkflowComplete(data.result)
              }
            }
          } catch (err) {
            console.error('[Chat] Workflow SSE parse error:', err)
          }
        },
        onError: (err) => {
          console.error('[Chat] Workflow SSE error:', err)
        },
        onClose: (info) => {
          console.warn('[Chat] Workflow SSE closed:', info)
        }
      },
      {
        maxRetries: 10,
        initialDelay: 1000,
        maxDelay: 30000,
        logReconnections: import.meta.env.DEV
      }
    )

    // Debug and expose for testing
    const eventSource = workflowConnection.getEventSource()
    debugSSE('WorkflowStream', eventSource)
    exposeSSEForTesting('workflow', eventSource)

    return () => {
      workflowConnection.close()
    }
  }, [sessionId, onWorkflowComplete])

  // Listen for clarification questions from SSE (with automatic reconnection)
  useEffect(() => {
    if (!sessionId) return

    const clarificationConnection = createReconnectingEventSource(
      `${API_BASE}/api/clarification/stream?session_id=${sessionId}`,
      {
        onOpen: (e) => {
          if (import.meta.env.DEV) {
            console.log('[Chat] Clarification SSE connection opened')
          }
        },
        onMessage: (event) => {
          try {
            const data = JSON.parse(event.data)

            if (data.type === 'connected') {
              if (import.meta.env.DEV) {
                console.log('[Chat] Clarification SSE connected:', data.session_id)
              }
            } else if (data.type === 'question') {
              addAgentMessage('UserClarification', `❓ ${data.question}`)

              if (data.suggested_answers && data.suggested_answers.length > 0) {
                addSystemMessage(`Vorschläge: ${data.suggested_answers.join(', ')}`)
              }
            }
          } catch (err) {
            console.error('[Chat] Clarification SSE parse error:', err)
          }
        },
        onError: (err) => {
          console.error('[Chat] Clarification SSE error:', err)
        },
        onClose: (info) => {
          console.warn('[Chat] Clarification SSE closed:', info)
        }
      },
      {
        maxRetries: 10,
        initialDelay: 1000,
        maxDelay: 30000,
        logReconnections: import.meta.env.DEV
      }
    )

    // Debug and expose for testing
    const eventSource = clarificationConnection.getEventSource()
    debugSSE('ClarificationStream', eventSource)
    exposeSSEForTesting('clarificationChat', eventSource)

    return () => {
      clarificationConnection.close()
    }
  }, [sessionId])

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h3>💬 Agent Chat</h3>
        <div className="chat-status">
          {isWorkflowRunning ? (
            <span className="status-running">🟢 Workflow läuft</span>
          ) : (
            <span className="status-idle">⚪ Bereit</span>
          )}
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <p>💡 Willkommen beim Master Workflow</p>
            <p>Lade Dateien hoch und starte den Prozess über "Start Mining"</p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div key={msg.id} className={`message message-${msg.sender}`}>
                <div className="message-header">
                  <span className="message-sender">
                    {msg.sender === 'user' ? '👤 Du' :
                     msg.sender === 'system' ? '⚙️ System' :
                     `🤖 ${msg.sender}`}
                  </span>
                  <span className="message-time">{msg.timestamp}</span>
                </div>
                <div className="message-content">{msg.content}</div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
          placeholder={isWorkflowRunning ? "Antwort eingeben..." : "Nachricht eingeben..."}
          disabled={!sessionId}
        />
        <button
          onClick={handleSendMessage}
          disabled={!inputMessage.trim() || !sessionId}
        >
          Senden
        </button>
      </div>
    </div>
  )
}

export default ChatInterface
