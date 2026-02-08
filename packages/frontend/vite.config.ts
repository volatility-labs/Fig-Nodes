import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/',
  plugins: [react()],
  resolve: {
    alias: {
      // elkjs main entry imports "web-worker" which doesn't exist;
      // redirect to the self-contained bundle that has no external deps.
      elkjs: 'elkjs/lib/elk.bundled.js',
    },
  },
  server: {
    proxy: {
      '^/(api|execute|examples)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
  },
});
