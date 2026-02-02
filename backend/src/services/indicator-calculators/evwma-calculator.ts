// src/services/indicator-calculators/evwma-calculator.ts
// Translated from: services/indicator_calculators/evwma_calculator.py

import type { OHLCVBar } from '../../core/types';

export interface EvwmaResult {
  evwma: (number | null)[];
}

/**
 * Calculate EVWMA (Exponential Volume Weighted Moving Average).
 *
 * EVWMA combines volume-weighted price with exponential smoothing:
 * 1. Calculate typical price (HLC/3)
 * 2. Calculate volume-weighted price (typical_price * volume)
 * 3. Use either cumulative volume or rolling window volume
 * 4. Calculate VWMA = volume_weighted_price_sum / volume_sum
 * 5. Apply exponential smoothing with alpha = 2 / (length + 1)
 *
 * @param bars - List of OHLCV bars
 * @param length - Period for exponential smoothing
 * @param useCumVolume - If true, use cumulative volume; if false, use rolling window
 * @param rollWindow - Window size for rolling volume (required if useCumVolume=false)
 * @returns Dictionary with 'evwma' as a list of calculated values for each bar.
 */
export function calculateEvwma(
  bars: readonly OHLCVBar[],
  length: number,
  useCumVolume: boolean = false,
  rollWindow: number | null = null
): EvwmaResult {
  if (length <= 0) {
    return { evwma: new Array(bars.length).fill(null) };
  }

  if (!useCumVolume && rollWindow === null) {
    throw new Error('rollWindow must be provided when useCumVolume=false');
  }

  if (rollWindow === null) {
    rollWindow = length;
  }

  if (!bars || bars.length === 0) {
    return { evwma: [] };
  }

  const results: (number | null)[] = new Array(bars.length).fill(null);

  // Calculate typical price and volume-weighted price for each bar
  const typicalPrices: number[] = [];
  const vwpValues: number[] = []; // volume-weighted price
  const volumes: number[] = [];

  for (const bar of bars) {
    const typicalPrice = (bar.high + bar.low + bar.close) / 3.0;
    const volume = bar.volume ?? 0.0;
    typicalPrices.push(typicalPrice);
    vwpValues.push(typicalPrice * volume);
    volumes.push(volume);
  }

  // Calculate VWMA (volume-weighted moving average) for each bar
  const vwmaValues: (number | null)[] = [];

  if (useCumVolume) {
    // Use cumulative volume
    let cumVwp = 0.0;
    let cumVolume = 0.0;

    for (let i = 0; i < bars.length; i++) {
      cumVwp += vwpValues[i];
      cumVolume += volumes[i];

      if (cumVolume > 0) {
        vwmaValues.push(cumVwp / cumVolume);
      } else {
        vwmaValues.push(null);
      }
    }
  } else {
    // Use rolling window volume
    for (let i = 0; i < bars.length; i++) {
      const windowStart = Math.max(0, i - rollWindow! + 1);
      const windowVwp = vwpValues.slice(windowStart, i + 1).reduce((a, b) => a + b, 0);
      const windowVolume = volumes.slice(windowStart, i + 1).reduce((a, b) => a + b, 0);

      if (windowVolume > 0) {
        vwmaValues.push(windowVwp / windowVolume);
      } else {
        vwmaValues.push(null);
      }
    }
  }

  // Apply exponential smoothing to VWMA values
  const alpha = 2.0 / (length + 1);
  let evwma: number | null = null;

  for (let i = 0; i < bars.length; i++) {
    const vwma = vwmaValues[i];

    if (vwma === null) {
      evwma = null;
      continue;
    }

    if (evwma === null) {
      // Try to find a valid window to initialize EVWMA
      const windowStart = Math.max(0, i - length + 1);
      const window = vwmaValues.slice(windowStart, i + 1);
      const validValues = window.filter((v): v is number => v !== null);

      if (validValues.length >= length) {
        // Initialize with simple average of first length values
        evwma = validValues.slice(0, length).reduce((a, b) => a + b, 0) / length;
      } else {
        continue;
      }
    }

    // Apply exponential smoothing
    evwma = vwma * alpha + evwma * (1 - alpha);

    // Only set result if we have enough data
    if (i >= length - 1) {
      results[i] = evwma;
    }
  }

  return { evwma: results };
}

/**
 * Calculate rolling correlation between two series.
 *
 * @param x - First series (can contain null values)
 * @param y - Second series (can contain null values)
 * @param window - Window size for rolling correlation
 * @returns List of correlation values, with null for insufficient data
 */
export function calculateRollingCorrelation(
  x: (number | null)[],
  y: (number | null)[],
  window: number
): (number | null)[] {
  if (x.length !== y.length) {
    throw new Error('Series x and y must have the same length');
  }

  if (window <= 0) {
    return new Array(x.length).fill(null);
  }

  const results: (number | null)[] = new Array(x.length).fill(null);

  for (let i = window - 1; i < x.length; i++) {
    const windowX = x.slice(i - window + 1, i + 1);
    const windowY = y.slice(i - window + 1, i + 1);

    // Filter out null values
    const validPairs: [number, number][] = [];
    for (let j = 0; j < windowX.length; j++) {
      const a = windowX[j];
      const b = windowY[j];
      if (a !== null && b !== null) {
        validPairs.push([a, b]);
      }
    }

    if (validPairs.length < 2) {
      results[i] = null;
      continue;
    }

    const validX = validPairs.map((pair) => pair[0]);
    const validY = validPairs.map((pair) => pair[1]);

    // Calculate mean
    const meanX = validX.reduce((a, b) => a + b, 0) / validX.length;
    const meanY = validY.reduce((a, b) => a + b, 0) / validY.length;

    // Calculate covariance and variances
    let covariance = 0;
    let varianceX = 0;
    let varianceY = 0;

    for (let j = 0; j < validX.length; j++) {
      covariance += (validX[j] - meanX) * (validY[j] - meanY);
      varianceX += (validX[j] - meanX) ** 2;
      varianceY += (validY[j] - meanY) ** 2;
    }

    // Calculate correlation
    const denominator = Math.sqrt(varianceX * varianceY);
    if (denominator === 0) {
      results[i] = null;
    } else {
      const correlation = covariance / denominator;
      results[i] = correlation;
    }
  }

  return results;
}
