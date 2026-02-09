// src/services/indicator-calculators/atr-calculator.ts
// Translated from: services/indicator_calculators/atr_calculator.py

import { calculateEma } from './ema-calculator';
import { calculateSma } from './sma-calculator';

function calculateWilderMa(
  data: (number | null)[],
  period: number
): (number | null)[] {
  if (period <= 0 || data.length < period) {
    return new Array(data.length).fill(null);
  }

  const results: (number | null)[] = new Array(data.length).fill(null);

  let firstValidIndex = -1;
  for (let i = period - 1; i < data.length; i++) {
    const window = data.slice(i - period + 1, i + 1);
    const validValues = window.filter((v): v is number => v !== null);
    if (validValues.length === period) {
      firstValidIndex = i;
      break;
    }
  }

  if (firstValidIndex === -1) {
    return results;
  }

  const seedWindow = data.slice(firstValidIndex - period + 1, firstValidIndex + 1);
  const seedSum = (seedWindow as number[]).reduce((acc, v) => acc + v, 0);
  results[firstValidIndex] = seedSum / period;

  for (let i = firstValidIndex + 1; i < data.length; i++) {
    const prevMa = results[i - 1];
    const currentValue = data[i];

    if (currentValue !== null) {
      if (prevMa !== null) {
        results[i] = (prevMa * (period - 1) + currentValue) / period;
      } else {
        const window = data.slice(i - period + 1, i + 1);
        const validValues = window.filter((v): v is number => v !== null);
        if (validValues.length === period) {
          results[i] = validValues.reduce((acc, v) => acc + v, 0) / period;
        } else {
          results[i] = null;
        }
      }
    } else {
      results[i] = prevMa !== null ? prevMa : null;
    }
  }

  return results;
}

export interface AtrResult {
  atr: (number | null)[];
}

/**
 * Calculate True Range for a single point.
 *
 * @param high - Current high price
 * @param low - Current low price
 * @param prevClose - Previous close price (null for first point or if previous close is null)
 * @returns True Range value or null
 */
export function calculateTr(
  high: number | null,
  low: number | null,
  prevClose: number | null
): number | null {
  // If no previous point, or current values are null, or previous close is null
  if (high === null || low === null || prevClose === null) {
    // For the very first point, TR is just High - Low
    if (high !== null && low !== null) {
      return high - low;
    }
    return null;
  }

  const highLow = high - low;
  const highClose = Math.abs(high - prevClose);
  const lowClose = Math.abs(low - prevClose);

  return Math.max(highLow, highClose, lowClose);
}

/**
 * Calculate ATR (Average True Range) indicator.
 *
 * @param highs - List of high prices (can contain null values)
 * @param lows - List of low prices (can contain null values)
 * @param closes - List of close prices (can contain null values)
 * @param length - Period for ATR calculation
 * @param smoothing - Smoothing method - "RMA" (default), "SMA", or "EMA"
 * @returns Dictionary with 'atr' as a list of calculated values for each row
 */
export function calculateAtr(
  highs: readonly (number | null)[],
  lows: readonly (number | null)[],
  closes: readonly (number | null)[],
  length: number,
  smoothing: 'RMA' | 'SMA' | 'EMA' = 'RMA'
): AtrResult {
  const dataLength = highs.length;

  if (length <= 0 || dataLength === 0) {
    return { atr: new Array(dataLength).fill(null) };
  }

  if (lows.length !== dataLength || closes.length !== dataLength) {
    return { atr: new Array(dataLength).fill(null) };
  }

  // Calculate True Range values
  const trValues: (number | null)[] = [];

  for (let i = 0; i < dataLength; i++) {
    const currentHigh = highs[i];
    const currentLow = lows[i];
    const prevClose = i > 0 ? closes[i - 1] : null;
    const trVal = calculateTr(currentHigh, currentLow, prevClose);
    trValues.push(trVal);
  }

  // Calculate ATR using selected smoothing method
  let atrValues: (number | null)[];

  if (smoothing === 'SMA') {
    const smaResult = calculateSma(trValues, length);
    atrValues = smaResult.sma;
  } else if (smoothing === 'EMA') {
    const emaResult = calculateEma(trValues, length);
    atrValues = emaResult.ema;
  } else {
    // Default to RMA
    atrValues = calculateWilderMa(trValues, length);
  }

  return { atr: atrValues };
}
