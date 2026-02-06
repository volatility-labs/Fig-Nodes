// src/nodes/custom/polygon/polygon-custom-bars-node.ts
// Translated from: nodes/custom/polygon/polygon_custom_bars_node.py

import { Base } from '@fig-node/core';
import {
  AssetSymbol,
  NodeCategory,
  NodeUIConfig,
  OHLCVBar,
  ParamMeta,
  ProgressState,
  getType,
} from '@fig-node/core';
import { fetchBars } from '../services/polygon-service';

/**
 * Fetches custom aggregate bars (OHLCV) for a symbol from Massive.com API (formerly Polygon.io).
 *
 * Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
 * to use api.massive.com, but the API routes remain unchanged.
 *
 * For crypto symbols, the ticker is automatically prefixed with "X:" (e.g., BTCUSD -> X:BTCUSD)
 * as required by the Massive.com crypto aggregates API.
 */
export class PolygonCustomBars extends Base {
  static required_keys = ['POLYGON_API_KEY'];
  static inputs = { symbol: getType('AssetSymbol') };
  static outputs = { ohlcv: getType('OHLCVBundle') };
  static uiConfig: NodeUIConfig = {
    size: [280, 140],
    displayResults: false,
    resizable: true,
  };

  static defaultParams = {
    multiplier: 1,
    timespan: 'day',
    lookback_period: '3 months',
    adjusted: true,
    sort: 'asc',
    limit: 5000,
  };

  static paramsMeta: ParamMeta[] = [
    { name: 'multiplier', type: 'number', default: 1, min: 1, step: 1 },
    {
      name: 'timespan',
      type: 'combo',
      default: 'day',
      options: ['minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'],
    },
    {
      name: 'lookback_period',
      type: 'combo',
      default: '3 months',
      options: [
        '1 day',
        '3 days',
        '1 week',
        '2 weeks',
        '1 month',
        '2 months',
        '3 months',
        '4 months',
        '6 months',
        '9 months',
        '1 year',
        '18 months',
        '2 years',
        '3 years',
        '5 years',
        '10 years',
      ],
    },
    { name: 'adjusted', type: 'combo', default: true, options: [true, false] },
    { name: 'sort', type: 'combo', default: 'asc', options: ['asc', 'desc'] },
    { name: 'limit', type: 'number', default: 5000, min: 1, max: 50000, step: 1 },
  ];

  static CATEGORY = NodeCategory.MARKET;

  protected async executeImpl(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const symbol = inputs.symbol as AssetSymbol | undefined;

    if (!symbol || !(symbol instanceof AssetSymbol)) {
      throw new Error('Symbol input is required');
    }

    const apiKey = this.credentials.get('POLYGON_API_KEY');
    if (!apiKey) {
      throw new Error('Polygon API key not found in vault');
    }

    const [bars, metadata] = await fetchBars(symbol, apiKey, this.params);

    // Report status via progress callback
    this.emitProgress(
      ProgressState.UPDATE,
      undefined,
      `Fetched bars for ${symbol.ticker}`,
      { polygon_data_status: metadata.data_status || 'unknown' }
    );

    // Build OHLCVBundle (Map with symbol.key as key)
    const bundle = new Map<string, OHLCVBar[]>();
    bundle.set(symbol.key, bars);

    return { ohlcv: bundle };
  }
}
