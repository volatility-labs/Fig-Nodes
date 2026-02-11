import { BodyWidgetType, type BodyWidget } from '@sosa/core';
import type { WidgetProps } from './widget-registry';

type StatusBodyWidget = Extract<BodyWidget, { type: BodyWidgetType.STATUS }>;
type StatusWidgetProps = Omit<WidgetProps, 'widget'> & { widget: StatusBodyWidget };

function StatusWidget({ value }: StatusWidgetProps) {
  const strValue = value != null ? String(value) : '';
  return (
    <div className="fig-widget fig-widget-status">
      <span className="fig-status-text">{strValue}</span>
    </div>
  );
}

export default StatusWidget;
