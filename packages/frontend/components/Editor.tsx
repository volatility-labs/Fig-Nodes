// components/Editor.tsx
// Main graph editor component wrapping React Flow

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Connection,
  type NodeChange,
  type EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { FigNode } from './FigNode';
import { ContextMenu } from './ContextMenu';
import { NodePalette } from './NodePalette';
import { useGraphStore } from '../stores/graph-store';
import {
  toFlowNodes,
  toFlowEdges,
  connectionToEdge,
  type NodeMetadataMap,
  type FigNodeData,
} from '../stores/flow-adapter';
import type { GraphNode } from '@fig-node/core';

const nodeTypes = { figNode: FigNode };

interface EditorInnerProps {
  nodeMetadata: NodeMetadataMap;
}

function EditorInner({ nodeMetadata }: EditorInnerProps) {
  const reactFlowInstance = useReactFlow();

  // Graph store state
  const doc = useGraphStore((s) => s.doc);
  const addEdge = useGraphStore((s) => s.addEdge);
  const removeEdge = useGraphStore((s) => s.removeEdge);
  const removeNode = useGraphStore((s) => s.removeNode);
  const updateNodePosition = useGraphStore((s) => s.updateNodePosition);
  const addNode = useGraphStore((s) => s.addNode);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId?: string;
    canvasPosition: { x: number; y: number };
  } | null>(null);

  // Structural keys — only change when nodes/edges are added, removed, or repositioned
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const structuralKey = useMemo(() => {
    return Object.entries(doc.nodes)
      .map(([id, n]) => `${id}:${n.type}:${n.position?.[0] ?? 0}:${n.position?.[1] ?? 0}:${n.title ?? ''}`)
      .join('|');
  }, [doc]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const edgesKey = useMemo(() => {
    return doc.edges.map((e) => `${e.from}->${e.to}`).join('|');
  }, [doc]);

  // Derive React Flow nodes/edges — only recomputes on structural changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const flowNodes = useMemo(
    () => toFlowNodes(doc, nodeMetadata),
    [structuralKey, nodeMetadata],
  );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const flowEdges = useMemo(
    () => toFlowEdges(doc),
    [edgesKey],
  );

  // Local React Flow state for smooth interactions
  const [nodes, setNodes] = useState<Node<FigNodeData>[]>(flowNodes);
  const [edges, setEdges] = useState<Edge[]>(flowEdges);

  // Sync from store to local state when store changes
  useEffect(() => { setNodes(flowNodes); }, [flowNodes]);
  useEffect(() => { setEdges(flowEdges); }, [flowEdges]);

  // Handle node position changes
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds) as Node<FigNodeData>[]);

      // Sync position changes back to store on drag end
      for (const change of changes) {
        if (change.type === 'position' && change.dragging === false && change.position) {
          updateNodePosition(change.id, [change.position.x, change.position.y]);
        }
        if (change.type === 'remove') {
          removeNode(change.id);
        }
      }
    },
    [updateNodePosition, removeNode],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((eds) => applyEdgeChanges(changes, eds));

      for (const change of changes) {
        if (change.type === 'remove') {
          // Find the edge in the store and remove it
          const edge = edges.find((e) => e.id === change.id);
          if (edge?.sourceHandle && edge?.targetHandle) {
            removeEdge(
              `${edge.source}.${edge.sourceHandle}`,
              `${edge.target}.${edge.targetHandle}`,
            );
          }
        }
      }
    },
    [edges, removeEdge],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const edge = connectionToEdge(connection);
      if (edge) addEdge(edge);
    },
    [addEdge],
  );

  // Context menu
  const onPaneContextMenu = useCallback(
    (event: React.MouseEvent | MouseEvent) => {
      event.preventDefault();
      const position = reactFlowInstance.screenToFlowPosition({
        x: (event as MouseEvent).clientX,
        y: (event as MouseEvent).clientY,
      });
      setContextMenu({
        x: (event as MouseEvent).clientX,
        y: (event as MouseEvent).clientY,
        canvasPosition: position,
      });
    },
    [reactFlowInstance],
  );

  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault();
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      setContextMenu({
        x: event.clientX,
        y: event.clientY,
        nodeId: node.id,
        canvasPosition: position,
      });
    },
    [reactFlowInstance],
  );

  // Drag-and-drop from palette
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/fig-node-type');
      if (!type) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const meta = nodeMetadata[type];
      const id = `${type.toLowerCase()}_${Date.now()}`;
      const node: GraphNode = {
        type,
        params: meta?.defaultParams ? { ...meta.defaultParams } : {},
        position: [position.x, position.y],
      };
      addNode(id, node);
    },
    [reactFlowInstance, nodeMetadata, addNode],
  );

  return (
    <div className="fig-editor-container">
      <NodePalette nodeMetadata={nodeMetadata} />
      <div className="fig-flow-container">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onPaneContextMenu={onPaneContextMenu}
          onNodeContextMenu={onNodeContextMenu}
          onDragOver={onDragOver}
          onDrop={onDrop}
          fitView
          deleteKeyCode={['Backspace', 'Delete']}
        >
          <Background />
          <Controls />
          <MiniMap
            style={{ background: '#1a1a1a' }}
            maskColor="rgba(0, 0, 0, 0.5)"
          />
        </ReactFlow>

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
    </div>
  );
}

// ============ Wrapper with Provider ============

interface EditorProps {
  nodeMetadata: NodeMetadataMap;
}

export function Editor({ nodeMetadata }: EditorProps) {
  return (
    <ReactFlowProvider>
      <EditorInner nodeMetadata={nodeMetadata} />
    </ReactFlowProvider>
  );
}
