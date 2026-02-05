// src/nodes/core/market/filters/adx-filter-node.ts
// Translated from: nodes/core/market/filters/adx_filter_node.py

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import { IndicatorType, createIndicatorResult, createIndicatorValue } from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  IndicatorResult,
  NodeUIConfig,
} from '../../../../core/types';
import { calculateAdx } from '../../../../services/indicator-calculators';

/**
 * Filters assets based on ADX (Average Directional Index) values.
 */
export class ADXFilter extends BaseIndicatorFilter {
  static override defaultParams: DefaultParams = {
    min_adx: 25.0,
    timeperiod: 14,
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'min_adx',
      type: 'number',
      default: 25.0,
      min: 0.0,
      max: 100.0,
      step: 0.1,
    },
    { name: 'timeperiod', type: 'number', default: 14, min: 1, step: 1 },
  ];

  static uiConfig: NodeUIConfig = {
    size: [220, 100],
    displayResults: false,
    resizable: false,
  };

  protected override validateIndicatorParams(): void {
    const minAdx = this.params.min_adx ?? 25.0;
    const timeperiod = this.params.timeperiod ?? 14;

    if (typeof minAdx !== 'number' || minAdx < 0) {
      throw new Error('Minimum ADX cannot be negative');
    }
    if (typeof timeperiod !== 'number' || timeperiod <= 0) {
      throw new Error('Time period must be positive');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ADX,
        timestamp: 0,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'No data',
      });
    }

    const timeperiodParam = this.params.timeperiod;
    const timeperiod = Math.floor(typeof timeperiodParam === 'number' ? timeperiodParam : 14);

    if (ohlcvData.length < timeperiod) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ADX,
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
    const result = calculateAdx(highs, lows, closes, timeperiod);
    const adxSeries = result.adx;

    // Get the last value from the series
    let latestAdx: number | null = null;
    if (adxSeries && adxSeries.length > 0) {
      latestAdx = adxSeries[adxSeries.length - 1];
    }

    if (latestAdx === null) {
      latestAdx = 0.0;
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.ADX,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: latestAdx }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error || indicatorResult.values.single === undefined) {
      return false;
    }

    const latestAdx = indicatorResult.values.single;
    const minAdxParam = this.params.min_adx;
    const minAdx = typeof minAdxParam === 'number' ? minAdxParam : 25.0;

    return latestAdx >= minAdx;
  }
}
