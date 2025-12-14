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
    host: true, // Listen on all addresses (0.0.0.0)
    strictPort: true,
    port: 5173,
    // Fix HMR when running behind a reverse proxy (SSL)
    hmr: {
        host: 'wl.nandn.cc',
        protocol: 'wss',
    },
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