// components/displays/ChartDisplay.tsx
// Static chart preview — shows chart count from execution results

import type { OutputDisplayOptions } from '@fig-node/core';

interface ChartDisplayProps {
  value: Record<string, unknown>;
  options?: OutputDisplayOptions;
}

export function ChartDisplay({ value }: ChartDisplayProps) {
  const chartCount = Object.keys(value.charts ?? value).length;

  return (
    <div className="fig-display-chart nodrag">
      <div className="fig-chart-preview-icon">📊</div>
      <span className="fig-chart-preview-label">
        {chartCount} chart{chartCount !== 1 ? 's' : ''}
      </span>
    </div>
  );
}
