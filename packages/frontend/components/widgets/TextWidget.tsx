import { BodyWidgetType, type BodyWidget } from '@sosa/core';
import type { WidgetProps } from './widget-registry';

type TextBodyWidget = Extract<BodyWidget, { type: BodyWidgetType.TEXT }>;
type TextWidgetProps = Omit<WidgetProps, 'widget'> & { widget: TextBodyWidget };

function TextWidget({ widget, value, onChange }: TextWidgetProps) {
  const strValue = value != null ? String(value) : '';
  return (
    <div className="fig-widget">
      {widget.label && <label className="fig-widget-label">{widget.label}</label>}
      <input
        className="fig-widget-input"
        type="text"
        value={strValue}
        placeholder={widget.options?.placeholder}
        onChange={(e) => onChange(e.target.value)}
        onPointerDown={(e) => e.stopPropagation()}
      />
    </div>
  );
}

export default TextWidget;
