// src/nodes/core/market/utils/extract-symbols-node.ts
// Translated from: nodes/core/market/utils/extract_symbols_node.py

import { Base } from '../../../base/base-node';
import { getType } from '../../../../core/types';
import type {
  NodeInputs,
  NodeOutputs,
  ParamMeta,
  DefaultParams,
  AssetSymbolData,
  OHLCVBar,
  OHLCVBundle,
} from '../../../../core/types';
import { AssetSymbol } from '../../../../core/types';

/**
 * Extracts a list of asset symbols from an OHLCV bundle.
 * Takes an OHLCV bundle (Map<AssetSymbol, OHLCVBar[]>) and outputs
 * just the list of AssetSymbol keys.
 */
export class ExtractSymbols extends Base {
  static override inputs: Record<string, unknown> = {
    ohlcv_bundle: getType('OHLCVBundle'),
  };
  static override outputs: Record<string, unknown> = {
    symbols: getType('AssetSymbolList'),
  };
  static override defaultParams: DefaultParams = {};
  static override paramsMeta: ParamMeta[] = [];

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    // Extract the asset symbols (keys) from the OHLCV bundle
    const symbols = Array.from(ohlcvBundle.keys());

    return { symbols };
  }
}
