// src/nodes/core/market/utils/ohlcv-plot-enhanced-node.ts
//
// NOTE: This TypeScript version computes chart data but does NOT render images.
// The Python version used matplotlib for server-side rendering.
// In this architecture, we return computed data for frontend rendering.

import { Node, NodeCategory, port, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, AssetClass, type OHLCVBar } from './types';
import { calculateEma } from './ema-calculator';
import { calculateSma } from './sma-calculator';
import { calculateVbp } from './vbp-calculator';

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

// Constants
const MIN_BARS_REQUIRED = 10;
const DEFAULT_VBP_COLOR = '#FF6B35';

interface NormalizedBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface ChartDataOutput {
  symbol: string;
  assetClass: string;
  bars: NormalizedBar[];
  overlays: Array<{
    type: string;
    period: number;
    values: Array<number | null>;
    color: string;
    label: string;
  }>;
  vbpLevels: number[];
  vbpColor: string;
  vbpStyle: string;
}

/**
 * Normalize OHLCV bars to consistent format.
 */
function normalizeBars(bars: OHLCVBar[]): NormalizedBar[] {
  const cleaned: NormalizedBar[] = [];

  for (const b of bars || []) {
    try {
      const timestamp = b.timestamp ?? 0;
      const open = b.open;
      const high = b.high;
      const low = b.low;
      const close = b.close;

      if (open === undefined || high === undefined || low === undefined || close === undefined) {
        continue;
      }

      cleaned.push({
        timestamp: Number(timestamp),
        open: Number(open),
        high: Number(high),
        low: Number(low),
        close: Number(close),
      });
    } catch {
      continue;
    }
  }

  cleaned.sort((a, b) => a.timestamp - b.timestamp);
  return cleaned;
}

/**
 * Find significant VBP levels from histogram.
 */
function findSignificantLevels(
  histogram: Array<{ priceLevel?: number; volume?: number }>,
  numLevels: number
): Array<{ priceLevel: number; volume: number }> {
  if (!histogram || histogram.length === 0) {
    return [];
  }

  const sorted = [...histogram]
    .filter((item) => typeof item.volume === 'number')
    .sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0));

  return sorted.slice(0, numLevels).map((item) => ({
    priceLevel: item.priceLevel ?? 0,
    volume: item.volume ?? 0,
  }));
}

/**
 * Fetch weekly bars for VBP calculation.
 */
async function fetchWeeklyBarsForVbp(
  symbol: AssetSymbol,
  apiKey: string,
  lookbackYears: number
): Promise<OHLCVBar[]> {
  const lookbackDays = lookbackYears * 365;

  const fetchParams = {
    multiplier: 1,
    timespan: 'week' as const,
    lookback_period: `${lookbackDays} days`,
    adjusted: true,
    sort: 'asc' as const,
    limit: 50000,
  };

  const [bars] = await fetchBars(symbol, apiKey, fetchParams);
  return bars;
}

/**
 * Calculate VBP levels from weekly bars.
 */
function calculateVbpLevelsFromWeekly(
  weeklyBars: OHLCVBar[],
  bins: number,
  numLevels: number,
  useDollarWeighted: boolean = false,
  useCloseOnly: boolean = false
): number[] {
  if (!weeklyBars || weeklyBars.length < MIN_BARS_REQUIRED) {
    return [];
  }

  const vbpResult = calculateVbp(weeklyBars, bins, useDollarWeighted, useCloseOnly);

  if (vbpResult.pointOfControl === null) {
    return [];
  }

  const significantLevels = findSignificantLevels(vbpResult.histogram, numLevels);

  return significantLevels
    .map((level) => level.priceLevel)
    .filter((price) => price > 0);
}

/**
 * Calculate overlay (SMA or EMA).
 */
function calculateOverlay(
  closes: number[],
  period: number,
  maType: string
): Array<number | null> {
  if (!closes || period <= 1) {
    return [];
  }

  if (maType === 'SMA') {
    const result = calculateSma(closes, period);
    return result.sma || [];
  } else if (maType === 'EMA') {
    const result = calculateEma(closes, period);
    return result.ema || [];
  }

  return [];
}

/**
 * Enhanced OHLCV plot node with SMA/EMA overlays and VBP level calculation.
 *
 * NOTE: This TypeScript version returns computed chart data for frontend rendering
 * instead of generating images server-side like the Python/matplotlib version.
 *
 * - Inputs: either 'ohlcv_bundle' or 'ohlcv'
 * - Calculates VBP levels by fetching weekly bars from Polygon API
 * - Optional: overlay1, overlay2 (automatically calculated SMA/EMA from OHLCV data)
 * - Output: 'chart_data' -> structured data for frontend charting
 */
export class OHLCVPlotEnhanced extends Node {
  static definition: NodeDefinition = {
    inputs: [port('ohlcv_bundle', 'OHLCVBundle', { optional: true })],
    outputs: [port('chart_data', 'ConfigDict')],
    category: NodeCategory.MARKET,
    requiredCredentials: ['POLYGON_API_KEY'],
    ui: {
      outputDisplay: {
        type: 'chart-preview',
        bind: 'chart_data',
        options: {
          chartType: 'candlestick',
          modalEnabled: true,
          symbolSelector: true,
        },
      },
    },
    params: [
      { name: 'max_symbols', type: 'integer', default: 12, min: 1, max: 64, step: 4 },
      { name: 'lookback_bars', type: 'number', default: 60, min: 10, max: 5000, step: 10 },
      { name: 'overlay1_type', type: 'combo', default: 'SMA', options: ['SMA', 'EMA'] },
      { name: 'overlay1_period', type: 'number', default: 20, min: 2, max: 200, step: 1 },
      { name: 'overlay2_type', type: 'combo', default: 'SMA', options: ['SMA', 'EMA'] },
      { name: 'overlay2_period', type: 'number', default: 50, min: 2, max: 200, step: 1 },
      { name: 'show_vbp_levels', type: 'combo', default: true, options: [true, false] },
      { name: 'vbp_bins', type: 'number', default: 50, min: 10, max: 200, step: 5 },
      { name: 'vbp_num_levels', type: 'number', default: 5, min: 1, max: 20, step: 1 },
      { name: 'vbp_lookback_years', type: 'number', default: 2, min: 1, max: 10, step: 1 },
      { name: 'vbp_use_dollar_weighted', type: 'combo', default: false, options: [true, false] },
      { name: 'vbp_use_close_only', type: 'combo', default: false, options: [true, false] },
      { name: 'vbp_style', type: 'combo', default: 'dashed', options: ['solid', 'dashed', 'dotted'] },
    ],
  };

