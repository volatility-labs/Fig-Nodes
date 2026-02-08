// src/services/polygon-service.ts
// Translated from: services/polygon_service.py

import { AssetClass, type AssetSymbol, type OHLCVBar } from '../types';

export interface FetchBarsParams {
  multiplier: number;
  timespan: 'minute' | 'hour' | 'day' | 'week' | 'month' | 'quarter' | 'year';
  lookback_period: string;
  adjusted?: boolean;
  sort?: 'asc' | 'desc';
  limit?: number;
}

export interface BarMetadata {
  request_id?: string;
  results_count?: number;
  data_status?: string;
  api_status?: string;
  market_open?: boolean;
}

/**
 * Parse lookback period string like "14 days" into days number.
 */
export function parseLookbackPeriod(period: string): number {
  const match = period.match(/(\d+)\s*(day|days|week|weeks|month|months|year|years)/i);
  if (!match) {
    return 14; // default
  }

  const value = parseInt(match[1] ?? '14', 10);
  const unit = (match[2] ?? 'days').toLowerCase();

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
function calculateDateRange(lookbackPeriod: string): { from: number; to: number } {
  const days = parseLookbackPeriod(lookbackPeriod);
  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - days * 24 * 60 * 60 * 1000);

  return {
    from: startDate.getTime(),
    to: endDate.getTime(),
  };
}

/**
 * Check if US stock market is currently open (9:30 AM ET - 4:00 PM ET, Mon-Fri).
 */
export function isUSMarketOpen(): boolean {
  const now = new Date();

  // Convert to ET (handles DST automatically)
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

  // Check if it's a weekday
  if (['Sat', 'Sun'].includes(weekday)) {
    return false;
  }

  // Check if within market hours (9:30 AM - 4:00 PM ET)
  const currentMinutes = hour * 60 + minute;
  const marketOpenMinutes = 9 * 60 + 30; // 9:30 AM
  const marketCloseMinutes = 16 * 60; // 4:00 PM

  return currentMinutes >= marketOpenMinutes && currentMinutes <= marketCloseMinutes;
}

/**
 * Fetch OHLCV bars from Polygon/Massive API.
 */
export async function fetchBars(
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

  // Build URL - Massive.com API (formerly Polygon.io)
  let ticker = symbol.ticker.toUpperCase();

  // Add "X:" prefix for crypto tickers
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

  // Determine market status
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

    // Determine data status
    let dataStatus: string;
    if (!marketIsOpen) {
      dataStatus = 'market-closed';
    } else if (apiStatus === 'OK') {
      dataStatus = 'real-time';
    } else if (apiStatus === 'DELAYED') {
      dataStatus = 'delayed';
    } else {
      dataStatus = 'unknown';
    }

    // Convert results to OHLCVBar format
    const bars: OHLCVBar[] = data.results.map((r: Record<string, number>) => ({
      timestamp: r.t,
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
        data_status: dataStatus,
        api_status: apiStatus,
        market_open: marketIsOpen,
      },
    ];
  } catch (error) {
    console.error(`Error fetching bars for ${ticker}:`, error);
    return [[], { request_id: undefined, results_count: 0, data_status: 'error' }];
  }
}

// ======================== Massive.com Helpers ========================

/**
 * Build snapshot tickers list with proper prefixes.
 */
export function massiveBuildSnapshotTickers(filterSymbols: AssetSymbol[]): string[] {
  const tickers: string[] = [];
  for (const sym of filterSymbols) {
    if (sym.assetClass === AssetClass.CRYPTO) {
      tickers.push(`X:${sym.toString()}`);
    } else {
      tickers.push(sym.ticker.toUpperCase());
    }
  }
  return tickers;
}

/**
 * Safely get numeric value from dict with default.
 */
export function massiveGetNumericFromDict(
  data: Record<string, unknown>,
  key: string,
  defaultValue: number
): number {
  const value = data[key];
  if (typeof value === 'number') {
    return value;
  }
  return defaultValue;
}

