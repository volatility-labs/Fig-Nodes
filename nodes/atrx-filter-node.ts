// src/nodes/core/market/filters/atrx-filter-node.ts

import { Node, port, NodeCategory, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle, type IndicatorResult, type SerializedOHLCVBundle, deserializeOHLCVBundle } from './types';
import { calculateAtrxLastValue } from './atrx-calculator';

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
 * Filters OHLCV bundle based on ATRX indicator thresholds.
 */
export class AtrXFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      { name: 'length', type: 'integer', default: 14 },
      { name: 'smoothing', type: 'combo', default: 'RMA', options: ['RMA', 'EMA', 'SMA'] },
      { name: 'price', type: 'text', default: 'Close' },
      { name: 'ma_length', type: 'integer', default: 50 },
      { name: 'upper_threshold', type: 'float', default: 6.0 },
      { name: 'lower_threshold', type: 'float', default: -4.0 },
      {
        name: 'filter_condition',
        type: 'combo',
        default: 'outside',
        options: ['outside', 'inside'],
      },
    ],
  };

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: 0,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'No data',
      });
    }

    // Check minimum data requirements first
    const lengthParam = this.params.length ?? 14;
    const maLengthParam = this.params.ma_length ?? 50;

    const lengthValue = typeof lengthParam === 'number' ? Math.floor(lengthParam) : 14;
    const maLengthValue = typeof maLengthParam === 'number' ? Math.floor(maLengthParam) : 50;

    const minRequired = Math.max(lengthValue, maLengthValue);
    if (ohlcvData.length < minRequired) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'Insufficient data',
      });
    }

    // Get smoothing parameter
    const smoothing = this.params.smoothing ?? 'RMA';
    if (smoothing !== 'RMA' && smoothing !== 'SMA' && smoothing !== 'EMA') {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: `Invalid smoothing method '${smoothing}'. Must be 'RMA', 'SMA', or 'EMA'.`,
      });
    }

    // Extract lists directly from OHLCV data
    const highPrices = ohlcvData.map((bar) => bar.high);
    const lowPrices = ohlcvData.map((bar) => bar.low);
    const closePrices = ohlcvData.map((bar) => bar.close);

    // Map price column name
    const priceCol = String(this.params.price ?? 'Close');
    const priceMap: Record<string, number[]> = {
      Open: ohlcvData.map((bar) => bar.open),
      High: highPrices,
      Low: lowPrices,
      Close: closePrices,
    };

    if (!(priceCol in priceMap)) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: `Invalid price column '${priceCol}'`,
      });
    }

    const sourcePrices = priceMap[priceCol]!;

    // Call optimized calculator for last value only
    const smoothingStr = typeof smoothing === 'string' ? smoothing : 'RMA';
    const atrxValue = calculateAtrxLastValue(
      highPrices,
      lowPrices,
      closePrices,
      sourcePrices,
      lengthValue,
      maLengthValue,
      smoothingStr as 'RMA' | 'SMA' | 'EMA'
    );

    if (atrxValue === null) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ATRX,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0.0 }),
        params: this.params,
        error: 'ATRX calculation resulted in null',
      });
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.ATRX,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({ single: atrxValue }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    const value = indicatorResult.values.single;

    const upperThresholdParam = this.params.upper_threshold;
    const upperThreshold = typeof upperThresholdParam === 'number' ? upperThresholdParam : 6.0;

    const lowerThresholdParam = this.params.lower_threshold;
    const lowerThreshold = typeof lowerThresholdParam === 'number' ? lowerThresholdParam : -4.0;

    const filterConditionParam = this.params.filter_condition;
    const filterCondition = typeof filterConditionParam === 'string' ? filterConditionParam : 'outside';

    if (filterCondition === 'outside') {
      return value >= upperThreshold || value <= lowerThreshold;
    } else {
      // "inside"
      return lowerThreshold <= value && value <= upperThreshold;
    }
  }
}
