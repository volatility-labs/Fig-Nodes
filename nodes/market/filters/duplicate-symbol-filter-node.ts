// src/nodes/core/market/filters/duplicate-symbol-filter-node.ts
// Translated from: nodes/core/market/filters/duplicate_symbol_filter_node.py

import { BaseFilter } from './base/base-filter-node';
import { getType } from '@fig-node/core';
import type {
  NodeInputs,
  NodeOutputs,
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  OHLCVBundle,
  NodeUIConfig,
} from '@fig-node/core';
import { AssetSymbol } from '@fig-node/core';

/**
 * Compare symbols across up to 3 inputs to find common or unique symbols.
 *
 * Accepts OHLCV bundles or symbol lists from ExtractSymbols.
 * Connect up to 3 inputs to compare symbols between them.
 */
export class DuplicateSymbolFilter extends BaseFilter {
  static override inputs: Record<string, unknown> = {
    ohlcv_bundle_1: getType('OHLCVBundle'),
    ohlcv_bundle_2: getType('OHLCVBundle'),
    ohlcv_bundle_3: getType('OHLCVBundle'),
  };

  static override defaultParams: DefaultParams = {
    operation: 'common', // common, unique_to_1, unique_to_2, unique_to_3, all
    compare_by: 'ticker', // ticker, symbol_string
    case_insensitive: true,
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'operation',
      type: 'combo',
      default: 'common',
      options: ['common', 'unique_to_1', 'unique_to_2', 'unique_to_3', 'all'],
      label: 'Operation',
      description:
        'common: symbols in all connected inputs | unique_to_X: symbols only in ohlcv_bundle_X | all: union of all symbols',
    },
    {
      name: 'compare_by',
      type: 'combo',
      default: 'ticker',
      options: ['ticker', 'symbol_string'],
      label: 'Compare By',
      description: 'Compare symbols by ticker (base symbol) or full symbol string',
    },
    {
      name: 'case_insensitive',
      type: 'boolean',
      default: true,
      label: 'Case Insensitive',
      description: 'Compare symbols case-insensitively',
    },
  ];

  static uiConfig: NodeUIConfig = {
    size: [220, 100],
    displayResults: false,
    resizable: false,
  };

  /**
   * Normalize input to OHLCV bundle format.
   * Handles both OHLCV bundles (Map<AssetSymbol, OHLCVBar[]>) and symbol lists (AssetSymbol[]).
   */
  private normalizeInput(inputData: unknown): OHLCVBundle {
    if (inputData === null || inputData === undefined) {
      return new Map();
    }

    // If it's already a Map
    if (inputData instanceof Map) {
      const result: OHLCVBundle = new Map();
      for (const [key, value] of inputData) {
        if (key instanceof AssetSymbol && Array.isArray(value)) {
          result.set(key, value as OHLCVBar[]);
        }
      }
      return result;
    }

    // If it's an array, treat as symbol list and create empty bundles
    if (Array.isArray(inputData)) {
      const result: OHLCVBundle = new Map();
      for (const item of inputData) {
        if (item instanceof AssetSymbol) {
          result.set(item, []);
        }
      }
      return result;
    }

    // If it's a plain object, try to convert
    if (typeof inputData === 'object') {
      const result: OHLCVBundle = new Map();
      // This would need proper deserialization in production
      return result;
    }

    return new Map();
  }

  /**
   * Extract list of symbols from normalized input.
   */
  private getSymbolsFromInput(inputData: OHLCVBundle): AssetSymbol[] {
    return Array.from(inputData.keys());
  }

  /**
   * Create a comparison key from a symbol based on compare_by setting.
   */
  private makeKey(symbol: AssetSymbol): string {
    const compareBy = this.params.compare_by ?? 'ticker';
    const caseInsensitive = this.params.case_insensitive ?? true;

    let key: string;
    if (compareBy === 'ticker') {
      key = symbol.ticker;
    } else {
      // symbol_string
      key = symbol.toString();
    }

    if (caseInsensitive) {
      return key.toLowerCase();
    }
    return key;
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    // Normalize all inputs to OHLCV bundle format
    const ohlcvBundle1 = this.normalizeInput(inputs.ohlcv_bundle_1);
    const ohlcvBundle2 = this.normalizeInput(inputs.ohlcv_bundle_2);
    const ohlcvBundle3 = this.normalizeInput(inputs.ohlcv_bundle_3);

    // Get operation mode
    const operation = this.params.operation ?? 'common';

    // Determine which inputs are connected
    const connectedInputs: Array<[string, OHLCVBundle]> = [];
    if (ohlcvBundle1.size > 0) {
      connectedInputs.push(['ohlcv_bundle_1', ohlcvBundle1]);
    }
    if (ohlcvBundle2.size > 0) {
      connectedInputs.push(['ohlcv_bundle_2', ohlcvBundle2]);
    }
    if (ohlcvBundle3.size > 0) {
      connectedInputs.push(['ohlcv_bundle_3', ohlcvBundle3]);
    }

    if (connectedInputs.length === 0) {
      console.warn('DuplicateSymbolFilter: No inputs connected');
      return { filtered_ohlcv_bundle: new Map() };
    }

    // Build symbol sets for each input
    const symbolSets: Map<string, Set<string>> = new Map();
    const symbolMaps: Map<string, Map<string, AssetSymbol>> = new Map();
    const inputBundles: Map<string, OHLCVBundle> = new Map();

    for (const [name, bundle] of connectedInputs) {
      const symbols = this.getSymbolsFromInput(bundle);
      const keys: Set<string> = new Set();
      const keyToSymbol: Map<string, AssetSymbol> = new Map();

      for (const symbol of symbols) {
        const k = this.makeKey(symbol);
        keys.add(k);
        if (!keyToSymbol.has(k)) {
          keyToSymbol.set(k, symbol);
        }
      }

      symbolSets.set(name, keys);
      symbolMaps.set(name, keyToSymbol);
      inputBundles.set(name, bundle);
    }

    // Execute operation
    const filtered: OHLCVBundle = new Map();

    if (operation === 'common') {
      // Symbols in ALL connected inputs
      if (connectedInputs.length === 0) {
        // No-op
      } else if (connectedInputs.length === 1) {
        // If only one input, return all symbols from it
        const [, bundle] = connectedInputs[0];
        for (const [symbol, data] of bundle) {
          filtered.set(symbol, data);
        }
      } else {
        // Intersection of all inputs
        let commonKeys = new Set(symbolSets.get(connectedInputs[0][0])!);
        for (let i = 1; i < connectedInputs.length; i++) {
          const [name] = connectedInputs[i];
          const otherKeys = symbolSets.get(name)!;
          commonKeys = new Set([...commonKeys].filter((k) => otherKeys.has(k)));
        }

        // Use first input's bundle for data
        const firstName = connectedInputs[0][0];
        for (const k of commonKeys) {
          const symbol = symbolMaps.get(firstName)!.get(k)!;
          // Try to get data from any input that has it
          let found = false;
          for (const [_name, bundle] of connectedInputs) {
            if (bundle.has(symbol)) {
              filtered.set(symbol, bundle.get(symbol)!);
              found = true;
              break;
            }
          }
          if (!found) {
            // If no bundle has data, create empty entry
            filtered.set(symbol, []);
          }
        }
      }
    } else if (operation === 'unique_to_1' && symbolSets.has('ohlcv_bundle_1')) {
      // Symbols only in ohlcv_bundle_1, not in others
      let uniqueKeys = new Set(symbolSets.get('ohlcv_bundle_1')!);
      for (const [name] of connectedInputs) {
        if (name !== 'ohlcv_bundle_1') {
          const otherKeys = symbolSets.get(name)!;
          uniqueKeys = new Set([...uniqueKeys].filter((k) => !otherKeys.has(k)));
        }
      }

      for (const k of uniqueKeys) {
        const symbol = symbolMaps.get('ohlcv_bundle_1')!.get(k)!;
        filtered.set(symbol, inputBundles.get('ohlcv_bundle_1')!.get(symbol) ?? []);
      }
    } else if (operation === 'unique_to_2' && symbolSets.has('ohlcv_bundle_2')) {
      // Symbols only in ohlcv_bundle_2, not in others
      let uniqueKeys = new Set(symbolSets.get('ohlcv_bundle_2')!);
      for (const [name] of connectedInputs) {
        if (name !== 'ohlcv_bundle_2') {
          const otherKeys = symbolSets.get(name)!;
          uniqueKeys = new Set([...uniqueKeys].filter((k) => !otherKeys.has(k)));
        }
      }

      for (const k of uniqueKeys) {
        const symbol = symbolMaps.get('ohlcv_bundle_2')!.get(k)!;
        filtered.set(symbol, inputBundles.get('ohlcv_bundle_2')!.get(symbol) ?? []);
      }
    } else if (operation === 'unique_to_3' && symbolSets.has('ohlcv_bundle_3')) {
      // Symbols only in ohlcv_bundle_3, not in others
      let uniqueKeys = new Set(symbolSets.get('ohlcv_bundle_3')!);
      for (const [name] of connectedInputs) {
        if (name !== 'ohlcv_bundle_3') {
          const otherKeys = symbolSets.get(name)!;
          uniqueKeys = new Set([...uniqueKeys].filter((k) => !otherKeys.has(k)));
        }
      }

      for (const k of uniqueKeys) {
        const symbol = symbolMaps.get('ohlcv_bundle_3')!.get(k)!;
        filtered.set(symbol, inputBundles.get('ohlcv_bundle_3')!.get(symbol) ?? []);
      }
    } else if (operation === 'all') {
      // Union of all symbols from all inputs
      const allKeys: Set<string> = new Set();
      for (const [name] of connectedInputs) {
        for (const k of symbolSets.get(name)!) {
          allKeys.add(k);
        }
      }

      // Build merged result, preferring data from first input that has it
      for (const k of allKeys) {
        let symbol: AssetSymbol | null = null;
        let bundleData: OHLCVBar[] = [];

        // Find symbol and data from first input that has this key
        for (const [name, bundle] of connectedInputs) {
          if (symbolMaps.get(name)!.has(k)) {
            symbol = symbolMaps.get(name)!.get(k)!;
            if (bundle.has(symbol)) {
              bundleData = bundle.get(symbol)!;
            }
            break;
          }
        }

        if (symbol) {
          filtered.set(symbol, bundleData);
        }
      }
    }

    console.log(
      `DuplicateSymbolFilter: Operation '${operation}' returned ${filtered.size} symbols`
    );
    return { filtered_ohlcv_bundle: filtered };
  }
}
