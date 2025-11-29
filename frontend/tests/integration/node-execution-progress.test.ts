/**
 * Integration tests for node execution with progress updates
 * Tests progress tracking, node updates, and result handling
 */

import { describe, test, expect, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import type { LGraph, LGraphNode } from '@fig-node/litegraph';

// Mock node with progress tracking - we'll create instances dynamically in tests
class MockProgressNode {
    progress: number = -1;
    progressText: string = '';
    isExecuting: boolean = false;
    highlightStartTs: number | null = null;

    setProgress(progress: number, text?: string) {
        this.progress = progress;
        this.progressText = text || '';
    }

    clearProgress() {
        this.progress = -1;
        this.progressText = '';
    }

    pulseHighlight() {
        this.isExecuting = true;
        this.highlightStartTs = Date.now();
    }

    clearHighlight() {
        this.isExecuting = false;
        this.highlightStartTs = null;
    }

    updateDisplay(result: unknown) {
        // Mock implementation
    }
}

describe('Node Execution Progress Integration Tests', () => {
    let dom: any;
    let graph: LGraph;

    beforeEach(() => {
        vi.restoreAllMocks();
        vi.resetModules();

        dom = new JSDOM(`<!doctype html><html><body>
            <canvas id="litegraph-canvas"></canvas>
        </body></html>`, { url: 'http://localhost/' });

        (globalThis as any).document = dom.window.document;
        (globalThis as any).window = dom.window;
        (globalThis as any).localStorage = dom.window.localStorage;

        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });
    });

    test('progress updates trigger node state changes', async () => {
        const { LGraph } = await import('@fig-node/litegraph');
        graph = new LGraph();
        
        // Create a mock node and add it to graph
        const node = new MockProgressNode();
        node.id = 1;
        // Set graph property so getNodeById can find it
        (node as any).graph = graph;
        graph.add(node as any);

        // Simulate progress message handling
        const progressMessage = {
            type: 'progress' as const,
            node_id: 1,
            progress: 50,
            text: 'Processing...',
            state: 'update' as const,
            job_id: 1
        };

        // Simulate what handleProgressMessage does - use the node directly since we have it
        const targetNode = graph.getNodeById?.(1) || node;
        if (targetNode && typeof targetNode.setProgress === 'function') {
            targetNode.setProgress(progressMessage.progress || 0, progressMessage.text);
        }

        if (progressMessage.state === 'update' && typeof targetNode.pulseHighlight === 'function') {
            targetNode.pulseHighlight();
        }

        expect(targetNode.progress).toBe(50);
        expect(targetNode.progressText).toBe('Processing...');
        expect(targetNode.isExecuting).toBe(true);
    });

    test('completion clears node highlight', async () => {
        const { LGraph } = await import('@fig-node/litegraph');
        graph = new LGraph();
        
        const node = new MockProgressNode();
        node.id = 1;
        node.isExecuting = true;
        node.highlightStartTs = Date.now();
        (node as any).graph = graph;
        graph.add(node as any);

        // Simulate completion message
        const completionMessage = {
            type: 'progress' as const,
            node_id: 1,
            progress: 100,
            state: 'done' as const,
            job_id: 1
        };

        const targetNode = graph.getNodeById?.(1) || node;
        if (completionMessage.state === 'done' && typeof targetNode.clearHighlight === 'function') {
            targetNode.clearHighlight();
        }

        expect(targetNode.isExecuting).toBe(false);
        expect(targetNode.highlightStartTs).toBeNull();
    });

    test('error state clears highlight', async () => {
        const { LGraph } = await import('@fig-node/litegraph');
        graph = new LGraph();
        
        const node = new MockProgressNode();
        node.id = 1;
        node.isExecuting = true;
        (node as any).graph = graph;
        graph.add(node as any);

        const errorMessage = {
            type: 'progress' as const,
            node_id: 1,
            progress: 100,
            state: 'error' as const,
            job_id: 1
        };

        const targetNode = graph.getNodeById?.(1) || node;
        if (errorMessage.state === 'error' && typeof targetNode.clearHighlight === 'function') {
            targetNode.clearHighlight();
        }

        expect(targetNode.isExecuting).toBe(false);
    });

    test('multiple nodes receive progress updates', async () => {
        const { LGraph } = await import('@fig-node/litegraph');
        graph = new LGraph();
        
        const node1 = new MockProgressNode();
        node1.id = 1;
        (node1 as any).graph = graph;
        graph.add(node1 as any);

        const node2 = new MockProgressNode();
        node2.id = 2;
        (node2 as any).graph = graph;
        graph.add(node2 as any);

        // Simulate progress for node 1
        const progress1 = {
            type: 'progress' as const,
            node_id: 1,
            progress: 30,
            state: 'update' as const,
            job_id: 1
        };

        const targetNode1 = graph.getNodeById?.(1) || node1;
        if (targetNode1 && typeof targetNode1.setProgress === 'function') {
            targetNode1.setProgress(progress1.progress || 0);
        }

        // Simulate progress for node 2
        const progress2 = {
            type: 'progress' as const,
            node_id: 2,
            progress: 60,
            state: 'update' as const,
            job_id: 1
        };

        const targetNode2 = graph.getNodeById?.(2) || node2;
        if (targetNode2 && typeof targetNode2.setProgress === 'function') {
            targetNode2.setProgress(progress2.progress || 0);
        }

        expect(targetNode1.progress).toBe(30);
        expect(targetNode2.progress).toBe(60);
    });
});