/**
 * Parse ticker for market to extract base ticker and quote currency.
 */
export function massiveParseTickerForMarket(
  ticker: string,
  market: string
): [string, string | null] {
  if (!['crypto', 'fx'].includes(market) || !ticker.includes(':')) {
    return [ticker, null];
  }

  const parts = ticker.split(':', 2);
  const tick = parts[1];

  // Check for quote currency suffix (e.g., BTCUSD -> BTC, USD)
  if (tick && tick.length > 3) {
    const possibleQuote = tick.slice(-3);
    if (/^[A-Z]{3}$/.test(possibleQuote)) {
      return [tick.slice(0, -3), possibleQuote];
    }
  }

  return [ticker, null];
}

/**
 * Fetch ETF type codes from Massive.com API.
 */
export async function massiveFetchTickerTypes(apiKey: string): Promise<Set<string>> {
  const url = 'https://api.massive.com/v3/reference/tickers/types';

  try {
    const response = await fetch(`${url}?apiKey=${apiKey}`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const results = data.results || [];
    const etfTypeCodes = new Set<string>();

    for (const item of results) {
      if (typeof item !== 'object' || item === null) continue;

      const code = typeof item.code === 'string' ? item.code : '';
      const description = typeof item.description === 'string' ? item.description.toLowerCase() : '';
      const typeCode = code.toLowerCase();

      if (
        typeCode.includes('etf') ||
        typeCode.includes('etn') ||
        typeCode.includes('etp') ||
        description.includes('exchange traded')
      ) {
        etfTypeCodes.add(code);
      }
    }

    return etfTypeCodes;
  } catch (error) {
    console.warn('Failed to fetch ticker types, using defaults:', error);
    return new Set(['ETF', 'ETN', 'ETP']);
  }
}

/**
 * Fetch snapshot data from Massive.com API.
 */
export async function massiveFetchSnapshot(
  apiKey: string,
  locale: string,
  markets: string,
  market: string,
  tickers: string[] | null,
  includeOtc: boolean
): Promise<Record<string, unknown>[]> {
  const url = `https://api.massive.com/v2/snapshot/locale/${locale}/markets/${markets}/tickers`;

  const params = new URLSearchParams();
  params.set('apiKey', apiKey);

  if (includeOtc && ['stocks', 'otc'].includes(market)) {
    params.set('include_otc', 'true');
  }

  if (tickers && tickers.length > 0) {
    params.set('tickers', tickers.join(','));
  }

  const response = await fetch(`${url}?${params.toString()}`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch snapshot: ${response.status} - ${errorText}`);
  }

  const data = await response.json();
  const tickersRaw = data.tickers || [];

  if (!Array.isArray(tickersRaw)) {
    return [];
  }

  return tickersRaw.filter(
    (t: unknown): t is Record<string, unknown> =>
      typeof t === 'object' && t !== null
  );
}

/**
 * Fetch filtered tickers with ETF filtering for a specific list.
 */
export async function massiveFetchFilteredTickersForList(
  apiKey: string,
  market: string,
  excludeEtfs: boolean,
  tickers: string[]
): Promise<Set<string>> {
  let etfTypes = new Set<string>();
  if (['stocks', 'otc'].includes(market)) {
    etfTypes = await massiveFetchTickerTypes(apiKey);
  }

  const refMarket = market === 'otc' ? 'otc' : market;
  const allowed = new Set<string>();

  for (const ticker of tickers) {
    const params = new URLSearchParams();
    params.set('active', 'true');
    params.set('limit', '1');
    params.set('apiKey', apiKey);
    params.set('market', refMarket);
    params.set('ticker', ticker);

    try {
      const response = await fetch(
        `https://api.massive.com/v3/reference/tickers?${params.toString()}`
      );

      if (response.status !== 200) {
        allowed.add(ticker);
        continue;
      }

      const data = await response.json();
      const results = data.results || [];

      if (!Array.isArray(results) || results.length === 0) {
        allowed.add(ticker);
        continue;
      }

      const firstItem = results[0];
      if (typeof firstItem !== 'object' || firstItem === null) {
        allowed.add(ticker);
        continue;
      }

      const typeStr = typeof firstItem.type === 'string' ? firstItem.type : '';
      const marketStr = typeof firstItem.market === 'string' ? firstItem.market : '';

      const isEtf =
        etfTypes.has(typeStr) ||
        typeStr.toLowerCase().includes('etf') ||
        typeStr.toLowerCase().includes('etn') ||
        typeStr.toLowerCase().includes('etp') ||
        marketStr === 'etp';

      if (excludeEtfs && isEtf) {
        continue;
      }
      if (!excludeEtfs && !isEtf) {
        continue;
      }

      allowed.add(ticker);
    } catch {
      allowed.add(ticker);
    }
  }

  return allowed;
}

