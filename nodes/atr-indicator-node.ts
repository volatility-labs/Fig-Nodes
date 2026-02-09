// src/nodes/core/market/indicators/atr-indicator-node.ts

import { Node, port } from '@sosa/core';
import type { NodeDefinition } from '@sosa/core';
import { IndicatorType, createIndicatorResult, createIndicatorValue, type IndicatorValue, type OHLCVBar, type OHLCVBundle } from './types';
import { calculateAtr } from './atr-calculator';

abstract class BaseIndicator extends Node {
  static definition: NodeDefinition = {
    inputs: {
      ohlcv: port('OHLCVBundle'),
    },
    outputs: {
      results: port('IndicatorResultList'),
    },
    params: [
      {
        name: 'indicators',
        type: 'combo',
        default: [IndicatorType.MACD, IndicatorType.RSI, IndicatorType.ADX],
        options: Object.values(IndicatorType),
      },
      {
        name: 'timeframe',
        type: 'combo',
        default: '1d',
        options: ['1m', '5m', '15m', '1h', '4h', '1d', '1w', '1M'],
      },
    ],
  };

  protected abstract mapToIndicatorValue(
    indType: IndicatorType,
    raw: Record<string, unknown>
  ): IndicatorValue;
}

/**
 * Computes the ATR indicator for a single asset's OHLCV data.
 */
export class ATRIndicator extends BaseIndicator {
  static override definition: NodeDefinition = {
    ...BaseIndicator.definition,
    params: [
      { name: 'window', type: 'integer', default: 14, min: 1, step: 1 },
    ],
  };

  protected mapToIndicatorValue(
    _indType: IndicatorType,
    _raw: Record<string, unknown>
  ): IndicatorValue {
    // This node computes ATR locally using calculator functions.
    // Implementing to satisfy BaseIndicator's abstract method.
    throw new Error('Unsupported indicator type for ATRIndicator');
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ohlcvBundle = inputs.ohlcv as OHLCVBundle | undefined;
    if (!ohlcvBundle || ohlcvBundle.size === 0) {
      return { results: [] };
    }

    // Get the first (and typically only) symbol's bars
    const ohlcv = ohlcvBundle.values().next().value as OHLCVBar[] | undefined;

    if (!ohlcv || ohlcv.length === 0) {
      return { results: [] };
    }

    const windowValue = this.params.window ?? 14;
    if (typeof windowValue !== 'number') {
      return { results: [] };
    }
    const window = Math.floor(windowValue);

    const highs = ohlcv.map((bar) => bar.high);
    const lows = ohlcv.map((bar) => bar.low);
    const closes = ohlcv.map((bar) => bar.close);

    if (highs.length < window) {
      return { results: [] };
    }

    const atrResult = calculateAtr(highs, lows, closes, window);
    const atrValues = atrResult.atr;
    const latestAtr = atrValues.length > 0 ? atrValues[atrValues.length - 1] : null;

    const latestTimestampMs = ohlcv[ohlcv.length - 1].timestamp;

    const result = createIndicatorResult({
      indicatorType: IndicatorType.ATR,
      timestamp: latestTimestampMs,
      values: createIndicatorValue({ single: latestAtr ?? 0.0 }),
      params: this.params,
    });

    return { results: [result] };
  }
}
