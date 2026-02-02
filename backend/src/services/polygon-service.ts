// src/services/polygon-service.ts
// Translated from: services/polygon_service.py
// TODO: Implement full Polygon API service using fetch

import type { AssetSymbol, OHLCVBar } from '../core/types';

export interface FetchBarsParams {
  multiplier: number;
  timespan: 'minute' | 'hour' | 'day' | 'week';
  lookback_period: string;
  adjusted?: boolean;
  sort?: 'asc' | 'desc';
  limit?: number;
}

export interface BarMetadata {
  request_id?: string;
  results_count?: number;
}

/**
 * Parse lookback period string like "14 days" into days number.
 */
export function parseLookbackPeriod(period: string): number {
  const match = period.match(/(\d+)\s*(day|days|week|weeks|month|months|year|years)/i);
  if (!match) {
    return 14; // default
  }

  const value = parseInt(match[1], 10);
  const unit = match[2].toLowerCase();

  switch (unit) {
    case 'day':
    case 'days':
      return value;
    case 'week':
    case 'weeks':
      return value * 7;
    case 'month':
    case 'months':
      return value * 30;
    case 'year':
    case 'years':
      return value * 365;
    default:
      return value;
  }
}

/**
 * Calculate start and end dates from lookback period.
 */
function calculateDateRange(lookbackPeriod: string): { from: string; to: string } {
  const days = parseLookbackPeriod(lookbackPeriod);
  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - days * 24 * 60 * 60 * 1000);

  const formatDate = (d: Date): string => {
    return d.toISOString().split('T')[0];
  };

  return {
    from: formatDate(startDate),
    to: formatDate(endDate),
  };
}

/**
 * Fetch OHLCV bars from Polygon API.
 */
export async function fetchBars(
  symbol: AssetSymbol,
  apiKey: string,
  params: FetchBarsParams
): Promise<[OHLCVBar[], BarMetadata]> {
  const { multiplier, timespan, lookback_period, adjusted = true, sort = 'asc', limit = 50000 } = params;
  const { from, to } = calculateDateRange(lookback_period);

  // Build URL - Polygon API v2 aggregates endpoint
  const ticker = symbol.ticker.toUpperCase();
  const url = new URL(
    `https://api.polygon.io/v2/aggs/ticker/${ticker}/range/${multiplier}/${timespan}/${from}/${to}`
  );

  url.searchParams.set('apiKey', apiKey);
  url.searchParams.set('adjusted', adjusted.toString());
  url.searchParams.set('sort', sort);
  url.searchParams.set('limit', limit.toString());

  try {
    const response = await fetch(url.toString());

    if (!response.ok) {
      console.error(`Polygon API error: ${response.status} ${response.statusText}`);
      return [[], { request_id: undefined, results_count: 0 }];
    }

    const data = await response.json();

    if (data.status !== 'OK' || !data.results) {
      console.warn(`Polygon API returned no results for ${ticker}`);
      return [[], { request_id: data.request_id, results_count: 0 }];
    }

    // Convert Polygon results to OHLCVBar format
    const bars: OHLCVBar[] = data.results.map((r: Record<string, number>) => ({
      timestamp: r.t, // Unix timestamp in milliseconds
      open: r.o,
      high: r.h,
      low: r.l,
      close: r.c,
      volume: r.v,
    }));

    return [
      bars,
      {
        request_id: data.request_id,
        results_count: data.resultsCount ?? bars.length,
      },
    ];
  } catch (error) {
    console.error(`Error fetching bars for ${ticker}:`, error);
    return [[], { request_id: undefined, results_count: 0 }];
  }
}
