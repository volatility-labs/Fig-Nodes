// components/editor/ReteEditor.tsx
// Main Rete.js v2 editor component — Rete is the single source of truth for graph structure.
// Non-component exports (undo, redo, autoArrange, dirty flag) live in editor-actions.ts
// to keep this file Fast Refresh–compatible.

import React, { useCallback, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { ClassicPreset, NodeEditor } from 'rete';
import { AreaPlugin, AreaExtensions } from 'rete-area-plugin';
import { ConnectionPlugin, Presets as ConnectionPresets } from 'rete-connection-plugin';
import { ReactPlugin, Presets as ReactPresets } from 'rete-react-plugin';
import styled from 'styled-components';
import { MinimapPlugin } from 'rete-minimap-plugin';
import { HistoryPlugin, Presets as HistoryPresets } from 'rete-history-plugin';
import { AutoArrangePlugin, Presets as ArrangePresets } from 'rete-auto-arrange-plugin';
import { ContextMenuPlugin, Presets as ContextMenuPresets } from 'rete-context-menu-plugin';
import { getDOMSocketPosition } from 'rete-render-utils';
import { getSocketKey, areSocketKeysCompatible, getOrCreateSocket } from '@sosa/core';

import type { NodeMetadataMap } from '../../types/nodes';
import { typeColor } from './type-colors';
import {
  ReteAdapter,
  FigReteNode,
  type FrontendSchemes,
  type AreaExtra,
} from './rete-adapter';
import { setEditorAdapter } from './editor-ref';
import { editorRefs, markDirty, undo, redo } from './editor-actions';
import { restoreFromAutosave } from '../../services/FileManager';
import { ReteNodeComponent, setNodeMetadata } from './ReteNode';
import { NodePalette } from '../NodePalette';
import { LogPanel } from '../LogPanel';
import { addNodeToEditor } from './add-node';

// ============ Module-level refs for render components (connection coloring) ============

let _editorRef: NodeEditor<FrontendSchemes> | null = null;
let _metaRef: NodeMetadataMap = {};

// ============ Context Menu Item (filters non-standard DOM props from rete-react-plugin) ============

const ContextMenuItem = styled.div.withConfig({
  shouldForwardProp: (prop) => prop !== 'hasSubitems',
})`
  color: #fff;
  padding: 4px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  background-color: rgba(110, 136, 255, 0.8);
  cursor: pointer;
  width: 100%;
  position: relative;
  &:first-child { border-top-left-radius: 5px; border-top-right-radius: 5px; }
  &:last-child { border-bottom-left-radius: 5px; border-bottom-right-radius: 5px; }
  &:hover { background-color: rgba(130, 153, 255, 0.8); }
  ${(props: any) => props.hasSubitems && `
    &:after {
      content: '\u25BA';
      position: absolute;
      opacity: 0.6;
      right: 5px;
      top: 5px;
    }
  `}
`;

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
  let strokeWidth = 2;
  let dashArray: string | undefined;

  if (_editorRef && props.data.sourceOutput) {
    try {
      const sourceNode = _editorRef.getNode(props.data.source);
      if (sourceNode) {
          const meta = _metaRef[sourceNode.nodeType];
          if (meta) {
            const outputSpec = meta.outputs[props.data.sourceOutput];
            if (outputSpec) {
              const key = getSocketKey(outputSpec);
              if (key === 'exec') {
                color = '#FFFFFF';
                strokeWidth = 3;
                dashArray = '8 4';
              } else {
                color = typeColor(outputSpec);
              }
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
        strokeWidth={strokeWidth}
        strokeDasharray={dashArray}
        style={{ pointerEvents: 'auto' }}
      />
    </svg>
  );
}

// ============ Editor Props ============

interface ReteEditorProps {
  nodeMetadata: NodeMetadataMap;
}

export function ReteEditor({ nodeMetadata }: ReteEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const adapterRef = useRef<ReteAdapter | null>(null);
  const areaRef = useRef<AreaPlugin<FrontendSchemes, AreaExtra> | null>(null);

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
    const minimap = new MinimapPlugin<FrontendSchemes>({ minDistance: 800 });
    const history = new HistoryPlugin<FrontendSchemes>();
    const arrange = new AutoArrangePlugin<FrontendSchemes>();

    areaRef.current = area;

    // Set module-level refs for render components (connection coloring)
    _editorRef = editor;
    _metaRef = nodeMetadata;

    // Set shared refs for editor-actions (undo/redo/arrange/dirty)
    editorRefs.editor = editor;
    editorRefs.area = area;
    editorRefs.history = history;
    editorRefs.arrange = arrange;

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

    // Minimap rendering
    reactPlugin.addPreset(ReactPresets.minimap.setup({ size: 200 }) as any);

    // Context menu rendering (custom item filters non-standard DOM props)
    reactPlugin.addPreset(ReactPresets.contextMenu.setup({
      customize: {
        item() { return ContextMenuItem as any; },
      },
    }) as any);

    // Connection preset
    connection.addPreset(ConnectionPresets.classic.setup() as any);

    // History preset
    history.addPreset(HistoryPresets.classic.setup());

    // Auto-arrange preset
    arrange.addPreset(ArrangePresets.classic.setup());

    // Context menu plugin — build node factories from metadata
    const nodeFactories: [string, () => FigReteNode][] = Object.entries(nodeMetadata).map(
      ([typeName, meta]) => [
        typeName,
        () => {
          const id = `${typeName.toLowerCase()}_${Date.now()}`;
          const node = new FigReteNode(
            id,
            typeName,
            typeName,
            meta.defaultParams ? { ...meta.defaultParams } : {},
          );
          // Wire sockets from metadata
          for (const [name, spec] of Object.entries(meta.inputs)) {
            const socket = getOrCreateSocket(spec);
            node.addInput(name, new ClassicPreset.Input(socket, name, (spec as any).multi ?? false));
          }
          for (const [name, spec] of Object.entries(meta.outputs)) {
            const socket = getOrCreateSocket(spec);
            node.addOutput(name, new ClassicPreset.Output(socket, name));
          }
          return node;
        },
      ],
    );
    const contextMenu = new ContextMenuPlugin<FrontendSchemes>({
      items: ContextMenuPresets.classic.setup(nodeFactories),
    });

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

    // ============ Sync node dimensions for minimap ============
    area.addPipe((ctx) => {
      if (ctx.type === 'render' && ctx.data.type === 'node') {
        // After a node renders, sync its actual DOM size to node.width/height
        // so the minimap reflects real dimensions.
        // clientWidth is already the unscaled layout width (CSS transforms
        // on the parent content holder don't affect it).
        const nodeId = ctx.data.payload.id;
        requestAnimationFrame(() => {
          const view = area.nodeViews.get(nodeId);
          const node = editor.getNode(nodeId);
          if (view?.element && node) {
            const w = view.element.clientWidth;
            const h = view.element.clientHeight;
            if (w > 0 && h > 0) {
              node.width = w;
              node.height = h;
            }
          }
        });
      }
      return ctx;
    });

    // ============ Wire plugins ============
    editor.use(area);
    area.use(connection as any);
    area.use(reactPlugin as any);
    area.use(minimap as any);
    area.use(history as any);
    area.use(arrange as any);
    area.use(contextMenu as any);

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
      editorRefs.editor = null;
      editorRefs.area = null;
      editorRefs.history = null;
      editorRefs.arrange = null;
      setEditorAdapter(null as any);
      area.destroy();
    };
  }, [nodeMetadata]);

  // ============ Drag-and-drop from palette ============
  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/sosa-type');
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

  // ============ Keyboard shortcuts ============
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't interfere with inputs
      if ((e.target as HTMLElement).tagName === 'INPUT' ||
          (e.target as HTMLElement).tagName === 'TEXTAREA' ||
          (e.target as HTMLElement).tagName === 'SELECT') {
        return;
      }

      // Undo: Ctrl+Z (without Shift)
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
        return;
      }

      // Redo: Ctrl+Shift+Z or Ctrl+Y
      if ((e.ctrlKey || e.metaKey) && ((e.key === 'z' && e.shiftKey) || e.key === 'y')) {
        e.preventDefault();
        redo();
        return;
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
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
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      />
      <LogPanel />
    </div>
  );
}
