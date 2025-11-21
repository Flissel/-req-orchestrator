/**
 * Centralized API Configuration for Frontend
 *
 * This module provides a single source of truth for API base URLs
 * in the frontend HTML files. It automatically detects the runtime
 * environment and constructs appropriate API endpoints.
 *
 * Usage in HTML files:
 *   <script src="config.js"></script>
 *   <script>
 *     const API_BASE = window.API_CONFIG.BACKEND_URL;
 *     fetch(`${API_BASE}/api/v1/health`);
 *   </script>
 */

(function() {
  'use strict';

  /**
   * Detects port from URL search params (e.g., ?backend_port=8087)
   * @param {string} paramName - URL parameter name
   * @param {string} defaultPort - Default port if not found
   * @returns {string} Port number
   */
  function getPortFromURL(paramName, defaultPort) {
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get(paramName) || defaultPort;
    } catch (e) {
      return defaultPort;
    }
  }

  /**
   * Builds API base URL with fallback chain:
   * 1. URL parameter (e.g., ?backend_port=8087)
   * 2. Current hostname with default port
   * 3. Localhost fallback
   *
   * @param {string} urlParam - URL parameter name
   * @param {string} defaultPort - Default port number
   * @param {string} localhostFallback - Localhost fallback URL
   * @returns {string} Complete API base URL
   */
  function buildAPIBase(urlParam, defaultPort, localhostFallback) {
    const port = getPortFromURL(urlParam, defaultPort);
    const hostname = window.location.hostname;

    // If running from file:// protocol, use localhost fallback
    if (window.location.protocol === 'file:') {
      return localhostFallback;
    }

    // Use current hostname with detected/default port
    return `${window.location.protocol}//${hostname}:${port}`;
  }

  // Default port configuration (matches .env.example)
  const DEFAULT_PORTS = {
    BACKEND_PORT: '8087',      // FastAPI backend
    ARCH_TEAM_PORT: '8000',    // Arch team Flask service
    QDRANT_PORT: '6333'        // Qdrant (direct access, rarely needed in frontend)
  };

  // Localhost fallback URLs (for file:// protocol or development)
  const LOCALHOST_FALLBACK = {
    BACKEND: `http://localhost:${DEFAULT_PORTS.BACKEND_PORT}`,
    ARCH_TEAM: `http://localhost:${DEFAULT_PORTS.ARCH_TEAM_PORT}`,
    QDRANT: `http://localhost:${DEFAULT_PORTS.QDRANT_PORT}`
  };

  // Build runtime configuration
  const API_CONFIG = {
    // FastAPI Backend (port 8087 by default)
    BACKEND_URL: buildAPIBase('backend_port', DEFAULT_PORTS.BACKEND_PORT, LOCALHOST_FALLBACK.BACKEND),

    // Arch Team Service (port 8000 by default)
    ARCH_TEAM_URL: buildAPIBase('arch_team_port', DEFAULT_PORTS.ARCH_TEAM_PORT, LOCALHOST_FALLBACK.ARCH_TEAM),

    // Qdrant (rarely accessed directly from frontend)
    QDRANT_URL: buildAPIBase('qdrant_port', DEFAULT_PORTS.QDRANT_PORT, LOCALHOST_FALLBACK.QDRANT),

    // Legacy aliases (backward compatibility)
    get API_BASE() {
      return this.BACKEND_URL;
    },

    // Runtime information
    IS_FILE_PROTOCOL: window.location.protocol === 'file:',
    CURRENT_HOSTNAME: window.location.hostname,

    // Helper method to log configuration
    logConfig: function() {
      console.log('[API Config] Backend:', this.BACKEND_URL);
      console.log('[API Config] Arch Team:', this.ARCH_TEAM_URL);
      console.log('[API Config] Protocol:', window.location.protocol);
      console.log('[API Config] Hostname:', this.CURRENT_HOSTNAME);
    }
  };

  // Expose configuration globally
  window.API_CONFIG = API_CONFIG;

  // Log configuration in development (can be disabled in production)
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    API_CONFIG.logConfig();
  }
})();
