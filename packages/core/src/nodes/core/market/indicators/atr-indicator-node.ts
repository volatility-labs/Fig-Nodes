// src/nodes/core/market/indicators/atr-indicator-node.ts
// Translated from: nodes/core/market/indicators/atr_indicator_node.py

import { BaseIndicator } from './base/base-indicator-node';
import {
  IndicatorType,
  createIndicatorResult,
  createIndicatorValue,
  getType,
} from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  NodeInputs,
  NodeOutputs,
  IndicatorValue,
  OHLCVBar,
  OHLCVBundle,
  NodeUIConfig,
} from '../../../../core/types';
import { calculateAtr } from '../../../../services/indicator-calculators';

/**
 * Computes the ATR indicator for a single asset's OHLCV data.
 */
export class ATRIndicator extends BaseIndicator {
  static uiConfig: NodeUIConfig = {
    size: [220, 100],
    displayResults: false,
    resizable: false,
  };

  static override inputs: Record<string, unknown> = {
    ohlcv: getType('OHLCVBundle'),
  };

  static override outputs: Record<string, unknown> = {
    results: Array, // list[IndicatorResult]
  };

  static override defaultParams: DefaultParams = {
    window: 14,
  };

  static override paramsMeta: ParamMeta[] = [
    { name: 'window', type: 'integer', default: 14, min: 1, step: 1 },
  ];

  protected mapToIndicatorValue(
    _indType: IndicatorType,
    _raw: Record<string, unknown>
  ): IndicatorValue {
    // This node computes ATR locally using calculator functions.
    // Implementing to satisfy BaseIndicator's abstract method.
    throw new Error('Unsupported indicator type for ATRIndicator');
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
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
