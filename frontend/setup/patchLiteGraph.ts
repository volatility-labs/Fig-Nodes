// Runtime patch to allow nodes to capture mouse wheel events before LiteGraph handles them
// Inspired by Sven's branch commit cbd9462

import { LiteGraph } from '@fig-node/litegraph';

// Only patch once
if (!(LiteGraph as any)._wheelPatched) {
    const proto = (LiteGraph as any).LGraphCanvas?.prototype;
    if (proto && typeof proto.processMouseWheel === 'function') {
        const original = proto.processMouseWheel;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        proto.processMouseWheel = function (event: WheelEvent): void {
            // `this` is LGraphCanvas
            // Early return if canvas zoom is disabled
            if (!this.graph || !this.allow_dragcanvas) {
                original.call(this, event);
                return;
            }
            
            // Adjust mouse event first (like original does) to get canvas coordinates
            this.adjustMouseEvent(event);
            
            // Get canvas coordinates from the adjusted event
            const canvasX = (event as any).canvasX ?? event.clientX;
            const canvasY = (event as any).canvasY ?? event.clientY;
            
            const graph = this.graph;
            
            if (graph && typeof graph.getNodeOnPos === 'function') {
                try {
                    // Get node at mouse position - check visible nodes
                    const node = graph.getNodeOnPos(canvasX, canvasY, graph.visible_nodes);
                    
                    // Also check if any node is selected (for zoom when selected)
                    const selectedNodes = this.selected_nodes || {};
                    const hasSelectedNode = Object.keys(selectedNodes).length > 0;
                    
                    // Handle wheel events when mouse is over a node that has onMouseWheel
                    // OR when a node is selected (for zoom when selected)
                    if (node && typeof node.onMouseWheel === 'function') {
                        // Local coords relative to node
                        const nodePos = node.pos ?? [0, 0];
                        const local: [number, number] = [canvasX - nodePos[0], canvasY - nodePos[1]];
                        const handled = node.onMouseWheel(event, local, this);
                        if (handled) {
                            // Node handled it - prevent canvas zoom/pan by not calling original
                            event.preventDefault();
                            event.stopPropagation();
                            // Also stop the graph change
                            return;
                        }
                    }
                    
                    // Also check selected nodes (for zoom when selected, even if mouse is outside)
                    if (hasSelectedNode) {
                        for (const nodeId in selectedNodes) {
                            const selectedNode = selectedNodes[nodeId];
                            if (selectedNode && typeof selectedNode.onMouseWheel === 'function') {
                                // Use node's position for local coords
                                const nodePos = selectedNode.pos ?? [0, 0];
                                const local: [number, number] = [canvasX - nodePos[0], canvasY - nodePos[1]];
                                const handled = selectedNode.onMouseWheel(event, local, this);
                                if (handled) {
                                    // Node handled it - prevent canvas zoom/pan
                                    event.preventDefault();
                                    event.stopPropagation();
                                    return;
                                }
                            }
                        }
                    }
                } catch (err) {
                    // Log error but continue with original behavior
                    console.warn('Error in wheel patch:', err);
                }
            }
            // Fallback to original behaviour
            original.call(this, event);
        };
        (LiteGraph as any)._wheelPatched = true;
    }
}
