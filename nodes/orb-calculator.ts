// src/services/indicator-calculators/orb-calculator.ts
// Translated from: services/indicator_calculators/orb_calculator.py

import { AssetClass, type AssetSymbol, type OHLCVBar } from './types';

export interface OrbResult {
  rel_vol: number | null;
  direction: string | null;
  or_high: number | null;
  or_low: number | null;
  error?: string;
}

/**
 * Get date string in YYYY-MM-DD format for ET timezone.
 */
function getEtDateString(timestampMs: number): string {
  const date = new Date(timestampMs);
  const etFormatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  return etFormatter.format(date);
}

/**
 * Get current date in ET timezone.
 */
function getTodayEtDate(): string {
  const now = new Date();
  const etFormatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  return etFormatter.format(now);
}

/**
 * Check if a bar timestamp falls within the opening range.
 */
function isInOpeningRange(
  barTimestampMs: number,
  openTimeMs: number,
  openRangeEndMs: number
): boolean {
  return barTimestampMs >= openTimeMs && barTimestampMs < openRangeEndMs;
}

/**
 * Create market open time for a given date (9:30 AM ET for stocks).
 */
function createMarketOpenTimeMs(dateStr: string, hour: number = 9, minute: number = 30): number {
  // Parse the date string (YYYY-MM-DD)
  const [year, month, day] = dateStr.split('-').map(Number);

  // Create date at the specified time in local timezone, then adjust for ET
  // This is a simplified approach - in production you might want a proper timezone library
  const date = new Date(year, month - 1, day, hour, minute, 0, 0);

  // Get the offset for Eastern Time (accounting for DST)
  const etOffset = getEtOffset(date);

  // Adjust to get UTC time that represents the ET time
  return date.getTime() + (date.getTimezoneOffset() * 60000) + (etOffset * 3600000);
}

/**
 * Get Eastern Time offset from UTC in hours (accounting for DST).
 */
function getEtOffset(date: Date): number {
  // ET is UTC-5 (EST) or UTC-4 (EDT)
  const jan = new Date(date.getFullYear(), 0, 1);
  const jul = new Date(date.getFullYear(), 6, 1);

  // Determine if we're in DST based on the date
  const isDst = date.getTimezoneOffset() < Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());

  return isDst ? -4 : -5;
}

