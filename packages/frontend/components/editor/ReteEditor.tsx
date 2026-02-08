// components/editor/ReteEditor.tsx
// Main Rete.js v2 editor component — Rete is the single source of truth for graph structure.

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ClassicPreset, NodeEditor } from 'rete';
import { AreaPlugin, AreaExtensions } from 'rete-area-plugin';
import { ConnectionPlugin, Presets as ConnectionPresets } from 'rete-connection-plugin';
import { ReactPlugin, Presets as ReactPresets } from 'rete-react-plugin';
import { MinimapPlugin } from 'rete-minimap-plugin';
import { getDOMSocketPosition } from 'rete-render-utils';
import { getSocketKey, areSocketKeysCompatible } from '@fig-node/core';

import type { NodeMetadataMap } from '../../types/nodes';
import { typeColor } from './type-colors';
import {
  ReteAdapter,
  type FrontendSchemes,
  type AreaExtra,
} from './rete-adapter';
import { setEditorAdapter } from './editor-ref';
import { restoreFromAutosave } from '../../services/FileManager';
import { ReteNodeComponent, setNodeMetadata } from './ReteNode';
import { ContextMenu } from '../ContextMenu';
import { NodePalette } from '../NodePalette';
import { addNodeToEditor } from './add-node';

// ============ Module-level refs for render components ============

let _editorRef: NodeEditor<FrontendSchemes> | null = null;
let _metaRef: NodeMetadataMap = {};

// ============ Custom Socket Visual ============

function FigSocket(props: { data: ClassicPreset.Socket }) {
  const color = typeColor(props.data.name);
  return (
    <div
      className="fig-socket"
      title={props.data.name}
      style={{ borderColor: color, '--socket-color': color } as React.CSSProperties}
    />
  );
}

// ============ Custom Connection Visual ============

function FigConnection(props: { data: any; styles?: () => any }) {
  const { path } = ReactPresets.classic.useConnection();
  if (!path) return null;

  let color = '#555';
  if (_editorRef && props.data.sourceOutput) {
    try {
      const sourceNode = _editorRef.getNode(props.data.source);
      if (sourceNode) {
          const meta = _metaRef[sourceNode.nodeType];
          if (meta) {
            const outputSpec = meta.outputs[props.data.sourceOutput];
            if (outputSpec) {
              color = typeColor(outputSpec);
            }
          }
        }
    } catch { /* node may have been removed */ }
  }

  return (
    <svg
      data-testid="connection"
      style={{
        overflow: 'visible',
        position: 'absolute',
        pointerEvents: 'none',
        width: '9999px',
        height: '9999px',
      }}
    >
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2}
        style={{ pointerEvents: 'auto' }}
      />
    </svg>
  );
}

// ============ Dirty flag for autosave ============

let _dirty = false;

export function isDirty(): boolean {
  return _dirty;
}

export function clearDirty(): void {
  _dirty = false;
}

export function markDirty(): void {
  _dirty = true;
}

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

    // Set module-level refs for render components
    _editorRef = editor;
    _metaRef = nodeMetadata;

    // Custom socket position watcher — disable the default 12px horizontal
    // offset so connection endpoints land at the socket centre (our CSS
    // already places sockets at the node edge).
    const socketPositionWatcher = getDOMSocketPosition({
      offset: (position) => position,
    });

    // Custom node + socket + connection rendering
    reactPlugin.addPreset(ReactPresets.classic.setup({
      socketPositionWatcher,
      customize: {
        node() {
          return ReteNodeComponent as any;
        },
        socket() {
          return FigSocket as any;
        },
        connection() {
          return FigConnection as any;
        },
      },
    }) as any);

    // Connection preset
    connection.addPreset(ConnectionPresets.classic.setup() as any);

    // Create adapter
    const adapter = new ReteAdapter(editor, nodeMetadata);
    adapter.setArea(area);
    adapterRef.current = adapter;

    // Expose adapter to services (FileManager, WebSocketClient)
    setEditorAdapter(adapter);

    // ============ Connection validation via editor pipe ============
    editor.addPipe((ctx) => {
      if (ctx.type === 'connectioncreate') {
        const { data } = ctx;
        const sourceNode = editor.getNode(data.source);
        const targetNode = editor.getNode(data.target);

        if (sourceNode && targetNode && data.sourceOutput && data.targetInput) {
          const sourceKey = getSocketKey(String(sourceNode.outputs[data.sourceOutput]?.socket?.name ?? 'any'));
          const targetKey = getSocketKey(String(targetNode.inputs[data.targetInput]?.socket?.name ?? 'any'));
          if (!areSocketKeysCompatible(sourceKey, targetKey)) {
            return undefined; // Block incompatible connection
          }

          const targetMeta = nodeMetadata[targetNode.nodeType];
          const inputSpec = targetMeta?.inputs?.[data.targetInput];
          const inputAllowsMultiple = inputSpec?.multi === true;
          if (!inputAllowsMultiple) {
            const hasExistingConnection = editor.getConnections().some((conn) =>
              conn.target === data.target && conn.targetInput === data.targetInput
            );
            if (hasExistingConnection) {
              return undefined; // Block ambiguous extra connection on single-input ports
            }
          }
        }
      }
      return ctx;
    });

    // ============ Dirty-flag pipes for autosave ============
    editor.addPipe((ctx) => {
      if (adapter.loading) return ctx;
      if (ctx.type === 'nodecreated' || ctx.type === 'noderemoved' ||
          ctx.type === 'connectioncreated' || ctx.type === 'connectionremoved') {
        markDirty();
      }
      return ctx;
    });

    area.addPipe((ctx) => {
      if (adapter.loading) return ctx;
      if (ctx.type === 'nodetranslated') {
        markDirty();
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

    // Restore autosaved graph now that the adapter and all plugins are ready
    restoreFromAutosave();

    // ============ Cleanup ============
    return () => {
      _editorRef = null;
      setEditorAdapter(null as any);
      area.destroy();
    };
  }, [nodeMetadata]);

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
      const adapter = adapterRef.current;
      if (!area || !adapter) return;

      const transform = area.area.transform;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const canvasX = (event.clientX - rect.left - transform.x) / transform.k;
      const canvasY = (event.clientY - rect.top - transform.y) / transform.k;

      addNodeToEditor(adapter, type, [canvasX, canvasY], nodeMetadata);
    },
    [nodeMetadata],
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

        const nodes = editor.getNodes();
        for (const node of nodes) {
          if ((node as any).selected) {
            adapter.removeNode(node.id);
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

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
