import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// Vite configuration for InvestPI React Frontend
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8050',
        changeOrigin: true,
      },
      '/healthz': {
        target: 'http://127.0.0.1:8050',
        changeOrigin: true,
      },
      '/apidocs': {
        target: 'http://127.0.0.1:8050',
        changeOrigin: true,
      },
      '/apispec.json': {
        target: 'http://127.0.0.1:8050',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
