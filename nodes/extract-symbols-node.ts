// src/nodes/core/market/utils/extract-symbols-node.ts

import { Node, PortType, port } from '@sosa/core';
import type { NodeDefinition } from '@sosa/core';
import type { OHLCVBundle } from './types';

/**
 * Extracts a list of asset symbols from an OHLCV bundle.
 * Takes an OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>) and outputs
 * just the list of AssetSymbol keys.
 */
export class ExtractSymbols extends Node {
  static definition: NodeDefinition = {
    inputs: [port('ohlcv_bundle', PortType.OHLCV_BUNDLE)],
    outputs: [port('symbols', PortType.ASSET_SYMBOL_LIST)],
    ui: {},
    params: [],
  };

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    // Extract the asset symbols (keys) from the OHLCV bundle
    const symbols = Array.from(ohlcvBundle.keys());

    return { symbols };
  }
}
