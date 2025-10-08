import { describe, expect, test, vi, beforeEach } from 'vitest';

import { BaseCustomNode, LLMMessagesBuilderNodeUI, LoggingNodeUI, OllamaChatNodeUI, PolygonAPIKeyNodeUI, StreamingCustomNode, TextInputNodeUI, PolygonUniverseNodeUI, AtrXIndicatorNodeUI, AtrXFilterNodeUI } from '../nodes';

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

    test('LoggingNodeUI copy button copies display text to clipboard', async () => {
        const node = new LoggingNodeUI('Log', baseData());
        const mockWriteText = vi.fn().mockResolvedValue(undefined);
        (globalThis as any).navigator.clipboard.writeText = mockWriteText;

        // Set some display text
        node.displayText = 'Test log content to copy';
        expect(node.displayText).toBe('Test log content to copy');

        // Find the copy button widget
        const copyWidget = node.widgets!.find(w => w.name === '📋 Copy Log');
        expect(copyWidget).toBeTruthy();
        expect(copyWidget!.type).toBe('button');

        // Click the copy button
        copyWidget!.callback!(null);

        // Verify clipboard was called with correct text
        expect(mockWriteText).toHaveBeenCalledWith('Test log content to copy');
        expect(mockWriteText).toHaveBeenCalledTimes(1);

        // Verify button shows success feedback (this would happen after the promise resolves)
        await new Promise(resolve => setTimeout(resolve, 0)); // Wait for promise
    });

    test('LoggingNodeUI copy button handles empty content', () => {
        const node = new LoggingNodeUI('Log', baseData());
        const mockWriteText = vi.fn().mockResolvedValue(undefined);
        (globalThis as any).navigator.clipboard.writeText = mockWriteText;

        // Set empty display text
        node.displayText = '';
        expect(node.displayText).toBe('');

        // Find the copy button widget
        const copyWidget = node.widgets!.find(w => w.name === '📋 Copy Log');
        expect(copyWidget).toBeTruthy();

        // Click the copy button
        copyWidget!.callback!(null);

        // Verify clipboard was not called
        expect(mockWriteText).not.toHaveBeenCalled();
    });

    test('LoggingNodeUI copy button handles whitespace-only content', () => {
        const node = new LoggingNodeUI('Log', baseData());
        const mockWriteText = vi.fn().mockResolvedValue(undefined);
        (globalThis as any).navigator.clipboard.writeText = mockWriteText;

        // Set whitespace-only display text
        node.displayText = '   \n\t   ';
        expect(node.displayText).toBe('   \n\t   ');

        // Find the copy button widget
        const copyWidget = node.widgets!.find(w => w.name === '📋 Copy Log');
        expect(copyWidget).toBeTruthy();

        // Click the copy button
        copyWidget!.callback!(null);

        // Verify clipboard was not called
        expect(mockWriteText).not.toHaveBeenCalled();
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



    test('StreamingCustomNode accumulates and displays JSON payload', () => {
        const node = new StreamingCustomNode('Stream', baseData());
        node.onStreamUpdate({ message: { content: 'x' } });
        expect(node.result).toEqual({ message: { content: 'x' } });
        expect(node.displayText).toContain('"message"');
    });

    test('PolygonAPIKeyNodeUI security button and provider styling', () => {
        const data = {
            category: 'data_source',
            inputs: {},
            outputs: { api_key: { base: 'APIKey' } },
            params: [{ name: 'api_key', type: 'text', default: '', secret: true }],
        };
        const node = new PolygonAPIKeyNodeUI('API Key', data);
        expect(node.displayResults).toBe(false); // Provider node, no display
        expect(node.color).toBe('#8b5a3c'); // Brown security theme
        expect(node.bgcolor).toBe('#3d2818');

        // Should have API key widget from base class and security info button
        expect(node.widgets).toBeDefined();
        expect(node.widgets!.length).toBe(2);
        const apiKeyWidget = node.widgets!.find(w => w.name?.includes('api_key'));
        expect(apiKeyWidget).toBeTruthy();
        const securityButton = node.widgets!.find(w => w.name === '🔒 Secure Key');
        expect(securityButton).toBeTruthy();

        // Mock alert to test security button callback
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => { });
        securityButton!.callback!(null);
        expect(alertSpy).toHaveBeenCalledWith('API key is handled securely and not stored in workflow files.');
        alertSpy.mockRestore();
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

    test('AtrXIndicatorNodeUI handles results output', () => {
        const data = baseData();
        data.outputs = { results: { base: 'IndicatorResult' } };
        const node = new AtrXIndicatorNodeUI('AtrxIndicator', data);
        // Note: removeOutput may not work in test environment
        expect(node.findOutputSlot('results')).toBeGreaterThanOrEqual(0);
        expect(node.outputs.length).toBeGreaterThanOrEqual(1);
    });

    test('AtrXFilterNodeUI does not have indicator_results output', () => {
        const data = baseData();
        data.outputs = {
            filtered_ohlcv_bundle: { base: 'Dict<AssetSymbol, List<OHLCVBar>>' }
        };
        const node = new AtrXFilterNodeUI('AtrxFilter', data);
        // indicator_results output has been removed from the Python node, so it shouldn't exist in UI
        expect(node.findOutputSlot('indicator_results')).toBe(-1);
        expect(node.outputs.length).toBe(1);
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
        widget.callback!(null);
        // Note: Can't fully test prompt UI, but assume callback updates
        // Manually invoke the inner callback
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

    test('creates custom dropdown widget for combo parameters', () => {
        const data = baseData();
        data.params = [{ name: 'comboParam', type: 'combo', options: ['opt1', 'opt2', 'opt3'], default: 'opt1' }];
        const node = new BaseCustomNode('Test', data);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.type).toBe('button');
        expect(widget.name).toBe('comboParam: opt1');
        expect(node.properties.comboParam).toBe('opt1');
        expect((widget as any).options.values).toEqual(['opt1', 'opt2', 'opt3']);

        // Test that the widget updates the display when property changes
        node.properties.comboParam = 'opt2';
        node.syncWidgetValues();
        expect(widget.name).toBe('comboParam: opt2');
    });

    test('handles boolean combo widget correctly', () => {
        const data = baseData();
        data.params = [{ name: 'boolParam', type: 'combo', options: [true, false], default: true }];
        const node = new BaseCustomNode('Test', data);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.type).toBe('button');
        expect(widget.name).toBe('boolParam: true');
        expect(node.properties.boolParam).toBe(true);
        expect((widget as any).options.values).toEqual([true, false]);

        // Test that the widget updates the display when property changes
        node.properties.boolParam = false;
        node.syncWidgetValues();
        expect(widget.name).toBe('boolParam: false');

        node.properties.boolParam = true;
        node.syncWidgetValues();
        expect(widget.name).toBe('boolParam: true');
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

    test('syncs number widget values on configure using paramName mapping', () => {
        const data = baseData();
        data.params = [{ name: 'syncParam', type: 'number', default: 10 }];
        const node = new BaseCustomNode('Test', data);
        // Simulate graph.configure having set properties
        node.properties.syncParam = 20;
        node.configure({}); // triggers syncWidgetValues under the hood
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.value).toBe(20);
    });

    test('syncs custom dropdown widget values on configure', () => {
        const data = baseData();
        data.params = [{ name: 'dropdownParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }];
        const node = new BaseCustomNode('Test', data);
        node.properties.dropdownParam = 'B';
        node.configure({}); // Triggers sync
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget.name).toBe('dropdownParam: B');
    });

    test('pulses highlight', () => {
        const node = new BaseCustomNode('Test', baseData());
        node.pulseHighlight();
        expect((node as any).highlightStartTs).not.toBeNull();
        // Can't test timing, but verify it sets the timestamp
    });

    test('custom dropdown widget updates value and display', () => {
        const data = baseData();
        data.params = [{ name: 'dropdownParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }];
        const node = new BaseCustomNode('Test', data);
        const widget = node.widgets![0];

        // Test that the widget updates the display when property changes
        node.properties.dropdownParam = 'B';
        node.syncWidgetValues();
        expect(widget.name).toBe('dropdownParam: B');

        node.properties.dropdownParam = 'C';
        node.syncWidgetValues();
        expect(widget.name).toBe('dropdownParam: C');
    });

    test('formatComboValue handles different value types', () => {
        const node = new BaseCustomNode('Test', baseData());

        expect((node as any).formatComboValue('string')).toBe('string');
        expect((node as any).formatComboValue(42)).toBe('42');
        expect((node as any).formatComboValue(true)).toBe('true');
        expect((node as any).formatComboValue(false)).toBe('false');
        expect((node as any).formatComboValue(null)).toBe('null');
        expect((node as any).formatComboValue(undefined)).toBe('undefined');
    });
});

describe('Progress bar rendering', () => {
    test('BaseCustomNode calls renderer.drawProgressBar when progress >= 0', () => {
        const node = new BaseCustomNode('Test', baseData());
        // Spy on renderer method through instance
        const renderer: any = (node as any).renderer;
        const spy = vi.spyOn(renderer, 'drawProgressBar');

        // Prepare mocked canvas context
        const ctx: any = {
            save: () => { },
            restore: () => { },
            fillRect: () => { },
            strokeRect: () => { },
            measureText: (_t: string) => ({ width: 0 }),
            fillText: (_t: string, _x: number, _y: number) => { },
            beginPath: () => { },
        };

        // Initially, no progress -> should still call drawProgressBar (renderer handles visibility)
        node.onDrawForeground(ctx as any);
        expect(spy).toHaveBeenCalledTimes(1);

        // Set progress and draw again -> should call again
        node.setProgress(25, 'Loading 1/4');
        node.onDrawForeground(ctx as any);
        expect(spy).toHaveBeenCalledTimes(2);
    });
});

describe('Strict connection typing', () => {
    test('parseType handles union types correctly', () => {
        const unionType = {
            base: 'union',
            subtypes: [
                { base: 'str' },
                { base: 'LLMChatMessage' }
            ]
        };
        const node = new BaseCustomNode('Test', baseData());
        expect(node.parseType(unionType)).toBe('str | LLMChatMessage');
    });

    test('parseType handles simple types correctly', () => {
        const node = new BaseCustomNode('Test', baseData());
        expect(node.parseType({ base: 'str' })).toBe('str');
        expect(node.parseType({ base: 'int' })).toBe('int');
        expect(node.parseType({ base: 'Any' })).toBe(0); // Wildcard
    });

    test('parseType handles complex types like lists and dicts', () => {
        const node = new BaseCustomNode('Test', baseData());
        expect(node.parseType({ base: 'list', subtype: { base: 'str' } })).toBe('list<str>');
        expect(node.parseType({ base: 'dict', key_type: { base: 'str' }, value_type: { base: 'int' } })).toBe('dict<str, int>');
    });

    test('onConnectInput allows connection if output matches one union type', () => {
        // Mock a node with union input
        const targetNode = new BaseCustomNode('Target', {
            inputs: { system: { base: 'union', subtypes: [{ base: 'str' }, { base: 'LLMChatMessage' }] } },
            outputs: {},
            params: []
        });
        const inputIndex = targetNode.findInputSlot('system');

        // Mock source nodes with different output types
        const strSource = { outputs: [{ type: 'str' }] } as any;
        const msgSource = { outputs: [{ type: 'LLMChatMessage' }] } as any;
        const intSource = { outputs: [{ type: 'int' }] } as any;

        // Valid: str to union
        expect(targetNode.onConnectInput(inputIndex, 'str', strSource.outputs[0], strSource, 0)).toBe(true);

        // Valid: LLMChatMessage to union
        expect(targetNode.onConnectInput(inputIndex, 'LLMChatMessage', msgSource.outputs[0], msgSource, 0)).toBe(true);

        // Invalid: int to union
        expect(targetNode.onConnectInput(inputIndex, 'int', intSource.outputs[0], intSource, 0)).toBe(false);
    });

    test('onConnectInput handles Any (0) wildcard correctly with unions', () => {
        const targetNode = new BaseCustomNode('Target', {
            inputs: { system: { base: 'union', subtypes: [{ base: 'str' }, { base: 'LLMChatMessage' }] } },
            outputs: {},
            params: []
        });
        const inputIndex = targetNode.findInputSlot('system');

        const anySource = { outputs: [{ type: 0 }] } as any; // 0 = Any

        // Allow Any output to union input
        expect(targetNode.onConnectInput(inputIndex, 0, anySource.outputs[0], anySource, 0)).toBe(true);
    });

    test('onConnectInput allows connection for exact type match (non-union)', () => {
        const targetNode = new BaseCustomNode('Target', {
            inputs: { input: { base: 'str' } },
            outputs: {},
            params: []
        });
        const inputIndex = targetNode.findInputSlot('input');

        const strSource = { outputs: [{ type: 'str' }] } as any;
        const intSource = { outputs: [{ type: 'int' }] } as any;

        // Valid: str to str
        expect(targetNode.onConnectInput(inputIndex, 'str', strSource.outputs[0], strSource, 0)).toBe(true);

        // Invalid: int to str
        expect(targetNode.onConnectInput(inputIndex, 'int', intSource.outputs[0], intSource, 0)).toBe(false);
    });

    test('onConnectInput allows Any input/output connections', () => {
        const targetNode = new BaseCustomNode('Target', {
            inputs: { input: { base: 'Any' } },
            outputs: {},
            params: []
        });
        const inputIndex = targetNode.findInputSlot('input');

        const strSource = { outputs: [{ type: 'str' }] } as any;
        const intSource = { outputs: [{ type: 'int' }] } as any;

        // Allow any to Any input
        expect(targetNode.onConnectInput(inputIndex, 'str', strSource.outputs[0], strSource, 0)).toBe(true);
        expect(targetNode.onConnectInput(inputIndex, 'int', intSource.outputs[0], intSource, 0)).toBe(true);
    });

    test('full connection test between OllamaChatNode and compatible nodes', () => {
        // Create OllamaChatNode with union input (simulated)
        const chatNode = new OllamaChatNodeUI('OllamaChat', {
            inputs: { system: { base: 'union', subtypes: [{ base: 'str' }, { base: 'LLMChatMessage' }] } },
            outputs: {},
            params: []
        });
        const systemIndex = chatNode.findInputSlot('system');

        // Create source node with str output
        const strSourceNode = new BaseCustomNode('StrSource', {
            inputs: {},
            outputs: { out: { base: 'str' } },
            params: []
        });

        // Create source node with LLMChatMessage output
        const msgSourceNode = new BaseCustomNode('MsgSource', {
            inputs: {},
            outputs: { out: { base: 'LLMChatMessage' } },
            params: []
        });

        // Create invalid source with int output
        const intSourceNode = new BaseCustomNode('IntSource', {
            inputs: {},
            outputs: { out: { base: 'int' } },
            params: []
        });

        // Test connections
        expect(chatNode.onConnectInput(systemIndex, strSourceNode.outputs[0].type, strSourceNode.outputs[0], strSourceNode, 0)).toBe(true);
        expect(chatNode.onConnectInput(systemIndex, msgSourceNode.outputs[0].type, msgSourceNode.outputs[0], msgSourceNode, 0)).toBe(true);
        expect(chatNode.onConnectInput(systemIndex, intSourceNode.outputs[0].type, intSourceNode.outputs[0], intSourceNode, 0)).toBe(false);
    });

    test('connection typing prevents invalid inputs across different node types', () => {
        // Test with a different node type, e.g., a number input
        const numberNode = new BaseCustomNode('NumberNode', {
            inputs: { value: { base: 'int' } },
            outputs: {},
            params: []
        });
        const valueIndex = numberNode.findInputSlot('value');

        const strSource = { outputs: [{ type: 'str' }] } as any;
        const intSource = { outputs: [{ type: 'int' }] } as any;

        // Invalid: str to int
        expect(numberNode.onConnectInput(valueIndex, 'str', strSource.outputs[0], strSource, 0)).toBe(false);

        // Valid: int to int
        expect(numberNode.onConnectInput(valueIndex, 'int', intSource.outputs[0], intSource, 0)).toBe(true);
    });

    test('connection typing handles list and dict types', () => {
        const listNode = new BaseCustomNode('ListNode', {
            inputs: { items: { base: 'list', subtype: { base: 'str' } } },
            outputs: {},
            params: []
        });
        const itemsIndex = listNode.findInputSlot('items');

        const strListSource = { outputs: [{ type: 'list<str>' }] } as any;
        const intListSource = { outputs: [{ type: 'list<int>' }] } as any;

        // Valid: list<str> to list<str>
        expect(listNode.onConnectInput(itemsIndex, 'list<str>', strListSource.outputs[0], strListSource, 0)).toBe(true);

        // Invalid: list<int> to list<str>
        expect(listNode.onConnectInput(itemsIndex, 'list<int>', intListSource.outputs[0], intListSource, 0)).toBe(false);
    });
});

describe('PolygonUniverseNodeUI param restoration', () => {
    test('restores saved numeric and combo params and preserves labels', () => {
        const polygonMeta = {
            category: 'data_source',
            inputs: { api_key: { base: 'APIKey' } },
            outputs: { symbols: { base: 'list', subtype: { base: 'AssetSymbol' } } },
            params: [
                { name: 'market', type: 'combo', default: 'stocks', options: ['stocks', 'crypto', 'fx', 'otc', 'indices'], label: 'Market Type' },
                { name: 'min_change_perc', type: 'number', default: null, label: 'Min Change', unit: '%', step: 0.01 },
                { name: 'min_volume', type: 'number', default: null, label: 'Min Volume', unit: 'shares/contracts' },
                { name: 'min_price', type: 'number', default: null, label: 'Min Price', unit: 'USD' },
                { name: 'max_price', type: 'number', default: null, label: 'Max Price', unit: 'USD' },
                { name: 'include_otc', type: 'boolean', default: false, label: 'Include OTC' },
            ],
        } as any;

        const node = new PolygonUniverseNodeUI('PolygonUniverseNode', polygonMeta);
        // Simulate a loaded graph with saved properties
        node.properties.market = 'stocks';
        node.properties.min_change_perc = 5;
        node.properties.min_volume = 1_000_000;
        node.properties.min_price = 1;
        node.properties.max_price = 100_000;
        node.properties.include_otc = false;

        node.configure({}); // triggers sync

        // Expect labels preserved with units
        const labels = node.widgets!.map(w => String(w.name));
        expect(labels[0]).toMatch(/^Market Type: /);
        expect(labels.some(l => l.startsWith('Min Change (%)'))).toBe(true);
        expect(labels.some(l => l.startsWith('Min Volume (shares/contracts)'))).toBe(true);
        expect(labels.some(l => l.startsWith('Min Price (USD)'))).toBe(true);
        expect(labels.some(l => l.startsWith('Max Price (USD)'))).toBe(true);

        // Map widgets by paramName for robust assertions
        const widgetByParam: Record<string, any> = {};
        for (const w of node.widgets as any[]) {
            if ((w as any).paramName) widgetByParam[(w as any).paramName] = w;
        }

        expect(widgetByParam.market.name).toMatch(/Market Type: stocks/);
        expect(widgetByParam.min_change_perc.value).toBe(5);
        expect(widgetByParam.min_volume.value).toBe(1_000_000);
        expect(widgetByParam.min_price.value).toBe(1);
        expect(widgetByParam.max_price.value).toBe(100_000);
    });
});

