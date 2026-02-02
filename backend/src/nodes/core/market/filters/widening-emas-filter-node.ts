// src/nodes/core/market/filters/widening-emas-filter-node.ts
// Translated from: nodes/core/market/filters/widening_emas_filter_node.py

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
 * Filters assets based on whether the difference between two EMAs is widening or narrowing.
 *
 * Calculates the difference between two EMAs and compares it to the previous period's difference
 * to determine if the EMAs are diverging (widening) or converging (narrowing).
 *
 * Formula: [EMA(fast_period) - EMA(slow_period)] compared to [previous EMA(fast_period) - EMA(slow_period)]
 *
 * Widening: Current difference > Previous difference
 * Narrowing: Current difference < Previous difference
 *
 * Only assets meeting the widening/narrowing condition will pass the filter.
 */
export class WideningEMAsFilter extends BaseIndicatorFilter {
  static override defaultParams: DefaultParams = {
    fast_ema_period: 10,
    slow_ema_period: 30,
    widening: true,
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'fast_ema_period',
      type: 'number',
      default: 10,
      min: 2,
      step: 1,
      label: 'Fast EMA Period',
      description: 'Period for the faster EMA (e.g., 10)',
    },
    {
      name: 'slow_ema_period',
      type: 'number',
      default: 30,
      min: 2,
      step: 1,
      label: 'Slow EMA Period',
      description: 'Period for the slower EMA (e.g., 30)',
    },
    {
      name: 'widening',
      type: 'text',
      default: 'true',
      label: 'Check for Widening',
      description: 'true: filter for widening EMAs, false: filter for narrowing EMAs',
    },
  ];

  protected override validateIndicatorParams(): void {
    const fastPeriod = this.params.fast_ema_period ?? 10;
    const slowPeriod = this.params.slow_ema_period ?? 30;

    if (typeof fastPeriod !== 'number' || fastPeriod < 2) {
      throw new Error('Fast EMA period must be at least 2');
    }
    if (typeof slowPeriod !== 'number' || slowPeriod < 2) {
      throw new Error('Slow EMA period must be at least 2');
    }
    if (fastPeriod >= slowPeriod) {
      throw new Error('Fast EMA period must be less than slow EMA period');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult(
        IndicatorType.EMA,
        0,
        createIndicatorValue(0, { ema_difference: 0.0, is_widening: 0 }),
        this.params,
        'No data'
      );
    }

    // Need enough data for both EMAs plus one comparison period
    let fastPeriodRaw = this.params.fast_ema_period ?? 10;
    let slowPeriodRaw = this.params.slow_ema_period ?? 30;

    const fastPeriod = typeof fastPeriodRaw === 'number' ? Math.floor(fastPeriodRaw) : 10;
    const slowPeriod = typeof slowPeriodRaw === 'number' ? Math.floor(slowPeriodRaw) : 30;

    const minDataNeeded = Math.max(fastPeriod, slowPeriod) + 1;

    if (ohlcvData.length < minDataNeeded) {
      return createIndicatorResult(
        IndicatorType.EMA,
        ohlcvData[ohlcvData.length - 1].timestamp,
        createIndicatorValue(0, { ema_difference: 0.0, is_widening: 0 }),
        this.params,
        `Insufficient data: need at least ${minDataNeeded} bars`
      );
    }

    // Extract close prices
    const closePrices = ohlcvData.map((bar) => bar.close);

    // Calculate EMAs using the calculator
    const fastEmaResult = calculateEma(closePrices, fastPeriod);
    const slowEmaResult = calculateEma(closePrices, slowPeriod);

    const fastEmaSeries = fastEmaResult.ema;
    const slowEmaSeries = slowEmaResult.ema;

    // Check if we have enough data for comparison
    if (fastEmaSeries.length < 2 || slowEmaSeries.length < 2) {
      return createIndicatorResult(
        IndicatorType.EMA,
        ohlcvData[ohlcvData.length - 1].timestamp,
        createIndicatorValue(0, { ema_difference: 0.0, is_widening: 0 }),
        this.params,
        'Unable to calculate EMA difference'
      );
    }

    // Get the last two values from each EMA series
    const currentFast = fastEmaSeries[fastEmaSeries.length - 1];
    const prevFast = fastEmaSeries[fastEmaSeries.length - 2];
    const currentSlow = slowEmaSeries[slowEmaSeries.length - 1];
    const prevSlow = slowEmaSeries[slowEmaSeries.length - 2];

    // Check for null values (calculator returns null when insufficient data)
    if (currentFast === null || prevFast === null || currentSlow === null || prevSlow === null) {
      return createIndicatorResult(
        IndicatorType.EMA,
        ohlcvData[ohlcvData.length - 1].timestamp,
        createIndicatorValue(0, { ema_difference: 0.0, is_widening: 0 }),
        this.params,
        'EMA calculation returned null values'
      );
    }

    // Calculate EMA differences for the last two periods
    const currentDiff = currentFast - currentSlow;
    const prevDiff = prevFast - prevSlow;

    // Check if widening (current difference > previous difference)
    const isWidening = currentDiff > prevDiff;

    return createIndicatorResult(
      IndicatorType.EMA,
      ohlcvData[ohlcvData.length - 1].timestamp,
      createIndicatorValue(0, {
        ema_difference: currentDiff,
        is_widening: isWidening ? 1 : 0,
        fast_ema: currentFast,
        slow_ema: currentSlow,
        prev_difference: prevDiff,
      }),
      this.params
    );
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    const lines = indicatorResult.values.lines;
    if (!('is_widening' in lines)) {
      return false;
    }

    const isWidening = lines.is_widening === 1;

    // Handle string "true"/"false" from UI
    let wideningParam = this.params.widening ?? true;
    if (typeof wideningParam === 'string') {
      wideningParam = wideningParam.toLowerCase() === 'true';
    }

    return isWidening === wideningParam;
  }
}
