import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: ['./tests/setup.ts'],
        include: [
            'tests/unit/**/*.test.ts',
            'tests/integration/**/*.test.ts'
        ],
        exclude: [
            'node_modules',
            'dist',
            'coverage'
        ],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html'],
            exclude: [
                'node_modules/',
                'tests/',
                'coverage/',
                'dist/',
                '**/*.d.ts',
                '**/*.config.*',
                '**/setup.ts'
            ]
        },
        testTimeout: 15000,
        hookTimeout: 15000
    },
    resolve: {
        alias: {
            '@': resolve(__dirname, './'),
            '@/utils': resolve(__dirname, './utils'),
            '@/services': resolve(__dirname, './services'),
            '@/nodes': resolve(__dirname, './nodes')
        }
    }
});
