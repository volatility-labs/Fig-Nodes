// components/FigNode.tsx
// Generic node component that renders ALL node types, driven by backend uiConfig.

import React, { useCallback, memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { FigNodeData } from '../stores/flow-adapter';
import { useGraphStore } from '../stores/graph-store';
import { NodeDisplay } from './displays/NodeDisplay';

function FigNodeComponent({ id, data }: NodeProps) {
  const nodeData = data as unknown as FigNodeData;

  // Dynamic state — read directly from the store so param changes don't
  // trigger a full React Flow node-list recompute (which would steal focus).
  const params = useGraphStore(useCallback((s) => s.doc.nodes[id]?.params ?? {}, [id]));
  const displayResult = useGraphStore(useCallback((s) => s.displayResults[id], [id]));
  const status = useGraphStore(useCallback((s) => s.nodeStatus[id], [id]));
  const setParam = useGraphStore((s) => s.setParam);

  const executing = status?.executing ?? false;
  const progress = status?.progress;
  const error = status?.error;

  const handleParamChange = useCallback(
    (key: string, value: unknown) => {
      setParam(id, key, value);
    },
    [id, setParam],
  );

  // Auto-generate widgets from paramsMeta when uiConfig.body is empty
  const bodyWidgets = nodeData.uiConfig?.body ?? [];
  const paramsMeta = nodeData.paramsMeta ?? [];

  const effectiveWidgets = bodyWidgets.length > 0
    ? bodyWidgets.map((w) => ({
        type: w.type,
        id: w.id,
        label: w.label,
        bind: w.bind,
        options: w.options as BodyWidgetProps['widget']['options'],
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

  const outputDisplay = nodeData.uiConfig?.outputDisplay;

  return (
    <div
      className={`fig-node ${executing ? 'executing' : ''} ${error ? 'error' : ''}`}
      style={{
        '--node-color': nodeData.uiConfig?.color ?? '#2a2a2a',
        '--node-bgcolor': nodeData.uiConfig?.bgcolor ?? '#1a1a1a',
      } as React.CSSProperties}
    >
      {/* Header */}
      <div className="fig-node-header">
        <span className="fig-node-title">{nodeData.title ?? nodeData.type}</span>
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

      {/* Input handles */}
      <div className="fig-node-inputs">
        {nodeData.inputs.map((input) => (
          <div key={input.name} className="fig-node-port fig-node-input-port">
            <Handle
              type="target"
              position={Position.Left}
              id={input.name}
            />
            <span className="fig-node-port-label">{input.name}</span>
          </div>
        ))}
      </div>

      {/* Body widgets from uiConfig or auto-generated from paramsMeta */}
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

      {/* Output handles */}
      <div className="fig-node-outputs">
        {nodeData.outputs.map((output) => (
          <div key={output.name} className="fig-node-port fig-node-output-port">
            <span className="fig-node-port-label">{output.name}</span>
            <Handle
              type="source"
              position={Position.Right}
              id={output.name}
            />
          </div>
        ))}
      </div>

      {/* Display area (charts, images, text output) */}
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

// ============ Body Widget Renderer ============

interface BodyWidgetProps {
  widget: {
    type: string;
    id: string;
    label?: string;
    bind?: string;
    options?: {
      placeholder?: string;
      rows?: number;
      readonly?: boolean;
      options?: Array<string | number | boolean>;
      min?: number;
      max?: number;
      step?: number;
      [key: string]: unknown;
    };
    dataSource?: {
      endpoint: string;
      fallback?: unknown[];
      [key: string]: unknown;
    };
  };
  value: unknown;
  onChange: (value: unknown) => void;
}

const BodyWidget = memo(function BodyWidget({ widget, value, onChange }: BodyWidgetProps) {
  const strValue = value != null ? String(value) : '';

  switch (widget.type) {
    case 'textarea':
    case 'code':
    case 'json':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <textarea
            className="fig-widget-textarea nodrag nowheel"
            value={strValue}
            placeholder={widget.options?.placeholder}
            rows={widget.options?.rows ?? 3}
            readOnly={widget.options?.readonly}
            onChange={(e) => onChange(e.target.value)}
          />
        </div>
      );

    case 'text':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <input
            className="fig-widget-input nodrag"
            type="text"
            value={strValue}
            placeholder={widget.options?.placeholder}
            readOnly={widget.options?.readonly}
            onChange={(e) => onChange(e.target.value)}
          />
        </div>
      );

    case 'combo':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <select
            className="fig-widget-select nodrag"
            value={strValue}
            onChange={(e) => onChange(e.target.value)}
          >
            {(widget.options?.options ?? []).map((opt) => (
              <option key={String(opt)} value={String(opt)}>
                {String(opt)}
              </option>
            ))}
          </select>
        </div>
      );

    case 'number':
    case 'integer':
    case 'int':
    case 'float':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <input
            className="fig-widget-number nodrag"
            type="number"
            value={value != null ? Number(value) : ''}
            min={widget.options?.min}
            max={widget.options?.max}
            step={widget.options?.step ?? (widget.type === 'integer' || widget.type === 'int' ? 1 : undefined)}
            onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          />
        </div>
      );

    case 'boolean':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <select
            className="fig-widget-select nodrag"
            value={String(!!value)}
            onChange={(e) => onChange(e.target.value === 'true')}
          >
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        </div>
      );

    case 'progress':
      return (
        <div className="fig-widget fig-widget-progress">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <div className="fig-progress-bar">
            <div
              className="fig-progress-fill"
              style={{ width: `${typeof value === 'number' ? value : 0}%` }}
            />
          </div>
        </div>
      );

    case 'status':
      return (
        <div className="fig-widget fig-widget-status">
          <span className="fig-status-text">{strValue}</span>
        </div>
      );

    default:
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <input
            className="fig-widget-input nodrag"
            type="text"
            value={strValue}
            onChange={(e) => onChange(e.target.value)}
          />
        </div>
      );
  }
});

export const FigNode = memo(FigNodeComponent);
