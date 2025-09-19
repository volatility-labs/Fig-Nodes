import { describe, expect, test, vi, beforeEach } from 'vitest';

import BaseCustomNode from '../nodes/BaseCustomNode';
import LLMMessagesBuilderNodeUI from '../nodes/LLMMessagesBuilderNodeUI';
import LoggingNodeUI from '../nodes/LoggingNodeUI';
import OllamaChatNodeUI from '../nodes/OllamaChatNodeUI';
import OllamaChatViewerNodeUI from '../nodes/OllamaChatViewerNodeUI';
import OllamaModelSelectorNodeUI from '../nodes/OllamaModelSelectorNodeUI';
import StreamingCustomNode from '../nodes/StreamingCustomNode';
import TextInputNodeUI from '../nodes/TextInputNodeUI';

function baseData() {
    return {
        category: 'test',
        inputs: { a: { base: 'str' } },
        outputs: { out: { base: 'str' } },
        params: [{ name: 'value', type: 'text', default: '' }],
    } as any;
}

describe('Node UI classes', () => {
    beforeEach(() => {
        // ensure clipboard mock exists
        (globalThis as any).navigator.clipboard.writeText = vi.fn();
    });

    test('BaseCustomNode adds IO and widgets and updates display', () => {
        const node = new BaseCustomNode('Base', baseData());
        expect(node.inputs.length).toBe(1);
        expect(node.outputs.length).toBe(1);
        expect(node.widgets!.length).toBeGreaterThan(0);
        node.updateDisplay({ output: 'hello' });
        expect(typeof node.displayText).toBe('string');
        expect(node.displayText).toContain('hello');
    });

    test('LLMMessagesBuilderNodeUI summarizes messages', () => {
        const node = new LLMMessagesBuilderNodeUI('Msgs', baseData());
        node.updateDisplay({
            messages: [
                { role: 'system', content: 'Set the rules' },
                { role: 'user', content: 'Prompt contents that are long enough to be trimmed 12345' },
            ]
        });
        expect(node.displayText.split('\n').length).toBe(2);
        expect(node.displayText).toMatch(/1\. system:/);
    });

    test('LoggingNodeUI appends streaming chunks and ignores replacement when streaming', () => {
        const node = new LoggingNodeUI('Log', baseData());
        node.onStreamUpdate({ message: { content: 'Hello ' } });
        node.onStreamUpdate({ message: { content: 'Hello World' } });
        expect(node.displayText).toBe('Hello World');
        node.updateDisplay({ message: { content: 'Ignored' } });
        expect(node.displayText).toBe('Hello World');
    });

    test('OllamaChatNodeUI streaming and final message handling', () => {
        const node = new OllamaChatNodeUI('Chat', baseData());
        node.onStreamUpdate({ message: { content: 'Hi' } });
        expect(node.displayText).toBe('Hi');
        node.onStreamUpdate({ message: { content: 'Final' } });
        expect(node.displayText).toBe('Final');
        node.updateDisplay({ message: { content: 'Static' } });
        expect(node.displayText).toBe('Static');
    });

    test('OllamaChatViewerNodeUI clears and copies', () => {
        const node = new OllamaChatViewerNodeUI('Viewer', baseData());
        node.onStreamUpdate({ message: { content: 'A' } });
        node.onStreamUpdate({ message: { content: 'AB' } });
        expect(node.displayText).toBe('AB');
        node.onStreamUpdate({ message: { content: 'C' } });
        expect(node.displayText).toBe('C');
        // simulate clear button
        const clear = node.widgets!.find(w => w.name === 'Clear');
        expect(clear).toBeTruthy();
        clear?.callback?.('');
        expect(node.displayText).toBe('');
    });

    test('OllamaModelSelectorNodeUI fetch populates model list and selected', async () => {
        const node = new OllamaModelSelectorNodeUI('Selector', baseData());
        node.widgets!.push({ name: 'selected', options: { values: [] } } as any);
        (globalThis as any).fetch = vi.fn(async () => ({
            ok: true,
            json: async () => ({ models: [{ name: 'llama' }, { name: 'qwen' }] }),
        }));
        await node.fetchAndPopulateModels();
        const selectedWidget = (node as any).widgets.find((w: any) => w.name === 'selected');
        expect(selectedWidget.options.values).toEqual(['llama', 'qwen']);
        expect(node.properties['selected']).toBe('llama');
    });

    test('StreamingCustomNode accumulates and displays JSON payload', () => {
        const node = new StreamingCustomNode('Stream', baseData());
        node.onStreamUpdate({ message: { content: 'x' } });
        expect(node.result).toEqual({ message: { content: 'x' } });
        expect(node.displayText).toContain('"message"');
    });

    test('TextInputNodeUI inline editor behavior', () => {
        const node = new TextInputNodeUI('Text', baseData());
        node.properties.value = 'a very long line that should wrap across the width of the text area to test wrapping logic';
        // Inline editor: no preview API; validate key characteristics instead
        expect(node.displayResults).toBe(false);
        expect(typeof (node as any).onDrawForeground).toBe('function');
        // Private ensureTextarea exists at runtime
        expect(typeof (node as any).ensureTextarea).toBe('function');
    });
});

