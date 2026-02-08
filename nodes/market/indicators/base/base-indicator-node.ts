// src/nodes/core/market/indicators/base/base-indicator-node.ts

import { Node, port } from '@fig-node/core';
import type { NodeDefinition } from '@fig-node/core';
import { IndicatorType, type IndicatorValue } from '../../types';

/**
 * Base class for nodes that compute technical indicators from OHLCV data.
 * Subclasses should implement mapToIndicatorValue for specific indicator handling.
 */
export abstract class BaseIndicator extends Node {
  static definition: NodeDefinition = {
    inputs: {
      ohlcv: port('OHLCVBundle'),
    },
    outputs: {
      results: port('IndicatorResultList'),
    },
    defaults: {
      timeframe: '1d',
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

  /**
   * Maps raw indicator values to IndicatorValue format.
   * Handles heterogeneous outputs per indicator type.
   * Subclasses must implement this for specific mappings.
   */
  protected abstract mapToIndicatorValue(
    indType: IndicatorType,
    raw: Record<string, unknown>
  ): IndicatorValue;
}
