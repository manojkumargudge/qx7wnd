import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api is proxied to the FastAPI server; on Vercel it is routed to api/index.py.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