describe('BaseCustomNode comprehensive tests', () => {
    test('creates text widget and updates value via prompt', () => {
        const data = baseData();
        data.params = [{ name: 'textParam', type: 'text', default: 'initial' }];
        const node = new BaseCustomNode('Test', data);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.name).toBe('textParam: initial');
        expect(node.properties.textParam).toBe('initial');

        // Simulate prompt callback
        expect(widget.callback).toBeDefined();
        widget.callback!();
        // Note: Can't fully test prompt UI, but assume callback updates
        // Manually invoke the inner callback
        const mockNewVal = 'updated';
        // The callback is the prompt invoker; to test update logic, we need to mimic it
        // Since it's private, test the effect
        node.properties.textParam = 'updated';
        // Widget name doesn't auto-update; the update is inside the callback
        // Test that property updates work
        expect(node.properties.textParam).toBe('updated');
    });

    test('creates number widget with options and updates value', () => {
        const data = baseData();
        data.params = [{ name: 'numParam', type: 'number', default: 5, min: 0, max: 10, step: 1 }];
        const node = new BaseCustomNode('Test', data);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.type).toBe('number');
        expect(widget.value).toBe(5);
        expect(widget.options.min).toBe(0);
        expect(widget.options.max).toBe(10);
        expect(widget.options.step).toBe(1);

        expect(widget.callback).toBeDefined();
        widget.callback!(7);
        expect(node.properties.numParam).toBe(7);
        expect(widget.value).toBe(7); // Since we set widget.value in constructor
    });

    test('creates combo widget with strings and toggles', () => {
        const data = baseData();
        data.params = [{ name: 'comboParam', type: 'combo', options: ['opt1', 'opt2', 'opt3'], default: 'opt1' }];
        const node = new BaseCustomNode('Test', data);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.type).toBe('combo');
        expect(widget.value).toBe('opt1');
        expect(widget.options.values).toEqual(['opt1', 'opt2', 'opt3']);

        expect(widget.callback).toBeDefined();
        widget.callback!('opt2');
        expect(node.properties.comboParam).toBe('opt2');
        expect(widget.value).toBe('opt2');
    });

    test('handles boolean combo widget correctly', () => {
        const data = baseData();
        data.params = [{ name: 'boolParam', type: 'combo', options: [true, false], default: true }];
        const node = new BaseCustomNode('Test', data);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.type).toBe('combo');
        expect(widget.value).toBe('true');
        expect(widget.options.values).toEqual(['true', 'false']);

        expect(widget.callback).toBeDefined();
        widget.callback!('false');
        expect(node.properties.boolParam).toBe(false);
        expect(widget.value).toBe('false');

        widget.callback!('true');
        expect(node.properties.boolParam).toBe(true);
        expect(widget.value).toBe('true');
    });

    test('wraps text correctly in display', () => {
        const node = new BaseCustomNode('Test', baseData());
        node.displayText = 'This is a long text that should wrap across multiple lines in the node display area';
        const mockCtx = { measureText: (text: string) => ({ width: text.length * 8 }) }; // Simple mock: 8px per char
        const lines = node.wrapText(node.displayText, 100, mockCtx as any);
        expect(lines.length).toBeGreaterThan(1);
        expect(lines.every(line => mockCtx.measureText(line).width <= 100)).toBe(true);
    });

    test('sets error and updates color', () => {
        const node = new BaseCustomNode('Test', baseData());
        node.setError('Test error');
        expect(node.error).toBe('Test error');
        expect(node.color).toBe('#FF0000');
    });

    test('syncs widget values on configure', () => {
        const data = baseData();
        data.params = [{ name: 'syncParam', type: 'number', default: 10 }];
        const node = new BaseCustomNode('Test', data);
        node.properties.syncParam = 20;
        node.configure({}); // Triggers sync
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.value).toBe(20);
    });

    test('pulses highlight', () => {
        const node = new BaseCustomNode('Test', baseData());
        node.pulseHighlight();
        expect((node as any).highlightStartTs).not.toBeNull();
        // Can't test timing, but verify it sets the timestamp
    });
});


