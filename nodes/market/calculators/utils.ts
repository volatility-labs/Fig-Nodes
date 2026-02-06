// src/services/indicator-calculators/utils.ts
// Translated from: services/indicator_calculators/utils.py

/**
 * Helper for generic rolling window calculations.
 * Applies a callback function to each window of a specified period.
 * Handles initial null padding.
 */
export function rollingCalculation(
  data: (number | null)[],
  period: number,
  callback: (window: (number | null)[]) => number | null
): (number | null)[] {
  if (period <= 0 || data.length === 0) {
    return new Array(data.length).fill(null);
  }

  const results: (number | null)[] = new Array(data.length).fill(null);

  for (let i = period - 1; i < data.length; i++) {
    const windowData = data.slice(i - period + 1, i + 1);
    if (windowData.length === period) {
      results[i] = callback(windowData);
    }
  }

  return results;
}

/**
 * Calculates the rolling maximum over a given period, ignoring nulls.
 */
export function rollingMax(
  data: (number | null)[],
  period: number
): (number | null)[] {
  return rollingCalculation(data, period, (window) => {
    const validValues = window.filter((v): v is number => v !== null);
    return validValues.length > 0 ? Math.max(...validValues) : null;
  });
}

/**
 * Calculates the rolling minimum over a given period, ignoring nulls.
 */
export function rollingMin(
  data: (number | null)[],
  period: number
): (number | null)[] {
  return rollingCalculation(data, period, (window) => {
    const validValues = window.filter((v): v is number => v !== null);
    return validValues.length > 0 ? Math.min(...validValues) : null;
  });
}

/**
 * Calculates the rolling mean (Simple Moving Average - SMA), ignoring null values.
 */
export function calculateRollingMean(
  data: (number | null)[],
  period: number
): (number | null)[] {
  return rollingCalculation(data, period, (window) => {
    const validValues = window.filter((v): v is number => v !== null);
    if (validValues.length === 0) {
      return null;
    }
    const sum = validValues.reduce((acc, v) => acc + v, 0);
    return sum / validValues.length;
  });
}

/**
 * Calculates the rolling sum, returning null if any value in the window is null.
 */
export function calculateRollingSumStrict(
  data: (number | null)[],
  period: number
): (number | null)[] {
  return rollingCalculation(data, period, (window) => {
    if (window.some((v) => v === null)) {
      return null;
    }
    return (window as number[]).reduce((acc, v) => acc + v, 0);
  });
}

/**
 * Calculates the rolling population standard deviation.
 * Ignores nulls in the window. Returns null if fewer than 2 points.
 */
export function calculateRollingStdDev(
  data: (number | null)[],
  period: number
): (number | null)[] {
  const calculateStdDev = (window: (number | null)[]): number | null => {
    const validValues = window.filter((v): v is number => v !== null);
    if (validValues.length < 2) {
      return null;
    }

    const mean = validValues.reduce((acc, v) => acc + v, 0) / validValues.length;
    const variance =
      validValues.reduce((acc, val) => acc + (val - mean) ** 2, 0) /
      validValues.length;
    return variance >= 0 ? Math.sqrt(variance) : 0.0;
  };

  return rollingCalculation(data, period, calculateStdDev);
}

/**
 * Calculates Wilder's Smoothing Average (RMA).
 * This is similar to EMA but uses alpha = 1 / period.
 * Correctly handles null values by carrying forward the previous valid MA.
 */
export function calculateWilderMa(
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
