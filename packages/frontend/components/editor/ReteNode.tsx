// components/editor/ReteNode.tsx
// Custom React component for Rete node rendering

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Presets } from 'rete-react-plugin';
import { getSocketKey, type BodyWidget as BodyWidgetModel, type BodyWidgetType, type ParamMeta } from '@sosa/core';
import type { FigReteNode } from './rete-adapter';
import { useGraphStore } from '../../stores/graphStore';
import type { NodeSchemaMap } from '../../types/nodes';
import { BodyWidget } from '../widgets/BodyWidget';
import { NodeDisplay } from '../displays/NodeDisplay';
import { markDirty } from './editor-actions';

// Shared metadata reference — set by the editor on init
let _nodeMetadata: NodeSchemaMap = {};
export function setNodeMetadata(meta: NodeSchemaMap): void {
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
  const nodeRef = useRef<HTMLDivElement>(null);

  const [collapsed, setCollapsed] = useState(false);
  const collapseRef = useRef<HTMLSpanElement>(null);

  // Params live on the FigReteNode — use local state for reactivity
  const [params, setParams] = useState<Record<string, unknown>>(node.params);

  // Execution state from store (kept in Zustand)
  const displayResult = useGraphStore(useCallback((s) => s.displayResults[nodeId], [nodeId]));
  const status = useGraphStore(useCallback((s) => s.nodeStatus[nodeId], [nodeId]));

  const executing = status?.executing ?? false;
  const progress = status?.progress;
  const error = status?.error;

  const handleHeaderDoubleClick = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  // Native pointerdown on collapse toggle — must intercept before Rete's drag handler
  useEffect(() => {
    const el = collapseRef.current;
    if (!el) return;
    const handler = (e: PointerEvent) => {
      e.stopPropagation();
      e.preventDefault();
      setCollapsed((prev) => !prev);
    };
    el.addEventListener('pointerdown', handler, { capture: true });
    return () => el.removeEventListener('pointerdown', handler, { capture: true });
  }, []);

  // Sync node dimensions after collapse toggle so minimap stays accurate
  useEffect(() => {
    requestAnimationFrame(() => {
      if (nodeRef.current) {
        const w = nodeRef.current.clientWidth;
        const h = nodeRef.current.clientHeight;
        if (w > 0 && h > 0) {
          node.width = w;
          node.height = h;
        }
      }
    });
  }, [collapsed, node]);

  const handleParamChange = useCallback(
    (key: string, value: unknown) => {
      const updated = { ...node.params, [key]: value };
      node.params = updated;
      setParams(updated);
      markDirty();
    },
    [node],
  );

  const toBodyWidgetType = (type: ParamMeta['type']): BodyWidgetType => {
    switch (type) {
      case 'text':
      case 'textarea':
      case 'number':
      case 'integer':
      case 'int':
      case 'float':
      case 'combo':
      case 'boolean':
        return type;
      case 'fileupload':
        // No dedicated body widget yet; fallback keeps params editable.
        return 'text';
      default:
        return 'text';
    }
  };

  const widgetFromParam = (param: ParamMeta): BodyWidgetModel => {
    const base = {
      id: param.name,
      bind: param.name,
      label: param.label ?? param.name,
      dataSource: Object.values(dataSources).find((ds) => ds.targetParam === param.name),
    };

    switch (toBodyWidgetType(param.type)) {
      case 'text':
        return {
          ...base,
          type: 'text',
          options: { placeholder: param.description },
        };
      case 'textarea':
        return {
          ...base,
          type: 'textarea',
          options: { placeholder: param.description },
        };
      case 'combo':
        return {
          ...base,
          type: 'combo',
          options: {
            options: Array.isArray(param.options) ? param.options : undefined,
          },
        };
      case 'number':
        return {
          ...base,
          type: 'number',
          options: { min: param.min, max: param.max, step: param.step, unit: param.unit },
        };
      case 'integer':
        return {
          ...base,
          type: 'integer',
          options: { min: param.min, max: param.max, step: param.step, unit: param.unit },
        };
      case 'int':
        return {
          ...base,
          type: 'int',
          options: { min: param.min, max: param.max, step: param.step, unit: param.unit },
        };
      case 'float':
        return {
          ...base,
          type: 'float',
          options: { min: param.min, max: param.max, step: param.step, unit: param.unit },
        };
      case 'boolean':
        return { ...base, type: 'boolean' };
      case 'progress':
        return { ...base, type: 'progress' };
      case 'status':
        return { ...base, type: 'status' };
      case 'image':
        return { ...base, type: 'image' };
      case 'chart':
        return { ...base, type: 'chart' };
      case 'table':
        return { ...base, type: 'table' };
      case 'custom':
        return { ...base, type: 'custom' };
      case 'code':
        return {
          ...base,
          type: 'code',
          options: { placeholder: param.description },
        };
      case 'json':
        return {
          ...base,
          type: 'json',
          options: { placeholder: param.description },
        };
      default:
        return {
          ...base,
          type: 'text',
          options: { placeholder: param.description },
        };
    }
  };

  // Build widget list from uiConfig or paramsMeta
  const bodyWidgets = meta?.uiConfig?.body ?? [];
  const paramsMeta = meta?.params ?? [];

  const dataSources = meta?.uiConfig?.dataSources ?? {};

  const effectiveWidgets: BodyWidgetModel[] = bodyWidgets.length > 0
    ? bodyWidgets
    : paramsMeta.map((p) => widgetFromParam(p));

  const outputDisplay = meta?.uiConfig?.outputDisplay;

  // Build input/output port data from metadata
  const inputPorts = meta?.inputs ?? [];
  const outputPorts = meta?.outputs ?? [];

  const formatPortLabel = (portName: string): string => portName.replace(/_/g, ' ');

  return (
    <div
      ref={nodeRef}
      className={`sosa ${node.selected ? 'selected' : ''} ${executing ? 'executing' : ''} ${error ? 'error' : ''} ${collapsed ? 'collapsed' : ''}`}
      style={{
        '--node-color': meta?.uiConfig?.color ?? '#2a2a2a',
        '--node-bgcolor': meta?.uiConfig?.bgcolor ?? '#1a1a1a',
      } as React.CSSProperties}
    >
      {/* Header */}
      <div className="sosa-header" onDoubleClick={handleHeaderDoubleClick}>
        <span className="sosa-title">{node.label}</span>
        <span className="sosa-header-right">
          {executing && (
            <span className="sosa-progress">
              {progress !== undefined ? `${Math.round(progress)}%` : '...'}
            </span>
          )}
          <span ref={collapseRef} className="sosa-collapse-toggle">{collapsed ? '+' : '\u2212'}</span>
        </span>
      </div>

      {/* Error banner */}
      {!collapsed && error && (
        <div className="sosa-error">{error}</div>
      )}

      {/* Input ports */}
      <div className={`sosa-inputs ${collapsed ? 'sosa-ports-collapsed' : ''}`}>
        {inputPorts.map((input) => {
          const socket = node.inputs[input.name];
          const isExec = getSocketKey(input) === 'exec';
          return (
            <div key={input.name} className={`sosa-port sosa-input-port${isExec ? ' fig-exec-port' : ''}`}>
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
              {!collapsed && (
                <>
                  <span className="sosa-port-label">{formatPortLabel(input.name)}</span>
                  {!isExec && (
                    <span className="sosa-port-type" title={`Socket: ${getSocketKey(input)}`}>
                      {getSocketKey(input)}
                    </span>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Body widgets */}
      {!collapsed && effectiveWidgets.length > 0 && (
        <div className="sosa-body">
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
      <div className={`sosa-outputs ${collapsed ? 'sosa-ports-collapsed' : ''}`}>
        {outputPorts.map((output) => {
          const socket = node.outputs[output.name];
          const isExec = getSocketKey(output) === 'exec';
          return (
            <div key={output.name} className={`sosa-port sosa-output-port${isExec ? ' fig-exec-port' : ''}`}>
              {!collapsed && !isExec && (
                <span className="sosa-port-type" title={`Socket: ${getSocketKey(output)}`}>
                  {getSocketKey(output)}
                </span>
              )}
              {!collapsed && (
                <span className="sosa-port-label">{formatPortLabel(output.name)}</span>
              )}
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
      {!collapsed && displayResult && outputDisplay && (
        <div className="sosa-display">
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
