import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, the web app runs on :5173 and forwards /api to the FastAPI backend on :8000.
// In the Render build, FastAPI serves the built files itself (one origin).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
