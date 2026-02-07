// components/widgets/BodyWidget.tsx
// Reusable body widget renderer extracted from FigNode

import React, { memo } from 'react';

export interface BodyWidgetProps {
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

export const BodyWidget = memo(function BodyWidget({ widget, value, onChange }: BodyWidgetProps) {
  const strValue = value != null ? String(value) : '';

  // Stop pointer events from propagating to the Rete area plugin
  const stopPropagation = (e: React.PointerEvent) => e.stopPropagation();

  switch (widget.type) {
    case 'textarea':
    case 'code':
    case 'json':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <textarea
            className="fig-widget-textarea"
            value={strValue}
            placeholder={widget.options?.placeholder}
            rows={widget.options?.rows ?? 3}
            readOnly={widget.options?.readonly}
            onChange={(e) => onChange(e.target.value)}
            onPointerDown={stopPropagation}
            onWheel={(e) => e.stopPropagation()}
          />
        </div>
      );

    case 'text':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <input
            className="fig-widget-input"
            type="text"
            value={strValue}
            placeholder={widget.options?.placeholder}
            readOnly={widget.options?.readonly}
            onChange={(e) => onChange(e.target.value)}
            onPointerDown={stopPropagation}
          />
        </div>
      );

    case 'combo':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <select
            className="fig-widget-select"
            value={strValue}
            onChange={(e) => onChange(e.target.value)}
            onPointerDown={stopPropagation}
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
            className="fig-widget-number"
            type="number"
            value={value != null ? Number(value) : ''}
            min={widget.options?.min}
            max={widget.options?.max}
            step={widget.options?.step ?? (widget.type === 'integer' || widget.type === 'int' ? 1 : undefined)}
            onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
            onPointerDown={stopPropagation}
          />
        </div>
      );

    case 'boolean':
      return (
        <div className="fig-widget">
          {widget.label && <label className="fig-widget-label">{widget.label}</label>}
          <select
            className="fig-widget-select"
            value={String(!!value)}
            onChange={(e) => onChange(e.target.value === 'true')}
            onPointerDown={stopPropagation}
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
            className="fig-widget-input"
            type="text"
            value={strValue}
            onChange={(e) => onChange(e.target.value)}
            onPointerDown={stopPropagation}
          />
        </div>
      );
  }
});
