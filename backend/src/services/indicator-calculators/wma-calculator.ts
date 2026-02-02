// src/services/indicator-calculators/wma-calculator.ts
// Translated from: services/indicator_calculators/wma_calculator.py

export interface WmaResult {
  wma: (number | null)[];
}

/**
 * Calculate WMA (Weighted Moving Average) indicator.
 *
 * @param values - List of values to calculate WMA on (can contain null values)
 * @param period - Period for WMA calculation
 * @returns Dictionary with 'wma' as a list of calculated values for each row
 * @throws Error if period is not greater than 0
 */
export function calculateWma(
  values: readonly (number | null)[],
  period: number
): WmaResult {
  if (period <= 0) {
    throw new Error('WMA period must be greater than 0.');
  }

  const results: (number | null)[] = [];
  const divisor = (period * (period + 1)) / 2;

  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      results.push(null);
      continue;
    }

    const window = values.slice(i - period + 1, i + 1);

    // Check if any value in window is null
    if (window.some((v) => v === null)) {
      results.push(null);
      continue;
    }

    // Calculate weighted sum (all values are guaranteed to be number at this point)
    const windowFloats = window as number[];
    const weightedSum = windowFloats.reduce(
      (acc, val, idx) => acc + val * (idx + 1),
      0
    );
    results.push(weightedSum / divisor);
  }

  return { wma: results };
}
