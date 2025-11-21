/**
 * SSE Debug Utility
 *
 * Helper functions for debugging Server-Sent Events (SSE) connections.
 * Tracks EventSource lifecycle, readyState transitions, and connection health.
 */

/**
 * EventSource readyState constants
 * @see https://developer.mozilla.org/en-US/docs/Web/API/EventSource/readyState
 */
export const SSE_STATE = {
  CONNECTING: 0,
  OPEN: 1,
  CLOSED: 2
}

/**
 * Get human-readable state name
 * @param {number} readyState - EventSource readyState (0, 1, or 2)
 * @returns {string} State name
 */
export function getStateName(readyState) {
  switch (readyState) {
    case SSE_STATE.CONNECTING:
      return 'CONNECTING'
    case SSE_STATE.OPEN:
      return 'OPEN'
    case SSE_STATE.CLOSED:
      return 'CLOSED'
    default:
      return 'UNKNOWN'
  }
}

/**
 * Debug SSE connection lifecycle
 * Logs connection state changes and health status
 *
 * @param {string} name - Descriptive name for this SSE connection
 * @param {EventSource} eventSource - EventSource instance to monitor
 * @returns {void}
 *
 * @example
 * const es = new EventSource('/api/stream')
 * debugSSE('WorkflowStream', es)
 */
export function debugSSE(name, eventSource) {
  if (!eventSource) {
    console.warn(`[SSE-Debug] ${name} - EventSource is null/undefined`)
    return
  }

  // Log initial state
  const initialState = getStateName(eventSource.readyState)
  console.log(`[SSE-Debug] ${name} - Initial state: ${initialState} (${eventSource.readyState})`)

  // Monitor open event
  eventSource.addEventListener('open', () => {
    console.log(`[SSE-Debug] ${name} - ✅ OPEN (connection established)`)
    console.log(`[SSE-Debug] ${name} - URL: ${eventSource.url}`)
  })

  // Monitor error event
  eventSource.addEventListener('error', (event) => {
    const state = getStateName(eventSource.readyState)
    console.error(`[SSE-Debug] ${name} - ⚠️ ERROR (state: ${state})`)

    if (eventSource.readyState === SSE_STATE.CONNECTING) {
      console.error(`[SSE-Debug] ${name} - Connection failed, attempting retry...`)
    } else if (eventSource.readyState === SSE_STATE.CLOSED) {
      console.error(`[SSE-Debug] ${name} - Connection closed`)
    }
  })

  // Monitor message event
  eventSource.addEventListener('message', (event) => {
    console.log(`[SSE-Debug] ${name} - 📨 Message received (${event.data.length} chars)`)
  })
}

/**
 * Check if EventSource is connected (OPEN state)
 * @param {EventSource} eventSource - EventSource instance
 * @returns {boolean} True if connection is open
 */
export function isSSEConnected(eventSource) {
  return eventSource && eventSource.readyState === SSE_STATE.OPEN
}

/**
 * Get SSE connection status summary
 * @param {EventSource} eventSource - EventSource instance
 * @returns {Object} Status object with state, connected flag, and URL
 */
export function getSSEStatus(eventSource) {
  if (!eventSource) {
    return {
      state: 'NONE',
      readyState: null,
      connected: false,
      url: null
    }
  }

  return {
    state: getStateName(eventSource.readyState),
    readyState: eventSource.readyState,
    connected: isSSEConnected(eventSource),
    url: eventSource.url
  }
}

/**
 * Log all SSE connections status (for debugging)
 * @param {Object} connections - Map of connection name to EventSource
 *
 * @example
 * logAllSSEStatus({
 *   workflow: workflowSource,
 *   clarification: clarificationSource
 * })
 */
export function logAllSSEStatus(connections) {
  console.group('[SSE-Debug] Connection Status Summary')

  Object.entries(connections).forEach(([name, eventSource]) => {
    const status = getSSEStatus(eventSource)
    const icon = status.connected ? '✅' : '⚠️'
    console.log(`${icon} ${name}: ${status.state} (readyState: ${status.readyState})`)

    if (status.url) {
      console.log(`   URL: ${status.url}`)
    }
  })

  console.groupEnd()
}

/**
 * Expose SSE instances to window for E2E testing
 * Only in development mode
 *
 * @param {string} name - Connection name
 * @param {EventSource} eventSource - EventSource instance
 */
export function exposeSSEForTesting(name, eventSource) {
  if (import.meta.env.DEV) {
    window.__sseConnections = window.__sseConnections || {}
    window.__sseConnections[name] = eventSource
    console.log(`[SSE-Debug] Exposed window.__sseConnections.${name} for testing`)
  }
}
