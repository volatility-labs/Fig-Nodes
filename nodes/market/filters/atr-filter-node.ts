// src/nodes/core/market/filters/atr-filter-node.ts

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import type { NodeDefinition } from '@fig-node/core';
import { IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type IndicatorResult } from '../types';
import { calculateAtr } from '../calculators/atr-calculator';

/**
 * Filters assets based on ATR (Average True Range) values.
 */
export class ATRFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    defaults: {
      min_atr: 0.0,
      window: 14,
    },
    params: [
      { name: 'min_atr', type: 'number', default: 0.0, min: 0.0, step: 0.1 },
      { name: 'window', type: 'number', default: 14, min: 1, step: 1 },
    ],
    ui: {
      resultDisplay: 'none',
      actions: [
        { id: 'previewFiltered', label: 'Preview Filtered', icon: '👁' },
        { id: 'copySummary', label: 'Copy Summary', icon: '📋' },
      ],
    },
  };

  protected override validateIndicatorParams(): void {
    const minAtr = this.params.min_atr ?? 0.0;
    const window = this.params.window ?? 14;

    if (typeof minAtr !== 'number' || minAtr < 0) {
      throw new Error('Minimum ATR cannot be negative');
    }
    if (typeof window !== 'number' || window <= 0) {
      throw new Error('Window must be positive');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATR,
        timestamp: 0,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'No data',
      });
    }

    const windowParam = this.params.window;
    const window = Math.floor(typeof windowParam === 'number' ? windowParam : 14);

    if (ohlcvData.length < window) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATR,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Extract lists for the calculator
    const highs = ohlcvData.map((bar) => bar.high);
    const lows = ohlcvData.map((bar) => bar.low);
    const closes = ohlcvData.map((bar) => bar.close);

    // Use the calculator - returns full time series
    const result = calculateAtr(highs, lows, closes, window);
    const atrSeries = result.atr;

    // Get the last value from the series
    let latestAtr: number | null = null;
    if (atrSeries && atrSeries.length > 0) {
      latestAtr = atrSeries[atrSeries.length - 1];
    }

    if (latestAtr === null) {
      latestAtr = 0.0;
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.ATR,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: latestAtr }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error || indicatorResult.values.single === undefined) {
      return false;
    }

    const latestAtr = indicatorResult.values.single;
    const minAtrParam = this.params.min_atr;
    const minAtr = typeof minAtrParam === 'number' ? minAtrParam : 0.0;

    return latestAtr >= minAtr;
  }
}
