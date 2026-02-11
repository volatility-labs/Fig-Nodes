import { Node, port, NodeCategory, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, type OHLCVBar, type OHLCVBundle, type IndicatorResult, type SerializedOHLCVBundle, deserializeOHLCVBundle } from './types';

export abstract class BaseIndicatorFilter extends Node {
  static override definition: NodeDefinition = {
    inputs: [port('ohlcv_bundle', 'OHLCVBundle')],
    outputs: [port('filtered_ohlcv_bundle', 'OHLCVBundle')],
    category: NodeCategory.MARKET,
    ui: {
      resultDisplay: 'none',
    },
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
