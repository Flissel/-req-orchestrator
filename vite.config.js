import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

// Port configuration from environment variables with fallback defaults
// Note: Vite only exposes env vars prefixed with VITE_ to the client
const FRONTEND_PORT = parseInt(process.env.FRONTEND_PORT || '4000')
const BACKEND_PORT = parseInt(process.env.VITE_BACKEND_PORT || process.env.BACKEND_PORT || '8087')

// Note: ARCH_TEAM_PORT no longer needed - arch_team routes now handled by FastAPI

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    allowedHosts: ['host.docker.internal', 'localhost'],
    proxy: {
      // All API routes now go to FastAPI backend (port 8087)
      // arch_team, mining, kg, rag, validation, clarification, workflow routes
      // are all handled by arch_team_router in FastAPI
      "/api": {
        target: `http://localhost:${BACKEND_PORT}`,
        changeOrigin: true
      },
      "/data": {
        target: `http://localhost:${BACKEND_PORT}`,
        changeOrigin: true
      }
    }
  }
})