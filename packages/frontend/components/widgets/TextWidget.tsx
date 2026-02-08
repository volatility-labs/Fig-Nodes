import { registerWidget, type WidgetProps } from './widget-registry';

function TextWidget({ widget, value, onChange }: WidgetProps) {
  const strValue = value != null ? String(value) : '';
  return (
    <div className="fig-widget">
      {widget.label && <label className="fig-widget-label">{widget.label}</label>}
      <input
        className="fig-widget-input"
        type="text"
        value={strValue}
        placeholder={widget.options?.placeholder as string | undefined}
        readOnly={widget.options?.readonly as boolean | undefined}
        onChange={(e) => onChange(e.target.value)}
        onPointerDown={(e) => e.stopPropagation()}
      />
    </div>
  );
}

registerWidget('text', TextWidget);
export default TextWidget;
