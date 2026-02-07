// components/ContextMenu.tsx
// Right-click context menu for the graph canvas and nodes

import { useCallback, useEffect, useRef } from 'react';
import type { NodeMetadataMap } from '../types/node-metadata';
import type { GraphNode } from '@fig-node/core';
import { useGraphStore } from '../stores/graph-store';

interface ContextMenuProps {
  x: number;
  y: number;
  /** If set, this is a node context menu */
  nodeId?: string;
  /** Canvas position where the menu was opened (for placing new nodes) */
  canvasPosition: { x: number; y: number };
  nodeMetadata: NodeMetadataMap;
  onClose: () => void;
}

export function ContextMenu({
  x,
  y,
  nodeId,
  canvasPosition,
  nodeMetadata,
  onClose,
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const addNode = useGraphStore((s) => s.addNode);
  const removeNode = useGraphStore((s) => s.removeNode);

  // Close on click outside or Escape
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [onClose]);

  const handleAddNode = useCallback(
    (type: string) => {
      const meta = nodeMetadata[type];
      const id = `${type.toLowerCase()}_${Date.now()}`;
      const node: GraphNode = {
        type,
        params: meta?.defaultParams ? { ...meta.defaultParams } : {},
        position: [canvasPosition.x, canvasPosition.y],
      };
      addNode(id, node);
      onClose();
    },
    [canvasPosition, nodeMetadata, addNode, onClose],
  );

  const handleDeleteNode = useCallback(() => {
    if (nodeId) {
      removeNode(nodeId);
      onClose();
    }
  }, [nodeId, removeNode, onClose]);

  // Group node types by category
  const categorized = new Map<string, string[]>();
  for (const [typeName, meta] of Object.entries(nodeMetadata)) {
    const cat = meta.category ?? 'Other';
    if (!categorized.has(cat)) categorized.set(cat, []);
    categorized.get(cat)!.push(typeName);
  }

  return (
    <div
      ref={menuRef}
      className="fig-context-menu"
      style={{ left: x, top: y }}
    >
      {nodeId ? (
        // Node context menu
        <>
          <div className="fig-context-menu-header">Node: {nodeId}</div>
          <button className="fig-context-menu-item" onClick={handleDeleteNode}>
            Delete Node
          </button>
        </>
      ) : (
        // Canvas context menu - add node
        <>
          <div className="fig-context-menu-header">Add Node</div>
          {[...categorized.entries()].map(([category, types]) => (
            <div key={category} className="fig-context-menu-category">
              <div className="fig-context-menu-category-label">{category}</div>
              {types.map((type) => (
                <button
                  key={type}
                  className="fig-context-menu-item"
                  onClick={() => handleAddNode(type)}
                >
                  {type}
                </button>
              ))}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
