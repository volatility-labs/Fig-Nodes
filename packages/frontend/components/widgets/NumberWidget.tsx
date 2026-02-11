import type { BodyWidget } from '@sosa/core';
import type { WidgetProps } from './widget-registry';

type NumberBodyWidget = Extract<BodyWidget, { type: 'number' | 'integer' | 'int' | 'float' }>;
type NumberWidgetProps = Omit<WidgetProps, 'widget'> & { widget: NumberBodyWidget };

function NumberWidget({ widget, value, onChange }: NumberWidgetProps) {
  const type = widget.type;
  const isInteger = type === 'integer' || type === 'int';
  const unit = widget.options?.unit;
  const label = widget.label
    ? unit
      ? `${widget.label} (${unit})`
      : widget.label
    : undefined;
  return (
    <div className="fig-widget">
      {label && <label className="fig-widget-label">{label}</label>}
      <input
        className="fig-widget-number"
        type="number"
        value={value != null ? Number(value) : ''}
        min={widget.options?.min}
        max={widget.options?.max}
        step={widget.options?.step ?? (isInteger ? 1 : undefined)}
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        onPointerDown={(e) => e.stopPropagation()}
      />
    </div>
  );
}

export default NumberWidget;
