// src/services/indicator-calculators/atrx-calculator.ts
// Translated from: services/indicator_calculators/atrx_calculator.py

import { calculateAtr, calculateTr } from './atr-calculator';
import { calculateSma } from './sma-calculator';

export interface AtrxResult {
  atrx: (number | null)[];
}

/**
 * Calculate ATRX indicator following TradingView methodology:
 * A = ATR% = ATR / Last Done Price
 * B = % Gain From 50-MA = (Price - SMA50) / SMA50
 * ATRX = B / A = (% Gain From 50-MA) / ATR%
 *
 * @param highs - List of high prices (can contain null values)
 * @param lows - List of low prices (can contain null values)
 * @param closes - List of close prices (can contain null values)
 * @param prices - List of prices to use for calculation (can contain null values)
 * @param length - Period for ATR calculation (default: 14)
 * @param maLength - Period for SMA calculation (default: 50)
 * @param smoothing - Smoothing method for ATR - "RMA" (default), "SMA", or "EMA"
 * @returns Dictionary with 'atrx' as a list of calculated values for each row
 *
 * Reference: https://www.tradingview.com/script/oimVgV7e-ATR-multiple-from-50-MA/
 */
export function calculateAtrx(
  highs: readonly (number | null)[],
  lows: readonly (number | null)[],
  closes: readonly (number | null)[],
  prices: readonly (number | null)[],
  length: number = 14,
  maLength: number = 50,
  smoothing: 'RMA' | 'SMA' | 'EMA' = 'RMA'
): AtrxResult {
  const dataLength = highs.length;
  if (length <= 0 || maLength <= 0) {
    return { atrx: new Array(dataLength).fill(null) };
  }

  if (
    lows.length !== dataLength ||
    closes.length !== dataLength ||
    prices.length !== dataLength
  ) {
    return { atrx: new Array(dataLength).fill(null) };
  }

  // Calculate ATR with specified smoothing
  const atrResult = calculateAtr(highs, lows, closes, length, smoothing);
  const atrValues = atrResult.atr;

  if (!atrValues || atrValues.length === 0) {
    return { atrx: new Array(dataLength).fill(null) };
  }

  // Calculate SMA
  const smaResult = calculateSma(prices, maLength);
  const smaValues = smaResult.sma;

  if (!smaValues || smaValues.length === 0) {
    return { atrx: new Array(dataLength).fill(null) };
  }

  // Calculate ATRX for each point
  const results: (number | null)[] = [];

  for (let i = 0; i < dataLength; i++) {
    // Need at least maLength points for SMA and length points for ATR
    if (i < Math.max(length, maLength) - 1) {
      results.push(null);
      continue;
    }

    const currentPrice = prices[i];
    const currentAtr = atrValues[i];
    const currentSma = smaValues[i];

    // Check for invalid values
    if (
      currentPrice === null ||
      currentAtr === null ||
      currentSma === null ||
      currentAtr === 0 ||
      currentSma === 0 ||
      currentPrice === 0
    ) {
      results.push(null);
      continue;
    }

    // Calculate ATR% = ATR / Last Done Price
    const atrPercent = currentAtr / currentPrice;

    // Calculate % Gain From 50-MA = (Price - SMA50) / SMA50
    const percentGainFrom50ma = (currentPrice - currentSma) / currentSma;

    // Calculate ATRX = (% Gain From 50-MA) / ATR%
    if (atrPercent === 0) {
      results.push(null);
    } else {
      const atrx = percentGainFrom50ma / atrPercent;
      results.push(atrx);
    }
  }

  return { atrx: results };
}

/**
 * Optimized ATRX calculation that only computes the last value.
 * Uses incremental sliding windows instead of full array calculations.
 *
 * This is faster than calculateAtrx() when only the last value is needed.
 *
 * @returns The last ATRX value or null if calculation is not possible.
 */