interface BarData {
  timestamp: number; // milliseconds
  dateStr: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Calculate ORB (Opening Range Breakout) indicator including relative volume and direction.
 *
 * This implementation extracts opening range data from 5-minute bars and calculates:
 * 1. Relative Volume: Current opening range volume vs average of previous periods
 * 2. Direction: Bullish, bearish, or doji based on opening range price movement
 *
 * @param bars - List of 5-minute OHLCV bars (aggregated bars from Polygon)
 * @param symbol - Asset symbol (used to determine opening range time based on asset class)
 * @param orMinutes - Opening range period in minutes (default: 5)
 * @param avgPeriod - Period for calculating average volume (default: 14 days)
 * @param nowFunc - Optional function to use instead of Date.now for testing
 * @returns Dictionary with 'rel_vol', 'direction', 'or_high', and 'or_low'
 *
 * Reference Paper Implementation:
 *   The paper uses:
 *   - Relative Volume = (Volume in first n minutes) / (Avg of last 14 days) * 100
 */
export function calculateOrb(
  bars: readonly OHLCVBar[],
  symbol: AssetSymbol,
  orMinutes: number = 5,
  avgPeriod: number = 14,
  nowFunc: (() => number) | null = null
): OrbResult {
  if (!bars || bars.length === 0) {
    return {
      rel_vol: null,
      direction: null,
      or_high: null,
      or_low: null,
      error: 'No bars provided',
    };
  }

  // Convert bars to internal format with ET date strings
  const barData: BarData[] = bars.map((bar) => ({
    timestamp: bar.timestamp,
    dateStr: getEtDateString(bar.timestamp),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume ?? 0,
  }));

  // Get today's date in ET
  const todayDate = nowFunc ? getEtDateString(nowFunc()) : getTodayEtDate();

  // Group bars by date
  const dailyGroups: Map<string, BarData[]> = new Map();
  for (const bar of barData) {
    if (!dailyGroups.has(bar.dateStr)) {
      dailyGroups.set(bar.dateStr, []);
    }
    dailyGroups.get(bar.dateStr)!.push(bar);
  }

  // Calculate opening range volumes, directions, highs, and lows for each day
  const orVolumes: Map<string, number> = new Map();
  const orDirections: Map<string, string> = new Map();
  const orHighs: Map<string, number> = new Map();
  const orLows: Map<string, number> = new Map();

  for (const [dateKey, dayBars] of dailyGroups) {
    // Sort bars by timestamp to ensure chronological order
    const dayBarsSorted = [...dayBars].sort((a, b) => a.timestamp - b.timestamp);

    // Determine opening range time based on asset class
    let openTimeMs: number;
    if (symbol.assetClass === AssetClass.CRYPTO) {
      // For crypto, use UTC midnight (00:00:00)
      const [year, month, day] = dateKey.split('-').map(Number);
      openTimeMs = Date.UTC(year, month - 1, day, 0, 0, 0);
    } else {
      // For stocks, use 9:30 AM Eastern as opening range
      openTimeMs = createMarketOpenTimeMs(dateKey, 9, 30);
    }

    // Look for bars within the opening range (uses orMinutes parameter)
    const openRangeEndMs = openTimeMs + orMinutes * 60 * 1000;

    // Find bars that start within the opening range
    const orCandidates = dayBarsSorted.filter((bar) =>
      isInOpeningRange(bar.timestamp, openTimeMs, openRangeEndMs)
    );

    if (orCandidates.length === 0) {
      continue;
    }

    // Pick the earliest bar in the opening range for volume and direction
    const orBar = orCandidates[0];

    // Calculate opening range metrics from earliest bar
    const orVolume = orBar.volume;
    const orOpen = orBar.open;
    const orClose = orBar.close;

    // Calculate high/low across all opening range bars (handles orMinutes > 5)
    const orHigh = Math.max(...orCandidates.map((b) => b.high));
    const orLow = Math.min(...orCandidates.map((b) => b.low));

    // Determine direction
    let direction: string;
    if (orClose > orOpen) {
      direction = 'bullish';
    } else if (orClose < orOpen) {
      direction = 'bearish';
    } else {
      direction = 'doji';
    }

    orVolumes.set(dateKey, orVolume);
    orDirections.set(dateKey, direction);
    orHighs.set(dateKey, orHigh);
    orLows.set(dateKey, orLow);
  }

  // Calculate relative volume
  const sortedDates = [...orVolumes.keys()].sort();
  if (sortedDates.length < 1) {
    return {
      rel_vol: null,
      direction: null,
      or_high: null,
      or_low: null,
      error: 'Insufficient days',
    };
  }

  // Determine target date (today or last trading day)
  let targetDate: string;
  if (symbol.assetClass === AssetClass.CRYPTO) {
    // For crypto, use previous day
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    targetDate = getEtDateString(yesterday.getTime());
  } else {
    // For stocks, use today if available, otherwise last trading day
    if (sortedDates.includes(todayDate)) {
      targetDate = todayDate;
    } else {
      targetDate = sortedDates[sortedDates.length - 1];
    }
  }

  // Calculate average volume from past periods (excluding target date)
  const targetVolumeDate = orVolumes.has(targetDate)
    ? targetDate
    : sortedDates[sortedDates.length - 1];

  let pastVolumes: number[];
  if (sortedDates.length > avgPeriod) {
    pastVolumes = sortedDates
      .slice(-avgPeriod - 1, -1)
      .map((d) => orVolumes.get(d)!)
      .filter((v) => v !== undefined);
  } else {
    pastVolumes = sortedDates
      .slice(0, -1)
      .map((d) => orVolumes.get(d)!)
      .filter((v) => v !== undefined);
  }

  const avgVol =
    pastVolumes.length > 0
      ? pastVolumes.reduce((a, b) => a + b, 0) / pastVolumes.length
      : 0.0;

  const currentVol = orVolumes.get(targetVolumeDate) ?? 0.0;

  let relVol: number;
  if (avgVol > 0) {
    relVol = (currentVol / avgVol) * 100;
  } else if (currentVol > 0) {
    relVol = Infinity;
  } else {
    relVol = 0.0;
  }

  // Get direction, high, and low for target date
  const direction = orDirections.get(targetDate) ?? 'doji';
  const orHigh = orHighs.get(targetDate) ?? null;
  const orLow = orLows.get(targetDate) ?? null;

  return {
    rel_vol: relVol,
    direction,
    or_high: orHigh,
    or_low: orLow,
  };
}
