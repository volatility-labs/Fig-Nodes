// src/nodes/core/market/indicators/orb-indicator-node.ts

import { Node, port } from '@sosa/core';
import type { NodeDefinition } from '@sosa/core';
import { IndicatorType, createIndicatorResult, createIndicatorValue, AssetClass, AssetSymbol, type IndicatorValue, type OHLCVBar } from './types';
import { calculateOrb } from './orb-calculator';

abstract class BaseIndicator extends Node {
  static definition: NodeDefinition = {
    inputs: {
      ohlcv: port('OHLCVBundle'),
    },
    outputs: {
      results: port('IndicatorResultList'),
    },
    params: [
      {
        name: 'indicators',
        type: 'combo',
        default: [IndicatorType.MACD, IndicatorType.RSI, IndicatorType.ADX],
        options: Object.values(IndicatorType),
      },
      {
        name: 'timeframe',
        type: 'combo',
        default: '1d',
        options: ['1m', '5m', '15m', '1h', '4h', '1d', '1w', '1M'],
      },
    ],
  };

  protected abstract mapToIndicatorValue(
    indType: IndicatorType,
    raw: Record<string, unknown>
  ): IndicatorValue;
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

/**
 * Computes the ORB (Opening Range Breakout) indicator for a single asset.
 * Outputs relative volume (RVOL) and direction (bullish/bearish/doji).
 */
export class OrbIndicator extends BaseIndicator {
  static override definition: NodeDefinition = {
    ...BaseIndicator.definition,
    inputs: {
      symbol: port('AssetSymbol'),
    },
    outputs: {
      results: port('IndicatorResultList'),
    },
    params: [
      { name: 'or_minutes', type: 'number', default: 5, min: 1, step: 1 },
      { name: 'avg_period', type: 'number', default: 14, min: 1, step: 1 },
    ],
    requiredCredentials: ['POLYGON_API_KEY'],
  };

  protected mapToIndicatorValue(
    _indType: IndicatorType,
    _raw: Record<string, unknown>
  ): IndicatorValue {
    // ORB node uses its own run path and does not rely on base mapping.
    return createIndicatorValue({ single: NaN });
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    console.log('='.repeat(80));
    console.log('ORB INDICATOR: Starting execution');
    console.log('='.repeat(80));

    const symbolRaw = inputs.symbol;
    if (!symbolRaw || !(symbolRaw instanceof AssetSymbol)) {
      console.warn('No symbol provided to ORB indicator');
      return { results: [] };
    }
    const symbol = symbolRaw;

    console.log(`ORB INDICATOR: Processing symbol ${symbol.ticker}`);

    // Get API key
    const apiKey = this.credentials.get('POLYGON_API_KEY');
    if (!apiKey || !apiKey.trim()) {
      console.error('Polygon API key not found in vault');
      return { results: [] };
    }

    // Get parameters
    const avgPeriodRaw = this.params.avg_period ?? 14;
    const orMinutesRaw = this.params.or_minutes ?? 5;

    // Type guards
    if (typeof avgPeriodRaw !== 'number') {
      console.error(`avg_period must be a number, got ${typeof avgPeriodRaw}`);
      return { results: [] };
    }

    if (typeof orMinutesRaw !== 'number') {
      console.error(`or_minutes must be a number, got ${typeof orMinutesRaw}`);
      return { results: [] };
    }

    const avgPeriod = Math.floor(avgPeriodRaw);
    const orMinutes = Math.floor(orMinutesRaw);

    // Fetch 5-min bars for last avg_period + 1 days
    const fetchParams = {
      multiplier: 5,
      timespan: 'minute' as const,
      lookback_period: `${avgPeriod + 1} days`,
      adjusted: true,
      sort: 'asc' as const,
      limit: 50000,
    };

    try {
      console.log(`ORB INDICATOR: Fetching bars with params:`, fetchParams);

      const [bars] = await fetchBars(symbol, apiKey, fetchParams);

      if (!bars || bars.length === 0) {
        console.log(`ORB INDICATOR: No bars fetched for ${symbol.ticker}`);
        console.warn(`No bars fetched for ${symbol.ticker}`);
        return { results: [] };
      }

      console.log(`ORB INDICATOR: Fetched ${bars.length} bars for ${symbol.ticker}`);
      console.log(
        `ORB INDICATOR: First bar timestamp: ${bars[0].timestamp}, last bar timestamp: ${bars[bars.length - 1].timestamp}`
      );

      // Use the calculator to calculate ORB indicators
      console.log('ORB INDICATOR: Calling calculateOrb...');
      const result = calculateOrb(bars, symbol, orMinutes, avgPeriod);
      console.log(`ORB INDICATOR: Got result:`, result);

      if (result.error) {
        console.warn(`ORB calculation error for ${symbol.ticker}: ${result.error}`);
        return { results: [] };
      }

      const relVolRaw = result.rel_vol;
      const direction = result.direction ?? 'doji';

      // Type guard for rel_vol
      if (typeof relVolRaw !== 'number') {
        console.error(`rel_vol must be a number, got ${typeof relVolRaw}`);
        return { results: [] };
      }

      const relVol = relVolRaw;

      // Get the latest timestamp from bars for the result
      const latestTimestamp = bars.length > 0 ? bars[bars.length - 1].timestamp : 0;

      // Return values in lines (for RVOL) and series (for direction)
      const values = createIndicatorValue({
        single: 0,
        lines: { rel_vol: relVol },
        series: [{ direction }],
      });

      const indicatorResult = createIndicatorResult({
        indicatorType: IndicatorType.ORB,
        timestamp: latestTimestamp,
        values: values,
        params: this.params,
      });

      return { results: [indicatorResult] };
    } catch (error) {
      console.error(`Error calculating ORB for ${symbol.ticker}:`, error);
      return { results: [] };
    }
  }
}
