// src/services/indicator-calculators/lod-calculator.ts
// Translated from: services/indicator_calculators/lod_calculator.py

import { calculateAtr } from './atr-calculator';

export interface LodResult {
  lod_distance_pct: (number | null)[];
  current_price: (number | null)[];
  low_of_day: (number | null)[];
  atr: (number | null)[];
}

/**
 * Calculate LoD (Low of Day Distance) indicator.
 *
 * LoD Distance measures the distance of current price from the low of the day
 * as a percentage of ATR (Average True Range).
 *
 * Formula: LoD Distance % = ((current_price - low_of_day) / ATR) * 100
 *
 * @param highs - List of high prices (can contain null values)
 * @param lows - List of low prices (can contain null values)
 * @param closes - List of close prices (can contain null values)
 * @param atrWindow - Period for ATR calculation (default: 14)
 * @returns Dictionary with 'lod_distance_pct', 'current_price', 'low_of_day', and 'atr'
 *
 * Reference: https://www.tradingview.com/script/uloAa2EI-Swing-Data-ADR-RVol-PVol-Float-Avg-Vol/
 *
 * Example:
 *   Current price (A) = $24.49
 *   Low Price (B) = $22.16
 *   Difference (A) - (B) = $2.33
 *   ATR = $2.25
 *   LoD dist = $2.33 / $2.25 = 103.55% (round up to nearest whole number = 104%)
 */
export function calculateLod(
  highs: readonly (number | null)[],
  lows: readonly (number | null)[],
  closes: readonly (number | null)[],
  atrWindow: number = 14
): LodResult {
  const dataLength = highs.length;

  if (atrWindow <= 0 || dataLength === 0) {
    return {
      lod_distance_pct: new Array(dataLength).fill(null),
      current_price: new Array(dataLength).fill(null),
      low_of_day: new Array(dataLength).fill(null),
      atr: new Array(dataLength).fill(null),
    };
  }

  if (lows.length !== dataLength || closes.length !== dataLength) {
    return {
      lod_distance_pct: new Array(dataLength).fill(null),
      current_price: new Array(dataLength).fill(null),
      low_of_day: new Array(dataLength).fill(null),
      atr: new Array(dataLength).fill(null),
    };
  }

  // Calculate ATR using Wilder's smoothing (RMA)
  const atrResult = calculateAtr(highs, lows, closes, atrWindow);
  const atrValues = atrResult.atr;

  if (!atrValues || atrValues.length !== dataLength) {
    return {
      lod_distance_pct: new Array(dataLength).fill(null),
      current_price: new Array(dataLength).fill(null),
      low_of_day: new Array(dataLength).fill(null),
      atr: new Array(dataLength).fill(null),
    };
  }

  // Calculate LoD Distance for each point
  const lodDistancePct: (number | null)[] = [];
  const currentPrices: (number | null)[] = [];
  const lowOfDays: (number | null)[] = [];

  for (let i = 0; i < dataLength; i++) {
    const currentPrice = closes[i];
    const lowOfDay = lows[i];
    const atr = atrValues[i];

    currentPrices.push(currentPrice);
    lowOfDays.push(lowOfDay);

    // Check for invalid values
    if (
      currentPrice === null ||
      lowOfDay === null ||
      atr === null ||
      atr <= 0
    ) {
      lodDistancePct.push(null);
      continue;
    }

    // Calculate LoD Distance as percentage of ATR
    // LoD Distance % = ((current_price - low_of_day) / ATR) * 100
    const lodDistance = ((currentPrice - lowOfDay) / atr) * 100;

    // Ensure non-negative distance
    lodDistancePct.push(Math.max(0.0, lodDistance));
  }

  return {
    lod_distance_pct: lodDistancePct,
    current_price: currentPrices,
    low_of_day: lowOfDays,
    atr: atrValues,
  };
}
