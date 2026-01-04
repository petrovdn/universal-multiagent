import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Avoid `localhost` → IPv6 (::1) resolution issues in some environments.
        // Backend is typically bound on IPv4 (0.0.0.0/127.0.0.1).
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        // WebSocket proxy target must also avoid IPv6 localhost resolution.
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    // Use esbuild (default) to avoid optional terser dependency during CI builds
    minify: 'esbuild',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        fileSelector: resolve(__dirname, 'file-selector.html'),
        workspaceFolderSelector: resolve(__dirname, 'workspace-folder-selector.html'),
        onecSettings: resolve(__dirname, 'onec-settings.html'),
        projectladSettings: resolve(__dirname, 'projectlad-settings.html')
      },
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom')) {
              return 'react-vendor'
            }
            if (id.includes('lucide-react')) {
              return 'ui-vendor'
            }
          }
        },
      },
    },
  },
  base: '/', // Base path for production
})



