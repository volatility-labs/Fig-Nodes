// src/services/indicator-calculators/ema-calculator.ts
// Translated from: services/indicator_calculators/ema_calculator.py

export interface EmaResult {
  ema: (number | null)[];
}

/**
 * Calculate EMA (Exponential Moving Average) indicator.
 *
 * @param values - List of values to calculate EMA on (can contain null values)
 * @param period - Period for EMA calculation
 * @returns Dictionary with 'ema' as a list of calculated values for each row
 */
export function calculateEma(
  values: readonly (number | null)[],
  period: number
): EmaResult {
  if (period <= 0) {
    return { ema: new Array(values.length).fill(null) };
  }

  const results: (number | null)[] = new Array(values.length).fill(null);
  const k = 2 / (period + 1);
  let ema: number | null = null;

  for (let i = 0; i < values.length; i++) {
    const value = values[i];

    if (value === null) {
      ema = null;
      continue;
    }

    if (ema === null) {
      // Try to find a valid window to initialize EMA
      const windowStart = Math.max(0, i - period + 1);
      const window = values.slice(windowStart, i + 1);
      const validValues = window.filter((v): v is number => v !== null);

      if (validValues.length === period) {
        ema = validValues.reduce((acc, v) => acc + v, 0) / period;
      }
    } else {
      ema = value * k + ema * (1 - k);
    }

    if (i >= period - 1) {
      results[i] = ema;
    }
  }

  return { ema: results };
}
