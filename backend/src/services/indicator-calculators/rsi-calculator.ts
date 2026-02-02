// src/services/indicator-calculators/rsi-calculator.ts
// Translated from: services/indicator_calculators/rsi_calculator.py

export interface RsiResult {
  rsi: (number | null)[];
}

/**
 * Calculate RSI (Relative Strength Index) indicator.
 *
 * @param values - List of values to calculate RSI on (can contain null values)
 * @param length - Period for RSI calculation (default: 14)
 * @returns Dictionary with 'rsi' as a list of calculated values for each row
 */
export function calculateRsi(
  values: readonly (number | null)[],
  length: number = 14
): RsiResult {
  if (length <= 0) {
    return { rsi: new Array(values.length).fill(null) };
  }

  const results: (number | null)[] = [];
  let avgGain = 0.0;
  let avgLoss = 0.0;
  let consecutiveValid = 0;
  let initCalculated = false;

  for (let i = 0; i < values.length; i++) {
    if (i === 0) {
      results.push(null);
      const currentVal = values[i];
      consecutiveValid = currentVal !== null ? 1 : 0;
      continue;
    }

    const current = values[i];
    const prev = values[i - 1];

    if (current === null || prev === null) {
      results.push(null);
      avgGain = 0.0;
      avgLoss = 0.0;
      initCalculated = false;
      consecutiveValid = current !== null ? 1 : 0;
      continue;
    }

    consecutiveValid += 1;

    const change = current - prev;
    const gain = change > 0 ? change : 0.0;
    const loss = change < 0 ? -change : 0.0;

    if (initCalculated) {
      avgGain = (avgGain * (length - 1) + gain) / length;
      avgLoss = (avgLoss * (length - 1) + loss) / length;
      if (avgLoss === 0) {
        results.push(100.0);
      } else {
        const rs = avgGain / avgLoss;
        const rsi = 100 - 100 / (1 + rs);
        results.push(rsi);
      }
    } else {
      avgGain += gain;
      avgLoss += loss;
      if (consecutiveValid === length + 1) {
        avgGain /= length;
        avgLoss /= length;
        initCalculated = true;
        if (avgLoss === 0) {
          results.push(100.0);
        } else {
          const rs = avgGain / avgLoss;
          const rsi = 100 - 100 / (1 + rs);
          results.push(rsi);
        }
      } else {
        results.push(null);
      }
    }
  }

  return { rsi: results };
}
