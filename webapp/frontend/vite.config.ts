import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { readFileSync } from 'fs'

// package.json is the single source of the version. The Docker build copies the
// same value into the backend image, so the UI, the CHANGELOG and the Ring
// User-Agent cannot drift apart.
const { version } = JSON.parse(readFileSync(path.resolve(__dirname, 'package.json'), 'utf-8'))

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(version) },
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    proxy: {
      '/api':        'http://localhost:8080',
      '/proxy':      'http://localhost:8080',
      '/stream':     'http://localhost:8080',
      '/recordings': 'http://localhost:8080',
      '/ws': { target: 'ws://localhost:8080', ws: true },
    },
  },
})
