// src/nodes/core/market/filters/base/base-indicator-filter-node.ts

import { BaseFilter } from './base-filter-node';
import { NodeCategory } from '@sosa/core';
import type { NodeDefinition } from '@sosa/core';
import {
  AssetSymbol,
  type OHLCVBar,
  type OHLCVBundle,
  type IndicatorResult,
  type SerializedOHLCVBundle,
  deserializeOHLCVBundle,
} from '../../types';

/**
 * Base class for indicator filter nodes that filter OHLCV bundles based on technical indicators.
 *
 * Input: OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>)
 * Output: Filtered OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>)
 */
export abstract class BaseIndicatorFilter extends BaseFilter {
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

  /**
   * Override in subclasses to validate indicator-specific parameters.
   */
  protected validateIndicatorParams(): void {
    // Default implementation does nothing
  }

  /**
   * Normalize ohlcv_bundle to ensure all values are arrays, not null/undefined.
   *
   * This provides consistent handling across all indicator filters for cases where
   * upstream nodes may not have normalized null values in bundles. Empty arrays
   * indicate no data and are skipped during execution.
   */
  override validateInputs(inputs: Record<string, unknown>): void {
    const bundleRaw = inputs.ohlcv_bundle;

    if (bundleRaw !== null && bundleRaw !== undefined) {
      // Handle both Map and plain object formats
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
        // Convert plain object to Map via deserialization
        inputs.ohlcv_bundle = deserializeOHLCVBundle(bundleRaw as SerializedOHLCVBundle);
      }
    }

    super.validateInputs(inputs);
  }

  /**
   * Calculate the indicator and return IndicatorResult.
   * Must be implemented by subclasses to specify IndicatorType and mapping.
   */
  protected abstract calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult;

  /**
   * Determine if the asset should pass based on IndicatorResult.
   * Must be implemented by subclasses.
   */
  protected abstract shouldPassFilter(indicatorResult: IndicatorResult): boolean;

  protected override async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();
    const totalSymbols = ohlcvBundle.size;
    let processedSymbols = 0;

    // Initial progress signal
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
        // Progress should still advance even on failure
        processedSymbols++;
        try {
          const pct = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
          this.progress(pct, `${processedSymbols}/${totalSymbols}`);
        } catch {
          // Ignore progress reporting errors
        }
        continue;
      }

      // Advance progress after successful processing
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
