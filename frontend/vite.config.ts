import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

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
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'ui-vendor': ['lucide-react'],
        },
      },
    },
  },
  base: '/', // Base path for production
})



