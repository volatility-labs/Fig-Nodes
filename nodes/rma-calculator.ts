// src/services/indicator-calculators/rma-calculator.ts
// Translated from: services/indicator_calculators/rma_calculator.py

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
