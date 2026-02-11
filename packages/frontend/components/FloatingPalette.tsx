// components/FloatingPalette.tsx
// Floating searchable node palette — appears on canvas double-click

import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import type { NodeSchemaMap } from '../types/nodes';

interface FloatingPaletteProps {
  nodeMetadata: NodeSchemaMap;
  position: { x: number; y: number };
  onSelect: (type: string) => void;
  onClose: () => void;
}

export function FloatingPalette({ nodeMetadata, position, onSelect, onClose }: FloatingPaletteProps) {
  const [search, setSearch] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Filter nodes by search query
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

  // Flat list for keyboard navigation
  const flatList = useMemo(() => {
    const items: string[] = [];
    for (const [, types] of categorized) {
      for (const [name] of types) items.push(name);
    }
    return items;
  }, [categorized]);

  // Reset active index when search changes
  useEffect(() => setActiveIndex(0), [search]);

  // Auto-focus search input
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Close on click outside
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [onClose]);

  // Close on Escape
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, flatList.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === 'Enter' && flatList.length > 0) {
        e.preventDefault();
        const selected = flatList[activeIndex];
        if (selected) onSelect(selected);
        return;
      }
    },
    [flatList, activeIndex, onSelect, onClose],
  );

  // Scroll active item into view
  useEffect(() => {
    const active = listRef.current?.querySelector('[data-active="true"]');
    active?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  // Position the palette, clamping to viewport
  const style = useMemo(() => {
    const width = 280;
    const maxHeight = 360;
    const pad = 8;
    let x = position.x;
    let y = position.y;
    if (x + width + pad > window.innerWidth) x = window.innerWidth - width - pad;
    if (y + maxHeight + pad > window.innerHeight) y = window.innerHeight - maxHeight - pad;
    if (x < pad) x = pad;
    if (y < pad) y = pad;
    return { left: x, top: y };
  }, [position]);

  let itemIndex = 0;

  return (
    <div className="floating-palette" ref={rootRef} style={style} onKeyDown={handleKeyDown}>
      <div className="floating-palette-search">
        <input
          ref={inputRef}
          type="text"
          placeholder="Search nodes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          spellCheck={false}
        />
      </div>
      <div className="floating-palette-list" ref={listRef}>
        {[...categorized.entries()].map(([category, types]) => (
          <div key={category} className="floating-palette-category">
            <div className="floating-palette-category-label">{category}</div>
            {types.map(([name, meta]) => {
              const idx = itemIndex++;
              const isActive = idx === activeIndex;
              return (
                <div
                  key={name}
                  className={`floating-palette-item${isActive ? ' active' : ''}`}
                  data-active={isActive}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => onSelect(name)}
                >
                  <span className="floating-palette-item-name">{name}</span>
                  {meta.description && (
                    <span className="floating-palette-item-desc">{meta.description}</span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
        {categorized.size === 0 && (
          <div className="floating-palette-empty">No nodes found</div>
        )}
      </div>
    </div>
  );
}
