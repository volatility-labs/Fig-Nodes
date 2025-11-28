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
            console.log('🔵 PATCHED processMouseWheel called:', {
                hasGraph: !!this.graph,
                allow_dragcanvas: this.allow_dragcanvas,
                deltaX: event.deltaX,
                deltaY: event.deltaY
            });
            
            // Early return if canvas zoom is disabled
            if (!this.graph || !this.allow_dragcanvas) {
                console.log('❌ PATCH: Early return, calling original anyway');
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
                    
                    console.log('Wheel patch check:', { 
                        hasNode: !!node, 
                        hasSelectedNode, 
                        nodeHasWheel: node && typeof node.onMouseWheel === 'function' 
                    });
                    
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
                            console.log('Node handled wheel event');
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
                                    console.log('Selected node handled wheel event');
                                    return;
                                }
                            }
                        }
                    }
                    
                    // No node handled it - let canvas handle it (for panning when background is selected)
                    console.log('✅ No node handled, proceeding to canvas panning');
                } catch (err) {
                    // Log error but continue with original behavior
                    console.warn('❌ Error in wheel patch:', err);
                }
            }
            
            // Canvas panning logic (when no nodes selected or no node handled the event)
            // This matches the behavior we want: scroll to pan when canvas background is selected
            const selectedNodes = this.selected_nodes || {};
            const hasSelectedNode = Object.keys(selectedNodes).length > 0;
            
            // Only pan if no nodes are selected (canvas background is "selected")
            if (!hasSelectedNode) {
                console.log('🎯 Canvas background selected - panning on scroll');
                
                // Check if mouse is over canvas viewport
                const pos: [number, number] = [event.clientX, event.clientY];
                const viewport = (this as any).viewport;
                if (viewport) {
                    // Simple viewport check - if viewport exists, check if mouse is in it
                    const isInViewport = pos[0] >= viewport[0] && pos[0] <= viewport[2] && 
                                        pos[1] >= viewport[1] && pos[1] <= viewport[3];
                    if (!isInViewport) {
                        console.log('❌ Mouse outside viewport, skipping pan');
                        return;
                    }
                }
                
                // Panning logic
                const ds = (this as any).ds;
                if (!ds) {
                    console.log('❌ No ds (display system), calling original');
                    original.call(this, event);
                    return;
                }
                
                const scale = ds.scale || 1;
                // Strict shift detection - only zoom if shift is explicitly pressed
                // Check both shiftKey and getModifierState to be sure
                const shiftPressed = event.shiftKey === true || (event.getModifierState && event.getModifierState('Shift') === true);
                
                console.log('🎯 Pan/Zoom check:', { 
                    shiftPressed, 
                    shiftKey: event.shiftKey, 
                    getModifierState: event.getModifierState ? event.getModifierState('Shift') : 'N/A',
                    deltaY: event.deltaY 
                });
                
                if (shiftPressed) {
                    // Shift + scroll: ZOOM
                    const zoomSpeed = (this as any).zoom_speed || 1.1;
                    let newScale = scale;
                    const delta = event.deltaY !== undefined ? event.deltaY : (event.wheelDeltaY ?? event.detail * -60);
                    
                    // Use base zoom speed for all scrolling (no multiplier)
                    const effectiveZoomSpeed = zoomSpeed;
                    
                    if (delta > 0) {
                        // Scrolling down: zoom out
                        newScale *= 1 / effectiveZoomSpeed;
                    } else if (delta < 0) {
                        // Scrolling up: zoom in
                        newScale *= effectiveZoomSpeed;
                    }
                    
                    // Clamp scale to reasonable bounds to prevent zooming too far
                    const minScale = 0.01;
                    const maxScale = 10;
                    newScale = Math.max(minScale, Math.min(maxScale, newScale));
                    
                    if (ds.changeScale) {
                        ds.changeScale(newScale, [event.clientX, event.clientY]);
                        event.preventDefault();
                        event.stopPropagation();
                        console.log('🔍 Zoomed to scale:', newScale, { delta, effectiveZoomSpeed, oldScale: scale });
                        
                        // Force redraw
                        if ((this as any).graph && typeof (this as any).graph.change === 'function') {
                            (this as any).graph.change();
                        }
                        if ((this as any).dirty_canvas !== undefined) {
                            (this as any).dirty_canvas = true;
                        }
                        return;
                    }
                } else {
                    // Regular scroll: PAN
                    const panSpeed = 1.18 * (1 / scale);
                    const deltaX = event.deltaX || 0;
                    const deltaY = event.deltaY || 0;
                    
                    if (deltaX !== 0 || deltaY !== 0) {
                        if (ds.offset) {
                            // Reverse the direction: scroll right should pan right, scroll down should pan down
                            ds.offset[0] += deltaX * panSpeed;
                            ds.offset[1] += deltaY * panSpeed;
                            event.preventDefault();
                            event.stopPropagation();
                            console.log('🎯 Panned canvas:', { deltaX, deltaY, newOffset: [ds.offset[0], ds.offset[1]] });
                            
                            // Force redraw
                            if ((this as any).graph && typeof (this as any).graph.change === 'function') {
                                (this as any).graph.change();
                            }
                            // Mark canvas as dirty for redraw
                            if ((this as any).dirty_canvas !== undefined) {
                                (this as any).dirty_canvas = true;
                            }
                            return;
                        }
                    }
                }
            }
            
            // Fallback to original behaviour if we didn't handle it
            console.log('⚠️ Falling back to original.processMouseWheel');
            original.call(this, event);
        };
        (LiteGraph as any)._wheelPatched = true;
    }
}