export function calculateAtrxLastValue(
  highs: readonly (number | null)[],
  lows: readonly (number | null)[],
  closes: readonly (number | null)[],
  prices: readonly (number | null)[],
  length: number = 14,
  maLength: number = 50,
  smoothing: 'RMA' | 'SMA' | 'EMA' = 'RMA'
): number | null {
  const dataLength = highs.length;
  if (length <= 0 || maLength <= 0) {
    return null;
  }

  if (
    lows.length !== dataLength ||
    closes.length !== dataLength ||
    prices.length !== dataLength
  ) {
    return null;
  }

  const minRequired = Math.max(length, maLength);
  if (dataLength < minRequired) {
    return null;
  }

  // Calculate TR values incrementally - only what we need for the last ATR
  const trValues: (number | null)[] = [];
  for (let i = 0; i < dataLength; i++) {
    const currentHigh = highs[i];
    const currentLow = lows[i];
    const prevClose = i > 0 ? closes[i - 1] : null;
    const trVal = calculateTr(currentHigh, currentLow, prevClose);
    trValues.push(trVal);
  }

  // Calculate last ATR value using incremental smoothing
  let lastAtr: number | null = null;

  if (smoothing === 'SMA') {
    // Get last 'length' valid TR values
    const trWindow = trValues
      .slice(-length)
      .filter((v): v is number => v !== null);
    if (trWindow.length === length) {
      lastAtr = trWindow.reduce((a, b) => a + b, 0) / length;
    }
  } else if (smoothing === 'EMA') {
    // EMA: Compute incrementally, only track what's needed for last value
    const k = 2 / (length + 1);
    let ema: number | null = null;
    let validCount = 0;

    // Find first valid window to initialize
    for (let i = length - 1; i < dataLength; i++) {
      const window = trValues.slice(i - length + 1, i + 1);
      const validValues = window.filter((v): v is number => v !== null);
      if (validValues.length === length) {
        ema = validValues.reduce((a, b) => a + b, 0) / length;
        validCount = i + 1;
        break;
      }
    }

    if (ema === null) {
      return null;
    }

    // Continue EMA calculation from initialization point
    let currentEma: number = ema;
    for (let i = validCount; i < dataLength; i++) {
      const trVal = trValues[i];
      if (trVal !== null) {
        currentEma = trVal * k + currentEma * (1 - k);
      }
    }

    lastAtr = currentEma;
  } else {
    // RMA (Wilder's Smoothing)
    let rma: number | null = null;
    let firstValidIndex = -1;

    // Find first valid window
    for (let i = length - 1; i < dataLength; i++) {
      const window = trValues.slice(i - length + 1, i + 1);
      const validValues = window.filter((v): v is number => v !== null);
      if (validValues.length === length) {
        firstValidIndex = i;
        const seedWindow = trValues.slice(i - length + 1, i + 1) as number[];
        rma = seedWindow.reduce((a, b) => a + b, 0) / length;
        break;
      }
    }

    if (rma === null) {
      return null;
    }

    // Continue RMA calculation incrementally
    let currentRma: number = rma;
    for (let i = firstValidIndex + 1; i < dataLength; i++) {
      const trVal = trValues[i];
      if (trVal !== null) {
        currentRma = (currentRma * (length - 1) + trVal) / length;
      }
    }

    lastAtr = currentRma;
  }

  if (lastAtr === null || lastAtr === 0) {
    return null;
  }

  const finalAtr: number = lastAtr;

  // Incremental SMA calculation for last value only
  // Use running sum for O(1) window management
  let smaSum = 0.0;
  const priceDeque: number[] = [];

  for (const price of prices) {
    if (price !== null) {
      // If deque is at max capacity, remove oldest value from sum
      if (priceDeque.length === maLength) {
        const oldest = priceDeque.shift()!;
        smaSum -= oldest;
      }

      priceDeque.push(price);
      smaSum += price;
    }
  }

  if (priceDeque.length < maLength) {
    return null;
  }

  const lastSma = smaSum / maLength;

  if (lastSma === 0) {
    return null;
  }

  const lastPrice = prices[prices.length - 1];
  if (lastPrice === null || lastPrice === 0) {
    return null;
  }

  // Calculate ATRX from last values
  const atrPercent = finalAtr / lastPrice;
  if (atrPercent === 0) {
    return null;
  }

  const percentGainFrom50ma = (lastPrice - lastSma) / lastSma;
  const atrx = percentGainFrom50ma / atrPercent;

  return atrx;
}
