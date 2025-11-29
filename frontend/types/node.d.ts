/**
 * Extended node interfaces for type-safe node access
 * 
 * This file defines interfaces for nodes that extend LGraphNode
 * with custom methods used throughout the application.
 */

import type { LGraphNode } from '@fig-node/litegraph';
import type { ExecutionResults } from './resultTypes';

/**
 * Node interface with custom methods used in WebSocket handlers and UI updates
 * 
 * This interface extends LGraphNode with methods that are added by BaseCustomNode
 * and other custom node implementations.
 */
export interface NodeWithMethods extends LGraphNode {
    /**
     * Clear the highlight/pulse effect on the node
     */
    clearHighlight?: () => void;
    
    /**
     * Set progress indicator on the node
     * @param progress Progress percentage (0-100)
     * @param text Optional progress text to display
     */
    setProgress?: (progress: number, text?: string) => void;
    
    /**
     * Clear progress indicator on the node
     */
    clearProgress?: () => void;
    
    /**
     * Update the display with new result data
     * @param result Result data from node execution
     */
    updateDisplay?: (result: unknown) => void;
    
    /**
     * Handle streaming updates for streaming nodes
     * @param result Streaming result data
     */
    onStreamUpdate?: (result: unknown) => void;
    
    /**
     * Set error state on the node
     * @param error Error message to display
     */
    setError?: (error: string) => void;
    
    /**
     * Pulse highlight effect (for active execution)
     */
    pulseHighlight?: () => void;
    
    /**
     * Mark canvas as dirty to trigger redraw
     * @param foreground Whether to redraw foreground
     * @param background Whether to redraw background
     */
    setDirtyCanvas?: (foreground: boolean, background: boolean) => void;
    
    /**
     * Reset node state (used by Logging nodes)
     */
    reset?: () => void;
    
    /**
     * Whether this node supports streaming updates
     */
    isStreaming?: boolean;
    
    /**
     * Error message displayed on the node
     */
    error?: string;
    
    /**
     * Highlight start timestamp (for pulse animation)
     */
    highlightStartTs?: number | null;
    
    /**
     * Whether the node is currently executing
     */
    isExecuting?: boolean;
    
    /**
     * Node color (can be undefined for default)
     */
    color?: string | undefined;
    
    /**
     * Node type identifier
     */
    type?: string;
}

/**
 * Type guard to check if a node has the expected methods
 */
export function isNodeWithMethods(node: LGraphNode | null | undefined): node is NodeWithMethods {
    return node !== null && node !== undefined;
}

