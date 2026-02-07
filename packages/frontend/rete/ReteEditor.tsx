// rete/ReteEditor.tsx
// Main Rete.js v2 editor component — replaces the React Flow Editor

import { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { NodeEditor } from 'rete';
import { AreaPlugin, AreaExtensions } from 'rete-area-plugin';
import { ConnectionPlugin, Presets as ConnectionPresets } from 'rete-connection-plugin';
import { ReactPlugin, Presets as ReactPresets } from 'rete-react-plugin';
import { MinimapPlugin } from 'rete-minimap-plugin';
import { areTypesCompatible } from '@fig-node/core';
import type { GraphNode } from '@fig-node/core';

import { useGraphStore } from '../stores/graph-store';
import type { NodeMetadataMap } from '../types/node-metadata';
import {
  ReteAdapter,
  type FrontendSchemes,
  type AreaExtra,
} from './rete-adapter';
import { ReteNodeComponent, setNodeMetadata } from './components/ReteNode';
import { ContextMenu } from '../components/ContextMenu';
import { NodePalette } from '../components/NodePalette';

// ============ Editor Props ============

interface ReteEditorProps {
  nodeMetadata: NodeMetadataMap;
}

export function ReteEditor({ nodeMetadata }: ReteEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const adapterRef = useRef<ReteAdapter | null>(null);
  const areaRef = useRef<AreaPlugin<FrontendSchemes, AreaExtra> | null>(null);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId?: string;
    canvasPosition: { x: number; y: number };
  } | null>(null);

  // Store actions
  const addNode = useGraphStore((s) => s.addNode);
  const removeNode = useGraphStore((s) => s.removeNode);
  const addEdge = useGraphStore((s) => s.addEdge);
  const removeEdge = useGraphStore((s) => s.removeEdge);
  const updateNodePosition = useGraphStore((s) => s.updateNodePosition);

  useEffect(() => {
    if (!containerRef.current) return;

    // Make metadata available to node components
    setNodeMetadata(nodeMetadata);

    // Create Rete instances — use `any` for plugin generics to avoid
    // deep structural type mismatches between FigReteNode and ClassicPreset.Node
    const editor = new NodeEditor<FrontendSchemes>();
    const area = new AreaPlugin<FrontendSchemes, AreaExtra>(containerRef.current);
    const connection = new ConnectionPlugin<FrontendSchemes, AreaExtra>();
    const reactPlugin = new ReactPlugin<FrontendSchemes, AreaExtra>({ createRoot } as any);
    const minimap = new MinimapPlugin<FrontendSchemes>();

    areaRef.current = area;

    // Custom node rendering
    reactPlugin.addPreset(ReactPresets.classic.setup({
      customize: {
        node() {
          return ReteNodeComponent as any;
        },
      },
    }) as any);

    // Connection preset
    connection.addPreset(ConnectionPresets.classic.setup() as any);

    // Create adapter for bidirectional sync
    const adapter = new ReteAdapter(editor, nodeMetadata);
    adapter.setArea(area);
    adapterRef.current = adapter;

    // ============ Connection validation via editor pipe ============
    editor.addPipe((ctx) => {
      if (ctx.type === 'connectioncreate') {
        const { data } = ctx;
        const sourceNode = editor.getNode(data.source);
        const targetNode = editor.getNode(data.target);

        if (sourceNode && targetNode) {
          const sourceType = sourceNode.nodeType;
          const targetType = targetNode.nodeType;
          const sourceMeta = nodeMetadata[sourceType];
          const targetMeta = nodeMetadata[targetType];

          if (sourceMeta && targetMeta && data.sourceOutput && data.targetInput) {
            const outputTypeStr = sourceMeta.outputs[data.sourceOutput];
            const inputTypeStr = targetMeta.inputs[data.targetInput];

            if (outputTypeStr != null && inputTypeStr != null) {
              if (!areTypesCompatible(String(outputTypeStr), String(inputTypeStr))) {
                return undefined; // Block incompatible connection
              }
            }
          }
        }
      }
      return ctx;
    });

    // ============ Rete → Store sync ============
    editor.addPipe((ctx) => {
      if (adapter.syncing) return ctx;

      if (ctx.type === 'connectioncreated') {
        const conn = ctx.data;
        const sourceDocId = adapter.getDocId(conn.source);
        const targetDocId = adapter.getDocId(conn.target);

        if (sourceDocId && targetDocId && conn.sourceOutput && conn.targetInput) {
          addEdge({
            from: `${sourceDocId}.${conn.sourceOutput}`,
            to: `${targetDocId}.${conn.targetInput}`,
          });
        }
      }

      if (ctx.type === 'connectionremoved') {
        const conn = ctx.data;
        const sourceDocId = adapter.getDocId(conn.source);
        const targetDocId = adapter.getDocId(conn.target);

        if (sourceDocId && targetDocId && conn.sourceOutput && conn.targetInput) {
          removeEdge(
            `${sourceDocId}.${conn.sourceOutput}`,
            `${targetDocId}.${conn.targetInput}`,
          );
        }
      }

      return ctx;
    });

    // ============ Area events → Store sync ============
    area.addPipe((ctx) => {
      if (adapter.syncing) return ctx;

      if (ctx.type === 'nodetranslated') {
        const { id, position } = ctx.data;
        const docId = adapter.getDocId(id);
        if (docId) {
          updateNodePosition(docId, [position.x, position.y]);
        }
      }

      return ctx;
    });

    // ============ Wire plugins ============
    editor.use(area);
    area.use(connection as any);
    area.use(reactPlugin as any);
    area.use(minimap as any);

    // Select + ordering extensions
    AreaExtensions.selectableNodes(area as any, AreaExtensions.selector(), {
      accumulating: AreaExtensions.accumulateOnCtrl(),
    });
    AreaExtensions.simpleNodesOrder(area as any);

    // Load initial document
    const doc = useGraphStore.getState().doc;
    adapter.loadDocument(doc);

    // ============ Cleanup ============
    return () => {
      area.destroy();
    };
  }, [nodeMetadata, addEdge, removeEdge, updateNodePosition]);

  // ============ Store → Rete sync (subscribe to Zustand changes) ============
  useEffect(() => {
    const adapter = adapterRef.current;
    if (!adapter) return;

    // Subscribe to store changes and sync to Rete
    const unsubscribe = useGraphStore.subscribe((state, prevState) => {
      if (adapter.syncing) return;

      const doc = state.doc;
      const prevDoc = prevState.doc;
      if (doc === prevDoc) return;

      // Detect node additions
      for (const [id, node] of Object.entries(doc.nodes)) {
        if (!(id in prevDoc.nodes)) {
          adapter.addNode(id, node);
        }
      }

      // Detect node removals
      for (const id of Object.keys(prevDoc.nodes)) {
        if (!(id in doc.nodes)) {
          adapter.removeNode(id);
        }
      }

      // Detect edge additions
      for (const edge of doc.edges) {
        const existed = prevDoc.edges.some((e) => e.from === edge.from && e.to === edge.to);
        if (!existed) {
          adapter.addEdge(edge);
        }
      }

      // Detect edge removals
      for (const edge of prevDoc.edges) {
        const stillExists = doc.edges.some((e) => e.from === edge.from && e.to === edge.to);
        if (!stillExists) {
          adapter.removeEdge(edge.from, edge.to);
        }
      }
    });

    return unsubscribe;
  }, []);

  // ============ Context menu handler ============
  const handleContextMenu = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();

      const area = areaRef.current;
      if (!area) return;

      // Convert screen coordinates to canvas coordinates
      const transform = area.area.transform;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const canvasX = (event.clientX - rect.left - transform.x) / transform.k;
      const canvasY = (event.clientY - rect.top - transform.y) / transform.k;

      setContextMenu({
        x: event.clientX,
        y: event.clientY,
        canvasPosition: { x: canvasX, y: canvasY },
      });
    },
    [],
  );

  // ============ Drag-and-drop from palette ============
  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/fig-node-type');
      if (!type) return;

      const area = areaRef.current;
      if (!area) return;

      const transform = area.area.transform;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const canvasX = (event.clientX - rect.left - transform.x) / transform.k;
      const canvasY = (event.clientY - rect.top - transform.y) / transform.k;

      const meta = nodeMetadata[type];
      const id = `${type.toLowerCase()}_${Date.now()}`;
      const node: GraphNode = {
        type,
        params: meta?.defaultParams ? { ...meta.defaultParams } : {},
        position: [canvasX, canvasY],
      };
      addNode(id, node);
    },
    [nodeMetadata, addNode],
  );

  // ============ Keyboard delete ============
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Don't interfere with inputs
        if ((e.target as HTMLElement).tagName === 'INPUT' ||
            (e.target as HTMLElement).tagName === 'TEXTAREA' ||
            (e.target as HTMLElement).tagName === 'SELECT') {
          return;
        }

        const adapter = adapterRef.current;
        const editor = adapter?.editor;
        if (!editor) return;

        // Find selected nodes via area views
        const area = areaRef.current;
        if (!area) return;

        const nodes = editor.getNodes();
        for (const node of nodes) {
          const view = area.nodeViews.get(node.id);
          if (view && (view as any).selected) {
            const docId = adapter.getDocId(node.id);
            if (docId) {
              removeNode(docId);
            }
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [removeNode]);

  return (
    <div className="fig-editor-container">
      <NodePalette nodeMetadata={nodeMetadata} />
      <div
        className="fig-flow-container"
        ref={containerRef}
        onContextMenu={handleContextMenu}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      />

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          nodeId={contextMenu.nodeId}
          canvasPosition={contextMenu.canvasPosition}
          nodeMetadata={nodeMetadata}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}
