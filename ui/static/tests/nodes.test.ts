import { describe, expect, test, vi, beforeEach } from 'vitest';
import { LiteGraph, LGraphNode } from '@comfyorg/litegraph';

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
        expect(node.widgets.length).toBeGreaterThan(0);
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
        node.onStreamUpdate({ assistant_text: 'Hello ' });
        node.onStreamUpdate({ assistant_text: 'Hello World' });
        expect(node.displayText).toBe('Hello World');
        node.updateDisplay({ assistant_text: 'Ignored' });
        expect(node.displayText).toBe('Hello World');
    });

    test('OllamaChatNodeUI streaming and final message handling', () => {
        const node = new OllamaChatNodeUI('Chat', baseData());
        node.onStreamUpdate({ assistant_text: 'Hi', assistant_done: false });
        expect(node.displayText).toBe('Hi');
        node.onStreamUpdate({ assistant_message: { content: 'Final' } });
        expect(node.displayText).toBe('Final');
        node.updateDisplay({ output: 'Static' });
        expect(node.displayText).toBe('Static');
    });

    test('OllamaChatViewerNodeUI clears and copies', () => {
        const node = new OllamaChatViewerNodeUI('Viewer', baseData());
        node.onStreamUpdate({ assistant_text: 'A' });
        node.onStreamUpdate({ assistant_text: 'AB' });
        expect(node.displayText).toBe('AB');
        node.onStreamUpdate({ assistant_message: { content: 'C' } });
        expect(node.displayText).toBe('C');
        // simulate clear button
        const clear = node.widgets.find(w => w.name === 'Clear');
        expect(clear).toBeTruthy();
        clear.callback('');
        expect(node.displayText).toBe('');
    });

    test('OllamaModelSelectorNodeUI fetch populates model list and selected', async () => {
        const node = new OllamaModelSelectorNodeUI('Selector', baseData());
        node.widgets.push({ name: 'selected', options: { values: [] } } as any);
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
        node.onStreamUpdate({ assistant_text: 'x' });
        expect(node.result).toEqual({ assistant_text: 'x' });
        expect(node.displayText).toContain('"assistant_text": "x"');
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


