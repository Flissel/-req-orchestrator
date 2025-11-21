import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Port configuration from environment variables with fallback defaults
// Note: Vite only exposes env vars prefixed with VITE_ to the client
const FRONTEND_PORT = parseInt(process.env.FRONTEND_PORT || '3000')
const BACKEND_PORT = parseInt(process.env.VITE_BACKEND_PORT || process.env.BACKEND_PORT || '8087')
const ARCH_TEAM_PORT = parseInt(process.env.VITE_ARCH_TEAM_PORT || process.env.ARCH_TEAM_PORT || '8000')

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    proxy: {
      // Arch team service endpoints (Flask on port 8000)
      '/api/arch_team': {
        target: `http://localhost:${ARCH_TEAM_PORT}`,
        changeOrigin: true
      },
      '/api/workflow': {
        target: `http://localhost:${ARCH_TEAM_PORT}`,
        changeOrigin: true
      },
      '/api/clarification': {
        target: `http://localhost:${ARCH_TEAM_PORT}`,
        changeOrigin: true
      },
      '/api/validation/run': {
        target: `http://localhost:${ARCH_TEAM_PORT}`,
        changeOrigin: true
      },
      // Main backend endpoints (FastAPI on port 8087)
      '/api': {
        target: `http://localhost:${BACKEND_PORT}`,
        changeOrigin: true
      },
      '/data': {
        target: `http://localhost:${BACKEND_PORT}`,
        changeOrigin: true
      }
    }
  }
})