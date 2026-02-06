// src/nodes/core/market/filters/base/base-filter-node.ts
// Translated from: nodes/core/market/filters/base/base_filter_node.py

import { Base } from '@fig-node/core';
import { getType } from '@fig-node/core';
import type {
  NodeInputs,
  NodeOutputs,
  NodeUIConfig,
  OHLCVBar,
  OHLCVBundle,
} from '@fig-node/core';
import { AssetSymbol } from '@fig-node/core';

/**
 * Base class for general filter nodes that filter OHLCV bundles based on arbitrary conditions.
 * Suitable for non-indicator based filters (e.g., volume thresholds, price ranges, market cap).
 *
 * Input: OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>)
 * Output: Filtered OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>)
 */
export abstract class BaseFilter extends Base {
  static override inputs: Record<string, unknown> = {
    ohlcv_bundle: getType('OHLCVBundle'),
  };
  static override outputs: Record<string, unknown> = {
    filtered_ohlcv_bundle: getType('OHLCVBundle'),
  };

  // Default UI config for all filter nodes
  static override uiConfig: NodeUIConfig = {
    size: [360, 140],
    displayResults: false,
    resultDisplay: 'none',
  };

  /**
   * Determine if the asset should pass the filter.
   * Must be implemented by subclasses.
   *
   * @param symbol - The asset symbol
   * @param ohlcvData - List of OHLCV bars
   * @returns True if the asset passes the filter, False otherwise
   */
  protected filterCondition(_symbol: AssetSymbol, _ohlcvData: OHLCVBar[]): boolean {
    throw new Error('Subclasses must implement filterCondition');
  }

  /**
   * Async version of filter condition. Defaults to calling sync version.
   * Override in subclasses if async filtering is needed (e.g., external API calls).
   *
   * @param symbol - The asset symbol
   * @param ohlcvData - List of OHLCV bars
   * @returns True if the asset passes the filter, False otherwise
   */
  protected async filterConditionAsync(
    symbol: AssetSymbol,
    ohlcvData: OHLCVBar[]
  ): Promise<boolean> {
    return this.filterCondition(symbol, ohlcvData);
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();

    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (!ohlcvData || ohlcvData.length === 0) {
        continue;
      }

      // Try async filter condition first, fall back to sync if not implemented
      try {
        if (await this.filterConditionAsync(symbol, ohlcvData)) {
          filteredBundle.set(symbol, ohlcvData);
        }
      } catch (e) {
        if (e instanceof Error && e.message.includes('must implement')) {
          // Fall back to sync version if async not overridden
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