/**
 * Fetch filtered tickers with pagination.
 */
export async function massiveFetchFilteredTickers(
  apiKey: string,
  market: string,
  excludeEtfs: boolean,
  includeOtc: boolean = false,
  progressCallback?: (progress: number, text: string) => void
): Promise<Set<string>> {
  const refMarket = market === 'otc' ? 'otc' : market;
  const needsEtfFilter = ['stocks', 'otc'].includes(market);

  let etfTypes = new Set<string>();
  if (needsEtfFilter) {
    etfTypes = await massiveFetchTickerTypes(apiKey);
  }

  const tickerSet = new Set<string>();
  let nextUrl: string | null = 'https://api.massive.com/v3/reference/tickers';
  let pageCount = 0;

  const baseParams = new URLSearchParams();
  baseParams.set('active', 'true');
  baseParams.set('limit', '1000');
  baseParams.set('apiKey', apiKey);
  if (['stocks', 'otc', 'crypto', 'fx', 'indices'].includes(market)) {
    baseParams.set('market', refMarket);
  }

  while (nextUrl) {
    let response: Response;

    if (pageCount > 0) {
      // Use next_url with apiKey appended
      const separator = nextUrl.includes('?') ? '&' : '?';
      response = await fetch(`${nextUrl}${separator}apiKey=${apiKey}`);
    } else {
      response = await fetch(`${nextUrl}?${baseParams.toString()}`);
    }

    if (!response.ok) {
      console.warn(`Failed to fetch ticker metadata page ${pageCount + 1}: ${response.status}`);
      break;
    }

    const data = await response.json();
    const results = data.results || [];

    for (const item of results) {
      if (typeof item !== 'object' || item === null) continue;

      const tickerRaw = item.ticker;
      if (typeof tickerRaw !== 'string' || !tickerRaw) continue;

      const ticker = tickerRaw;
      const tickerType = typeof item.type === 'string' ? item.type : '';
      const tickerMarket = typeof item.market === 'string' ? item.market : '';

      // Apply ETF filtering
      if (etfTypes.size > 0) {
        const isEtf =
          etfTypes.has(tickerType) ||
          tickerType.toLowerCase().includes('etf') ||
          tickerType.toLowerCase().includes('etn') ||
          tickerType.toLowerCase().includes('etp') ||
          tickerMarket === 'etp';

        if (excludeEtfs && isEtf) continue;
        if (!excludeEtfs && !isEtf) continue;
      }

      // Apply OTC filtering
      if (!includeOtc) {
        if (tickerMarket === 'otc' || tickerMarket === 'OTC') {
          continue;
        }
      }

      tickerSet.add(ticker);
    }

    // Check for next page
    nextUrl = data.next_url || null;
    pageCount++;

    // Progress reporting
    if (pageCount % 5 === 0 && progressCallback) {
      progressCallback(
        5.0 + Math.min(pageCount * 20, 25),
        `Fetched metadata for ${tickerSet.size} tickers (page ${pageCount})...`
      );
    }
  }

  return tickerSet;
}
