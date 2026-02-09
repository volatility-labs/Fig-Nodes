// src/nodes/core/market/filters/atr-filter-node.ts

import { Node, port, NodeCategory, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle, type IndicatorResult, type SerializedOHLCVBundle, deserializeOHLCVBundle } from './types';
import { calculateAtr } from './atr-calculator';

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
 * Filters assets based on ATR (Average True Range) values.
 */
export class ATRFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      { name: 'min_atr', type: 'number', default: 0.0, min: 0.0, step: 0.1 },
      { name: 'window', type: 'number', default: 14, min: 1, step: 1 },
    ],
    ui: {
      resultDisplay: 'none',
      actions: [
        { id: 'previewFiltered', label: 'Preview Filtered', icon: '👁' },
        { id: 'copySummary', label: 'Copy Summary', icon: '📋' },
      ],
    },
  };

  protected override validateIndicatorParams(): void {
    const minAtr = this.params.min_atr ?? 0.0;
    const window = this.params.window ?? 14;

    if (typeof minAtr !== 'number' || minAtr < 0) {
      throw new Error('Minimum ATR cannot be negative');
    }
    if (typeof window !== 'number' || window <= 0) {
      throw new Error('Window must be positive');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATR,
        timestamp: 0,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'No data',
      });
    }

    const windowParam = this.params.window;
    const window = Math.floor(typeof windowParam === 'number' ? windowParam : 14);

    if (ohlcvData.length < window) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATR,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Extract lists for the calculator
    const highs = ohlcvData.map((bar) => bar.high);
    const lows = ohlcvData.map((bar) => bar.low);
    const closes = ohlcvData.map((bar) => bar.close);

    // Use the calculator - returns full time series
    const result = calculateAtr(highs, lows, closes, window);
    const atrSeries = result.atr;

    // Get the last value from the series
    let latestAtr: number | null = null;
    if (atrSeries && atrSeries.length > 0) {
      latestAtr = atrSeries[atrSeries.length - 1];
    }

    if (latestAtr === null) {
      latestAtr = 0.0;
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.ATR,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: latestAtr }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error || indicatorResult.values.single === undefined) {
      return false;
    }

    const latestAtr = indicatorResult.values.single;
    const minAtrParam = this.params.min_atr;
    const minAtr = typeof minAtrParam === 'number' ? minAtrParam : 0.0;

    return latestAtr >= minAtr;
  }
}
