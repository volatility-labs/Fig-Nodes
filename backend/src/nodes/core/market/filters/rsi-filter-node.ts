// src/nodes/core/market/filters/rsi-filter-node.ts
// Translated from: nodes/core/market/filters/rsi_filter_node.py

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import { IndicatorType, createIndicatorResult, createIndicatorValue } from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  IndicatorResult,
} from '../../../../core/types';
import { calculateRsi } from '../../../../services/indicator-calculators';

/**
 * Filters assets based on RSI (Relative Strength Index) values.
 */
export class RSIFilter extends BaseIndicatorFilter {
  private minRsi: number = 30.0;
  private maxRsi: number = 70.0;
  private timeperiod: number = 14;

  static override defaultParams: DefaultParams = {
    min_rsi: 30.0,
    max_rsi: 70.0,
    timeperiod: 14,
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'min_rsi',
      type: 'number',
      default: 30.0,
      min: 0.0,
      max: 100.0,
      step: 1.0,
    },
    {
      name: 'max_rsi',
      type: 'number',
      default: 70.0,
      min: 0.0,
      max: 100.0,
      step: 1.0,
    },
    { name: 'timeperiod', type: 'number', default: 14, min: 1, step: 1 },
  ];

  protected override validateIndicatorParams(): void {
    const minRsiValue = this.params.min_rsi ?? 30.0;
    const maxRsiValue = this.params.max_rsi ?? 70.0;
    const timeperiodValue = this.params.timeperiod ?? 14;

    if (typeof minRsiValue !== 'number') {
      throw new Error('min_rsi must be a number');
    }
    if (typeof maxRsiValue !== 'number') {
      throw new Error('max_rsi must be a number');
    }
    if (typeof timeperiodValue !== 'number') {
      throw new Error('timeperiod must be an integer');
    }

    this.minRsi = minRsiValue;
    this.maxRsi = maxRsiValue;
    this.timeperiod = Math.floor(timeperiodValue);

    if (this.minRsi >= this.maxRsi) {
      throw new Error('Minimum RSI must be less than maximum RSI');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.RSI,
        timestamp: 0,
        values: createIndicatorValue({ single: NaN }),
        params: this.params,
        error: 'No data',
      });
    }

    if (ohlcvData.length < this.timeperiod) {
      return createIndicatorResult({
        indicatorType: IndicatorType.RSI,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: NaN }),
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Extract close prices
    const closePrices = ohlcvData.map((bar) => bar.close);

    // Use the calculator - returns full time series
    const result = calculateRsi(closePrices, this.timeperiod);
    const rsiSeries = result.rsi;

    // Return the last value from the series (or NaN if empty)
    let latestRsi: number = NaN;
    if (rsiSeries && rsiSeries.length > 0) {
      const latestRsiRaw = rsiSeries[rsiSeries.length - 1];
      latestRsi = latestRsiRaw !== null ? latestRsiRaw : NaN;
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.RSI,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: latestRsi }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error || indicatorResult.values.single === undefined) {
      return false;
    }

    const latestRsi = indicatorResult.values.single;
    if (Number.isNaN(latestRsi)) {
      return false;
    }

    return this.minRsi <= latestRsi && latestRsi <= this.maxRsi;
  }
}
