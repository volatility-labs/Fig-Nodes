// This node prepares OHLCV data for frontend chart rendering.
// Instead of generating images server-side, it outputs structured chart data
// that the frontend can render with Lightweight Charts or similar.

import { Node, NodeCategory, port, type NodeDefinition } from '@fig-node/core';
import type { OHLCVBar } from '../types';
import { calculateSma } from '../calculators/sma-calculator';
import { calculateEma } from '../calculators/ema-calculator';

// ============ Chart Data Types ============

export interface CandlestickData {
  time: number; // Unix timestamp in seconds (for Lightweight Charts)
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface LineSeriesData {
  time: number;
  value: number;
}

export interface OverlayConfig {
  id: string;
  label: string;
  type: 'SMA' | 'EMA';
  period: number;
  color: string;
  data: LineSeriesData[];
}

export interface HorizontalLine {
  price: number;
  color: string;
  lineStyle: 'solid' | 'dashed' | 'dotted';
  label?: string;
}

export interface ChartConfig {
  symbol: string;
  assetClass: string;
  candlesticks: CandlestickData[];
  overlays: OverlayConfig[];
  horizontalLines: HorizontalLine[];
  metadata: {
    barCount: number;
    startTime: number;
    endTime: number;
    priceRange: { min: number; max: number };
  };
}

export interface OHLCVChartOutput {
  charts: Record<string, ChartConfig>;
}

// ============ Helper Functions ============

function normalizeBars(bars: OHLCVBar[]): CandlestickData[] {
  const cleaned: CandlestickData[] = [];

  for (const bar of bars ?? []) {
    try {
      // Support both full names and abbreviations
      // Cast through unknown to handle potential abbreviated field names
      const barAny = bar as unknown as Record<string, unknown>;
      const timestampRaw = bar.timestamp ?? barAny.t ?? 0;
      const openRaw = bar.open ?? barAny.o;
      const highRaw = bar.high ?? barAny.h;
      const lowRaw = bar.low ?? barAny.l;
      const closeRaw = bar.close ?? barAny.c;
      const volumeRaw = bar.volume ?? barAny.v;

      if (openRaw == null || highRaw == null || lowRaw == null || closeRaw == null) {
        continue;
      }

      const timestamp = Number(timestampRaw);
      const open = Number(openRaw);
      const high = Number(highRaw);
      const low = Number(lowRaw);
      const close = Number(closeRaw);
      const volume = volumeRaw != null ? Number(volumeRaw) : undefined;

      if (isNaN(timestamp) || isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
        continue;
      }

      // Convert milliseconds to seconds for Lightweight Charts
      const timeInSeconds = timestamp > 1e12 ? Math.floor(timestamp / 1000) : timestamp;

      cleaned.push({
        time: timeInSeconds,
        open,
        high,
        low,
        close,
        volume,
      });
    } catch {
      continue;
    }
  }

  // Sort by time ascending
  cleaned.sort((a, b) => a.time - b.time);
  return cleaned;
}

function calculateOverlay(
  candlesticks: CandlestickData[],
  period: number,
  maType: 'SMA' | 'EMA'
): LineSeriesData[] {
  if (!candlesticks.length || period <= 1) {
    return [];
  }

  const closes = candlesticks.map((c) => c.close);
  let values: (number | null)[] = [];

  if (maType === 'SMA') {
    const result = calculateSma(closes, period);
    values = result.sma ?? [];
  } else if (maType === 'EMA') {
    const result = calculateEma(closes, period);
    values = result.ema ?? [];
  }

  // Map values to time series, filtering out nulls
  const series: LineSeriesData[] = [];
  for (let i = 0; i < candlesticks.length && i < values.length; i++) {
    const val = values[i];
    const candle = candlesticks[i];
    if (val != null && !isNaN(val) && candle) {
      series.push({
        time: candle.time,
        value: val,
      });
    }
  }

  return series;
}

// ============ Node Implementation ============

/**
 * Prepares OHLCV data for frontend chart rendering.
 *
 * Instead of generating server-side images (like Python matplotlib),
 * this node outputs structured chart configuration data that the
 * frontend can render with Lightweight Charts or similar libraries.
 *
 * Inputs:
 * - ohlcv_bundle: Dict mapping symbol keys to OHLCV bar arrays
 *
 * Outputs:
 * - charts: Dict mapping symbol strings to ChartConfig objects
 */
export class OHLCVChart extends Node {
  static definition: NodeDefinition = {
    inputs: {
      ohlcv_bundle: port('OHLCVBundle'),
    },
    outputs: {
      charts: port('ConfigDict'),
    },
    category: NodeCategory.MARKET,
    ui: {
      outputDisplay: {
        type: 'chart-preview',
        bind: 'charts',
        options: {
          chartType: 'candlestick',
          modalEnabled: true,
          symbolSelector: true,
        },
      },
    },
    params: [
      {
        name: 'max_symbols',
        type: 'integer',
        default: 12,
        min: 1,
        max: 64,
        step: 4,
        description: 'Maximum number of symbols to process',
      },
      {
        name: 'lookback_bars',
        type: 'number',
        default: 60,
        min: 10,
        max: 5000,
        step: 10,
        description: 'Number of bars to include (from most recent)',
      },
      {
        name: 'overlay1_enabled',
        type: 'combo',
        default: true,
        options: [true, false],
      },
      {
        name: 'overlay1_type',
        type: 'combo',
        default: 'SMA',
        options: ['SMA', 'EMA'],
      },
      {
        name: 'overlay1_period',
        type: 'number',
        default: 20,
        min: 2,
        max: 200,
        step: 1,
      },
      {
        name: 'overlay1_color',
        type: 'text',
        default: '#2196F3',
      },
      {
        name: 'overlay2_enabled',
        type: 'combo',
        default: true,
        options: [true, false],
      },
      {
        name: 'overlay2_type',
        type: 'combo',
        default: 'SMA',
        options: ['SMA', 'EMA'],
      },
      {
        name: 'overlay2_period',
        type: 'number',
        default: 50,
        min: 2,
        max: 200,
        step: 1,
      },
      {
        name: 'overlay2_color',
        type: 'text',
        default: '#FF9800',
      },
    ],
  };

