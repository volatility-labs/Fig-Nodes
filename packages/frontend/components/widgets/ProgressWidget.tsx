import type { BodyWidget } from '@sosa/core';
import type { WidgetProps } from './widget-registry';

type ProgressBodyWidget = Extract<BodyWidget, { type: 'progress' }>;
type ProgressWidgetProps = Omit<WidgetProps, 'widget'> & { widget: ProgressBodyWidget };

function ProgressWidget({ widget, value }: ProgressWidgetProps) {
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

export default ProgressWidget;
