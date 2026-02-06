// tests/setup.ts
import { vi } from 'vitest';

// Basic clipboard mock for tests that copy text
Object.assign(globalThis, {
    navigator: {
        clipboard: {
            writeText: vi.fn(async (_t: string) => undefined),
        },
    },
    alert: vi.fn(),
    prompt: vi.fn(),
    confirm: vi.fn(() => true),
});

// Default fetch mock (tests may override case-by-case)
if (!(globalThis as any).fetch) {
    (globalThis as any).fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
}

// Ensure URL blob helpers exist
if (!(globalThis as any).URL) {
    (globalThis as any).URL = {} as any;
}
if (!(globalThis as any).URL.createObjectURL) {
    (globalThis as any).URL.createObjectURL = vi.fn(() => 'blob:mock');
}
if (!(globalThis as any).URL.revokeObjectURL) {
    (globalThis as any).URL.revokeObjectURL = vi.fn();
}

// Polyfill Blob.text() in jsdom if missing
try {
    const hasBlob = typeof (globalThis as any).Blob !== 'undefined';
    const proto = hasBlob ? (globalThis as any).Blob.prototype : undefined;
    if (hasBlob && proto && typeof proto.text !== 'function') {
        proto.text = function thisTextPolyfill(): Promise<string> {
            return new Promise((resolve, reject) => {
                try {
                    const reader = new (globalThis as any).FileReader();
                    reader.onload = () => resolve(String(reader.result || ''));
                    reader.onerror = (e: any) => reject(e);
                    reader.readAsText(this as any);
                } catch (err) {
                    try { resolve(''); } catch { reject(err); }
                }
            });
        };
    }
} catch { /* ignore */ }

// Map global localStorage to window.localStorage in jsdom environment if missing
try {
    if (!(globalThis as any).localStorage && (globalThis as any).window?.localStorage) {
        (globalThis as any).localStorage = (globalThis as any).window.localStorage;
    }
} catch { /* ignore */ }

// Silence websocket wiring in tests
vi.mock('../services/WebSocketClient', () => ({
    setupWebSocket: vi.fn(),
    stopExecution: vi.fn(),
}));
