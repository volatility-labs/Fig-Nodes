// src/services/indicator-calculators/rma-calculator.ts
// Translated from: services/indicator_calculators/rma_calculator.py

import { calculateWilderMa } from './utils';

export interface RmaResult {
  rma: (number | null)[];
}

/**
 * Calculate RMA (Relative Moving Average / Wilder's Moving Average) indicator.
 *
 * @param values - List of values to calculate RMA on (can contain null values)
 * @param period - Period for RMA calculation
 * @returns Dictionary with 'rma' as a list of calculated values for each row
 *
 * Reference: https://www.tradingcode.net/tradingview/relative-moving-average/
 */
export function calculateRma(
  values: readonly (number | null)[],
  period: number
): RmaResult {
  if (period <= 0) {
    return { rma: new Array(values.length).fill(null) };
  }

  // Use Wilder's MA from utils
  const rmaValues = calculateWilderMa([...values], period);

  return { rma: rmaValues };
}
