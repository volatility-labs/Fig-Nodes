// src/nodes/core/market/filters/atrx-filter-node.ts

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import type { NodeDefinition } from '@fig-node/core';
import { IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type IndicatorResult } from '../types';
import { calculateAtrxLastValue } from '../calculators/atrx-calculator';

/**
 * Filters OHLCV bundle based on ATRX indicator thresholds.
 */
export class AtrXFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    defaults: {
      length: 14,
      smoothing: 'RMA',
      price: 'Close',
      ma_length: 50,
      upper_threshold: 6.0,
      lower_threshold: -4.0,
      filter_condition: 'outside',
    },
    params: [
      { name: 'length', type: 'integer', default: 14 },
      { name: 'smoothing', type: 'combo', default: 'RMA', options: ['RMA', 'EMA', 'SMA'] },
      { name: 'price', type: 'text', default: 'Close' },
      { name: 'ma_length', type: 'integer', default: 50 },
      { name: 'upper_threshold', type: 'float', default: 6.0 },
      { name: 'lower_threshold', type: 'float', default: -4.0 },
      {
        name: 'filter_condition',
        type: 'combo',
        default: 'outside',
        options: ['outside', 'inside'],
      },
    ],
  };

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: 0,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'No data',
      });
    }

    // Check minimum data requirements first
    const lengthParam = this.params.length ?? 14;
    const maLengthParam = this.params.ma_length ?? 50;

    const lengthValue = typeof lengthParam === 'number' ? Math.floor(lengthParam) : 14;
    const maLengthValue = typeof maLengthParam === 'number' ? Math.floor(maLengthParam) : 50;

    const minRequired = Math.max(lengthValue, maLengthValue);
    if (ohlcvData.length < minRequired) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Get smoothing parameter
    const smoothing = this.params.smoothing ?? 'RMA';
    if (smoothing !== 'RMA' && smoothing !== 'SMA' && smoothing !== 'EMA') {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: `Invalid smoothing method '${smoothing}'. Must be 'RMA', 'SMA', or 'EMA'.`,
      });
    }

    // Extract lists directly from OHLCV data
    const highPrices = ohlcvData.map((bar) => bar.high);
    const lowPrices = ohlcvData.map((bar) => bar.low);
    const closePrices = ohlcvData.map((bar) => bar.close);

    // Map price column name
    const priceCol = String(this.params.price ?? 'Close');
    const priceMap: Record<string, number[]> = {
      Open: ohlcvData.map((bar) => bar.open),
      High: highPrices,
      Low: lowPrices,
      Close: closePrices,
    };

    if (!(priceCol in priceMap)) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: `Invalid price column '${priceCol}'`,
      });
    }

    const sourcePrices = priceMap[priceCol]!;

    // Call optimized calculator for last value only
    const smoothingStr = typeof smoothing === 'string' ? smoothing : 'RMA';
    const atrxValue = calculateAtrxLastValue(
      highPrices,
      lowPrices,
      closePrices,
      sourcePrices,
      lengthValue,
      maLengthValue,
      smoothingStr as 'RMA' | 'SMA' | 'EMA'
    );

    if (atrxValue === null) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'ATRX calculation resulted in null',
      });
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.ATRX,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: atrxValue }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    const value = indicatorResult.values.single;

    const upperThresholdParam = this.params.upper_threshold;
    const upperThreshold = typeof upperThresholdParam === 'number' ? upperThresholdParam : 6.0;

    const lowerThresholdParam = this.params.lower_threshold;
    const lowerThreshold = typeof lowerThresholdParam === 'number' ? lowerThresholdParam : -4.0;

    const filterConditionParam = this.params.filter_condition;
    const filterCondition = typeof filterConditionParam === 'string' ? filterConditionParam : 'outside';

    if (filterCondition === 'outside') {
      return value >= upperThreshold || value <= lowerThreshold;
    } else {
      // "inside"
      return lowerThreshold <= value && value <= upperThreshold;
    }
  }
}
