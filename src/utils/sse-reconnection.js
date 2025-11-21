/**
 * SSE Reconnection Utility
 *
 * Provides automatic exponential backoff reconnection for EventSource connections.
 * Handles network failures gracefully with configurable retry limits.
 */

/**
 * Creates an EventSource with automatic reconnection logic
 *
 * @param {string} url - Relative URL for SSE endpoint (e.g., '/api/workflow/stream?session_id=123')
 * @param {Object} handlers - Event handlers
 * @param {Function} handlers.onOpen - Called when connection opens
 * @param {Function} handlers.onMessage - Called for each message (event.data will be parsed JSON)
 * @param {Function} handlers.onError - Called on connection errors
 * @param {Function} handlers.onConnected - Called when 'connected' event received
 * @param {Function} handlers.onClose - Called when connection permanently closes
 * @param {Object} options - Configuration options
 * @param {number} options.maxRetries - Maximum reconnection attempts (default: 10)
 * @param {number} options.initialDelay - Initial reconnection delay in ms (default: 1000)
 * @param {number} options.maxDelay - Maximum reconnection delay in ms (default: 30000)
 * @param {boolean} options.logReconnections - Log reconnection attempts to console (default: true)
 *
 * @returns {Object} Control object with methods: close(), getState()
 *
 * @example
 * const connection = createReconnectingEventSource(
 *   '/api/workflow/stream?session_id=123',
 *   {
 *     onMessage: (event) => {
 *       console.log('Received:', event.data)
 *     },
 *     onError: (error) => {
 *       console.error('SSE error:', error)
 *     },
 *     onConnected: (event) => {
 *       console.log('Connected to session:', event.data.session_id)
 *     }
 *   },
 *   { maxRetries: 5 }
 * )
 *
 * // Later, to close:
 * connection.close()
 */
export function createReconnectingEventSource(url, handlers = {}, options = {}) {
  const {
    maxRetries = 10,
    initialDelay = 1000,
    maxDelay = 30000,
    logReconnections = true
  } = options

  let reconnectDelay = initialDelay
  let retryCount = 0
  let eventSource = null
  let intentionallyClosed = false

  const connect = () => {
    if (intentionallyClosed) {
      if (logReconnections) {
        console.log('[SSE Reconnection] Connection was intentionally closed, not reconnecting')
      }
      return
    }

    if (retryCount > 0 && logReconnections) {
      console.log(`[SSE Reconnection] Attempt ${retryCount}/${maxRetries} for ${url}`)
    }

    eventSource = new EventSource(url)

    // Handle connection open
    eventSource.onopen = (e) => {
      // Reset reconnection parameters on successful connection
      reconnectDelay = initialDelay
      retryCount = 0

      if (logReconnections && retryCount > 0) {
        console.log('[SSE Reconnection] ✅ Successfully reconnected')
      }

      if (handlers.onOpen) {
        handlers.onOpen(e)
      }
    }

    // Handle messages
    eventSource.onmessage = (e) => {
      if (handlers.onMessage) {
        handlers.onMessage(e)
      }
    }

    // Handle errors and implement reconnection logic
    eventSource.onerror = (e) => {
      if (handlers.onError) {
        handlers.onError(e)
      }

      // Close the broken connection
      eventSource.close()

      // Attempt reconnection if not at max retries and not intentionally closed
      if (!intentionallyClosed && retryCount < maxRetries) {
        retryCount++

        if (logReconnections) {
          console.log(
            `[SSE Reconnection] Connection lost. Retrying in ${reconnectDelay}ms ` +
            `(attempt ${retryCount}/${maxRetries})`
          )
        }

        setTimeout(() => {
          connect()
        }, reconnectDelay)

        // Exponential backoff with max cap
        reconnectDelay = Math.min(reconnectDelay * 2, maxDelay)
      } else if (retryCount >= maxRetries) {
        if (logReconnections) {
          console.error(
            `[SSE Reconnection] ❌ Max reconnection attempts (${maxRetries}) reached for ${url}`
          )
        }

        if (handlers.onClose) {
          handlers.onClose({ reason: 'max_retries_exceeded', retryCount })
        }
      }
    }

    // Handle 'connected' event if handler provided
    if (handlers.onConnected) {
      eventSource.addEventListener('connected', (e) => {
        handlers.onConnected(e)
      })
    }

    return eventSource
  }

  // Start initial connection
  const initialEventSource = connect()

  // Return control object
  return {
    /**
     * Closes the connection and prevents automatic reconnection
     */
    close: () => {
      intentionallyClosed = true
      if (eventSource) {
        eventSource.close()
      }
      if (logReconnections) {
        console.log('[SSE Reconnection] Connection closed by user')
      }
    },

    /**
     * Gets current connection state
     * @returns {Object} State object with readyState, retryCount, url
     */
    getState: () => {
      return {
        readyState: eventSource ? eventSource.readyState : null,
        readyStateText: eventSource ? getReadyStateText(eventSource.readyState) : 'NONE',
        retryCount,
        maxRetries,
        url,
        intentionallyClosed
      }
    },

    /**
     * Gets the underlying EventSource instance (for testing/debugging)
     * @returns {EventSource|null}
     */
    getEventSource: () => eventSource
  }
}

/**
 * Helper function to get human-readable readyState
 * @param {number} readyState - EventSource readyState (0, 1, or 2)
 * @returns {string} State name
 */
function getReadyStateText(readyState) {
  switch (readyState) {
    case 0:
      return 'CONNECTING'
    case 1:
      return 'OPEN'
    case 2:
      return 'CLOSED'
    default:
      return 'UNKNOWN'
  }
}
