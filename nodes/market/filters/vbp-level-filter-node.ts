// src/nodes/core/market/filters/vbp-level-filter-node.ts

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import type { NodeDefinition } from '@fig-node/core';
import { IndicatorType, createIndicatorResult, createIndicatorValue, AssetSymbol, type OHLCVBar, type IndicatorResult, type OHLCVBundle } from '../types';
import { calculateVbp } from '../calculators/vbp-calculator';
import { fetchBars } from '../services/polygon-service';
import { RateLimiter } from '../rate-limiter';

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
    defaults: {
      bins: 50,
      lookback_years: 2,
      lookback_years_2: null,
      num_levels: 5,
      max_distance_to_support: 5.0,
      min_distance_to_resistance: 5.0,
      use_weekly: false,
      max_concurrent: 10,
      rate_limit_per_second: 95,
      use_dollar_weighted: false,
      use_close_only: false,
    },
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
