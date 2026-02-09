import { registerWidget, type WidgetProps } from './widget-registry';

function NumberWidget({ widget, value, onChange }: WidgetProps) {
  const type = widget.type;
  const isInteger = type === 'integer' || type === 'int';
  const unit = widget.options?.unit as string | undefined;
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
        min={widget.options?.min as number | undefined}
        max={widget.options?.max as number | undefined}
        step={(widget.options?.step as number | undefined) ?? (isInteger ? 1 : undefined)}
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        onPointerDown={(e) => e.stopPropagation()}
      />
    </div>
  );
}

registerWidget('number', NumberWidget);
registerWidget('integer', NumberWidget);
registerWidget('int', NumberWidget);
registerWidget('float', NumberWidget);
export default NumberWidget;
