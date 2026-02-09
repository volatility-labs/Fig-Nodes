// src/nodes/core/market/filters/sma-crossover-filter-node.ts

import { Node, port, NodeCategory, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle, type IndicatorResult, type SerializedOHLCVBundle, deserializeOHLCVBundle } from './types';
import { calculateSma } from './sma-calculator';

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
 * Filters assets where short-term SMA crosses above long-term SMA (bullish crossover).
 */
export class SMACrossoverFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      { name: 'short_period', type: 'number', default: 20, min: 1, step: 1 },
      { name: 'long_period', type: 'number', default: 50, min: 1, step: 1 },
    ],
  };

  private shortPeriod: number = 20;
  private longPeriod: number = 50;

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
