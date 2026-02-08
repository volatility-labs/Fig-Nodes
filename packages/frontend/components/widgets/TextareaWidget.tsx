import { registerWidget, type WidgetProps } from './widget-registry';

function TextareaWidget({ widget, value, onChange }: WidgetProps) {
  const strValue = value != null ? String(value) : '';
  return (
    <div className="fig-widget">
      {widget.label && <label className="fig-widget-label">{widget.label}</label>}
      <textarea
        className="fig-widget-textarea"
        value={strValue}
        placeholder={widget.options?.placeholder as string | undefined}
        rows={(widget.options?.rows as number) ?? 3}
        readOnly={widget.options?.readonly as boolean | undefined}
        onChange={(e) => onChange(e.target.value)}
        onPointerDown={(e) => e.stopPropagation()}
        onWheel={(e) => e.stopPropagation()}
      />
    </div>
  );
}

registerWidget('textarea', TextareaWidget);
registerWidget('code', TextareaWidget);
registerWidget('json', TextareaWidget);
export default TextareaWidget;
