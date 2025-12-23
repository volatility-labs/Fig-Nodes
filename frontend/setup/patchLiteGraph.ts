// Runtime patch to allow nodes to capture mouse wheel events before LiteGraph handles them
// Inspired by Sven's branch commit cbd9462

// Use a function that can be called when LiteGraph is available
// This avoids import resolution issues when this file is imported from React frontend
export function applyLiteGraphPatch() {
    // Try to get LiteGraph from global scope (works for both frontends after initialization)
    const LiteGraph = (typeof window !== 'undefined' && (window as any).LiteGraph) || 
                      (typeof globalThis !== 'undefined' && (globalThis as any).LiteGraph);
    
    if (!LiteGraph) {
        // LiteGraph not available yet, try again later
        setTimeout(applyLiteGraphPatch, 100);
        return;
    }
    
    if ((LiteGraph as any)._wheelPatched) return;
    const proto = (LiteGraph as any).LGraphCanvas?.prototype;
    
    // Patch processMouseWheel for custom scroll behavior:
    // - Regular scroll = PAN
    // - Shift + scroll = ZOOM
    if (proto && typeof proto.processMouseWheel === 'function') {
        const original = proto.processMouseWheel;
        proto.processMouseWheel = function (event: WheelEvent): void {
            // Early return if canvas is disabled
            if (!this.graph || !this.allow_dragcanvas) {
                original.call(this, event);
                return;
            }
            
            // Get display system
            const ds = (this as any).ds;
            if (!ds) {
                original.call(this, event);
                return;
            }
            
            // Check if shift is pressed for zoom mode
            const shiftPressed = event.shiftKey === true;
            const scale = ds.scale || 1;
            
            // First, check if any node wants to handle the wheel event
            this.adjustMouseEvent(event);
            const canvasX = (event as any).canvasX ?? event.clientX;
            const canvasY = (event as any).canvasY ?? event.clientY;
            
            if (this.graph && typeof this.graph.getNodeOnPos === 'function') {
                const node = this.graph.getNodeOnPos(canvasX, canvasY);
                if (node && typeof (node as any).onMouseWheel === 'function') {
                    const nodePos = node.pos ?? [0, 0];
                    const local: [number, number] = [canvasX - nodePos[0], canvasY - nodePos[1]];
                    const handled = (node as any).onMouseWheel(event, local, this);
                    if (handled) {
                        event.preventDefault();
                        event.stopPropagation();
                        return;
                    }
                }
            }
            
            if (shiftPressed) {
                // SHIFT + SCROLL = ZOOM
                // Check localStorage for zoom direction setting
                const zoomDirection = localStorage.getItem('zoom-direction') || 'reversed';
                const zoomSpeedSetting = localStorage.getItem('zoom-speed');
                const zoomSpeed = zoomSpeedSetting ? parseFloat(zoomSpeedSetting) : ((this as any).zoom_speed || 1.1);
                
                let newScale = scale;
                const delta = event.deltaY || 0;
                
                if (zoomDirection === 'reversed') {
                    // Reversed: scroll up = zoom in, scroll down = zoom out
                    if (delta > 0) {
                        newScale *= 1 / zoomSpeed; // Zoom out (scroll down)
                    } else if (delta < 0) {
                        newScale *= zoomSpeed; // Zoom in (scroll up)
                    }
                } else {
                    // Natural: scroll up = zoom out, scroll down = zoom in
                    if (delta > 0) {
                        newScale *= zoomSpeed; // Zoom in (scroll down)
                    } else if (delta < 0) {
                        newScale *= 1 / zoomSpeed; // Zoom out (scroll up)
                    }
                }
                
                // Clamp scale
                newScale = Math.max(0.01, Math.min(10, newScale));
                
                if (ds.changeScale) {
                    ds.changeScale(newScale, [event.clientX, event.clientY]);
                    event.preventDefault();
                    event.stopPropagation();
                    
                    if (this.graph?.change) this.graph.change();
                    if ((this as any).dirty_canvas !== undefined) (this as any).dirty_canvas = true;
                    return;
                }
            } else {
                // REGULAR SCROLL = PAN
                const panSpeedSetting = localStorage.getItem('pan-speed');
                const panSpeedMultiplier = panSpeedSetting ? parseFloat(panSpeedSetting) : 1.0;
                const panSpeed = (1.0 / scale) * panSpeedMultiplier;
                const deltaX = event.deltaX || 0;
                const deltaY = event.deltaY || 0;
                
                if (deltaX !== 0 || deltaY !== 0) {
                    if (ds.offset) {
                        // Pan: scrolling right shows content to the right, scrolling down shows content below
                        ds.offset[0] += deltaX * panSpeed;
                        ds.offset[1] += deltaY * panSpeed;
                        
                        event.preventDefault();
                        event.stopPropagation();
                        
                        if (this.graph?.change) this.graph.change();
                        if ((this as any).dirty_canvas !== undefined) (this as any).dirty_canvas = true;
                        return;
                    }
                }
            }
            
            // Fallback to original
            original.call(this, event);
        };
        (LiteGraph as any)._wheelPatched = true;
    }
}

// Auto-apply patch when this module is loaded
applyLiteGraphPatch();
