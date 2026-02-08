// src/nodes/core/io/asset-symbol-input-node.ts

import { Node, port, type NodeDefinition } from '@sosa/core';
import { AssetClass, AssetSymbol, InstrumentType } from '../market/types';

/**
 * Node to create a single AssetSymbol from user parameters.
 */
export class AssetSymbolInput extends Node {
  static definition: NodeDefinition = {
    inputs: {},
    outputs: { symbol: port('AssetSymbol') },

    ui: {},

    params: [
      { name: 'ticker', type: 'text', default: '' },
      {
        name: 'asset_class',
        type: 'combo',
        default: AssetClass.CRYPTO,
        options: Object.values(AssetClass),
      },
      {
        name: 'quote_currency',
        type: 'combo',
        default: 'USDT',
        options: ['USD', 'USDC', 'USDT'],
      },
      {
        name: 'instrument_type',
        type: 'combo',
        default: InstrumentType.PERPETUAL,
        options: Object.values(InstrumentType),
      },
    ],
  };

  protected async run(_inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    // Coerce params to enums and normalized cases
    const tickerValue = String(this.params.ticker ?? '').toUpperCase();
    const assetClassParam = this.params.asset_class ?? AssetClass.CRYPTO;
    const instrumentTypeParam = this.params.instrument_type ?? InstrumentType.SPOT;
    let quoteCurrencyValue = this.params.quote_currency ?? null;

    if (quoteCurrencyValue) {
      quoteCurrencyValue = String(quoteCurrencyValue).toUpperCase();
    }

    // Parse asset_class - accept both enum instance and name string
    let assetClassValue: AssetClass;
    if (Object.values(AssetClass).includes(assetClassParam as AssetClass)) {
      assetClassValue = assetClassParam as AssetClass;
    } else {
      const upperParam = String(assetClassParam).toUpperCase();
      if (Object.values(AssetClass).includes(upperParam as AssetClass)) {
        assetClassValue = upperParam as AssetClass;
      } else {
        throw new Error(`Invalid asset_class: ${assetClassParam}`);
      }
    }

    // Parse instrument_type - accept both enum instance and name string
    let instrumentTypeValue: InstrumentType;
    if (Object.values(InstrumentType).includes(instrumentTypeParam as InstrumentType)) {
      instrumentTypeValue = instrumentTypeParam as InstrumentType;
    } else {
      const upperParam = String(instrumentTypeParam).toUpperCase();
      if (Object.values(InstrumentType).includes(upperParam as InstrumentType)) {
        instrumentTypeValue = upperParam as InstrumentType;
      } else {
        throw new Error(`Invalid instrument_type: ${instrumentTypeParam}`);
      }
    }

    const symbol = new AssetSymbol(
      tickerValue,
      assetClassValue,
      quoteCurrencyValue ? String(quoteCurrencyValue) : undefined,
      instrumentTypeValue
    );

    return { symbol };
  }
}
