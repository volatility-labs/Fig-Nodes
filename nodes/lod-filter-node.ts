// src/nodes/core/market/filters/lod-filter-node.ts

import { Node, port, NodeCategory, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle, type IndicatorResult, type SerializedOHLCVBundle, deserializeOHLCVBundle } from './types';
import { calculateLod } from './lod-calculator';

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
 * Filters assets based on LoD (Low of Day Distance) values.
 *
 * LoD Distance is calculated as the distance of current price from the low of the day
 * as a percentage of ATR (Average True Range).
 *
 * Formula: LoD Distance % = ((current_price - low_of_day) / ATR) * 100
 *
 * Filter can be set to pass assets with LoD Distance above a minimum threshold or
 * below a maximum threshold.
 *
 * Parameter guidance:
 * - lod_distance_threshold: Enter a percentage of ATR (not price points).
 *   For example, 3.16 means the current price is 3.16% of one ATR above the
 *   day's low. Use numeric values like 3, 5.5, 10, etc. The underlying unit is '% of ATR'.
 * - filter_mode: Choose "min" to filter for assets above threshold, or "max" to filter
 *   for assets below threshold.
 *
 * Reference:
 * https://www.tradingview.com/script/uloAa2EI-Swing-Data-ADR-RVol-PVol-Float-Avg-Vol/
 */
export class LodFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      {
        name: 'lod_distance_threshold',
        type: 'number',
        default: 3.16,
        min: 0.0,
        step: 0.1,
        precision: 2,
        label: 'LoD Distance Threshold %',
        unit: '%',
        description: 'LoD distance threshold as percentage of ATR (e.g., 3.16 = 3.16% of ATR)',
      },
      {
        name: 'atr_window',
        type: 'number',
        default: 14,
        min: 1,
        step: 1,
        label: 'ATR Window',
        description: 'Period for ATR calculation',
      },
      {
        name: 'filter_mode',
        type: 'combo',
        default: 'min',
        options: ['min', 'max'],
        label: 'Filter Mode',
        description: 'Filter for assets above threshold (min) or below threshold (max)',
      },
    ],
  };

  protected override validateIndicatorParams(): void {
    const threshold = this.params.lod_distance_threshold;
    const atrWindow = this.params.atr_window;
    const filterMode = this.params.filter_mode;

    if (typeof threshold !== 'number') {
      throw new Error('LoD distance threshold must be a number');
    }
    if (threshold < 0) {
      throw new Error('LoD distance threshold cannot be negative');
    }

    if (typeof atrWindow !== 'number') {
      throw new Error('ATR window must be a number');
    }
    if (atrWindow <= 0) {
      throw new Error('ATR window must be positive');
    }

    if (filterMode !== 'min' && filterMode !== 'max') {
      throw new Error("Filter mode must be either 'min' or 'max'");
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.LOD,
        timestamp: 0,
        values: createIndicatorValue({ single: 0, lines: { lod_distance_pct: 0.0 } }),
        params: this.params,
        error: 'No data',
      });
    }

    const timestampValue = ohlcvData[ohlcvData.length - 1].timestamp;

    const atrWindowParam = this.params.atr_window;
    if (typeof atrWindowParam !== 'number') {
      return createIndicatorResult({
        indicatorType: IndicatorType.LOD,
        timestamp: timestampValue,
        values: createIndicatorValue({ single: 0, lines: { lod_distance_pct: 0.0 } }),
        params: this.params,
        error: 'Invalid ATR window parameter',
      });
    }
    const atrWindow = Math.floor(atrWindowParam);

    if (ohlcvData.length < atrWindow) {
      return createIndicatorResult({
        indicatorType: IndicatorType.LOD,
        timestamp: timestampValue,
        values: createIndicatorValue({ single: 0, lines: { lod_distance_pct: 0.0 } }),
        params: this.params,
        error: 'Insufficient data for ATR calculation',
      });
    }

    // Extract price data from OHLCV bars
    const highs = ohlcvData.map((bar) => bar.high);
    const lows = ohlcvData.map((bar) => bar.low);
    const closes = ohlcvData.map((bar) => bar.close);

    // Calculate LoD using the calculator
    const lodResult = calculateLod(highs, lows, closes, atrWindow);

    // Get the latest values
    const lodDistancePct = lodResult.lod_distance_pct[lodResult.lod_distance_pct.length - 1];
    const currentPrice = lodResult.current_price[lodResult.current_price.length - 1];
    const lowOfDay = lodResult.low_of_day[lodResult.low_of_day.length - 1];
    const atr = lodResult.atr[lodResult.atr.length - 1];

    // Check for invalid calculation
    if (
      lodDistancePct === null ||
      atr === null ||
      atr <= 0 ||
      currentPrice === null ||
      lowOfDay === null
    ) {
      return createIndicatorResult({
        indicatorType: IndicatorType.LOD,
        timestamp: timestampValue,
        values: createIndicatorValue({ single: 0, lines: { lod_distance_pct: 0.0 } }),
        params: this.params,
        error: 'Invalid LoD calculation',
      });
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.LOD,
      timestamp: timestampValue,
      values: createIndicatorValue({
        single: 0,
        lines: {
          lod_distance_pct: lodDistancePct,
          current_price: currentPrice,
          low_of_day: lowOfDay,
          atr: atr,
        },
      }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    const lines = indicatorResult.values.lines;
    if (!('lod_distance_pct' in lines)) {
      return false;
    }

    const lodDistancePct = lines.lod_distance_pct;

    if (!Number.isFinite(lodDistancePct)) {
      return false;
    }

    const thresholdParam = this.params.lod_distance_threshold;
    if (typeof thresholdParam !== 'number') {
      return false;
    }
    const lodDistanceThreshold = thresholdParam;

    const filterMode = this.params.filter_mode;

    if (filterMode === 'min') {
      // Filter for assets with LoD Distance ABOVE threshold
      return lodDistancePct >= lodDistanceThreshold;
    } else if (filterMode === 'max') {
      // Filter for assets with LoD Distance BELOW threshold
      return lodDistancePct <= lodDistanceThreshold;
    }

    return false;
  }
}
