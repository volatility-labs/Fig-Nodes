// src/nodes/core/market/filters/evwma-filter-node.ts

import { Node, NodeCategory, port } from '@sosa/core';
import type { NodeDefinition } from '@sosa/core';
import {
  AssetClass,
  AssetSymbol,
  IndicatorType,
  createIndicatorResult,
  createIndicatorValue,
  type OHLCVBar,
  type IndicatorResult,
  type OHLCVBundle,
  type SerializedOHLCVBundle,
  deserializeOHLCVBundle,
} from './types';
import { calculateEvwma, calculateRollingCorrelation } from './evwma-calculator';

abstract class BaseFilter extends Node {
  static override definition: NodeDefinition = {
    inputs: {
      ohlcv_bundle: port('OHLCVBundle'),
    },
    outputs: {
      filtered_ohlcv_bundle: port('OHLCVBundle'),
    },
    ui: {
      resultDisplay: 'none',
    },
  };

  protected filterCondition(_symbol: AssetSymbol, _ohlcvData: OHLCVBar[]): boolean {
    throw new Error('Subclasses must implement filterCondition');
  }

  protected async filterConditionAsync(
    symbol: AssetSymbol,
    ohlcvData: OHLCVBar[]
  ): Promise<boolean> {
    return this.filterCondition(symbol, ohlcvData);
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();

    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (!ohlcvData || ohlcvData.length === 0) {
        continue;
      }

      try {
        if (await this.filterConditionAsync(symbol, ohlcvData)) {
          filteredBundle.set(symbol, ohlcvData);
        }
      } catch (e) {
        if (e instanceof Error && e.message.includes('must implement')) {
          if (this.filterCondition(symbol, ohlcvData)) {
            filteredBundle.set(symbol, ohlcvData);
          }
        } else {
          throw e;
        }
      }
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}

abstract class BaseIndicatorFilter extends BaseFilter {
  static override definition: NodeDefinition = {
    ...BaseFilter.definition,
    category: NodeCategory.MARKET,
  };

  constructor(
    nodeId: string,
    params: Record<string, unknown> = {},
    graphContext?: Record<string, unknown>
  ) {
    super(nodeId, params, graphContext ?? {});
    this.validateIndicatorParams();
  }

  protected validateIndicatorParams(): void {
    // Default implementation does nothing
  }

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
 * EVWMA (Exponential Volume Weighted Moving Average) Filter
 *
 * Filters symbols based on EVWMA alignment and correlation across multiple timeframes.
 *
 * Requires warm-up period for accurate calculations.
 *
 * Note: Higher timeframes (4hr, 1day, weekly) are less accurate than shorter ones (1min, 5min, 15min).
 */
export class EVWMAFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    requiredCredentials: ['POLYGON_API_KEY'],
    params: [
      {
        name: 'evwma1_timeframe',
        type: 'combo',
        default: '1min',
        options: ['', '1min', '5min', '15min', '30min', '1hr', '4hr', '1day', 'weekly'],
        label: 'EVWMA 1 Timeframe',
        description: 'First EVWMA timeframe (leave blank to skip).',
      },
      {
        name: 'evwma2_timeframe',
        type: 'combo',
        default: '5min',
        options: ['', '1min', '5min', '15min', '30min', '1hr', '4hr', '1day', 'weekly'],
        label: 'EVWMA 2 Timeframe',
        description: 'Second EVWMA timeframe (leave blank to skip).',
      },
      {
        name: 'evwma3_timeframe',
        type: 'combo',
        default: '15min',
        options: ['', '1min', '5min', '15min', '30min', '1hr', '4hr', '1day', 'weekly'],
        label: 'EVWMA 3 Timeframe',
        description: 'Third EVWMA timeframe (leave blank to skip).',
      },
      {
        name: 'length',
        type: 'number',
        default: 325,
        min: 1,
        step: 1,
        label: 'EVWMA Length',
        description: 'Period for EVWMA calculation',
      },
      {
        name: 'correlation_threshold',
        type: 'number',
        default: 0.6,
        min: 0.0,
        max: 1.0,
        step: 0.01,
        label: 'Correlation Threshold',
        description: 'Minimum correlation between EVWMAs to pass filter',
      },
    ],
  };

