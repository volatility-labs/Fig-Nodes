import { describe, expect, test, beforeEach, vi } from 'vitest';
import { LinkModeManager } from '../../../services/LinkModeManager';

describe('LinkModeManager', () => {
    let linkModeManager: LinkModeManager;
    let mockCanvas: any;

    beforeEach(() => {
        mockCanvas = {
            links_render_mode: 0,
            render_curved_connections: false,
            setDirty: vi.fn()
        };

        linkModeManager = new LinkModeManager(mockCanvas);

        // Mock DOM element
        const mockButton = {
            textContent: '',
            title: ''
        };

        document.getElementById = vi.fn().mockReturnValue(mockButton as any);
    });

    test('initializes with default curved mode', () => {
        expect(linkModeManager.getCurrentLinkMode()).toBe(2); // SPLINE_LINK
        expect(mockCanvas.links_render_mode).toBe(2);
        expect(mockCanvas.render_curved_connections).toBe(true);
    });

    test('applyLinkMode updates canvas and button', () => {
        linkModeManager.applyLinkMode(0); // STRAIGHT_LINK

        expect(linkModeManager.getCurrentLinkMode()).toBe(0);
        expect(mockCanvas.links_render_mode).toBe(0);
        expect(mockCanvas.render_curved_connections).toBe(false);
    });

    test('applyLinkMode enables curved connections for spline mode', () => {
        linkModeManager.applyLinkMode(2); // SPLINE_LINK

        expect(mockCanvas.render_curved_connections).toBe(true);
    });

    test('applyLinkMode disables curved connections for non-spline modes', () => {
        linkModeManager.applyLinkMode(0); // STRAIGHT_LINK
        expect(mockCanvas.render_curved_connections).toBe(false);

        linkModeManager.applyLinkMode(1); // LINEAR_LINK
        expect(mockCanvas.render_curved_connections).toBe(false);
    });

    test('applyLinkMode calls setDirty if available', () => {
        linkModeManager.applyLinkMode(1);

        expect(mockCanvas.setDirty).toHaveBeenCalledWith(true, true);
    });

    test('applyLinkMode handles missing setDirty method', () => {
        delete mockCanvas.setDirty;

        // Should not throw
        expect(() => linkModeManager.applyLinkMode(1)).not.toThrow();
    });

    test('cycleLinkMode cycles through modes correctly', () => {
        // Start with curved (SPLINE_LINK = 2)
        expect(linkModeManager.getCurrentLinkMode()).toBe(2);

        // Cycle to orthogonal (LINEAR_LINK = 1)
        linkModeManager.cycleLinkMode();
        expect(linkModeManager.getCurrentLinkMode()).toBe(1);

        // Cycle to straight (STRAIGHT_LINK = 0)
        linkModeManager.cycleLinkMode();
        expect(linkModeManager.getCurrentLinkMode()).toBe(0);

        // Cycle back to curved
        linkModeManager.cycleLinkMode();
        expect(linkModeManager.getCurrentLinkMode()).toBe(2);
    });

    test('getLinkModeName returns correct names', () => {
        expect(linkModeManager.getLinkModeName(0)).toBe('Straight');
        expect(linkModeManager.getLinkModeName(1)).toBe('Orthogonal');
        expect(linkModeManager.getLinkModeName(2)).toBe('Curved');
    });

    test('getLinkModeName uses current mode when none specified', () => {
        linkModeManager.applyLinkMode(1);
        expect(linkModeManager.getLinkModeName()).toBe('Orthogonal');
    });

    test('getLinkModeName returns default for unknown mode', () => {
        expect(linkModeManager.getLinkModeName(999)).toBe('Curved');
    });

    test('updateButtonLabel updates button text and title', () => {
        const mockButton = {
            textContent: '',
            title: ''
        };

        document.getElementById = vi.fn().mockReturnValue(mockButton as any);

        linkModeManager.applyLinkMode(1); // Orthogonal

        expect(mockButton.textContent).toBe('Orthogonal');
        expect(mockButton.title).toBe('Link style: Orthogonal (click to cycle)');
    });

    test('updateButtonLabel handles missing button', () => {
        document.getElementById = vi.fn().mockReturnValue(null);

        // Should not throw
        expect(() => linkModeManager.applyLinkMode(1)).not.toThrow();
    });

    test('saveToGraphConfig adds linkRenderMode to config', () => {
        const graphData = { nodes: [], links: [] };

        linkModeManager.applyLinkMode(1);
        linkModeManager.saveToGraphConfig(graphData);

        expect(graphData.config).toBeDefined();
        expect(graphData.config.linkRenderMode).toBe(1);
    });

    test('saveToGraphConfig preserves existing config', () => {
        const graphData = {
            nodes: [],
            links: [],
            config: { existing: 'value' }
        };

        linkModeManager.saveToGraphConfig(graphData);

        expect(graphData.config.existing).toBe('value');
        expect(graphData.config.linkRenderMode).toBeDefined();
    });

    test('restoreFromGraphConfig applies saved link mode', () => {
        const graphData = {
            config: { linkRenderMode: 0 }
        };

        linkModeManager.restoreFromGraphConfig(graphData);

        expect(linkModeManager.getCurrentLinkMode()).toBe(0);
        expect(mockCanvas.links_render_mode).toBe(0);
    });

    test('restoreFromGraphConfig ignores invalid config', () => {
        const originalMode = linkModeManager.getCurrentLinkMode();

        linkModeManager.restoreFromGraphConfig({ config: { linkRenderMode: 'invalid' } });

        expect(linkModeManager.getCurrentLinkMode()).toBe(originalMode);
    });

    test('restoreFromGraphConfig ignores missing config', () => {
        const originalMode = linkModeManager.getCurrentLinkMode();

        linkModeManager.restoreFromGraphConfig({});

        expect(linkModeManager.getCurrentLinkMode()).toBe(originalMode);
    });

    test('restoreFromGraphConfig ignores missing linkRenderMode', () => {
        const originalMode = linkModeManager.getCurrentLinkMode();

        linkModeManager.restoreFromGraphConfig({ config: {} });

        expect(linkModeManager.getCurrentLinkMode()).toBe(originalMode);
    });

    test('link mode constants are correct', () => {
        // Test that our expected constants match LiteGraph constants
        expect(linkModeManager.getLinkModeName(0)).toBe('Straight');
        expect(linkModeManager.getLinkModeName(1)).toBe('Orthogonal');
        expect(linkModeManager.getLinkModeName(2)).toBe('Curved');
    });

    test('link mode names array is correct', () => {
        const names = (linkModeManager as any).linkModeNames;
        expect(names).toEqual(['Curved', 'Orthogonal', 'Straight']);
    });

    test('link mode values array is correct', () => {
        const values = (linkModeManager as any).linkModeValues;
        expect(values).toEqual([2, 1, 0]); // SPLINE_LINK, LINEAR_LINK, STRAIGHT_LINK
    });
});
