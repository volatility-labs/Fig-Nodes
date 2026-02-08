import { registerWidget, type WidgetProps } from './widget-registry';

function BooleanWidget({ widget, value, onChange }: WidgetProps) {
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

registerWidget('boolean', BooleanWidget);
export default BooleanWidget;
