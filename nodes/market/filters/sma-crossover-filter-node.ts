// src/nodes/core/market/filters/sma-crossover-filter-node.ts
// Translated from: nodes/core/market/filters/sma_crossover_filter_node.py

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import { IndicatorType, createIndicatorResult, createIndicatorValue } from '@fig-node/core';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  IndicatorResult,
  NodeUIConfig,
} from '@fig-node/core';
import { calculateSma } from '../calculators/sma-calculator';

/**
 * Filters assets where short-term SMA crosses above long-term SMA (bullish crossover).
 */
export class SMACrossoverFilter extends BaseIndicatorFilter {
  private shortPeriod: number = 20;
  private longPeriod: number = 50;

  static override defaultParams: DefaultParams = {
    short_period: 20,
    long_period: 50,
  };

  static override paramsMeta: ParamMeta[] = [
    { name: 'short_period', type: 'number', default: 20, min: 1, step: 1 },
    { name: 'long_period', type: 'number', default: 50, min: 1, step: 1 },
  ];

  static uiConfig: NodeUIConfig = {
    size: [220, 100],
    displayResults: false,
    resizable: false,
  };

  protected override validateIndicatorParams(): void {
    const shortPeriodValue = this.params.short_period ?? 20;
    const longPeriodValue = this.params.long_period ?? 50;

    if (typeof shortPeriodValue !== 'number') {
      throw new Error('short_period must be a number');
    }
    if (typeof longPeriodValue !== 'number') {
      throw new Error('long_period must be a number');
    }

    this.shortPeriod = Math.floor(shortPeriodValue);
    this.longPeriod = Math.floor(longPeriodValue);

    if (this.shortPeriod >= this.longPeriod) {
      throw new Error('Short period must be less than long period');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.SMA,
        timestamp: 0,
        values: createIndicatorValue({ single: 0 }), // false as number
        params: this.params,
        error: 'No data',
      });
    }

    if (ohlcvData.length < this.longPeriod) {
      return createIndicatorResult({
        indicatorType: IndicatorType.SMA,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0 }), // false as number
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Calculate SMAs using the calculator
    const closePrices = ohlcvData.map((bar) => bar.close);

    const shortSmaResult = calculateSma(closePrices, this.shortPeriod);
    const longSmaResult = calculateSma(closePrices, this.longPeriod);

    const shortSmaValues = shortSmaResult.sma;
    const longSmaValues = longSmaResult.sma;

    // Check for crossover by comparing last 2 values of each SMA
    // Bullish crossover: short SMA crosses above long SMA
    let latestCrossover = false;

    if (shortSmaValues.length >= 2 && longSmaValues.length >= 2) {
      const prevShort = shortSmaValues[shortSmaValues.length - 2];
      const currShort = shortSmaValues[shortSmaValues.length - 1];
      const prevLong = longSmaValues[longSmaValues.length - 2];
      const currLong = longSmaValues[longSmaValues.length - 1];

      // Only proceed if all values are valid (not null)
      if (
        prevShort !== null &&
        currShort !== null &&
        prevLong !== null &&
        currLong !== null
      ) {
        // Crossover occurs when previous period: short <= long, current period: short > long
        if (prevShort <= prevLong && currShort > currLong) {
          latestCrossover = true;
        }
      }
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.SMA,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: latestCrossover ? 1 : 0 }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error || indicatorResult.values.single === undefined) {
      return false;
    }

    const latestCrossover = indicatorResult.values.single;
    return latestCrossover === 1;
  }
}
