// components/displays/ChartDisplay.tsx
// Inline chart preview that dispatches to the ChartManager modal on click

import { useCallback } from 'react';
import type { OutputDisplayOptions } from '@fig-node/core';

interface ChartDisplayProps {
  value: Record<string, unknown>;
  options?: OutputDisplayOptions;
}

export function ChartDisplay({ value }: ChartDisplayProps) {
  const handleClick = useCallback(() => {
    // Dispatch custom event that ChartManager listens for
    const allCharts = (value.charts ?? value) as Record<string, unknown>;
    const firstKey = Object.keys(allCharts)[0];
    if (firstKey) {
      window.dispatchEvent(
        new CustomEvent('open-chart-modal', {
          detail: {
            chart: allCharts[firstKey],
            allCharts,
          },
        }),
      );
    }
  }, [value]);

  const chartCount = Object.keys(value.charts ?? value).length;

  return (
    <div className="fig-display-chart nodrag" onClick={handleClick} role="button" tabIndex={0}>
      <div className="fig-chart-preview-icon">📊</div>
      <span className="fig-chart-preview-label">
        {chartCount} chart{chartCount !== 1 ? 's' : ''} — click to view
      </span>
    </div>
  );
}
