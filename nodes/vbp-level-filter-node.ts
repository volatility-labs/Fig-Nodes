// src/nodes/core/market/filters/vbp-level-filter-node.ts

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
import { calculateVbp } from './vbp-calculator';

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

// Constants
const MIN_BARS_REQUIRED = 10;
const DAYS_PER_YEAR = 365.25;

/**
 * Filters assets based on Volume Profile (VBP) levels and distance from support/resistance.
 *
 * Calculates significant price levels based on volume distribution and checks if current price
 * is within specified distance from support (below) and resistance (above).
 */
export class VBPLevelFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    requiredCredentials: ['POLYGON_API_KEY'],
    params: [
      {
        name: 'bins',
        type: 'number',
        default: 50,
        min: 10,
        max: 200,
        step: 5,
        label: 'Number of Bins',
        description: 'Number of bins for volume histogram. More bins = finer granularity',
      },
      {
        name: 'lookback_years',
        type: 'number',
        default: 2,
        min: 1,
        max: 10,
        step: 1,
        label: 'Lookback Period (Years)',
        description: 'Number of years to look back for volume data',
      },
      {
        name: 'num_levels',
        type: 'number',
        default: 5,
        min: 1,
        max: 20,
        step: 1,
        label: 'Number of Levels',
        description: 'Number of significant volume levels to identify',
      },
      {
        name: 'max_distance_to_support',
        type: 'number',
        default: 5.0,
        min: 0.0,
        max: 50.0,
        step: 0.1,
        precision: 2,
        label: 'Max Distance to Support (%)',
        description: 'Maximum % distance to nearest support level',
      },
      {
        name: 'min_distance_to_resistance',
        type: 'number',
        default: 5.0,
        min: 0.0,
        max: 50.0,
        step: 0.1,
        precision: 2,
        label: 'Min Distance to Resistance (%)',
        description: 'Minimum % distance to nearest resistance level',
      },
    ],
  };

  private maxSafeConcurrency = 5;

  protected override validateIndicatorParams(): void {
    const binsRaw = this.params.bins ?? 50;
    const lookbackYearsRaw = this.params.lookback_years ?? 2;
    const numLevelsRaw = this.params.num_levels ?? 5;

    if (typeof binsRaw !== 'number' || binsRaw < 10) {
      throw new Error('Number of bins must be at least 10');
    }
    if (typeof lookbackYearsRaw !== 'number' || lookbackYearsRaw < 1) {
      throw new Error('Lookback period must be at least 1 year');
    }
    if (typeof numLevelsRaw !== 'number' || numLevelsRaw < 1) {
      throw new Error('Number of levels must be at least 1');
    }
  }

  private getIntParam(key: string, defaultVal: number): number {
    const raw = this.params[key] ?? defaultVal;
    if (typeof raw !== 'number') {
      throw new Error(`${key} must be a number, got ${typeof raw}`);
    }
    return Math.floor(raw);
  }

  private getFloatParam(key: string, defaultVal: number): number {
    const raw = this.params[key] ?? defaultVal;
    if (typeof raw !== 'number') {
      throw new Error(`${key} must be a number, got ${typeof raw}`);
    }
    return raw;
  }

  private getBoolParam(key: string, defaultVal: boolean): boolean {
    const raw = this.params[key];
    return raw !== undefined ? Boolean(raw) : defaultVal;
  }

  private aggregateToWeekly(ohlcvData: OHLCVBar[]): OHLCVBar[] {
    if (!ohlcvData || ohlcvData.length === 0) {
      return [];
    }

    const weeklyGroups: Record<string, OHLCVBar[]> = {};

    for (const bar of ohlcvData) {
      const dt = new Date(bar.timestamp);
      const year = dt.getUTCFullYear();
      const startOfYear = new Date(Date.UTC(year, 0, 1));
      const diff = dt.getTime() - startOfYear.getTime();
      const oneWeek = 7 * 24 * 60 * 60 * 1000;
      const week = Math.floor(diff / oneWeek) + 1;
      const weekKey = `${year}-W${week.toString().padStart(2, '0')}`;

      if (!weeklyGroups[weekKey]) {
        weeklyGroups[weekKey] = [];
      }
      weeklyGroups[weekKey].push(bar);
    }

    const weeklyBars: OHLCVBar[] = [];
    const sortedKeys = Object.keys(weeklyGroups).sort();

    for (const weekKey of sortedKeys) {
      const group = weeklyGroups[weekKey];
      if (!group || group.length === 0) continue;

      const weeklyBar: OHLCVBar = {
        timestamp: group[0].timestamp,
        open: group[0].open,
        high: Math.max(...group.map((b) => b.high)),
        low: Math.min(...group.map((b) => b.low)),
        close: group[group.length - 1].close,
        volume: group.reduce((sum, b) => sum + (b.volume ?? 0), 0),
      };
      weeklyBars.push(weeklyBar);
    }

    return weeklyBars;
  }

  private filterByLookbackPeriod(ohlcvData: OHLCVBar[], lookbackYears: number): OHLCVBar[] {
    if (!ohlcvData || ohlcvData.length === 0) {
      return [];
    }

    const lastTs = ohlcvData[ohlcvData.length - 1].timestamp;
    const cutoffTimestamp = lastTs - lookbackYears * DAYS_PER_YEAR * 24 * 60 * 60 * 1000;

    return ohlcvData.filter((bar) => bar.timestamp >= cutoffTimestamp);
  }

  private findSignificantLevels(
    histogram: Array<{ priceLow: number; priceHigh: number; priceLevel: number; volume: number }>,
    numLevels: number
  ): Array<{ priceLow: number; priceHigh: number; priceLevel: number; volume: number }> {
    if (!histogram || histogram.length === 0) {
      return [];
    }

    const sortedBins = [...histogram].sort((a, b) => {
      return b.volume - a.volume;
    });

    return sortedBins.slice(0, numLevels);
  }

  private calculateVbpForPeriod(
    ohlcvData: OHLCVBar[],
    lookbackYears: number
  ): Array<{ priceLow: number; priceHigh: number; priceLevel: number; volume: number }> {
    const filteredData = this.filterByLookbackPeriod(ohlcvData, lookbackYears);

    if (filteredData.length < MIN_BARS_REQUIRED) {
      return [];
    }

    const useWeekly = this.getBoolParam('use_weekly', false);
    const preparedData = useWeekly ? ohlcvData : this.aggregateToWeekly(filteredData);

    if (preparedData.length < MIN_BARS_REQUIRED) {
      return [];
    }

    const bins = this.getIntParam('bins', 50);
    const useDollarWeighted = this.getBoolParam('use_dollar_weighted', false);
    const useCloseOnly = this.getBoolParam('use_close_only', false);

    const vbpResult = calculateVbp(preparedData, bins, useDollarWeighted, useCloseOnly);

    if (vbpResult.pointOfControl === null) {
      return [];
    }

    const numLevels = this.getIntParam('num_levels', 5);
    return this.findSignificantLevels(vbpResult.histogram, numLevels);
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.VBP,
        timestamp: 0,
        values: createIndicatorValue({ single: 0, lines: {} }),
        params: this.params,
        error: 'No OHLCV data',
      });
    }

    const lookbackYears1 = this.getIntParam('lookback_years', 2);
    let allLevels = this.calculateVbpForPeriod(ohlcvData, lookbackYears1);

    const lookbackYears2Raw = this.params.lookback_years_2;
    if (lookbackYears2Raw !== null && typeof lookbackYears2Raw === 'number') {
      const levels2 = this.calculateVbpForPeriod(ohlcvData, lookbackYears2Raw);
      allLevels = [...allLevels, ...levels2];
    }

    if (allLevels.length === 0) {
      return createIndicatorResult({
        indicatorType: IndicatorType.VBP,
        timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
        values: createIndicatorValue({ single: 0, lines: {} }),
        params: this.params,
        error: 'No valid levels found',
      });
    }

    return this.buildIndicatorResult(ohlcvData, allLevels);
  }

  private getPriceLevel(level: { priceLow: number; priceHigh: number; priceLevel: number; volume: number }): number {
    return level.priceLevel;
  }

  private buildIndicatorResult(
    ohlcvData: OHLCVBar[],
    allLevels: Array<{ priceLow: number; priceHigh: number; priceLevel: number; volume: number }>
  ): IndicatorResult {
    const currentPrice = ohlcvData[ohlcvData.length - 1].close;
    const numLevels = this.getIntParam('num_levels', 5);

    const lookbackYears2Raw = this.params.lookback_years_2;
    const maxLevels = lookbackYears2Raw !== null ? numLevels * 2 : numLevels;

    // Deduplicate levels
    const sortedLevels = [...allLevels].sort((a, b) => b.volume - a.volume);
    const topLevels = sortedLevels.slice(0, maxLevels);

    type VbpLevel = { priceLow: number; priceHigh: number; priceLevel: number; volume: number };
    const uniqueLevels: VbpLevel[] = [];
    const seenPrices = new Set<number>();

    for (const level of topLevels) {
      const priceLevel = this.getPriceLevel(level);
      const priceRounded = Math.round(priceLevel * 100) / 100;
      if (!seenPrices.has(priceRounded)) {
        uniqueLevels.push(level);
        seenPrices.add(priceRounded);
      }
    }

    // Calculate support and resistance
    const supportLevels = uniqueLevels.filter((l) => this.getPriceLevel(l) < currentPrice);
    const resistanceLevels = uniqueLevels.filter((l) => this.getPriceLevel(l) > currentPrice);

    let closestSupportPrice: number;
    if (supportLevels.length > 0) {
      closestSupportPrice = Math.max(...supportLevels.map((l) => this.getPriceLevel(l)));
    } else if (uniqueLevels.length > 0) {
      closestSupportPrice = Math.min(...uniqueLevels.map((l) => this.getPriceLevel(l)));
    } else {
      closestSupportPrice = currentPrice;
    }

    let closestResistancePrice: number;
    if (resistanceLevels.length > 0) {
      closestResistancePrice = Math.min(...resistanceLevels.map((l) => this.getPriceLevel(l)));
    } else if (uniqueLevels.length > 0) {
      closestResistancePrice = Math.max(...uniqueLevels.map((l) => this.getPriceLevel(l)));
    } else {
      closestResistancePrice = currentPrice;
    }

    const hasResistanceAbove = resistanceLevels.length > 0;

    // Calculate distances
    const distanceToSupport = currentPrice > 0 ? (Math.abs(currentPrice - closestSupportPrice) / currentPrice) * 100 : 0;
    const distanceToResistance = hasResistanceAbove && currentPrice > 0
      ? (Math.abs(closestResistancePrice - currentPrice) / currentPrice) * 100
      : Infinity;

    return createIndicatorResult({
      indicatorType: IndicatorType.VBP,
      timestamp: ohlcvData[ohlcvData.length - 1].timestamp,
      values: createIndicatorValue({
        single: 0,
        lines: {
          current_price: currentPrice,
          closest_support: closestSupportPrice,
          closest_resistance: closestResistancePrice,
          distance_to_support: distanceToSupport,
          distance_to_resistance: distanceToResistance,
          num_levels: uniqueLevels.length,
          has_resistance_above: hasResistanceAbove ? 1 : 0,
        },
      }),
      params: this.params,
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    const lines = indicatorResult.values.lines;
    const distanceToSupportRaw = lines.distance_to_support ?? 0;
    const distanceToResistanceRaw = lines.distance_to_resistance ?? 0;
    const hasResistanceAbove = (lines.has_resistance_above ?? 1) === 1;

    if (!Number.isFinite(distanceToSupportRaw)) {
      return false;
    }

    const distanceToSupport = distanceToSupportRaw;
    const maxDistanceSupport = this.getFloatParam('max_distance_to_support', 5.0);

    if (distanceToSupport > maxDistanceSupport) {
      return false;
    }

    // If no resistance levels above, automatically pass
    if (!hasResistanceAbove) {
      return true;
    }

    if (!Number.isFinite(distanceToResistanceRaw)) {
      return false;
    }

    const distanceToResistance = distanceToResistanceRaw;
    const minDistanceResistance = this.getFloatParam('min_distance_to_resistance', 5.0);

    if (distanceToResistance < minDistanceResistance) {
      return false;
    }

    return true;
  }

  protected override async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const useWeekly = this.getBoolParam('use_weekly', false);

    // If use_weekly, we need to fetch weekly bars from API
    if (useWeekly) {
      const apiKey = this.credentials.get('POLYGON_API_KEY');
      if (!apiKey) {
        throw new Error('Polygon API key not found in vault');
      }

      const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

      if (ohlcvBundle.size === 0) {
        return { filtered_ohlcv_bundle: new Map() };
      }

      const maxConcurrent = this.getIntParam('max_concurrent', 10);
      const rateLimit = this.getIntParam('rate_limit_per_second', 95);

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

          // Fetch weekly bars
          const lookbackYears = this.getIntParam('lookback_years', 2);
          const lookbackDays = lookbackYears * 365;

          const fetchParams = {
            multiplier: 1,
            timespan: 'week' as const,
            lookback_period: `${lookbackDays} days`,
            adjusted: true,
            sort: 'asc' as const,
            limit: 50000,
          };

          const [weeklyBars] = await fetchBars(symbol, apiKey, fetchParams);
          const calculationData = weeklyBars.length > 0 ? weeklyBars : ohlcvData;

          const indicatorResult = this.calculateIndicator(calculationData);
          if (this.shouldPassFilter(indicatorResult)) {
            filteredBundle.set(symbol, ohlcvData);
          }

          completedCount++;
          const pct = (completedCount / totalSymbols) * 100;
          this.progress(pct, `${completedCount}/${totalSymbols}`);
        } catch (error) {
          console.error(`Error processing VBP for ${symbol.ticker}:`, error);
        }
      };

      for (let i = 0; i < queue.length; i += effectiveConcurrency) {
        const batch = queue.slice(i, i + effectiveConcurrency);
        await Promise.all(batch.map(([symbol, ohlcvData]) => processSymbol(symbol, ohlcvData)));
      }

      return { filtered_ohlcv_bundle: filteredBundle };
    }

    // Call parent's run implementation when not fetching weekly bars
    return super.run(inputs);
  }
}
