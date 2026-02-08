// src/services/indicator-calculators/vbp-calculator.ts
// Translated from: services/indicator_calculators/vbp_calculator.py

import type { OHLCVBar } from '../types';

export interface VbpHistogramBin {
  priceLow: number;
  priceHigh: number;
  priceLevel: number;
  volume: number;
}

export interface VbpResult {
  histogram: VbpHistogramBin[];
  pointOfControl: number | null;
  valueAreaHigh: number | null;
  valueAreaLow: number | null;
}

/**
 * Calculate VBP (Volume Profile) histogram data.
 *
 * @param bars - List of OHLCV bars (can contain null values in volume field)
 * @param numberOfBins - The number of price bins to create for the histogram
 * @param useDollarWeighted - If true, use dollar-weighted volume (volume * close) instead of raw volume
 * @param useCloseOnly - If true, bin by close price only; if false, use HLC average (typical price)
 * @returns Dictionary with 'histogram', 'pointOfControl', 'valueAreaHigh', 'valueAreaLow'
 */
export function calculateVbp(
  bars: readonly OHLCVBar[],
  numberOfBins: number,
  useDollarWeighted: boolean = false,
  useCloseOnly: boolean = false
): VbpResult {
  if (!bars || bars.length === 0 || numberOfBins <= 0) {
    return {
      histogram: [],
      pointOfControl: null,
      valueAreaHigh: null,
      valueAreaLow: null,
    };
  }

  // Find min and max prices
  let minPrice = Infinity;
  let maxPrice = -Infinity;
  let totalVolume = 0.0;

  for (const bar of bars) {
    if (bar.high > maxPrice) {
      maxPrice = bar.high;
    }
    if (bar.low < minPrice) {
      minPrice = bar.low;
    }
    const rawVolume = bar.volume ?? 0.0;
    // Calculate total volume using same weighting method as will be used in distribution
    const volume = useDollarWeighted ? rawVolume * bar.close : rawVolume;
    totalVolume += volume;
  }

  if (totalVolume === 0 || minPrice === maxPrice) {
    return {
      histogram: [],
      pointOfControl: null,
      valueAreaHigh: null,
      valueAreaLow: null,
    };
  }

  // Create histogram bins
  const binSize = (maxPrice - minPrice) / numberOfBins;
  const histogram: VbpHistogramBin[] = [];

  for (let i = 0; i < numberOfBins; i++) {
    const priceLow = minPrice + i * binSize;
    histogram.push({
      priceLow,
      priceHigh: priceLow + binSize,
      priceLevel: priceLow + binSize / 2,
      volume: 0.0,
    });
  }

  // Distribute volume into bins
  for (const bar of bars) {
    const rawVolume = bar.volume ?? 0.0;
    if (rawVolume > 0) {
      // Apply dollar weighting if requested
      const volume = useDollarWeighted ? rawVolume * bar.close : rawVolume;

      // Choose price for binning
      let binPrice: number;
      if (useCloseOnly) {
        binPrice = bar.close;
      } else {
        // Use HLC average (typical price)
        binPrice = (bar.high + bar.low + bar.close) / 3;
      }

      let binIndex = Math.floor((binPrice - minPrice) / binSize);
      if (binIndex >= numberOfBins) {
        binIndex = numberOfBins - 1;
      }
      if (binIndex < 0) {
        binIndex = 0;
      }

      if (binIndex >= 0 && binIndex < histogram.length) {
        histogram[binIndex].volume += volume;
      }
    }
  }

  if (histogram.length === 0) {
    return {
      histogram: [],
      pointOfControl: null,
      valueAreaHigh: null,
      valueAreaLow: null,
    };
  }

  // Find Point of Control (POC) - bin with highest volume
  let pocIndex = 0;
  let maxVolume = histogram[0].volume;
  for (let i = 1; i < histogram.length; i++) {
    if (histogram[i].volume > maxVolume) {
      maxVolume = histogram[i].volume;
      pocIndex = i;
    }
  }

  const pointOfControl = histogram[pocIndex].priceLevel;

  // Calculate Value Area (70% of total volume)
  const targetVolume = totalVolume * 0.7;
  let currentVolume = histogram[pocIndex].volume;
  let highIndex = pocIndex;
  let lowIndex = pocIndex;

  while (
    currentVolume < targetVolume &&
    (lowIndex > 0 || highIndex < numberOfBins - 1)
  ) {
    const nextHighVolume =
      highIndex + 1 < numberOfBins ? histogram[highIndex + 1].volume : -1.0;
    const nextLowVolume = lowIndex - 1 >= 0 ? histogram[lowIndex - 1].volume : -1.0;

    if (nextHighVolume > nextLowVolume) {
      highIndex += 1;
      currentVolume += nextHighVolume;
    } else {
      lowIndex -= 1;
      currentVolume += nextLowVolume;
    }
  }

  const valueAreaHigh = histogram[highIndex].priceHigh;
  const valueAreaLow = histogram[lowIndex].priceLow;

  return {
    histogram,
    pointOfControl,
    valueAreaHigh,
    valueAreaLow,
  };
}
