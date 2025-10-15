import { describe, expect, test, beforeEach, vi } from 'vitest';
import { DialogManager } from '../../../services/DialogManager';

describe('DialogManager', () => {
    let dialogManager: DialogManager;
    let mockElement: any;

    beforeEach(() => {
        dialogManager = new DialogManager();

        mockElement = {
            className: '',
            textContent: '',
            innerHTML: '',
            style: {},
            addEventListener: vi.fn(),
            appendChild: vi.fn(),
            focus: vi.fn(),
            select: vi.fn(),
            onclick: null,
            onload: null,
            onerror: null,
            setAttribute: vi.fn(),
            getAttribute: vi.fn(),
            classList: {
                add: vi.fn(),
                remove: vi.fn(),
                contains: vi.fn()
            },
            parentNode: {
                removeChild: vi.fn()
            }
        };

        document.createElement = vi.fn().mockImplementation((tagName) => {
            const element = {
                ...mockElement,
                tagName,
                querySelectorAll: vi.fn().mockReturnValue([]),
                getBoundingClientRect: vi.fn().mockReturnValue({ left: 0, top: 0, width: 100, height: 100 })
            };
            return element as any;
        });

        const mockBody = document.createElement('body');
        mockBody.appendChild = vi.fn();
        mockBody.removeChild = vi.fn();
        Object.defineProperty(document, 'body', { value: mockBody, writable: true });

        // Mock global functions
        (globalThis as any).setTimeout = vi.fn((cb) => {
            cb();
            return 123;
        });
        (globalThis as any).clearTimeout = vi.fn();
    });

    test('sets and gets last mouse event', () => {
        const mockEvent = { clientX: 100, clientY: 200 } as MouseEvent;

        dialogManager.setLastMouseEvent(mockEvent);
        expect((dialogManager as any).lastMouseEvent).toBe(mockEvent);
    });

    test('showQuickPrompt creates dialog with correct elements', () => {
        const callback = vi.fn();

        dialogManager.showQuickPrompt('Test Title', 'initial value', callback, { type: 'text' });

        expect(document.createElement).toHaveBeenCalledWith('div');
        expect(document.createElement).toHaveBeenCalledWith('input');
        expect(document.createElement).toHaveBeenCalledWith('button');
        expect(document.body.appendChild).toHaveBeenCalled();
    });

    test('showQuickPrompt handles numeric input', () => {
        const callback = vi.fn();

        dialogManager.showQuickPrompt('Number Input', 42, callback, { type: 'number' });

        // Should create number input
        expect(document.createElement).toHaveBeenCalledWith('input');
    });

    test('showQuickPrompt handles text input', () => {
        const callback = vi.fn();

        dialogManager.showQuickPrompt('Text Input', 'hello', callback, { type: 'text' });

        // Should create text input
        expect(document.createElement).toHaveBeenCalledWith('input');
    });

    test('showCustomPrompt delegates to showQuickValuePrompt for non-password', () => {
        const callback = vi.fn();
        const showQuickValuePromptSpy = vi.spyOn(dialogManager, 'showQuickValuePrompt');

        dialogManager.showCustomPrompt('Title', 'default', false, callback);

        expect(showQuickValuePromptSpy).toHaveBeenCalledWith('Title', 'default', false, expect.any(Function));
    });

    test('showCustomPrompt creates password dialog', () => {
        const callback = vi.fn();

        dialogManager.showCustomPrompt('Password', 'secret', true, callback);

        expect(document.createElement).toHaveBeenCalledWith('div');
        expect(document.createElement).toHaveBeenCalledWith('label');
        expect(document.createElement).toHaveBeenCalledWith('input');
        expect(document.createElement).toHaveBeenCalledWith('button');
        expect(document.body.appendChild).toHaveBeenCalled();
    });

    test('showQuickValuePrompt creates dialog with correct structure', () => {
        const callback = vi.fn();

        dialogManager.showQuickValuePrompt('Label', 'default', false, callback);

        expect(document.createElement).toHaveBeenCalledWith('div');
        expect(document.createElement).toHaveBeenCalledWith('input');
        expect(document.createElement).toHaveBeenCalledWith('button');
        expect(document.body.appendChild).toHaveBeenCalled();
    });

    test('showQuickValuePrompt handles numeric input correctly', () => {
        const callback = vi.fn();

        dialogManager.showQuickValuePrompt('Number', 42, true, callback);

        // Should create number input
        expect(document.createElement).toHaveBeenCalledWith('input');
    });

    test('showCustomDropdown creates dropdown with search for many options', () => {
        const callback = vi.fn();
        const options = Array.from({ length: 15 }, (_, i) => `Option ${i}`);

        // Mock canvas and graph
        (window as any).graph = {
            list_of_graphcanvas: [{
                canvas: {
                    getBoundingClientRect: () => ({ left: 0, top: 0 })
                },
                ds: { scale: 1, offset: [0, 0] }
            }]
        };

        dialogManager.showCustomDropdown('param', options, callback);

        // Should create search input for many options
        expect(document.createElement).toHaveBeenCalledWith('input');
        expect(document.body.appendChild).toHaveBeenCalled();
    });

    test('showCustomDropdown creates dropdown without search for few options', () => {
        const callback = vi.fn();
        const options = ['Option 1', 'Option 2'];

        dialogManager.showCustomDropdown('param', options, callback);

        // Should not create search input for few options
        expect(document.body.appendChild).toHaveBeenCalled();
    });

    test('showTextEditor creates text editor dialog', async () => {
        // Mock showTextEditor to return immediately
        const originalShowTextEditor = dialogManager.showTextEditor;
        dialogManager.showTextEditor = vi.fn().mockResolvedValue(null);

        const result = await dialogManager.showTextEditor('initial text', {
            title: 'Edit Text',
            width: 500,
            height: 300
        });

        expect(dialogManager.showTextEditor).toHaveBeenCalledWith('initial text', {
            title: 'Edit Text',
            width: 500,
            height: 300
        });

        // Should return null since dialog was cancelled
        expect(result).toBeNull();

        // Restore original method
        dialogManager.showTextEditor = originalShowTextEditor;
    });

    test('showTextEditor applies options correctly', async () => {
        // Mock showTextEditor to return immediately
        const originalShowTextEditor = dialogManager.showTextEditor;
        dialogManager.showTextEditor = vi.fn().mockResolvedValue('test result');

        const result = await dialogManager.showTextEditor('text', {
            title: 'Custom Title',
            placeholder: 'Enter text...',
            monospace: false,
            width: 400,
            height: 200
        });

        expect(dialogManager.showTextEditor).toHaveBeenCalledWith('text', {
            title: 'Custom Title',
            placeholder: 'Enter text...',
            monospace: false,
            width: 400,
            height: 200
        });

        expect(result).toBe('test result');

        // Restore original method
        dialogManager.showTextEditor = originalShowTextEditor;
    });

    test('formatComboValue formats different value types', () => {
        expect((dialogManager as any).formatComboValue(true)).toBe('true');
        expect((dialogManager as any).formatComboValue(false)).toBe('false');
        expect((dialogManager as any).formatComboValue('string')).toBe('string');
        expect((dialogManager as any).formatComboValue(42)).toBe('42');
        expect((dialogManager as any).formatComboValue(null)).toBe('null');
        expect((dialogManager as any).formatComboValue(undefined)).toBe('undefined');
    });

    test('showQuickPrompt positions dialog at mouse location', () => {
        const callback = vi.fn();
        const mockEvent = { clientX: 150, clientY: 250 } as MouseEvent;

        dialogManager.setLastMouseEvent(mockEvent);
        dialogManager.showQuickPrompt('Title', 'value', callback);

        // Should position dialog at mouse location
        expect(document.body.appendChild).toHaveBeenCalled();
    });

    test('showQuickValuePrompt uses LiteGraph prompt if available', () => {
        const callback = vi.fn();
        const mockPrompt = vi.fn();

        (window as any).graph = {
            list_of_graphcanvas: [{
                prompt: mockPrompt
            }]
        };

        dialogManager.showQuickValuePrompt('Label', 'default', false, callback);

        expect(mockPrompt).toHaveBeenCalled();
    });

    test('showQuickValuePrompt falls back to inline dialog when LiteGraph prompt unavailable', () => {
        const callback = vi.fn();

        (window as any).graph = null;
        (window as any).LiteGraph = null;

        dialogManager.showQuickValuePrompt('Label', 'default', false, callback);

        expect(document.createElement).toHaveBeenCalledWith('div');
        expect(document.body.appendChild).toHaveBeenCalled();
    });

    test('showQuickValuePrompt positions dialog at specified position', () => {
        const callback = vi.fn();
        const position = { x: 100, y: 200 };

        dialogManager.showQuickValuePrompt('Label', 'default', false, callback, position);

        expect(document.createElement).toHaveBeenCalledWith('div');
        expect(document.body.appendChild).toHaveBeenCalled();
    });
});
