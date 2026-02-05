// src/nodes/core/market/indicators/atrx-indicator-node.ts
// Translated from: nodes/core/market/indicators/atrx_indicator_node.py

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
import { calculateAtrx } from '../../../../services/indicator-calculators';

/**
 * Computes the ATRX indicator for a single asset's OHLCV data.
 * A = ATR% = ATR / Last Done Price
 * B = % Gain From 50-MA = (Price - SMA50) / SMA50
 * ATRX = B / A = (% Gain From 50-MA) / ATR%
 *
 * Reference:
 *     https://www.tradingview.com/script/oimVgV7e-ATR-multiple-from-50-MA/
 */
export class AtrXIndicator extends BaseIndicator {
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
    length: 14, // ATR period
    ma_length: 50, // SMA period for trend calculation
  };

  static override paramsMeta: ParamMeta[] = [
    { name: 'length', type: 'integer', default: 14, description: 'ATR period' },
    {
      name: 'ma_length',
      type: 'integer',
      default: 50,
      description: 'SMA period for trend calculation',
    },
  ];

  protected mapToIndicatorValue(
    _indType: IndicatorType,
    _raw: Record<string, unknown>
  ): IndicatorValue {
    // ATRX node uses its own _executeImpl path and does not rely on base mapping.
    return createIndicatorValue({ single: NaN });
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const ohlcvBundle = inputs.ohlcv as OHLCVBundle | undefined;
    if (!ohlcvBundle || ohlcvBundle.size === 0) {
      console.warn('Empty OHLCV bundle provided to ATRX indicator');
      return { results: [] };
    }

    // Get the first (and typically only) symbol's bars
    const ohlcv = ohlcvBundle.values().next().value as OHLCVBar[] | undefined;

    if (!ohlcv || ohlcv.length === 0) {
      console.warn('Empty OHLCV data provided to ATRX indicator');
      return { results: [] };
    }

    try {
      // Check for minimum data requirements first
      const lengthRaw = this.params.length ?? 14;
      const maLengthRaw = this.params.ma_length ?? 50;

      const lengthValue = typeof lengthRaw === 'number' ? Math.floor(lengthRaw) : 14;
      const maLengthValue = typeof maLengthRaw === 'number' ? Math.floor(maLengthRaw) : 50;

      const minRequired = Math.max(lengthValue, maLengthValue);
      if (ohlcv.length < minRequired) {
        console.warn(
          `Insufficient data for ATRX calculation: ${ohlcv.length} bars, need ${minRequired}`
        );
        return { results: [] };
      }

      // Extract lists directly from OHLCV data
      const highPrices = ohlcv.map((bar) => bar.high);
      const lowPrices = ohlcv.map((bar) => bar.low);
      const closePrices = ohlcv.map((bar) => bar.close);

      // Call calculator directly with required parameters
      const atrxResult = calculateAtrx(
        highPrices,
        lowPrices,
        closePrices,
        closePrices, // prices = close
        lengthValue,
        maLengthValue
      );
      const atrxValues = atrxResult.atrx;

      if (!atrxValues || atrxValues.length === 0) {
        console.warn('ATRX calculation returned empty results');
        return { results: [] };
      }

      // Get the last value
      const atrxValue = atrxValues[atrxValues.length - 1];

      // Filter out NaN results (e.g., zero volatility cases)
      if (atrxValue === null || Number.isNaN(atrxValue)) {
        console.warn('ATRX calculation resulted in NaN (likely zero volatility)');
        return { results: [] };
      }

      const result = createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcv[ohlcv.length - 1].timestamp,
        values: createIndicatorValue({ single: atrxValue }),
      });

      return { results: [result] };
    } catch (error) {
      console.error('Error calculating ATRX indicator:', error);
      return { results: [] };
    }
  }
}