  private maxSafeConcurrency = 5;

  protected override validateIndicatorParams(): void {
    const length = this.params.length ?? 325;
    if (typeof length !== 'number' || length <= 0) {
      throw new Error('length must be a positive number');
    }

    const rollWindow = this.params.roll_window ?? 325;
    if (typeof rollWindow !== 'number' || rollWindow <= 0) {
      throw new Error('roll_window must be a positive number');
    }

    const corrSmoothWindow = this.params.corr_smooth_window ?? 1;
    if (typeof corrSmoothWindow !== 'number' || corrSmoothWindow <= 0) {
      throw new Error('corr_smooth_window must be a positive number');
    }

    const correlationThreshold = this.params.correlation_threshold ?? 0.6;
    if (typeof correlationThreshold !== 'number' || correlationThreshold < 0 || correlationThreshold > 1) {
      throw new Error('correlation_threshold must be between 0 and 1');
    }
  }

  private timeframeToMultiplierTimespan(timeframe: string): [number, string] {
    const timeframeMap: Record<string, [number, string]> = {
      '1min': [1, 'minute'],
      '5min': [5, 'minute'],
      '15min': [15, 'minute'],
      '30min': [30, 'minute'],
      '1hr': [1, 'hour'],
      '4hr': [4, 'hour'],
      '1day': [1, 'day'],
      weekly: [1, 'week'],
    };
    return timeframeMap[timeframe] ?? [1, 'minute'];
  }

  private calculateLookbackDays(timeframe: string, length: number): number {
    if (timeframe === '1min') {
      return Math.max(1, Math.floor(length / (390 * 60))) + 1;
    } else if (timeframe.endsWith('min')) {
      const mins = parseInt(timeframe.replace('min', ''), 10);
      return Math.max(1, Math.floor((length * mins) / (390 * 60))) + 1;
    } else if (timeframe === '1hr') {
      return Math.max(1, Math.floor(length / 390)) + 1;
    } else if (timeframe === '4hr') {
      return Math.max(1, Math.floor((length * 4) / 390)) + 1;
    } else if (timeframe === '1day') {
      return Math.max(1, length) + 1;
    } else if (timeframe === 'weekly') {
      return Math.max(7, length * 7) + 1;
    }
    return 30;
  }

  private smoothCorrelation(correlations: (number | null)[], window: number): (number | null)[] {
    if (window <= 1) {
      return correlations;
    }

    const results: (number | null)[] = new Array(correlations.length).fill(null);

    for (let i = 0; i < correlations.length; i++) {
      const windowStart = Math.max(0, i - window + 1);
      const windowValues = correlations.slice(windowStart, i + 1);
      const validValues = windowValues.filter((v): v is number => v !== null);

      if (validValues.length > 0) {
        results[i] = validValues.reduce((a, b) => a + b, 0) / validValues.length;
      }
    }

    return results;
  }

