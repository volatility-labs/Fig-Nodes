// src/nodes/core/market/indicators/atr-indicator-node.ts

import { Node, port } from '@sosa/core';
import type { NodeDefinition } from '@sosa/core';
import { IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle } from './types';
import { calculateAtr } from './atr-calculator';

/**
 * Computes the ATR indicator for a single asset's OHLCV data.
 */
export class ATRIndicator extends Node {
  static override definition: NodeDefinition = {
    inputs: [port('ohlcv', 'OHLCVBundle')],
    outputs: [port('results', 'IndicatorResultList')],
    params: [
      { name: 'window', type: 'integer', default: 14, min: 1, step: 1 },
    ],
  };

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
