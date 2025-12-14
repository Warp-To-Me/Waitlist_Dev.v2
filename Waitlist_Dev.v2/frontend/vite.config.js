import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  base: '/static/dist/', // IMPORTANT: Base URL for assets in production/django
  build: {
    // Output to Django's static directory
    outDir: '../static/dist',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        main: './index.html',
      },
    },
  },
  server: {
    // Proxy API requests to Django during development
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
      '/static': 'http://127.0.0.1:8000',
    }
  }
})