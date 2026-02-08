import { registerWidget, type WidgetProps } from './widget-registry';

function StatusWidget({ value }: WidgetProps) {
  const strValue = value != null ? String(value) : '';
  return (
    <div className="fig-widget fig-widget-status">
      <span className="fig-status-text">{strValue}</span>
    </div>
  );
}

registerWidget('status', StatusWidget);
export default StatusWidget;