  private getIntParam(key: string, defaultValue: number): number {
    const raw = this.params[key];
    if (typeof raw === 'number') {
      return Math.floor(raw);
    }
    return defaultValue;
  }

  private getBoolParam(key: string, defaultValue: boolean): boolean {
    const raw = this.params[key];
    return raw !== undefined ? Boolean(raw) : defaultValue;
  }

  protected async run(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    let bundle = inputs.ohlcv_bundle as Map<string, OHLCVBar[]> | undefined;
    const singleBundle = inputs.ohlcv as Map<string, OHLCVBar[]> | undefined;

    // Merge both inputs if both provided
    if (bundle && singleBundle) {
      bundle = new Map([...bundle, ...singleBundle]);
    } else if (singleBundle) {
      bundle = singleBundle;
    }

    if (!bundle || bundle.size === 0) {
      throw new Error("Provide either 'ohlcv_bundle' or 'ohlcv'");
    }

    const lookbackRaw = this.params.lookback_bars;
    let lookback: number | null = null;
    if (typeof lookbackRaw === 'number') {
      lookback = Math.floor(lookbackRaw);
    }

    // Prepare overlay configurations
    const overlayConfigs: Array<{ period: number; type: string }> = [];
    for (let i = 1; i <= 2; i++) {
      const periodRaw = this.params[`overlay${i}_period`];
      const typeRaw = this.params[`overlay${i}_type`];

      if (typeof periodRaw === 'number' && typeof typeRaw === 'string') {
        overlayConfigs.push({ period: Math.floor(periodRaw), type: typeRaw });
      }
    }

    // VBP parameters
    let showVbp = this.getBoolParam('show_vbp_levels', true);
    const vbpBins = this.getIntParam('vbp_bins', 50);
    const vbpNumLevels = this.getIntParam('vbp_num_levels', 5);
    const vbpLookbackYears = this.getIntParam('vbp_lookback_years', 2);
    const vbpUseDollarWeighted = this.getBoolParam('vbp_use_dollar_weighted', false);
    const vbpUseCloseOnly = this.getBoolParam('vbp_use_close_only', false);
    const vbpColor = DEFAULT_VBP_COLOR;
    const vbpStyle = String(this.params.vbp_style || 'dashed');

    // Get API key for fetching weekly bars
    let apiKey: string | undefined;
    if (showVbp) {
      apiKey = this.credentials.get('POLYGON_API_KEY') ?? undefined;
      if (!apiKey) {
        showVbp = false;
      }
    }

    const chartData: Record<string, ChartDataOutput> = {};

    // Limit symbols
    const maxSyms = this.getIntParam('max_symbols', 12);
    const entries = Array.from(bundle.entries()).slice(0, maxSyms);

    for (const [symbolKey, bars] of entries) {
      let vbpLevels: number[] = [];

      // Parse symbol if possible (symbolKey might be string representation)
      if (showVbp && apiKey) {
        try {
          // Try to reconstruct AssetSymbol from key
          // Format is typically "TICKER" or "TICKER:QUOTE"
          const assetSymbol = new AssetSymbol(symbolKey, AssetClass.STOCKS);
          const weeklyBars = await fetchWeeklyBarsForVbp(assetSymbol, apiKey, vbpLookbackYears);
          if (weeklyBars.length > 0) {
            vbpLevels = calculateVbpLevelsFromWeekly(
              weeklyBars,
              vbpBins,
              vbpNumLevels,
              vbpUseDollarWeighted,
              vbpUseCloseOnly
            );
          }
        } catch (error) {
          console.warn(`Failed to fetch weekly bars for VBP calculation for ${symbolKey}: ${error}`);
        }
      }

      // Normalize and trim bars for display
      let norm = normalizeBars(bars);
      if (lookback !== null && lookback > 0 && norm.length > lookback) {
        norm = norm.slice(-lookback);
      }

      if (norm.length < MIN_BARS_REQUIRED) {
        continue;
      }

      // Calculate overlays
      const closePrices = norm.map((bar) => bar.close);
      const overlays: ChartDataOutput['overlays'] = [];
      const colors = ['#2196F3', '#FF9800'];

      for (let i = 0; i < overlayConfigs.length; i++) {
        const config = overlayConfigs[i];
        if (!config) continue;
        const overlayValues = calculateOverlay(closePrices, config.period, config.type);
        overlays.push({
          type: config.type,
          period: config.period,
          values: overlayValues,
          color: colors[i % colors.length] ?? '#888888',
          label: `${config.type} ${config.period}`,
        });
      }

      chartData[symbolKey] = {
        symbol: symbolKey,
        assetClass: AssetClass.STOCKS,
        bars: norm,
        overlays,
        vbpLevels: showVbp ? vbpLevels : [],
        vbpColor,
        vbpStyle,
      };
    }

    return { chart_data: chartData };
  }
}
