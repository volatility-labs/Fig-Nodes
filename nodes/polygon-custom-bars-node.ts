// src/nodes/custom/polygon/polygon-custom-bars-node.ts

import { Node, NodeCategory, ProgressState, port, type NodeDefinition } from '@sosa/core';
import { AssetClass, AssetSymbol, type OHLCVBar } from './types';

// ======================== Inlined from polygon-service.ts ========================

interface FetchBarsParams {
  multiplier: number;
  timespan: 'minute' | 'hour' | 'day' | 'week' | 'month' | 'quarter' | 'year';
  lookback_period: string;
  adjusted?: boolean;
  sort?: 'asc' | 'desc';
  limit?: number;
}

interface BarMetadata {
  request_id?: string;
  results_count?: number;
  data_status?: string;
  api_status?: string;
  market_open?: boolean;
}

function parseLookbackPeriod(period: string): number {
  const match = period.match(/(\d+)\s*(day|days|week|weeks|month|months|year|years)/i);
  if (!match) {
    return 14;
  }
  const value = parseInt(match[1] ?? '14', 10);
  const unit = (match[2] ?? 'days').toLowerCase();
  switch (unit) {
    case 'day': case 'days': return value;
    case 'week': case 'weeks': return value * 7;
    case 'month': case 'months': return value * 30;
    case 'year': case 'years': return value * 365;
    default: return value;
  }
}

function calculateDateRange(lookbackPeriod: string): { from: number; to: number } {
  const days = parseLookbackPeriod(lookbackPeriod);
  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - days * 24 * 60 * 60 * 1000);
  return { from: startDate.getTime(), to: endDate.getTime() };
}

function isUSMarketOpen(): boolean {
  const now = new Date();
  const etFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
    weekday: 'short',
  });
  const parts = etFormatter.formatToParts(now);
  const weekday = parts.find((p) => p.type === 'weekday')?.value || '';
  const hour = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10);
  const minute = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10);
  if (['Sat', 'Sun'].includes(weekday)) {
    return false;
  }
  const currentMinutes = hour * 60 + minute;
  const marketOpenMinutes = 9 * 60 + 30;
  const marketCloseMinutes = 16 * 60;
  return currentMinutes >= marketOpenMinutes && currentMinutes <= marketCloseMinutes;
}

async function fetchBars(
  symbol: AssetSymbol,
  apiKey: string,
  params: FetchBarsParams | Record<string, unknown>
): Promise<[OHLCVBar[], BarMetadata]> {
  const multiplier = (params.multiplier as number) || 1;
  const timespan = (params.timespan as string) || 'day';
  const lookbackPeriod = (params.lookback_period as string) || '3 months';
  const adjusted = params.adjusted !== false;
  const sort = (params.sort as string) || 'asc';
  const limit = (params.limit as number) || 5000;

  const { from, to } = calculateDateRange(lookbackPeriod);

  let ticker = symbol.ticker.toUpperCase();
  if (symbol.assetClass === AssetClass.CRYPTO) {
    ticker = `X:${symbol.toString()}`;
  }

  const url = new URL(
    `https://api.massive.com/v2/aggs/ticker/${ticker}/range/${multiplier}/${timespan}/${from}/${to}`
  );
  url.searchParams.set('apiKey', apiKey);
  url.searchParams.set('adjusted', adjusted.toString());
  url.searchParams.set('sort', sort);
  url.searchParams.set('limit', limit.toString());

  const marketIsOpen = symbol.assetClass === AssetClass.CRYPTO ? true : isUSMarketOpen();

  try {
    const response = await fetch(url.toString());
    if (!response.ok) {
      console.error(`Polygon API error: ${response.status} ${response.statusText}`);
      return [[], { request_id: undefined, results_count: 0, data_status: 'error' }];
    }
    const data = await response.json();
    const apiStatus = data.status;
    if (!['OK', 'DELAYED'].includes(apiStatus) || !data.results) {
      console.warn(`Polygon API returned no results for ${ticker}`);
      return [[], { request_id: data.request_id, results_count: 0, data_status: 'error' }];
    }
    let dataStatus: string;
    if (!marketIsOpen) { dataStatus = 'market-closed'; }
    else if (apiStatus === 'OK') { dataStatus = 'real-time'; }
    else if (apiStatus === 'DELAYED') { dataStatus = 'delayed'; }
    else { dataStatus = 'unknown'; }

    const bars: OHLCVBar[] = data.results.map((r: Record<string, number>) => ({
      timestamp: r.t, open: r.o, high: r.h, low: r.l, close: r.c, volume: r.v,
    }));

    return [bars, {
      request_id: data.request_id,
      results_count: data.resultsCount ?? bars.length,
      data_status: dataStatus,
      api_status: apiStatus,
      market_open: marketIsOpen,
    }];
  } catch (error) {
    console.error(`Error fetching bars for ${ticker}:`, error);
    return [[], { request_id: undefined, results_count: 0, data_status: 'error' }];
  }
}

// ======================== End inlined code ========================

/**
 * Fetches custom aggregate bars (OHLCV) for a symbol from Massive.com API (formerly Polygon.io).
 *
 * Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
 * to use api.massive.com, but the API routes remain unchanged.
 *
 * For crypto symbols, the ticker is automatically prefixed with "X:" (e.g., BTCUSD -> X:BTCUSD)
 * as required by the Massive.com crypto aggregates API.
 */
export class PolygonCustomBars extends Node {
  static definition: NodeDefinition = {
    inputs: [port('symbol', 'AssetSymbol')],
    outputs: [port('ohlcv', 'OHLCVBundle')],
    ui: {},
    category: NodeCategory.MARKET,
    requiredCredentials: ['POLYGON_API_KEY'],

    params: [
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
    ],
  };

  protected async run(
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
