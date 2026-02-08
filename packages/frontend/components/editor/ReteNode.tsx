// components/editor/ReteNode.tsx
// Custom React component for Rete node rendering

import React, { useCallback, useState } from 'react';
import { Presets } from 'rete-react-plugin';
import { getSocketKey } from '@fig-node/core';
import type { FigReteNode } from './rete-adapter';
import { useGraphStore } from '../../stores/graphStore';
import type { NodeMetadataMap } from '../../types/nodes';
import { BodyWidget } from '../widgets/BodyWidget';
import { NodeDisplay } from '../displays/NodeDisplay';
import { markDirty } from './editor-actions';

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

export function ReteNodeComponent({ data: node, emit }: ReteNodeProps) {
  const nodeId = node.id;
  const nodeType = node.nodeType;
  const meta = _nodeMetadata[nodeType];

  // Params live on the FigReteNode — use local state for reactivity
  const [params, setParams] = useState<Record<string, unknown>>(node.params);

  // Execution state from store (kept in Zustand)
  const displayResult = useGraphStore(useCallback((s) => s.displayResults[nodeId], [nodeId]));
  const status = useGraphStore(useCallback((s) => s.nodeStatus[nodeId], [nodeId]));

  const executing = status?.executing ?? false;
  const progress = status?.progress;
  const error = status?.error;

  const handleParamChange = useCallback(
    (key: string, value: unknown) => {
      const updated = { ...node.params, [key]: value };
      node.params = updated;
      setParams(updated);
      markDirty();
    },
    [node],
  );

  // Build widget list from uiConfig or paramsMeta
  const bodyWidgets = meta?.uiConfig?.body ?? [];
  const paramsMeta = meta?.params ?? [];

  const dataSources = meta?.uiConfig?.dataSources ?? {};

  const effectiveWidgets = bodyWidgets.length > 0
    ? bodyWidgets.map((w) => ({
        type: w.type,
        id: w.id,
        label: w.label,
        bind: w.bind,
        options: w.options as Record<string, unknown> | undefined,
        dataSource: w.dataSource,
      }))
    : paramsMeta.map((p) => {
        const matchingDs = Object.values(dataSources).find((ds) => ds.targetParam === p.name);
        return {
          type: p.type ?? 'text',
          id: p.name,
          bind: p.name,
          label: p.label ?? p.name,
          dataSource: matchingDs,
          options: {
            options: Array.isArray(p.options) ? p.options as Array<string | number | boolean> : undefined,
            min: p.min,
            max: p.max,
            step: p.step,
            placeholder: p.description,
          },
        };
      });

  const outputDisplay = meta?.uiConfig?.outputDisplay;

  // Build input/output port data from metadata
  const inputPorts = meta
    ? Object.entries(meta.inputs).map(([name, spec]) => ({ name, spec }))
    : [];
  const outputPorts = meta
    ? Object.entries(meta.outputs).map(([name, spec]) => ({ name, spec }))
    : [];

  const formatPortLabel = (portName: string): string => portName.replace(/_/g, ' ');

  return (
    <div
      className={`fig-node ${node.selected ? 'selected' : ''} ${executing ? 'executing' : ''} ${error ? 'error' : ''}`}
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
          const isExec = getSocketKey(input.spec) === 'exec';
          return (
            <div key={input.name} className={`fig-node-port fig-node-input-port${isExec ? ' fig-exec-port' : ''}`}>
              {socket && (
                <Presets.classic.RefSocket
                  name="input-socket"
                  side="input"
                  socketKey={input.name}
                  nodeId={node.id}
                  emit={emit as any}
                  payload={socket.socket!}
                  data-testid="input-socket"
                />
              )}
              <span className="fig-node-port-label">{formatPortLabel(input.name)}</span>
              {!isExec && (
                <span className="fig-node-port-type" title={`Socket: ${getSocketKey(input.spec)}`}>
                  {getSocketKey(input.spec)}
                </span>
              )}
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
          const isExec = getSocketKey(output.spec) === 'exec';
          return (
            <div key={output.name} className={`fig-node-port fig-node-output-port${isExec ? ' fig-exec-port' : ''}`}>
              {!isExec && (
                <span className="fig-node-port-type" title={`Socket: ${getSocketKey(output.spec)}`}>
                  {getSocketKey(output.spec)}
                </span>
              )}
              <span className="fig-node-port-label">{formatPortLabel(output.name)}</span>
              {socket && (
                <Presets.classic.RefSocket
                  name="output-socket"
                  side="output"
                  socketKey={output.name}
                  nodeId={node.id}
                  emit={emit as any}
                  payload={socket.socket!}
                  data-testid="output-socket"
                />
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
