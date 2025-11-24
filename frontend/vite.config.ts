import { defineConfig } from 'vite';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  base: '/',  // Changed from '/static/' - serves at root
  server: {
    proxy: {
      '^/(api|execute|examples)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      '@components': path.resolve(__dirname, './components'),
      '@nodes': path.resolve(__dirname, './nodes'),
      '@utils': path.resolve(__dirname, './utils'),
      '@tests': path.resolve(__dirname, './tests'),
      '@': path.resolve(__dirname, './'),
      '@fig-node/litegraph': path.resolve(__dirname, './fignode-litegraph.js')
    },
  },
  optimizeDeps: {
    include: ['@fig-node/litegraph'],
    exclude: [],
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
  },
}); 