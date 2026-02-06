// src/services/indicator-calculators/sma-calculator.ts
// Translated from: services/indicator_calculators/sma_calculator.py

export interface SmaResult {
  sma: (number | null)[];
}

/**
 * Calculate SMA (Simple Moving Average) indicator.
 *
 * @param values - List of values to calculate SMA on (can contain null values)
 * @param period - Period for SMA calculation
 * @returns Dictionary with 'sma' as a list of calculated values for each row
 */
export function calculateSma(
  values: readonly (number | null)[],
  period: number
): SmaResult {
  if (period <= 0) {
    return { sma: new Array(values.length).fill(null) };
  }

  const results: (number | null)[] = [];
  let sumVal = 0.0;
  const periodValues: number[] = [];

  for (let i = 0; i < values.length; i++) {
    const value = values[i];
    if (value !== null) {
      periodValues.push(value);
      sumVal += value;
    }

    if (i >= period) {
      const exitingValue = periodValues.shift();
      if (exitingValue !== undefined) {
        sumVal -= exitingValue;
      }
    }

    if (i >= period - 1) {
      const validCount = periodValues.length;
      if (validCount > 0) {
        results.push(sumVal / validCount);
      } else {
        results.push(null);
      }
    } else {
      results.push(null);
    }
  }

  return { sma: results };
}