  private getIntParam(key: string, defaultVal: number): number {
    const raw = this.params[key] ?? defaultVal;
    if (typeof raw === 'number') return Math.floor(raw);
    if (typeof raw === 'string') {
      const parsed = parseInt(raw, 10);
      return isNaN(parsed) ? defaultVal : parsed;
    }
    return defaultVal;
  }

  private getBoolParam(key: string, defaultVal: boolean): boolean {
    const raw = this.params[key];
    if (raw === undefined || raw === null) return defaultVal;
    if (typeof raw === 'boolean') return raw;
    if (typeof raw === 'string') return raw.toLowerCase() === 'true';
    return Boolean(raw);
  }

  private getStringParam(key: string, defaultVal: string): string {
    const raw = this.params[key] ?? defaultVal;
    return String(raw);
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    // Get OHLCV bundle - can be Map or plain object
    let bundle: Map<string, OHLCVBar[]> | Record<string, OHLCVBar[]> | null = null;

    const ohlcvBundle = inputs.ohlcv_bundle;
    if (ohlcvBundle instanceof Map) {
      bundle = ohlcvBundle;
    } else if (ohlcvBundle && typeof ohlcvBundle === 'object') {
      bundle = ohlcvBundle as Record<string, OHLCVBar[]>;
    }

    if (!bundle) {
      return { charts: {} };
    }

    // Get parameters
    const maxSymbols = this.getIntParam('max_symbols', 12);
    const lookbackBars = this.getIntParam('lookback_bars', 60);

    // Build overlay configurations
    const overlayConfigs: Array<{
      enabled: boolean;
      type: 'SMA' | 'EMA';
      period: number;
      color: string;
    }> = [];

    for (const i of [1, 2]) {
      const enabled = this.getBoolParam(`overlay${i}_enabled`, true);
      const type = this.getStringParam(`overlay${i}_type`, 'SMA') as 'SMA' | 'EMA';
      const period = this.getIntParam(`overlay${i}_period`, i === 1 ? 20 : 50);
      const color = this.getStringParam(`overlay${i}_color`, i === 1 ? '#2196F3' : '#FF9800');

      overlayConfigs.push({ enabled, type, period, color });
    }

    // Process each symbol
    const charts: Record<string, ChartConfig> = {};
    const entries = bundle instanceof Map ? Array.from(bundle.entries()) : Object.entries(bundle);
    const limitedEntries = entries.slice(0, maxSymbols);

    for (const [symbolKey, bars] of limitedEntries) {
      // Normalize bars
      let candlesticks = normalizeBars(bars);

      // Apply lookback
      if (lookbackBars > 0 && candlesticks.length > lookbackBars) {
        candlesticks = candlesticks.slice(-lookbackBars);
      }

      if (candlesticks.length === 0) {
        continue;
      }

      // Calculate overlays
      const overlays: OverlayConfig[] = [];
      for (let i = 0; i < overlayConfigs.length; i++) {
        const config = overlayConfigs[i];
        if (!config) continue;
        if (config.enabled && config.period > 1) {
          const data = calculateOverlay(candlesticks, config.period, config.type);
          if (data.length > 0) {
            overlays.push({
              id: `overlay_${i + 1}`,
              label: `${config.type} ${config.period}`,
              type: config.type,
              period: config.period,
              color: config.color,
              data,
            });
          }
        }
      }

      // Calculate metadata
      const prices = candlesticks.flatMap((c) => [c.high, c.low]);
      const priceMin = Math.min(...prices);
      const priceMax = Math.max(...prices);

      // Determine asset class from symbol if possible
      let assetClass = 'UNKNOWN';
      const symbolStr = String(symbolKey);
      if (symbolStr.includes('USDT') || symbolStr.includes('BTC') || symbolStr.includes('ETH')) {
        assetClass = 'CRYPTO';
      } else {
        assetClass = 'STOCKS';
      }

      // Get first and last candle (we already checked candlesticks.length > 0)
      const firstCandle = candlesticks[0]!;
      const lastCandle = candlesticks[candlesticks.length - 1]!;

      const chartConfig: ChartConfig = {
        symbol: symbolStr,
        assetClass,
        candlesticks,
        overlays,
        horizontalLines: [], // VBP levels could be added here
        metadata: {
          barCount: candlesticks.length,
          startTime: firstCandle.time,
          endTime: lastCandle.time,
          priceRange: { min: priceMin, max: priceMax },
        },
      };

      charts[String(symbolKey)] = chartConfig;
    }

    return { charts };
  }
}
