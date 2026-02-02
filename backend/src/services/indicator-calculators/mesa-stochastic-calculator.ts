// src/services/indicator-calculators/mesa-stochastic-calculator.ts
// Translated from: services/indicator_calculators/mesa_stochastic_calculator.py

/**
 * MESA Stochastic Multi Length Calculator
 *
 * Converts Pine Script MESA Stochastic indicator to TypeScript.
 *
 * Based on MESA Stochastic code published by @blackcat1402 under Mozilla Public License 2.0.
 */

export interface MesaStochasticResult {
  mesa_stochastic: (number | null)[];
}

export interface MesaStochasticMultiResult {
  mesa1: (number | null)[];
  mesa2: (number | null)[];
  mesa3: (number | null)[];
  mesa4: (number | null)[];
}

/**
 * Calculate MESA Stochastic indicator for a given price series.
 *
 * @param prices - List of price values (typically HL2 = (high + low) / 2). Can contain null values.
 * @param length - Lookback period for stochastic calculation
 * @returns Dictionary with 'mesa_stochastic' as a list of calculated values for each row.
 *          Returns null for positions where calculation isn't possible.
 */
export function calculateMesaStochastic(
  prices: readonly (number | null)[],
  length: number = 50
): MesaStochasticResult {
  const dataLength = prices.length;

  if (length <= 0 || dataLength === 0) {
    return { mesa_stochastic: new Array(dataLength).fill(null) };
  }

  if (dataLength < length + 10) {
    // Need enough data for HP filter
    return { mesa_stochastic: new Array(dataLength).fill(null) };
  }

  const pi = 2 * Math.asin(1);

  // Initialize arrays with null
  const hp: (number | null)[] = new Array(dataLength).fill(null);
  const filt: (number | null)[] = new Array(dataLength).fill(null);
  const stoc: (number | null)[] = new Array(dataLength).fill(null);
  const mesaStochastic: (number | null)[] = new Array(dataLength).fill(null);

  // Calculate alpha1 for HP filter
  const alpha1 =
    (Math.cos((0.707 * 2 * pi) / 48) + Math.sin((0.707 * 2 * pi) / 48) - 1) /
    Math.cos((0.707 * 2 * pi) / 48);

  // Calculate a1, b1, c1, c2, c3 for SuperSmoother filter
  const a1 = Math.exp((-1.414 * Math.PI) / 10);
  const b1 = 2 * a1 * Math.cos((1.414 * pi) / 10);
  const c2 = b1;
  const c3 = -a1 * a1;
  const c1 = 1 - c2 - c3;

  // Process each bar
  for (let i = 2; i < dataLength; i++) {
    const currentPrice = prices[i];
    const prevPrice = i > 0 ? prices[i - 1] : null;
    const prev2Price = i > 1 ? prices[i - 2] : null;

    // Skip if we don't have enough valid prices
    if (currentPrice === null || prevPrice === null || prev2Price === null) {
      continue;
    }

    // High-Pass Filter (HP)
    const prevHpRaw = hp[i - 1];
    const prev2HpRaw = hp[i - 2];
    const prevHpVal = prevHpRaw !== null ? prevHpRaw : 0.0;
    const prev2HpVal = prev2HpRaw !== null ? prev2HpRaw : 0.0;
    hp[i] =
      (1 - alpha1 / 2) * (1 - alpha1 / 2) * (currentPrice - 2 * prevPrice + prev2Price) +
      2 * (1 - alpha1) * prevHpVal -
      (1 - alpha1) * (1 - alpha1) * prev2HpVal;

    // SuperSmoother Filter
    const hpVal = hp[i];
    if (hpVal !== null) {
      const prevHp = hp[i - 1] !== null ? hp[i - 1]! : hpVal;
      const prevFilt = filt[i - 1] !== null ? filt[i - 1]! : hpVal;
      const prev2Filt = filt[i - 2] !== null ? filt[i - 2]! : hpVal;

      filt[i] = (c1 * (hpVal + prevHp)) / 2 + c2 * prevFilt + c3 * prev2Filt;
    } else {
      filt[i] = null;
    }

    // Stochastic calculation over lookback period
    if (i >= length && filt[i] !== null) {
      // Find highest and lowest in lookback window
      let highestC: number | null = null;
      let lowestC: number | null = null;

      for (let count = Math.max(0, i - length + 1); count <= i; count++) {
        const filtVal = filt[count];
        if (filtVal !== null) {
          if (highestC === null || filtVal > highestC) {
            highestC = filtVal;
          }
          if (lowestC === null || filtVal < lowestC) {
            lowestC = filtVal;
          }
        }
      }

      // Calculate stochastic
      const filtVal = filt[i];
      if (
        filtVal !== null &&
        highestC !== null &&
        lowestC !== null &&
        highestC !== lowestC
      ) {
        stoc[i] = (filtVal - lowestC) / (highestC - lowestC);
      } else {
        stoc[i] = 0.5; // Default to middle if no range
      }

      // Apply SuperSmoother to stochastic
      const stocVal = stoc[i];
      if (stocVal !== null) {
        const prevStoc = stoc[i - 1] !== null ? stoc[i - 1]! : stocVal;
        const prevMesa =
          mesaStochastic[i - 1] !== null ? mesaStochastic[i - 1]! : stocVal;
        const prev2Mesa =
          mesaStochastic[i - 2] !== null ? mesaStochastic[i - 2]! : stocVal;

        mesaStochastic[i] =
          (c1 * (stocVal + prevStoc)) / 2 + c2 * prevMesa + c3 * prev2Mesa;
      } else {
        mesaStochastic[i] = null;
      }
    } else if (i < length) {
      stoc[i] = null;
      mesaStochastic[i] = null;
    }
  }

  return { mesa_stochastic: mesaStochastic };
}

/**
 * Calculate MESA Stochastic for multiple lengths.
 *
 * @param prices - List of price values (typically HL2 = (high + low) / 2). Can contain null values.
 * @param length1 - First length (default 50)
 * @param length2 - Second length (default 21)
 * @param length3 - Third length (default 14)
 * @param length4 - Fourth length (default 9)
 * @returns Dictionary with keys "mesa1", "mesa2", "mesa3", "mesa4" and their respective values.
 */
export function calculateMesaStochasticMultiLength(
  prices: readonly (number | null)[],
  length1: number = 50,
  length2: number = 21,
  length3: number = 14,
  length4: number = 9
): MesaStochasticMultiResult {
  const mesa1Result = calculateMesaStochastic(prices, length1);
  const mesa2Result = calculateMesaStochastic(prices, length2);
  const mesa3Result = calculateMesaStochastic(prices, length3);
  const mesa4Result = calculateMesaStochastic(prices, length4);

  return {
    mesa1: mesa1Result.mesa_stochastic,
    mesa2: mesa2Result.mesa_stochastic,
    mesa3: mesa3Result.mesa_stochastic,
    mesa4: mesa4Result.mesa_stochastic,
  };
}
