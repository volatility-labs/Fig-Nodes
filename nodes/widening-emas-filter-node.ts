// src/nodes/core/market/filters/widening-emas-filter-node.ts

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
 * Filters assets based on whether the difference between two EMAs is widening or narrowing.
 *
 * Calculates the difference between two EMAs and compares it to the previous period's difference
 * to determine if the EMAs are diverging (widening) or converging (narrowing).
 *
 * Formula: [EMA(fast_period) - EMA(slow_period)] compared to [previous EMA(fast_period) - EMA(slow_period)]
 *
 * Widening: Current difference > Previous difference
 * Narrowing: Current difference < Previous difference
 *
 * Only assets meeting the widening/narrowing condition will pass the filter.
 */
export class WideningEMAsFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      {
        name: 'fast_ema_period',
        type: 'number',
        default: 10,
        min: 2,
        step: 1,
        label: 'Fast EMA Period',
        description: 'Period for the faster EMA (e.g., 10)',
      },
      {
        name: 'slow_ema_period',
        type: 'number',
        default: 30,
        min: 2,
        step: 1,
        label: 'Slow EMA Period',
        description: 'Period for the slower EMA (e.g., 30)',
      },
      {
        name: 'widening',
        type: 'text',
        default: 'true',
        label: 'Check for Widening',
        description: 'true: filter for widening EMAs, false: filter for narrowing EMAs',
      },
    ],
  };

  protected override validateIndicatorParams(): void {
    const fastPeriod = this.params.fast_ema_period ?? 10;
    const slowPeriod = this.params.slow_ema_period ?? 30;

    if (typeof fastPeriod !== 'number' || fastPeriod < 2) {
      throw new Error('Fast EMA period must be at least 2');
    }
    if (typeof slowPeriod !== 'number' || slowPeriod < 2) {
      throw new Error('Slow EMA period must be at least 2');
    }
    if (fastPeriod >= slowPeriod) {
      throw new Error('Fast EMA period must be less than slow EMA period');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA,
        timestamp: 0,
        values: createIndicatorValue({ single: 0, lines: { ema_difference: 0.0, is_widening: 0 } }),
        params: this.params,
        error: 'No data',
      });
    }

    // Need enough data for both EMAs plus one comparison period
    let fastPeriodRaw = this.params.fast_ema_period ?? 10;
    let slowPeriodRaw = this.params.slow_ema_period ?? 30;

    const fastPeriod = typeof fastPeriodRaw === 'number' ? Math.floor(fastPeriodRaw) : 10;
    const slowPeriod = typeof slowPeriodRaw === 'number' ? Math.floor(slowPeriodRaw) : 30;

    const minDataNeeded = Math.max(fastPeriod, slowPeriod) + 1;

    if (ohlcvData.length < minDataNeeded) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0, lines: { ema_difference: 0.0, is_widening: 0 } }),
        params: this.params,
        error: `Insufficient data: need at least ${minDataNeeded} bars`,
      });
    }

    // Extract close prices
    const closePrices = ohlcvData.map((bar) => bar.close);

    // Calculate EMAs using the calculator
    const fastEmaResult = calculateEma(closePrices, fastPeriod);
    const slowEmaResult = calculateEma(closePrices, slowPeriod);

    const fastEmaSeries = fastEmaResult.ema;
    const slowEmaSeries = slowEmaResult.ema;

    // Check if we have enough data for comparison
    if (fastEmaSeries.length < 2 || slowEmaSeries.length < 2) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0, lines: { ema_difference: 0.0, is_widening: 0 } }),
        params: this.params,
        error: 'Unable to calculate EMA difference',
      });
    }

    // Get the last two values from each EMA series
    const currentFast = fastEmaSeries[fastEmaSeries.length - 1];
    const prevFast = fastEmaSeries[fastEmaSeries.length - 2];
    const currentSlow = slowEmaSeries[slowEmaSeries.length - 1];
    const prevSlow = slowEmaSeries[slowEmaSeries.length - 2];

    // Check for null values (calculator returns null when insufficient data)
    if (currentFast === null || prevFast === null || currentSlow === null || prevSlow === null) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EMA,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0, lines: { ema_difference: 0.0, is_widening: 0 } }),
        params: this.params,
        error: 'EMA calculation returned null values',
      });
    }

    // Calculate EMA differences for the last two periods
    const currentDiff = currentFast - currentSlow;
    const prevDiff = prevFast - prevSlow;

    // Check if widening (current difference > previous difference)
    const isWidening = currentDiff > prevDiff;

    return createIndicatorResult({
      indicatorType: IndicatorType.EMA,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({
        single: 0,
        lines: {
          ema_difference: currentDiff,
          is_widening: isWidening ? 1 : 0,
          fast_ema: currentFast,
          slow_ema: currentSlow,
          prev_difference: prevDiff,
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
    if (!('is_widening' in lines)) {
      return false;
    }

    const isWidening = lines.is_widening === 1;

    // Handle string "true"/"false" from UI
    let wideningParam = this.params.widening ?? true;
    if (typeof wideningParam === 'string') {
      wideningParam = wideningParam.toLowerCase() === 'true';
    }

    return isWidening === wideningParam;
  }
}
