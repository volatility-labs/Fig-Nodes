// src/nodes/core/market/filters/orb-filter-node.ts

import { ParamType, type NodeDefinition } from '@sosa/core';
import {
  AssetClass,
  AssetSymbol,
  IndicatorType,
  createIndicatorResult,
  createIndicatorValue,
  type OHLCVBar,
  type IndicatorResult,
  type OHLCVBundle,
} from './types';
import { BaseIndicatorFilter } from './base-indicator-filter';
import { calculateOrb } from './orb-calculator';

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

function calculateDateRange(lookbackPeriod: string): { from: number; to: number } {
  const days = parseLookbackPeriod(lookbackPeriod);
  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - days * 24 * 60 * 60 * 1000);

  return {
    from: startDate.getTime(),
    to: endDate.getTime(),
  };
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
    if (!marketIsOpen) {
      dataStatus = 'market-closed';
    } else if (apiStatus === 'OK') {
      dataStatus = 'real-time';
    } else if (apiStatus === 'DELAYED') {
      dataStatus = 'delayed';
    } else {
      dataStatus = 'unknown';
    }

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

class RateLimiter {
  private maxPerSecond: number;
  private tokens: number;
  private lastRefill: number;

  constructor(maxPerSecond: number = 100) {
    this.maxPerSecond = maxPerSecond;
    this.tokens = maxPerSecond;
    this.lastRefill = Date.now();
  }

  private refillTokens(): void {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;
    const tokensToAdd = elapsed * this.maxPerSecond;
    this.tokens = Math.min(this.maxPerSecond, this.tokens + tokensToAdd);
    this.lastRefill = now;
  }

  async acquire(): Promise<void> {
    this.refillTokens();

    if (this.tokens >= 1) {
      this.tokens -= 1;
      return;
    }

    const waitTime = ((1 - this.tokens) / this.maxPerSecond) * 1000;
    await new Promise<void>((resolve) => setTimeout(resolve, waitTime));
    this.refillTokens();
    this.tokens -= 1;
  }
}

/**
 * Filters assets based on Opening Range Breakout (ORB) criteria including relative volume and direction.
 */
