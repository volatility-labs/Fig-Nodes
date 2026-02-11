import type { BodyWidget } from '@sosa/core';
import type { WidgetProps } from './widget-registry';

type BooleanBodyWidget = Extract<BodyWidget, { type: 'boolean' }>;
type BooleanWidgetProps = Omit<WidgetProps, 'widget'> & { widget: BooleanBodyWidget };

function BooleanWidget({ widget, value, onChange }: BooleanWidgetProps) {
  return (
    <div className="fig-widget">
      {widget.label && <label className="fig-widget-label">{widget.label}</label>}
      <select
        className="fig-widget-select"
        value={String(!!value)}
        onChange={(e) => onChange(e.target.value === 'true')}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    </div>
  );
}

export default BooleanWidget;
