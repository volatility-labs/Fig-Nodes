import { defineConfig } from 'vite';

export default defineConfig({
    base: '/static/',
    server: {
        proxy: {
            '/nodes': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/execute': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
}); 