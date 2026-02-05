// src/nodes/core/market/indicators/base/base-indicator-node.ts
// Translated from: nodes/core/market/indicators/base/base_indicator_node.py

import { Base } from '../../../../base/base-node';
import { getType, IndicatorType } from '../../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  IndicatorValue,
} from '../../../../../core/types';

/**
 * Base class for nodes that compute technical indicators from OHLCV data.
 * Subclasses should implement mapToIndicatorValue for specific indicator handling.
 */
export abstract class BaseIndicator extends Base {
  static override inputs: Record<string, unknown> = {
    ohlcv: getType('OHLCVBundle'),
  };
  static override outputs: Record<string, unknown> = {
    results: Array, // list[IndicatorResult]
  };

  static override defaultParams: DefaultParams = {
    timeframe: '1d',
  };

  static override paramsMeta: ParamMeta[] = [
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
  ];

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