export class OrbFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    requiredCredentials: ['POLYGON_API_KEY'],
    params: [
      { name: 'or_minutes', type: ParamType.NUMBER, default: 5, min: 1, step: 1 },
      { name: 'rel_vol_threshold', type: ParamType.NUMBER, default: 100.0, min: 0.0, step: 1.0 },
      {
        name: 'direction',
        type: ParamType.COMBO,
        default: 'both',
        options: ['bullish', 'bearish', 'both'],
      },
      { name: 'avg_period', type: ParamType.NUMBER, default: 14, min: 1, step: 1 },
      {
        name: 'filter_above_orh',
        type: ParamType.COMBO,
        default: 'false',
        options: ['true', 'false'],
      },
      {
        name: 'filter_below_orl',
        type: ParamType.COMBO,
        default: 'false',
        options: ['true', 'false'],
      },
    ],
  };

  private apiKey: string | undefined;
  private maxSafeConcurrency = 5;

  protected override validateIndicatorParams(): void {
    const orMinutes = this.params.or_minutes;
    const relVolThreshold = this.params.rel_vol_threshold;
    const avgPeriod = this.params.avg_period;
    const filterAboveOrh = this.params.filter_above_orh ?? 'false';
    const filterBelowOrl = this.params.filter_below_orl ?? 'false';

    if (typeof orMinutes !== 'number' || orMinutes <= 0) {
      throw new Error('Opening range minutes must be positive');
    }
    if (typeof relVolThreshold !== 'number' || relVolThreshold < 0) {
      throw new Error('Relative volume threshold cannot be negative');
    }
    if (typeof avgPeriod !== 'number' || avgPeriod <= 0) {
      throw new Error('Average period must be positive');
    }
    if (filterAboveOrh !== 'true' && filterAboveOrh !== 'false') {
      throw new Error('filter_above_orh must be "true" or "false"');
    }
    if (filterBelowOrl !== 'true' && filterBelowOrl !== 'false') {
      throw new Error('filter_below_orl must be "true" or "false"');
    }
  }

  private async calculateOrbIndicator(symbol: AssetSymbol, apiKey: string): Promise<IndicatorResult> {
    const avgPeriodRaw = this.params.avg_period;
    const orMinutesRaw = this.params.or_minutes;

    if (typeof avgPeriodRaw !== 'number') {
      throw new Error(`avg_period must be a number, got ${typeof avgPeriodRaw}`);
    }
    if (typeof orMinutesRaw !== 'number') {
      throw new Error(`or_minutes must be a number, got ${typeof orMinutesRaw}`);
    }

    const avgPeriod = Math.floor(avgPeriodRaw);
    const orMinutes = Math.floor(orMinutesRaw);

    // Fetch 5-min bars for last avg_period +1 days
    const fetchParams = {
      multiplier: 5,
      timespan: 'minute' as const,
      lookback_period: `${avgPeriod + 1} days`,
      adjusted: true,
      sort: 'asc' as const,
      limit: 50000,
    };

    const [bars] = await fetchBars(symbol, apiKey, fetchParams);

    if (!bars || bars.length === 0) {
      console.warn(`ORB_FILTER: No bars returned for ${symbol.ticker}`);
      return createIndicatorResult({
        indicatorType: IndicatorType.ORB,
        timestamp: 0,
        values: createIndicatorValue({}),
        params: this.params,
        error: 'No bars fetched',
      });
    }

    // Use the calculator to calculate ORB indicators
    const result = calculateOrb(bars, symbol, orMinutes, avgPeriod);

    if (result.error) {
      return createIndicatorResult({
        indicatorType: IndicatorType.ORB,
        timestamp: 0,
        values: createIndicatorValue({}),
        params: this.params,
        error: result.error,
      });
    }

    const relVolRaw = result.rel_vol;
    const direction = result.direction ?? 'doji';
    const orHigh = result.or_high;
    const orLow = result.or_low;

    if (typeof relVolRaw !== 'number') {
      throw new Error(`rel_vol must be a number, got ${typeof relVolRaw}`);
    }

    const relVol = relVolRaw;
    const latestTimestamp = bars[bars.length - 1].timestamp;
    const currentPrice = bars[bars.length - 1].close;

    const orHighFloat = orHigh ?? NaN;
    const orLowFloat = orLow ?? NaN;

    return createIndicatorResult({
      indicatorType: IndicatorType.ORB,
      timestamp: latestTimestamp,
      values: createIndicatorValue({
        single: 0,
        lines: {
          rel_vol: relVol,
          or_high: orHighFloat,
          or_low: orLowFloat,
          current_price: currentPrice,
        },
        series: [{ direction }],
      }),
      params: this.params,
    });
  }

  protected calculateIndicator(_ohlcvData: OHLCVBar[]): IndicatorResult {
    // Not used directly - we override run for async API calls
    throw new Error('Use async calculateOrbIndicator instead');
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (
      indicatorResult.error ||
      !indicatorResult.values.lines ||
      !indicatorResult.values.series
    ) {
      return false;
    }

    const relVol = indicatorResult.values.lines.rel_vol ?? 0;
    if (Number.isNaN(relVol)) {
      return false;
    }

    const directions = indicatorResult.values.series
      .filter((s) => 'direction' in s)
      .map((s) => s.direction as string);
    const direction = directions[0] ?? 'doji';

    if (direction === 'doji') {
      return false;
    }

    const relVolThreshold = this.params.rel_vol_threshold ?? 0.0;
    if (typeof relVolThreshold !== 'number') {
      throw new Error(`rel_vol_threshold must be a number`);
    }

    if (relVol < relVolThreshold) {
      return false;
    }

    const paramDir = this.params.direction;
    if (paramDir !== 'both' && direction !== paramDir) {
      return false;
    }

    // Additional price-based filters
    const lines = indicatorResult.values.lines;
    const currentPrice = lines.current_price ?? NaN;
    const orHigh = lines.or_high ?? NaN;
    const orLow = lines.or_low ?? NaN;

    // Check filter_above_orh
    const filterAboveOrhStr = this.params.filter_above_orh ?? 'false';
    const filterAboveOrh = filterAboveOrhStr === 'true';
    if (filterAboveOrh) {
      if (Number.isNaN(currentPrice) || Number.isNaN(orHigh)) {
        return false;
      }
      if (!(currentPrice > orHigh)) {
        return false;
      }
    }

    // Check filter_below_orl
    const filterBelowOrlStr = this.params.filter_below_orl ?? 'false';
    const filterBelowOrl = filterBelowOrlStr === 'true';
    if (filterBelowOrl) {
      if (Number.isNaN(currentPrice) || Number.isNaN(orLow)) {
        return false;
      }
      if (!(currentPrice < orLow)) {
        return false;
      }
    }

    return true;
  }

  protected override async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    this.apiKey = this.credentials.get('POLYGON_API_KEY');
    if (!this.apiKey || !this.apiKey.trim()) {
      throw new Error('Polygon API key not found in vault');
    }

    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const maxConcurrentParam = this.params.max_concurrent;
    const maxConcurrent = Math.floor(typeof maxConcurrentParam === 'number' ? maxConcurrentParam : 10);

    const rateLimitParam = this.params.rate_limit_per_second;
    const rateLimit = Math.floor(typeof rateLimitParam === 'number' ? rateLimitParam : 95);

    const filteredBundle: OHLCVBundle = new Map();
    const rateLimiter = new RateLimiter(rateLimit);
    const totalSymbols = ohlcvBundle.size;
    let completedCount = 0;

    // Create queue of symbols to process
    const queue: Array<[AssetSymbol, OHLCVBar[]]> = [];
    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (ohlcvData && ohlcvData.length > 0) {
        queue.push([symbol, ohlcvData]);
      }
    }

    // Process symbols with rate limiting
    const effectiveConcurrency = Math.min(maxConcurrent, this.maxSafeConcurrency);

    const processSymbol = async (symbol: AssetSymbol, ohlcvData: OHLCVBar[]): Promise<void> => {
      try {
        await rateLimiter.acquire();

        const indicatorResult = await this.calculateOrbIndicator(symbol, this.apiKey!);
        if (this.shouldPassFilter(indicatorResult)) {
          filteredBundle.set(symbol, ohlcvData);
        }

        completedCount++;
        const pct = (completedCount / totalSymbols) * 100;
        this.progress(pct, `${completedCount}/${totalSymbols}`);
      } catch (error) {
        console.error(`Error calculating ORB for ${symbol.ticker}:`, error);
      }
    };

    // Process in batches
    for (let i = 0; i < queue.length; i += effectiveConcurrency) {
      const batch = queue.slice(i, i + effectiveConcurrency);
      await Promise.all(batch.map(([sym, ohlcvData]) => processSymbol(sym, ohlcvData)));
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}
