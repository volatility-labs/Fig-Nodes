// rete/components/ReteNode.tsx
// Custom React component for Rete node rendering

import React, { useCallback } from 'react';
import { Presets } from 'rete-react-plugin';
import type { FigReteNode } from '../rete-adapter';
import { useGraphStore } from '../../stores/graph-store';
import type { NodeMetadataMap } from '../../types/node-metadata';
import { BodyWidget } from '../../components/widgets/BodyWidget';
import { NodeDisplay } from '../../components/displays/NodeDisplay';

// Shared metadata reference — set by the editor on init
let _nodeMetadata: NodeMetadataMap = {};
export function setNodeMetadata(meta: NodeMetadataMap): void {
  _nodeMetadata = meta;
}

// ============ Rete Node Component ============

interface ReteNodeProps {
  data: FigReteNode;
  emit: (data: { type: string; data: unknown }) => void;
}

export function ReteNodeComponent({ data: node }: ReteNodeProps) {
  const figNodeId = node.figNodeId;
  const nodeType = node.nodeType;
  const meta = _nodeMetadata[nodeType];

  // Dynamic state from store
  const params = useGraphStore(useCallback((s) => s.doc.nodes[figNodeId]?.params ?? {}, [figNodeId]));
  const displayResult = useGraphStore(useCallback((s) => s.displayResults[figNodeId], [figNodeId]));
  const status = useGraphStore(useCallback((s) => s.nodeStatus[figNodeId], [figNodeId]));
  const setParam = useGraphStore((s) => s.setParam);

  const executing = status?.executing ?? false;
  const progress = status?.progress;
  const error = status?.error;

  const handleParamChange = useCallback(
    (key: string, value: unknown) => {
      setParam(figNodeId, key, value);
    },
    [figNodeId, setParam],
  );

  // Build widget list from uiConfig or paramsMeta
  const bodyWidgets = meta?.uiConfig?.body ?? [];
  const paramsMeta = meta?.params ?? [];

  const effectiveWidgets = bodyWidgets.length > 0
    ? bodyWidgets.map((w) => ({
        type: w.type,
        id: w.id,
        label: w.label,
        bind: w.bind,
        options: w.options as Record<string, unknown> | undefined,
      }))
    : paramsMeta.map((p) => ({
        type: p.type ?? 'text',
        id: p.name,
        bind: p.name,
        label: p.label ?? p.name,
        options: {
          options: Array.isArray(p.options) ? p.options as Array<string | number | boolean> : undefined,
          min: p.min,
          max: p.max,
          step: p.step,
          placeholder: p.description,
        },
      }));

  const outputDisplay = meta?.uiConfig?.outputDisplay;

  // Build input/output port data from metadata
  const inputPorts = meta
    ? Object.entries(meta.inputs).map(([name, type]) => ({ name, type: String(type) }))
    : [];
  const outputPorts = meta
    ? Object.entries(meta.outputs).map(([name, type]) => ({ name, type: String(type) }))
    : [];

  return (
    <div
      className={`fig-node ${executing ? 'executing' : ''} ${error ? 'error' : ''}`}
      style={{
        '--node-color': meta?.uiConfig?.color ?? '#2a2a2a',
        '--node-bgcolor': meta?.uiConfig?.bgcolor ?? '#1a1a1a',
      } as React.CSSProperties}
    >
      {/* Header */}
      <div className="fig-node-header">
        <span className="fig-node-title">{node.label}</span>
        {executing && (
          <span className="fig-node-progress">
            {progress !== undefined ? `${Math.round(progress)}%` : '...'}
          </span>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="fig-node-error">{error}</div>
      )}

      {/* Input ports */}
      <div className="fig-node-inputs">
        {inputPorts.map((input) => {
          const socket = node.inputs[input.name];
          return (
            <div key={input.name} className="fig-node-port fig-node-input-port">
              {socket && (
                <Presets.classic.Socket data={socket.socket!} />
              )}
              <span className="fig-node-port-label">{input.name}</span>
            </div>
          );
        })}
      </div>

      {/* Body widgets */}
      {effectiveWidgets.length > 0 && (
        <div className="fig-node-body">
          {effectiveWidgets.map((widget) => (
            <BodyWidget
              key={widget.id}
              widget={widget}
              value={params[widget.bind ?? widget.id]}
              onChange={(v) => handleParamChange(widget.bind ?? widget.id, v)}
            />
          ))}
        </div>
      )}

      {/* Output ports */}
      <div className="fig-node-outputs">
        {outputPorts.map((output) => {
          const socket = node.outputs[output.name];
          return (
            <div key={output.name} className="fig-node-port fig-node-output-port">
              <span className="fig-node-port-label">{output.name}</span>
              {socket && (
                <Presets.classic.Socket data={socket.socket!} />
              )}
            </div>
          );
        })}
      </div>

      {/* Display area */}
      {displayResult && outputDisplay && (
        <div className="fig-node-display">
          <NodeDisplay
            type={outputDisplay.type}
            value={displayResult}
            options={outputDisplay.options}
          />
        </div>
      )}
    </div>
  );
}
