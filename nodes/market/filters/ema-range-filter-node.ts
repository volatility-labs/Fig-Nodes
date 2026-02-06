// src/nodes/core/market/filters/ema-range-filter-node.ts
// Translated from: nodes/core/market/filters/ema_range_filter_node.py

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import { IndicatorType, createIndicatorResult, createIndicatorValue } from '@fig-node/core';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  IndicatorResult,
  NodeUIConfig,
} from '@fig-node/core';
import { calculateEma } from '../calculators/ema-calculator';

/**
 * Filters assets where EMA(10, high-low range) > close / 100
 */
export class EmaRangeFilter extends BaseIndicatorFilter {
  static override defaultParams: DefaultParams = {
    timeperiod: 10,
    divisor: 100.0,
  };

  static override paramsMeta: ParamMeta[] = [
    { name: 'timeperiod', type: 'number', default: 10, min: 1, step: 1 },
    { name: 'divisor', type: 'number', default: 100.0, min: 1.0, step: 1.0 },
  ];

  static uiConfig: NodeUIConfig = {
    size: [220, 100],
    displayResults: false,
    resizable: false,
  };

  protected override validateIndicatorParams(): void {
    const timeperiod = this.params.timeperiod ?? 10;
    const divisor = this.params.divisor ?? 100.0;

    if (typeof timeperiod !== 'number' || timeperiod < 1) {
      throw new Error('Time period must be at least 1');
    }
    if (typeof divisor !== 'number' || divisor <= 0) {
      throw new Error('Divisor must be positive');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA_RANGE,
        timestamp: 0,
        values: createIndicatorValue({ single: NaN, lines: { ema_range: NaN, close: NaN } }),
        params: this.params,
        error: 'No data',
      });
    }

    const timeperiodParam = this.params.timeperiod;
    const timeperiod = Math.floor(typeof timeperiodParam === 'number' ? timeperiodParam : 10);

    if (ohlcvData.length < timeperiod) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA_RANGE,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: NaN, lines: { ema_range: NaN, close: ohlcvData[ohlcvData.length - 1].close } }),
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Calculate price range
    const priceRange = ohlcvData.map((bar) => bar.high - bar.low);
    const closes = ohlcvData.map((bar) => bar.close);

    // Calculate EMA using the calculator
    const emaResult = calculateEma(priceRange, timeperiod);
    const emaValues = emaResult.ema;
    const latestEma = emaValues.length > 0 ? emaValues[emaValues.length - 1] : null;
    const latestClose = closes[closes.length - 1];

    const emaRangeValue = latestEma !== null ? latestEma : NaN;

    return createIndicatorResult({
      indicatorType: IndicatorType.EMA_RANGE,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({
        single: NaN,
        lines: {
          ema_range: emaRangeValue,
          close: latestClose,
        },
      }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error || !indicatorResult.values.lines) {
      return false;
    }

    const values = indicatorResult.values.lines;
    if (!('ema_range' in values) || !('close' in values)) {
      return false;
    }

    const emaRange = values.ema_range;
    const close = values.close;
    if (Number.isNaN(emaRange) || Number.isNaN(close)) {
      return false;
    }

    const divisorParam = this.params.divisor;
    const divisor = typeof divisorParam === 'number' ? divisorParam : 100.0;

    return emaRange > close / divisor;
  }
}
