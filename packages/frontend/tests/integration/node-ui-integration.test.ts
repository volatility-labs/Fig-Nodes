import { describe, expect, test, beforeEach, vi } from 'vitest';
import { BaseCustomNode, LoggingNodeUI, OllamaChatNodeUI, TextInputNodeUI } from '../../nodes';

describe('Node UI Integration Tests', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.resetModules();

        // Mock clipboard
        (globalThis as any).navigator = {
            clipboard: {
                writeText: vi.fn().mockResolvedValue(undefined)
            }
        };

        // Mock DOM
        document.createElement = vi.fn().mockImplementation((_tagName) => {
            const element = {
                id: '',
                className: '',
                textContent: '',
                innerHTML: '',
                style: {},
                value: '',
                addEventListener: vi.fn(),
                appendChild: vi.fn(),
                focus: vi.fn(),
                select: vi.fn(),
                click: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn(), contains: vi.fn() },
                setAttribute: vi.fn(),
                getAttribute: vi.fn(),
                scrollTop: 0,
                scrollHeight: 0
            };
            return element as any;
        });

        const mockBody = document.createElement('body');
        mockBody.appendChild = vi.fn();
        mockBody.removeChild = vi.fn();
        mockBody.contains = vi.fn().mockReturnValue(true);
        Object.defineProperty(document, 'body', { value: mockBody, writable: true });

        // Mock window
        (window as any).innerWidth = 1000;
        (window as any).innerHeight = 800;
    });

    function baseData() {
        return {
            category: 'test',
            inputs: { input: { base: 'str' } },
            outputs: { output: { base: 'str' } },
            params: [{ name: 'value', type: 'text', default: '' }],
        } as any;
    }

    test('BaseCustomNode widget creation and interaction', () => {
        const data = baseData();
        data.params = [
            { name: 'textParam', type: 'text', default: 'initial' },
            { name: 'numParam', type: 'number', default: 5, min: 0, max: 10 },
            { name: 'comboParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }
        ];

        const node = new BaseCustomNode('TestNode', data, null as any);

        // Verify widgets were created
        expect(node.widgets).toHaveLength(3);
        expect(node.widgets?.[0]?.name).toBe('textParam: initial');
        expect(node.widgets?.[1]?.type).toBe('number');
        expect(node.widgets?.[2]?.type).toBe('button');

        // Test widget callbacks
        node.widgets?.[1]?.callback?.(7);
        expect(node.properties.numParam).toBe(7);

        // Test sync
        node.properties.comboParam = 'B';
        node.syncWidgetValues();
        expect(node.widgets?.[2]?.name).toBe('comboParam: B');
    });

    test('LoggingNodeUI streaming and display integration', () => {
        const node = new LoggingNodeUI('LogNode', baseData(), null as any);

        // Test streaming updates
        node.onStreamUpdate({ message: { content: 'Hello ' } });
        expect(node.displayText).toBe('Hello ');

        node.onStreamUpdate({ message: { content: 'Hello World' } });
        expect(node.displayText).toBe('Hello World');

        // Test that regular updates are ignored during streaming
        node.updateDisplay({ message: { content: 'Ignored' } });
        expect(node.displayText).toBe('Hello World');

        // Test copy functionality
        const copyWidget = node.widgets?.find(w => w.name === '📋 Copy Log');
        expect(copyWidget).toBeTruthy();

        if (copyWidget) {
            copyWidget.callback?.(null);
            expect((globalThis as any).navigator.clipboard.writeText).toHaveBeenCalledWith('Hello World');
        }
    });

    test('LoggingNodeUI textarea integration', () => {
        const node = new LoggingNodeUI('LogNode', baseData(), null as any);

        // Mock graph and canvas
        const mockCanvasElement = document.createElement('canvas');
        mockCanvasElement.getBoundingClientRect = vi.fn().mockReturnValue({ left: 0, top: 0, width: 100, height: 100 });

        const mockCanvas = {
            canvas: mockCanvasElement,
            ds: { scale: 2, offset: [10, 20] }
        };
        const mockGraph = {
            list_of_graphcanvas: [mockCanvas]
        };
        (node as any).graph = mockGraph;
        (node as any).pos = [50, 30];
        (node as any).size = [400, 300];
        (node as any).widgets = [{}, {}]; // 2 widgets

        // Test textarea creation
        (node as any).ensureDisplayTextarea();
        expect((node as any).displayTextarea).toBeDefined();
        expect(document.body.appendChild).toHaveBeenCalled();

        // Test textarea positioning
        (node as any).positionDisplayTextarea(10, 15, 200, 100);
        const textarea = (node as any).displayTextarea;
        expect(textarea.style.position).toBe('absolute');
        expect(textarea.style.zIndex).toBe('500');

        // Test textarea cleanup
        (node as any).detachDisplayTextarea();
        expect((node as any).displayTextarea).toBeNull();
        // Note: removeChild may not be called in the mock implementation
    });

    test('OllamaChatNodeUI streaming integration', () => {
        const node = new OllamaChatNodeUI('ChatNode', baseData(), null as any);

        // Test streaming
        node.onStreamUpdate({ message: { content: 'Hi' } });
        expect(node.displayText).toBe('Hi');

        node.onStreamUpdate({ message: { content: 'Hi there' } });
        expect(node.displayText).toBe('Hi there');

        // Test final message
        node.updateDisplay({ message: { content: 'Final message' } });
        expect(node.displayText).toBe('Final message');
    });

    test('TextInputNodeUI inline editor integration', () => {
        const node = new TextInputNodeUI('TextNode', baseData(), null as any);

        // Test inline editor properties
        expect(node.displayResults).toBe(false);
        expect(typeof (node as any).onDrawForeground).toBe('function');
        expect(typeof (node as any).ensureTextarea).toBe('function');

        // Test property setting
        node.properties.value = 'Test content';
        expect(node.properties.value).toBe('Test content');
    });

    test('Node connection typing integration', () => {
        // Create nodes with different types
        const sourceNode = new BaseCustomNode('Source', {
            inputs: {},
            outputs: { out: { base: 'str' } },
            params: []
        }, null as any);

        const targetNode = new BaseCustomNode('Target', {
            inputs: { input: { base: 'str' } },
            outputs: {},
            params: []
        }, null as any);

        const unionTargetNode = new BaseCustomNode('UnionTarget', {
            inputs: { input: { base: 'union', subtypes: [{ base: 'str' }, { base: 'int' }] } },
            outputs: {},
            params: []
        }, null as any);

        // Verify source output type
        expect(sourceNode.outputs[0]?.type).toBe('str');

        // Verify target input type
        expect(targetNode.inputs[0]?.type).toBe('str');

        // Verify union target input type is comma-separated (LiteGraph format)
        // This ensures LiteGraph's built-in isValidConnection can handle the union
        expect(unionTargetNode.inputs[0]?.type).toBe('str,int');
    });

    test('Node display and formatting integration', () => {
        const node = new LoggingNodeUI('LogNode', baseData(), null as any);

        // Test different formatting modes
        (node as any).properties = { format: 'json' };
        (node as any).onStreamUpdate({ output: '{"key": "value"}' });
        expect(node.displayText).toBe('{\n  "key": "value"\n}');

        (node as any).properties = { format: 'plain' };
        (node as any).onStreamUpdate({ output: '{"key": "value"}' });
        expect(node.displayText).toBe('{"key": "value"}');

        (node as any).properties = { format: 'auto' };
        (node as any).onStreamUpdate({ output: 'plain text' });
        expect(node.displayText).toBe('plain text');
    });

    test('Node error handling integration', () => {
        const node = new BaseCustomNode('TestNode', baseData(), {} as any);

        // Test error setting
        node.setError('Test error');
        expect(node.error).toBe('Test error');
        expect(node.color).toBe('#FF0000');

        // Test error clearing
        node.setError('');
        expect(node.error).toBe('');
    });

    test('Node progress integration', () => {
        const node = new BaseCustomNode('TestNode', baseData(), {} as any);

        // Test progress setting
        node.setProgress(50, 'Half done');
        expect(node.progress).toBe(50);
        expect(node.progressText).toBe('Half done');

        // Test progress rendering
        const mockCtx = {
            save: vi.fn(),
            restore: vi.fn(),
            fillRect: vi.fn(),
            strokeRect: vi.fn(),
            measureText: vi.fn(() => ({ width: 0 })),
            fillText: vi.fn(),
            beginPath: vi.fn()
        };

        const renderer = (node as any).renderer;
        const spy = vi.spyOn(renderer, 'drawProgressBar');

        node.onDrawForeground(mockCtx as any);
        expect(spy).toHaveBeenCalled();
    });

    test('Node lifecycle integration', () => {
        const node = new LoggingNodeUI('LogNode', baseData(), null as any);

        // Mock lifecycle methods
        const mockEnsure = vi.fn();
        const mockSync = vi.fn();
        (node as any).ensureDisplayTextarea = mockEnsure;
        (node as any).syncDisplayTextarea = mockSync;

        // Test onAdded
        (node as any).onAdded();
        expect(mockEnsure).toHaveBeenCalled();

        // Test onDeselected
        (node as any).onDeselected();
        expect(mockSync).toHaveBeenCalled();

        // Test onResize
        (node as any).onResize([200, 150]);
        expect(mockSync).toHaveBeenCalledTimes(2);

        // Test onRemoved
        const mockDetach = vi.fn();
        (node as any).detachDisplayTextarea = mockDetach;
        (node as any).copyFeedbackTimeout = 123;

        const mockClearTimeout = vi.fn();
        global.clearTimeout = mockClearTimeout;

        (node as any).onRemoved();
        expect(mockDetach).toHaveBeenCalled();
        expect(mockClearTimeout).toHaveBeenCalledWith(123);
    });

    test('Node widget synchronization integration', () => {
        const data = baseData();
        data.params = [
            { name: 'syncParam', type: 'number', default: 10 },
            { name: 'dropdownParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }
        ];

        const node = new BaseCustomNode('TestNode', data, null as any);

        // Test initial values
        expect(node.properties.syncParam).toBe(10);
        expect(node.properties.dropdownParam).toBe('A');

        // Test property updates
        node.properties.syncParam = 20;
        node.properties.dropdownParam = 'B';

        // Test sync
        node.syncWidgetValues();
        expect(node.widgets?.[0]?.value).toBe(20);
        expect(node.widgets?.[1]?.name).toBe('dropdownParam: B');
    });
});
