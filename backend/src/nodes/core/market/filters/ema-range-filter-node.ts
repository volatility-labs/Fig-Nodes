// src/nodes/core/market/filters/ema-range-filter-node.ts
// Translated from: nodes/core/market/filters/ema_range_filter_node.py

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import { IndicatorType, createIndicatorResult, createIndicatorValue } from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  IndicatorResult,
} from '../../../../core/types';
import { calculateEma } from '../../../../services/indicator-calculators';

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
      return createIndicatorResult(
        IndicatorType.EMA_RANGE,
        0,
        createIndicatorValue(NaN, { ema_range: NaN, close: NaN }),
        this.params,
        'No data'
      );
    }

    let timeperiodValue = this.params.timeperiod ?? 10;
    if (typeof timeperiodValue !== 'number') {
      timeperiodValue = 10;
    }
    const timeperiod = Math.floor(timeperiodValue);

    if (ohlcvData.length < timeperiod) {
      return createIndicatorResult(
        IndicatorType.EMA_RANGE,
        ohlcvData[ohlcvData.length - 1].timestamp,
        createIndicatorValue(NaN, { ema_range: NaN, close: ohlcvData[ohlcvData.length - 1].close }),
        this.params,
        'Insufficient data'
      );
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

    return createIndicatorResult(
      IndicatorType.EMA_RANGE,
      ohlcvData[ohlcvData.length - 1].timestamp,
      createIndicatorValue(NaN, {
        ema_range: emaRangeValue,
        close: latestClose,
      }),
      this.params
    );
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

    let divisor = this.params.divisor ?? 100.0;
    if (typeof divisor !== 'number') {
      divisor = 100.0;
    }

    return emaRange > close / divisor;
  }
}
