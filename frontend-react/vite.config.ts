import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5174, // Different from legacy frontend (5173)
    proxy: {
      // Proxy API calls to FastAPI backend
      '^/(api|execute|examples)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@services': path.resolve(__dirname, './src/services'),
      '@stores': path.resolve(__dirname, './src/stores'),
      '@legacy': path.resolve(__dirname, '../frontend'),
      '@fig-node/litegraph': path.resolve(__dirname, '../frontend/fignode-litegraph.js/dist/litegraph.es.js'),
    },
    conditions: ['import', 'module', 'browser', 'default'],
  },
  optimizeDeps: {
    include: ['react', 'react-dom', '@tanstack/react-query'],
    // Don't exclude @fig-node/litegraph - let Vite process it
  },
});

