import { useEffect, useCallback } from 'react';
import type { EditorInstance } from '@legacy/services/EditorInitializer';

/**
 * Hook to provide canvas utilities for better UX
 */
export function useLitegraphCanvas(editor: EditorInstance | null) {
  /**
   * Fit all nodes to view with animation
   */
  const fitToView = useCallback(() => {
    if (!editor?.canvas || !editor?.graph) {
      console.warn('Canvas not ready for fitToView');
      return;
    }

    const canvas = editor.canvas;
    const graph = editor.graph;

    try {
      // Clear selection first to fit all nodes
      if (canvas.selected_nodes) {
        canvas.selected_nodes = {};
      }
      
      // Use the canvas's built-in fit method if available
      if (typeof canvas.fitViewToSelectionAnimated === 'function') {
        canvas.fitViewToSelectionAnimated({
          duration: 300,
          zoom: 0.95,
          easing: 'easeInOutQuad'
        });
        
        // Ensure minimum zoom after animation
        setTimeout(() => {
          const ds = (canvas as any).ds;
          if (ds && ds.scale < 0.7) {
            ds.scale = 0.7;
            canvas.setDirty(true, true);
          }
        }, 350);
      } else {
        // Fallback: calculate bounds manually
        fitAllNodesToView(graph, canvas);
      }
      
      console.log('✅ Fit nodes to view');
    } catch (error) {
      console.error('Failed to fit to view:', error);
    }
  }, [editor]);

  /**
   * Center viewport on a specific node
   */
  const centerOnNode = useCallback((node: any) => {
    if (!editor?.canvas) return;

    const canvas = editor.canvas;
    const ds = (canvas as any).ds;
    
    if (!ds || !node.pos || !node.size) return;

    try {
      // Calculate node center
      const nodeCenterX = node.pos[0] + (node.size[0] / 2);
      const nodeCenterY = node.pos[1] + (node.size[1] / 2);
      
      // Get canvas dimensions
      const canvasRect = canvas.canvas.getBoundingClientRect();
      const viewportCenterX = canvasRect.width / (2 * ds.scale);
      const viewportCenterY = canvasRect.height / (2 * ds.scale);
      
      // Calculate offset to center the node
      ds.offset[0] = -(nodeCenterX - viewportCenterX);
      ds.offset[1] = -(nodeCenterY - viewportCenterY);
      
      // Ensure reasonable zoom level
      if (ds.scale < 0.7) {
        ds.scale = 0.7;
      }
      
      canvas.setDirty(true, true);
      
      console.log(`✅ Centered on node at (${nodeCenterX}, ${nodeCenterY})`);
    } catch (error) {
      console.error('Failed to center on node:', error);
    }
  }, [editor]);

  /**
   * Add a node at the viewport center (better UX than random position)
   */
  const addNodeAtViewportCenter = useCallback(async (nodeType: string) => {
    if (!editor) {
      console.warn('Editor not ready');
      return null;
    }

    try {
      // Use LiteGraph from global scope (available after editor initialization)
      const LiteGraph = (window as any).LiteGraph;
      if (!LiteGraph) {
        console.error('LiteGraph not available in global scope');
        return null;
      }
      
      const node = LiteGraph.createNode(nodeType);
      if (!node) {
        console.error(`Failed to create node: ${nodeType}`);
        return null;
      }

      const canvas = editor.canvas;
      const canvasElement = canvas.canvas;
      const rect = canvasElement.getBoundingClientRect();
      
      // Get viewport center
      const viewportCenterX = rect.width / 2;
      const viewportCenterY = rect.height / 2;
      
      // Convert to canvas coordinates
      const canvasPos = canvas.convertEventToCanvasOffset({
        clientX: rect.left + viewportCenterX,
        clientY: rect.top + viewportCenterY,
      } as MouseEvent);
      
      // Position node at center (offset to account for node size)
      if (Array.isArray(canvasPos) && canvasPos.length >= 2) {
        const nodeWidth = node.size?.[0] || 200;
        const nodeHeight = node.size?.[1] || 100;
        node.pos = [canvasPos[0] - nodeWidth / 2, canvasPos[1] - nodeHeight / 2];
      }
      
      // Add to graph
      editor.graph.add(node);
      
      // Select the new node
      if (canvas.selectNode) {
        canvas.selectNode(node);
      }
      
      // Center viewport on the new node
      setTimeout(() => {
        centerOnNode(node);
      }, 50);
      
      // Redraw
      canvas.draw(true, true);
      
      console.log(`✅ Added node: ${nodeType}`);
      return node;
    } catch (error) {
      console.error('Failed to add node:', error);
      return null;
    }
  }, [editor, centerOnNode]);

  return {
    fitToView,
    centerOnNode,
    addNodeAtViewportCenter,
  };
}

/**
 * Fallback: Calculate bounds and fit all nodes to view
 */
function fitAllNodesToView(graph: any, canvas: any) {
  if (!graph._nodes || graph._nodes.length === 0) {
    console.log('No nodes to fit');
    return;
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  // Calculate bounding box
  graph._nodes.forEach((node: any) => {
    if (node.pos && node.size) {
      const x = node.pos[0] || 0;
      const y = node.pos[1] || 0;
      const w = node.size[0] || 0;
      const h = node.size[1] || 0;
      
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + w);
      maxY = Math.max(maxY, y + h);
    }
  });

  if (!isFinite(minX)) return;

  const padding = 50;
  const bounds: [number, number, number, number] = [
    minX - padding,
    minY - padding,
    maxX - minX + (padding * 2),
    maxY - minY + (padding * 2)
  ];
  
  // Try to use animateToBounds if available
  if (canvas.animateToBounds && typeof canvas.animateToBounds === 'function') {
    canvas.animateToBounds(bounds, {
      duration: 300,
      zoom: 0.95,
      easing: 'easeInOutQuad'
    });
  } else {
    // Fallback to ds.fitToBounds
    const ds = (canvas as any).ds;
    if (ds && ds.fitToBounds) {
      ds.fitToBounds(bounds, { zoom: 0.95 });
      canvas.setDirty(true, true);
    }
  }
  
  // Ensure minimum zoom
  setTimeout(() => {
    const ds = (canvas as any).ds;
    if (ds && ds.scale < 0.7) {
      ds.scale = 0.7;
      canvas.setDirty(true, true);
    }
  }, 350);
}

