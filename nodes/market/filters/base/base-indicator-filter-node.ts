// src/nodes/core/market/filters/base/base-indicator-filter-node.ts
// Translated from: nodes/core/market/filters/base/base_indicator_filter_node.py

import { BaseFilter } from './base-filter-node';
import { NodeCategory } from '@fig-node/core';
import type {
  NodeInputs,
  NodeOutputs,
  OHLCVBar,
  OHLCVBundle,
  IndicatorResult,
} from '@fig-node/core';
import { AssetSymbol } from '@fig-node/core';

/**
 * Base class for indicator filter nodes that filter OHLCV bundles based on technical indicators.
 *
 * Input: OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>)
 * Output: Filtered OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>)
 */
export abstract class BaseIndicatorFilter extends BaseFilter {
  static override CATEGORY = NodeCategory.MARKET;

  constructor(
    id: number,
    params: Record<string, unknown> = {},
    graphContext?: Record<string, unknown>
  ) {
    super(id, params, graphContext ?? {});
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
  override validateInputs(inputs: NodeInputs): void {
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
        // Convert plain object to Map
        const normalizedBundle: OHLCVBundle = new Map();
        for (const [_key, value] of Object.entries(bundleRaw)) {
          // Try to reconstruct AssetSymbol if it's serialized
          // For now, skip non-AssetSymbol keys
          if (value === null || value === undefined) {
            continue;
          } else if (Array.isArray(value)) {
            // This branch handles cases where the key might be a serialized symbol
            // In production, proper deserialization would be needed
          }
        }
        inputs.ohlcv_bundle = normalizedBundle;
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

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();
    const totalSymbols = ohlcvBundle.size;
    let processedSymbols = 0;

    // Initial progress signal
    try {
      this.reportProgress(0.0, `0/${totalSymbols}`);
    } catch {
      // Ignore progress reporting errors
    }

    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (!ohlcvData || ohlcvData.length === 0) {
        processedSymbols++;
        try {
          const progress = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
          this.reportProgress(progress, `${processedSymbols}/${totalSymbols}`);
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
          const progress = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
          this.reportProgress(progress, `${processedSymbols}/${totalSymbols}`);
        } catch {
          // Ignore progress reporting errors
        }
        continue;
      }

      // Advance progress after successful processing
      processedSymbols++;
      try {
        const progress = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
        this.reportProgress(progress, `${processedSymbols}/${totalSymbols}`);
      } catch {
        // Ignore progress reporting errors
      }
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}
