// src/nodes/core/market/filters/ema-range-filter-node.ts

import { Node, port, NodeCategory, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle, type IndicatorResult, type SerializedOHLCVBundle, deserializeOHLCVBundle } from './types';
import { calculateEma } from './ema-calculator';

abstract class BaseFilter extends Node {
  static override definition: NodeDefinition = {
    inputs: {
      ohlcv_bundle: port('OHLCVBundle'),
    },
    outputs: {
      filtered_ohlcv_bundle: port('OHLCVBundle'),
    },
    ui: {
      resultDisplay: 'none',
    },
  };

  protected filterCondition(_symbol: AssetSymbol, _ohlcvData: OHLCVBar[]): boolean {
    throw new Error('Subclasses must implement filterCondition');
  }

  protected async filterConditionAsync(
    symbol: AssetSymbol,
    ohlcvData: OHLCVBar[]
  ): Promise<boolean> {
    return this.filterCondition(symbol, ohlcvData);
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();

    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (!ohlcvData || ohlcvData.length === 0) {
        continue;
      }

      try {
        if (await this.filterConditionAsync(symbol, ohlcvData)) {
          filteredBundle.set(symbol, ohlcvData);
        }
      } catch (e) {
        if (e instanceof Error && e.message.includes('must implement')) {
          if (this.filterCondition(symbol, ohlcvData)) {
            filteredBundle.set(symbol, ohlcvData);
          }
        } else {
          throw e;
        }
      }
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}

abstract class BaseIndicatorFilter extends BaseFilter {
  static override definition: NodeDefinition = {
    ...BaseFilter.definition,
    category: NodeCategory.MARKET,
  };

  constructor(
    nodeId: string,
    params: Record<string, unknown> = {},
    graphContext?: Record<string, unknown>
  ) {
    super(nodeId, params, graphContext ?? {});
    this.validateIndicatorParams();
  }

  protected validateIndicatorParams(): void {}

  override validateInputs(inputs: Record<string, unknown>): void {
    const bundleRaw = inputs.ohlcv_bundle;

    if (bundleRaw !== null && bundleRaw !== undefined) {
      if (bundleRaw instanceof Map) {
        const normalizedBundle: OHLCVBundle = new Map();
        for (const [key, value] of bundleRaw) {
          if (!(key instanceof AssetSymbol)) {
            continue;
          }
          if (value === null || value === undefined) {
            normalizedBundle.set(key, []);
          } else if (Array.isArray(value)) {
            normalizedBundle.set(key, value);
          }
        }
        inputs.ohlcv_bundle = normalizedBundle;
      } else if (typeof bundleRaw === 'object') {
        inputs.ohlcv_bundle = deserializeOHLCVBundle(bundleRaw as SerializedOHLCVBundle);
      }
    }

    super.validateInputs(inputs);
  }

  protected abstract calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult;

  protected abstract shouldPassFilter(indicatorResult: IndicatorResult): boolean;

  protected override async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();
    const totalSymbols = ohlcvBundle.size;
    let processedSymbols = 0;

    try {
      this.progress(0.0, `0/${totalSymbols}`);
    } catch {
      // Ignore progress reporting errors
    }

    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (!ohlcvData || ohlcvData.length === 0) {
        processedSymbols++;
        try {
          const pct = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
          this.progress(pct, `${processedSymbols}/${totalSymbols}`);
        } catch {
          // Ignore progress reporting errors
        }
        continue;
      }

      try {
        const indicatorResult = this.calculateIndicator(ohlcvData);

        if (this.shouldPassFilter(indicatorResult)) {
          filteredBundle.set(symbol, ohlcvData);
        }
      } catch (e) {
        console.warn(`Failed to process indicator for ${symbol.ticker}: ${e}`);
        processedSymbols++;
        try {
          const pct = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
          this.progress(pct, `${processedSymbols}/${totalSymbols}`);
        } catch {
          // Ignore progress reporting errors
        }
        continue;
      }

      processedSymbols++;
      try {
        const pct = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
        this.progress(pct, `${processedSymbols}/${totalSymbols}`);
      } catch {
        // Ignore progress reporting errors
      }
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}

/**
 * Filters assets where EMA(10, high-low range) > close / 100
 */
export class EmaRangeFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      { name: 'timeperiod', type: 'number', default: 10, min: 1, step: 1 },
      { name: 'divisor', type: 'number', default: 100.0, min: 1.0, step: 1.0 },
    ],
  };

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
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA_RANGE,
        timestamp: 0,
        values: createIndicatorValue({ single: NaN, lines: { ema_range: NaN, close: NaN } }),
        params: this.params,
        error: 'No data',
      });
    }

    const timeperiodParam = this.params.timeperiod;
    const timeperiod = Math.floor(typeof timeperiodParam === 'number' ? timeperiodParam : 10);

    if (ohlcvData.length < timeperiod) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA_RANGE,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: NaN, lines: { ema_range: NaN, close: ohlcvData[ohlcvData.length - 1].close } }),
        params: this.params,
        error: 'Insufficient data',
      });
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

    return createIndicatorResult({
      indicatorType: IndicatorType.EMA_RANGE,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({
        single: NaN,
        lines: {
          ema_range: emaRangeValue,
          close: latestClose,
        },
      }),
      params: this.params,
    });
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

    const divisorParam = this.params.divisor;
    const divisor = typeof divisorParam === 'number' ? divisorParam : 100.0;

    return emaRange > close / divisor;
  }
}
