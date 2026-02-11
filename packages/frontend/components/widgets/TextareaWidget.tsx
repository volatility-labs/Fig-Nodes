import type { BodyWidget } from '@sosa/core';
import type { WidgetProps } from './widget-registry';

type TextareaBodyWidget = Extract<BodyWidget, { type: 'textarea' | 'code' | 'json' }>;
type TextareaWidgetProps = Omit<WidgetProps, 'widget'> & { widget: TextareaBodyWidget };

function TextareaWidget({ widget, value, onChange }: TextareaWidgetProps) {
  const strValue = value != null ? String(value) : '';
  return (
    <div className="fig-widget">
      {widget.label && <label className="fig-widget-label">{widget.label}</label>}
      <textarea
        className="fig-widget-textarea"
        value={strValue}
        placeholder={widget.options?.placeholder}
        rows={3}
        onChange={(e) => onChange(e.target.value)}
        onPointerDown={(e) => e.stopPropagation()}
        onWheel={(e) => e.stopPropagation()}
      />
    </div>
  );
}

export default TextareaWidget;
