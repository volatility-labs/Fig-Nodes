// src/nodes/core/market/filters/rsi-filter-node.ts

import { Node, port, NodeCategory, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle, type IndicatorResult, type SerializedOHLCVBundle, deserializeOHLCVBundle } from './types';
import { calculateRsi } from './rsi-calculator';

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
 * Filters assets based on RSI (Relative Strength Index) values.
 */
export class RSIFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      {
        name: 'min_rsi',
        type: 'number',
        default: 30.0,
        min: 0.0,
        max: 100.0,
        step: 1.0,
      },
      {
        name: 'max_rsi',
        type: 'number',
        default: 70.0,
        min: 0.0,
        max: 100.0,
        step: 1.0,
      },
      { name: 'timeperiod', type: 'number', default: 14, min: 1, step: 1 },
    ],
    ui: {
      resultDisplay: 'none',
    },
  };

  private minRsi: number = 30.0;
  private maxRsi: number = 70.0;
  private timeperiod: number = 14;

  protected override validateIndicatorParams(): void {
    const minRsiValue = this.params.min_rsi ?? 30.0;
    const maxRsiValue = this.params.max_rsi ?? 70.0;
    const timeperiodValue = this.params.timeperiod ?? 14;

    if (typeof minRsiValue !== 'number') {
      throw new Error('min_rsi must be a number');
    }
    if (typeof maxRsiValue !== 'number') {
      throw new Error('max_rsi must be a number');
    }
    if (typeof timeperiodValue !== 'number') {
      throw new Error('timeperiod must be an integer');
    }

    this.minRsi = minRsiValue;
    this.maxRsi = maxRsiValue;
    this.timeperiod = Math.floor(timeperiodValue);

    if (this.minRsi >= this.maxRsi) {
      throw new Error('Minimum RSI must be less than maximum RSI');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.RSI,
        timestamp: 0,
        values: createIndicatorValue({ single: NaN }),
        params: this.params,
        error: 'No data',
      });
    }

    if (ohlcvData.length < this.timeperiod) {
      return createIndicatorResult({
        indicatorType: IndicatorType.RSI,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: NaN }),
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Extract close prices
    const closePrices = ohlcvData.map((bar) => bar.close);

    // Use the calculator - returns full time series
    const result = calculateRsi(closePrices, this.timeperiod);
    const rsiSeries = result.rsi;

    // Return the last value from the series (or NaN if empty)
    let latestRsi: number = NaN;
    if (rsiSeries && rsiSeries.length > 0) {
      const latestRsiRaw = rsiSeries[rsiSeries.length - 1];
      latestRsi = latestRsiRaw !== null ? latestRsiRaw : NaN;
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.RSI,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: latestRsi }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error || indicatorResult.values.single === undefined) {
      return false;
    }

    const latestRsi = indicatorResult.values.single;
    if (Number.isNaN(latestRsi)) {
      return false;
    }

    return this.minRsi <= latestRsi && latestRsi <= this.maxRsi;
  }
}
