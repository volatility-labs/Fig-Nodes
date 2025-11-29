// Runtime patch to allow nodes to capture mouse wheel events before LiteGraph handles them
// Inspired by Sven's branch commit cbd9462

import { LiteGraph } from '@fig-node/litegraph';

// Only patch once
if (!(LiteGraph as any)._wheelPatched) {
    const proto = (LiteGraph as any).LGraphCanvas?.prototype;
    
    // Patch processMouseDown to track when canvas background is clicked (for sticky panning)
    if (proto && typeof proto.processMouseDown === 'function') {
        const originalMouseDown = proto.processMouseDown;
        proto.processMouseDown = function (e: PointerEvent): void {
            // Call original first
            originalMouseDown.call(this, e);
            
            // After original processes, check if canvas background was clicked (no node selected)
            const selectedNodes = this.selected_nodes || {};
            const hasSelectedNode = Object.keys(selectedNodes).length > 0;
            
            // If no nodes selected, canvas background is "active" for panning
            // This allows scrolling to continue even when mouse moves over nodes
            (this as any)._canvasPanActive = !hasSelectedNode;
        };
    }
    
    // Patch processMouseUp to clear sticky panning state
    if (proto && typeof proto.processMouseUp === 'function') {
        const originalMouseUp = proto.processMouseUp;
        proto.processMouseUp = function (e: PointerEvent): void {
            // Call original first
            originalMouseUp.call(this, e);
            
            // Clear sticky panning state on mouse up
            // User can click again to reactivate if needed
            (this as any)._canvasPanActive = false;
        };
    }
    
    if (proto && typeof proto.processMouseWheel === 'function') {
        const original = proto.processMouseWheel;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        proto.processMouseWheel = function (event: WheelEvent): void {
            // `this` is LGraphCanvas
            // Debug logging removed for smoother performance
            
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
            const selectedNodes = this.selected_nodes || {};
            const hasSelectedNode = Object.keys(selectedNodes).length > 0;
            
            // Check if shift is pressed (zoom mode) - only then check nodes
            const shiftPressed = event.shiftKey === true || (event.getModifierState && event.getModifierState('Shift') === true);
            
            // Only check nodes if:
            // 1. Shift is pressed (zoom mode - nodes might want to handle zoom)
            // 2. Nodes are selected (nodes might want to handle zoom when selected)
            // Otherwise, skip node checks entirely for faster panning
            if (shiftPressed || hasSelectedNode) {
                if (graph && typeof graph.getNodeOnPos === 'function') {
                    try {
                        // Get node at mouse position
                        const node = graph.getNodeOnPos(canvasX, canvasY);
                        
                        // Handle wheel events when mouse is over a node that has onMouseWheel
                        // Only check if shift is pressed (zoom) or node is selected
                        if (node && typeof (node as any).onMouseWheel === 'function') {
                            // Local coords relative to node
                            const nodePos = node.pos ?? [0, 0];
                            const local: [number, number] = [canvasX - nodePos[0], canvasY - nodePos[1]];
                            const handled = (node as any).onMouseWheel(event, local, this);
                            if (handled) {
                                // Node handled it - prevent canvas zoom/pan
                                event.preventDefault();
                                event.stopPropagation();
                                return;
                            }
                        }
                        
                        // Also check selected nodes (for zoom when selected, even if mouse is outside)
                        if (hasSelectedNode) {
                            for (const nodeId in selectedNodes) {
                                const selectedNode = selectedNodes[nodeId];
                                if (selectedNode && typeof (selectedNode as any).onMouseWheel === 'function') {
                                    // Use node's position for local coords
                                    const nodePos = selectedNode.pos ?? [0, 0];
                                    const local: [number, number] = [canvasX - nodePos[0], canvasY - nodePos[1]];
                                    const handled = (selectedNode as any).onMouseWheel(event, local, this);
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
                        console.warn('❌ Error in wheel patch:', err);
                    }
                }
            }
            
            // Canvas panning logic (when no nodes selected or no node handled the event)
            // This matches the behavior we want: scroll to pan when canvas background is selected
            // Use already-declared variables from above
            
            // Pan if canvas is active (background clicked) OR no nodes selected
            // Canvas becomes "active" when clicked on background (no nodes selected)
            // This allows panning to continue even when mouse moves over nodes
            const canvasPanActive = (this as any)._canvasPanActive === true;
            const shouldPan = canvasPanActive || !hasSelectedNode;
            
            if (shouldPan) {
                
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
                // Use already-declared shiftPressed from above
                // Pan/Zoom check - debug logging removed for smoother performance
                
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
                    // Regular scroll: PAN with smooth, fluid motion
                    // Use a smoother pan speed calculation that feels more natural and "rolly"
                    const basePanSpeed = 0.6; // Lower base speed for smoother, more controlled feel
                    const panSpeed = basePanSpeed * (1 / scale);
                    
                    const deltaX = event.deltaX || 0;
                    const deltaY = event.deltaY || 0;
                    
                    if (deltaX !== 0 || deltaY !== 0) {
                        if (ds.offset) {
                            // Smooth, fluid panning: scroll right should pan right, scroll down should pan down
                            // Apply deltas with smooth speed multiplier for natural feel
                            ds.offset[0] += deltaX * panSpeed;
                            ds.offset[1] += deltaY * panSpeed;
                            event.preventDefault();
                            event.stopPropagation();
                            
                            // Force immediate redraw for responsive feel
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
            original.call(this, event);
        };
        (LiteGraph as any)._wheelPatched = true;
    }
}