  private async calculateEvwmaIndicator(
    symbol: AssetSymbol,
    apiKey: string,
    ohlcvData: OHLCVBar[]
  ): Promise<IndicatorResult> {
    const evwma1Tf = String(this.params.evwma1_timeframe ?? '1min');
    const evwma2Tf = String(this.params.evwma2_timeframe ?? '5min');
    const evwma3Tf = String(this.params.evwma3_timeframe ?? '15min');
    const length = typeof this.params.length === 'number' ? Math.floor(this.params.length) : 325;
    const useCumVolume = Boolean(this.params.use_cum_volume ?? false);
    const rollWindow = typeof this.params.roll_window === 'number' ? Math.floor(this.params.roll_window) : 325;
    const corrSmoothWindow = typeof this.params.corr_smooth_window === 'number' ? Math.floor(this.params.corr_smooth_window) : 1;
    const threshold = typeof this.params.correlation_threshold === 'number' ? this.params.correlation_threshold : 0.6;
    const requireAlignment = Boolean(this.params.require_alignment ?? true);
    const requirePriceAboveEvwma = Boolean(this.params.require_price_above_evwma ?? true);

    const selectedTimeframes = [evwma1Tf, evwma2Tf, evwma3Tf].filter((tf) => tf);

    if (selectedTimeframes.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EVWMA,
        timestamp: 0,
        values: createIndicatorValue({}),
        params: this.params,
        error: 'No EVWMA timeframes selected',
      });
    }

    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.EVWMA,
        timestamp: 0,
        values: createIndicatorValue({}),
        params: this.params,
        error: 'No OHLCV data provided',
      });
    }

    const currentPrice = ohlcvData[ohlcvData.length - 1].close;
    const latestTimestamp = ohlcvData[ohlcvData.length - 1].timestamp;

    const evwmaSeries: Record<string, (number | null)[]> = {};
    const evwmaLatestValues: Record<string, number> = {};

    for (let i = 0; i < selectedTimeframes.length; i++) {
      const timeframe = selectedTimeframes[i];
      const [multiplier, timespan] = this.timeframeToMultiplierTimespan(timeframe);
      const lookbackDays = this.calculateLookbackDays(timeframe, length);

      const fetchParams = {
        multiplier,
        timespan: timespan as 'minute' | 'hour' | 'day' | 'week',
        lookback_period: `${lookbackDays} days`,
        adjusted: true,
        sort: 'asc' as const,
        limit: 50000,
      };

      const [bars] = await fetchBars(symbol, apiKey, fetchParams);

      if (!bars || bars.length < length) {
        return createIndicatorResult({
          indicatorType: IndicatorType.EVWMA,
          timestamp: latestTimestamp,
          values: createIndicatorValue({}),
          params: this.params,
          error: `Insufficient data for ${timeframe} EVWMA: ${bars?.length ?? 0} bars`,
        });
      }

      const evwmaResult = calculateEvwma(bars, length, useCumVolume, rollWindow);
      const evwmaValues = evwmaResult.evwma;

      if (!evwmaValues || evwmaValues.length < length) {
        return createIndicatorResult({
          indicatorType: IndicatorType.EVWMA,
          timestamp: latestTimestamp,
          values: createIndicatorValue({}),
          params: this.params,
          error: `Insufficient EVWMA data for ${timeframe}`,
        });
      }

      const evwmaName = `evwma${i + 1}`;
      evwmaSeries[evwmaName] = evwmaValues;

      // Get latest EVWMA value
      let latestEvwma: number | null = null;
      for (let j = evwmaValues.length - 1; j >= 0; j--) {
        if (evwmaValues[j] !== null) {
          latestEvwma = evwmaValues[j];
          break;
        }
      }

      if (latestEvwma !== null) {
        evwmaLatestValues[evwmaName] = latestEvwma;
      }
    }

    // Check price above EVWMA if required
    if (requirePriceAboveEvwma) {
      for (const [evwmaName, latestEvwma] of Object.entries(evwmaLatestValues)) {
        if (currentPrice <= latestEvwma) {
          return createIndicatorResult({
            indicatorType: IndicatorType.EVWMA,
            timestamp: latestTimestamp,
            values: createIndicatorValue({}),
            params: this.params,
            error: `Price ${currentPrice} not above ${evwmaName} ${latestEvwma}`,
          });
        }
      }
    }

    // Check alignment if required
    if (requireAlignment && Object.keys(evwmaLatestValues).length >= 2) {
      const latestValues = selectedTimeframes.map((_, i) => evwmaLatestValues[`evwma${i + 1}`]).filter((v) => v !== undefined);
      if (latestValues.length >= 2) {
        for (let i = 0; i < latestValues.length - 1; i++) {
          if (latestValues[i] <= latestValues[i + 1]) {
            return createIndicatorResult({
              indicatorType: IndicatorType.EVWMA,
              timestamp: latestTimestamp,
              values: createIndicatorValue({}),
              params: this.params,
              error: `EVWMAs not aligned: ${latestValues}`,
            });
          }
        }
      }
    }

    // Calculate correlations if we have at least 2 EVWMAs
    let correlationPassed = true;
    if (Object.keys(evwmaSeries).length >= 2) {
      const evwmaNames = Object.keys(evwmaSeries);
      const allCorrelations: (number | null)[][] = [];

      for (let i = 0; i < evwmaNames.length; i++) {
        for (let j = i + 1; j < evwmaNames.length; j++) {
          const corr = calculateRollingCorrelation(
            evwmaSeries[evwmaNames[i]],
            evwmaSeries[evwmaNames[j]],
            rollWindow
          );
          allCorrelations.push(corr);
        }
      }

      if (allCorrelations.length > 0) {
        // Average correlations
        const avgCorrelations: (number | null)[] = [];
        const maxLen = Math.max(...allCorrelations.map((c) => c.length));
        for (let k = 0; k < maxLen; k++) {
          const valuesAtK = allCorrelations.map((c) => (k < c.length ? c[k] : null)).filter((v): v is number => v !== null);
          if (valuesAtK.length > 0) {
            avgCorrelations.push(valuesAtK.reduce((a, b) => a + b, 0) / valuesAtK.length);
          } else {
            avgCorrelations.push(null);
          }
        }

        const smoothedCorrelations = this.smoothCorrelation(avgCorrelations, corrSmoothWindow);

        // Get final correlation
        let finalCorr: number | null = null;
        for (let j = smoothedCorrelations.length - 1; j >= 0; j--) {
          if (smoothedCorrelations[j] !== null) {
            finalCorr = smoothedCorrelations[j];
            break;
          }
        }

        if (finalCorr === null || finalCorr < threshold) {
          correlationPassed = false;
        }
      }
    }

    const lines: Record<string, number> = { current_price: currentPrice };
    for (const [name, value] of Object.entries(evwmaLatestValues)) {
      lines[name] = value;
    }
    if (Object.keys(evwmaSeries).length >= 2) {
      lines.correlation_passed = correlationPassed ? 1.0 : 0.0;
    }

    return createIndicatorResult({
      indicatorType: IndicatorType.EVWMA,
      timestamp: latestTimestamp,
      values: createIndicatorValue({ single: 0, lines: lines }),
      params: this.params,
      error: correlationPassed ? null : 'Correlation below threshold',
    });
  }

  protected calculateIndicator(_ohlcvData: OHLCVBar[]): IndicatorResult {
    throw new Error('Use async calculateEvwmaIndicator instead');
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    if (!indicatorResult.values.lines) {
      return false;
    }

    const correlationPassed = indicatorResult.values.lines.correlation_passed ?? 1.0;
    return correlationPassed > 0.5;
  }

  protected override async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const apiKey = this.credentials.get('POLYGON_API_KEY');
    if (!apiKey) {
      throw new Error('Polygon API key not found in vault');
    }

    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    let maxConcurrentRaw = this.params.max_concurrent ?? 10;
    const maxConcurrent = typeof maxConcurrentRaw === 'number' ? Math.floor(maxConcurrentRaw) : 10;

    let rateLimitRaw = this.params.rate_limit_per_second ?? 95;
    const rateLimit = typeof rateLimitRaw === 'number' ? Math.floor(rateLimitRaw) : 95;

    const filteredBundle: OHLCVBundle = new Map();
    const rateLimiter = new RateLimiter(rateLimit);
    const totalSymbols = ohlcvBundle.size;
    let completedCount = 0;

    const queue: Array<[AssetSymbol, OHLCVBar[]]> = [];
    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (ohlcvData && ohlcvData.length > 0) {
        queue.push([symbol, ohlcvData]);
      }
    }

    const effectiveConcurrency = Math.min(maxConcurrent, this.maxSafeConcurrency);

    const processSymbol = async (symbol: AssetSymbol, ohlcvData: OHLCVBar[]): Promise<void> => {
      try {
        await rateLimiter.acquire();

        const indicatorResult = await this.calculateEvwmaIndicator(symbol, apiKey, ohlcvData);
        if (this.shouldPassFilter(indicatorResult)) {
          filteredBundle.set(symbol, ohlcvData);
        }

        completedCount++;
        const pct = (completedCount / totalSymbols) * 100;
        this.progress(pct, `${completedCount}/${totalSymbols}`);
      } catch (error) {
        console.error(`Error processing EVWMA for ${symbol.ticker}:`, error);
      }
    };

    for (let i = 0; i < queue.length; i += effectiveConcurrency) {
      const batch = queue.slice(i, i + effectiveConcurrency);
      await Promise.all(batch.map(([symbol, ohlcvData]) => processSymbol(symbol, ohlcvData)));
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}
