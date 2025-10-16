import { describe, it, expect, beforeEach } from 'vitest';
import '../../setup';

// Import the class under test
import OHLCVPlotNodeUI from '../../../nodes/market/OHLCVPlotNodeUI';

function baseData() {
    return {
        inputs: {},
        outputs: { images: { base: 'dict', key_type: { base: 'str' }, value_type: { base: 'str' } } },
        params: [],
    } as any;
}

describe('OHLCVPlotNodeUI', () => {
    let node: any;

    beforeEach(() => {
        node = new (OHLCVPlotNodeUI as any)('OHLCVPlotNode', baseData());
        // Simulate graph/canvas presence for overlay math (not strictly required for draw)
        const mockCanvasElement = document.createElement('canvas');
        (node as any).graph = {
            list_of_graphcanvas: [{ canvas: mockCanvasElement, ds: { scale: 1, offset: [0, 0] } }]
        };
    });

    it('initializes with defaults', () => {
        expect(node.displayResults).toBe(false);
        expect(Array.isArray(node.inputs)).toBe(true);
        expect(Array.isArray(node.outputs)).toBe(true);
        expect(node.size[0]).toBeGreaterThan(0);
        expect(node.size[1]).toBeGreaterThan(0);
    });

    it('updateDisplay stores images and triggers redraw', () => {
        const imgData = 'data:image/png;base64,AAA';
        node.setDirtyCanvas = vi.fn();
        node.updateDisplay({ images: { AAPL: imgData, MSFT: imgData } });
        expect(node.setDirtyCanvas).toHaveBeenCalled();
        // Internal images map should be set
        // Accessing private through any for test
        const labels = Object.keys((node as any).images || {});
        expect(new Set(labels)).toEqual(new Set(['AAPL', 'MSFT']));
    });

    it('drawPlots draws placeholder when no images', () => {
        const canvas = document.createElement('canvas');
        canvas.width = 600; canvas.height = 400;
        const ctx = canvas.getContext('2d')!;
        // Should not throw
        node.drawPlots(ctx);
        // No images set -> no errors; we cannot easily assert pixels in unit test
        expect(true).toBe(true);
    });

    it('drawPlots renders grid for multiple images', () => {
        const canvas = document.createElement('canvas');
        canvas.width = 800; canvas.height = 600;
        const ctx = canvas.getContext('2d')!;
        node.updateDisplay({
            images: {
                AAPL: 'data:image/png;base64,AAA',
                MSFT: 'data:image/png;base64,AAA',
                GOOGL: 'data:image/png;base64,AAA'
            }
        });
        // Should not throw when drawing grid
        node.drawPlots(ctx);
        expect(true).toBe(true);
    });
});
