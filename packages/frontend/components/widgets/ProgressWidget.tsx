import { registerWidget, type WidgetProps } from './widget-registry';

function ProgressWidget({ widget, value }: WidgetProps) {
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
}

registerWidget('progress', ProgressWidget);
export default ProgressWidget;
