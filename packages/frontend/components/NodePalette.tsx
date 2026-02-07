// components/NodePalette.tsx
// Searchable sidebar listing available node types

import React, { useState, useMemo, useCallback } from 'react';
import type { NodeMetadataMap } from '../types/node-metadata';
import type { GraphNode } from '@fig-node/core';
import { useGraphStore } from '../stores/graph-store';

interface NodePaletteProps {
  nodeMetadata: NodeMetadataMap;
}

export function NodePalette({ nodeMetadata }: NodePaletteProps) {
  const [search, setSearch] = useState('');
  const addNode = useGraphStore((s) => s.addNode);

  const filteredTypes = useMemo(() => {
    const query = search.toLowerCase();
    const entries = Object.entries(nodeMetadata);
    if (!query) return entries;
    return entries.filter(
      ([name, meta]) =>
        name.toLowerCase().includes(query) ||
        meta.category.toLowerCase().includes(query) ||
        meta.description.toLowerCase().includes(query),
    );
  }, [nodeMetadata, search]);

  // Group by category
  const categorized = useMemo(() => {
    const map = new Map<string, Array<[string, typeof nodeMetadata[string]]>>();
    for (const entry of filteredTypes) {
      const cat = entry[1].category ?? 'Other';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(entry);
    }
    return map;
  }, [filteredTypes]);

  const handleAddNode = useCallback(
    (type: string) => {
      const meta = nodeMetadata[type];
      const id = `${type.toLowerCase()}_${Date.now()}`;
      const node: GraphNode = {
        type,
        params: meta?.defaultParams ? { ...meta.defaultParams } : {},
        position: [100, 100],
      };
      addNode(id, node);
    },
    [nodeMetadata, addNode],
  );

  const handleDragStart = useCallback(
    (e: React.DragEvent, type: string) => {
      e.dataTransfer.setData('application/fig-node-type', type);
      e.dataTransfer.effectAllowed = 'move';
    },
    [],
  );

  return (
    <div className="fig-node-palette">
      <div className="fig-palette-header">
        <input
          type="text"
          className="fig-palette-search"
          placeholder="Search nodes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="fig-palette-list">
        {[...categorized.entries()].map(([category, types]) => (
          <div key={category} className="fig-palette-category">
            <div className="fig-palette-category-label">{category}</div>
            {types.map(([name, meta]) => (
              <div
                key={name}
                className="fig-palette-item"
                draggable
                onDragStart={(e) => handleDragStart(e, name)}
                onClick={() => handleAddNode(name)}
                title={meta.description}
              >
                <span className="fig-palette-item-name">{name}</span>
              </div>
            ))}
          </div>
        ))}
        {categorized.size === 0 && (
          <div className="fig-palette-empty">No nodes found</div>
        )}
      </div>
    </div>
  );
}
