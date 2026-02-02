// src/services/indicator-calculators/cco-calculator.ts
// Translated from: services/indicator_calculators/cco_calculator.py

/**
 * Cycle Channel Oscillator (CCO) Calculator
 *
 * Implements the Cycle Channel Oscillator indicator by LazyBear.
 *
 * Based on TradingView script: https://www.tradingview.com/script/3yAQDB3h-Cycle-Channel-Oscillator-LazyBear/
 *
 * The indicator calculates two oscillators:
 * - Fast Oscillator (oshort): Shows price location within the medium-term channel
 * - Slow Oscillator (omed): Shows location of short-term midline within medium-term channel
 */

import { calculateAtr } from './atr-calculator';
import { calculateRma } from './rma-calculator';

export interface CcoResult {
  fast_osc: (number | null)[];
  slow_osc: (number | null)[];
  short_cycle_top: (number | null)[];
  short_cycle_bottom: (number | null)[];
  short_cycle_midline: (number | null)[];
  medium_cycle_top: (number | null)[];
  medium_cycle_bottom: (number | null)[];
}

/**
 * Calculate Cycle Channel Oscillator (CCO).
 *
 * @param closes - Close prices
 * @param highs - High prices (optional, for ATR calculation)
 * @param lows - Low prices (optional, for ATR calculation)
 * @param shortCycleLength - Short cycle length (default 10)
 * @param mediumCycleLength - Medium cycle length (default 30)
 * @param shortCycleMultiplier - Short cycle multiplier for ATR offset (default 1.0)
 * @param mediumCycleMultiplier - Medium cycle multiplier for ATR offset (default 3.0)
 * @returns Dictionary with fast_osc, slow_osc, and channel values
 */
export function calculateCco(
  closes: readonly (number | null)[],
  highs: readonly (number | null)[] | null = null,
  lows: readonly (number | null)[] | null = null,
  shortCycleLength: number = 10,
  mediumCycleLength: number = 30,
  shortCycleMultiplier: number = 1.0,
  mediumCycleMultiplier: number = 3.0
): CcoResult {
  if (!closes || closes.length === 0) {
    return {
      fast_osc: [],
      slow_osc: [],
      short_cycle_top: [],
      short_cycle_bottom: [],
      short_cycle_midline: [],
      medium_cycle_top: [],
      medium_cycle_bottom: [],
    };
  }

  const dataLength = closes.length;

  if (shortCycleLength <= 0 || mediumCycleLength <= 0) {
    return {
      fast_osc: new Array(dataLength).fill(null),
      slow_osc: new Array(dataLength).fill(null),
      short_cycle_top: new Array(dataLength).fill(null),
      short_cycle_bottom: new Array(dataLength).fill(null),
      short_cycle_midline: new Array(dataLength).fill(null),
      medium_cycle_top: new Array(dataLength).fill(null),
      medium_cycle_bottom: new Array(dataLength).fill(null),
    };
  }

  const closesList = [...closes];

  // Calculate cycle lengths (divided by 2 as in PineScript)
  const scl = shortCycleLength / 2.0; // Short cycle length / 2
  const mcl = mediumCycleLength / 2.0; // Medium cycle length / 2
  const scl2 = scl / 2.0; // Half of short cycle
  const mcl2 = mcl / 2.0; // Half of medium cycle

  // Calculate RMAs
  const rmaShortResult = calculateRma(closesList, Math.floor(scl));
  const rmaMediumResult = calculateRma(closesList, Math.floor(mcl));

  const maScl = rmaShortResult.rma.length > 0 ? rmaShortResult.rma : new Array(dataLength).fill(null);
  const maMcl = rmaMediumResult.rma.length > 0 ? rmaMediumResult.rma : new Array(dataLength).fill(null);

  // Calculate ATR for offsets
  // Use closes for ATR if highs/lows not available (less accurate but works)
  let highsList: (number | null)[];
  let lowsList: (number | null)[];
  if (highs === null || lows === null) {
    // Approximate ATR using closes (not ideal but works)
    highsList = closesList;
    lowsList = closesList;
  } else {
    highsList = [...highs];
    lowsList = [...lows];
  }

  // Calculate ATR for short and medium cycles
  const atrShortResult = calculateAtr(highsList, lowsList, closesList, Math.floor(scl), 'RMA');
  const atrMediumResult = calculateAtr(highsList, lowsList, closesList, Math.floor(mcl), 'RMA');

  const atrShort = atrShortResult.atr.length > 0 ? atrShortResult.atr : new Array(dataLength).fill(null);
  const atrMedium = atrMediumResult.atr.length > 0 ? atrMediumResult.atr : new Array(dataLength).fill(null);

  // Calculate offsets
  const scmOff: (number | null)[] = [];
  const mcmOff: (number | null)[] = [];
  for (let i = 0; i < dataLength; i++) {
    if (atrShort[i] !== null) {
      scmOff.push(shortCycleMultiplier * atrShort[i]!);
    } else {
      scmOff.push(null);
    }

    if (atrMedium[i] !== null) {
      mcmOff.push(mediumCycleMultiplier * atrMedium[i]!);
    } else {
      mcmOff.push(null);
    }
  }

  // Calculate channel tops and bottoms
  const sct: (number | null)[] = [];
  const scb: (number | null)[] = [];
  const mct: (number | null)[] = [];
  const mcb: (number | null)[] = [];

  for (let i = 0; i < dataLength; i++) {
    // Short cycle channels
    const scl2Idx = i >= scl2 ? Math.floor(i - scl2) : 0;
    const maSclValRaw =
      scl2Idx >= 0 && maScl[scl2Idx] !== null ? maScl[scl2Idx] : closesList[i];
    const scmOffVal: number = scmOff[i] !== null ? scmOff[i]! : 0.0;

    if (maSclValRaw !== null) {
      const maSclVal: number = maSclValRaw;
      sct.push(maSclVal + scmOffVal);
      scb.push(maSclVal - scmOffVal);
    } else {
      sct.push(null);
      scb.push(null);
    }

    // Medium cycle channels
    const mcl2Idx = i >= mcl2 ? Math.floor(i - mcl2) : 0;
    const maMclValRaw =
      mcl2Idx >= 0 && maMcl[mcl2Idx] !== null ? maMcl[mcl2Idx] : closesList[i];
    const mcmOffVal: number = mcmOff[i] !== null ? mcmOff[i]! : 0.0;

    if (maMclValRaw !== null) {
      const maMclVal: number = maMclValRaw;
      mct.push(maMclVal + mcmOffVal);
      mcb.push(maMclVal - mcmOffVal);
    } else {
      mct.push(null);
      mcb.push(null);
    }
  }

  // Calculate short cycle midline (average of top and bottom)
  const scmm: (number | null)[] = [];
  for (let i = 0; i < dataLength; i++) {
    const sctVal = sct[i];
    const scbVal = scb[i];
    if (sctVal !== null && scbVal !== null) {
      scmm.push((sctVal + scbVal) / 2.0);
    } else {
      scmm.push(null);
    }
  }

  // Calculate oscillators
  // omed = (scmm - mcb) / (mct - mcb)  # Slow oscillator
  // oshort = (src - mcb) / (mct - mcb)  # Fast oscillator

  const omed: (number | null)[] = [];
  const oshort: (number | null)[] = [];

  for (let i = 0; i < dataLength; i++) {
    // Slow oscillator (omed)
    const scmmVal = scmm[i];
    const mcbVal = mcb[i];
    const mctVal = mct[i];
    if (scmmVal !== null && mcbVal !== null && mctVal !== null) {
      const mctMcbDiff = mctVal - mcbVal;
      if (mctMcbDiff !== 0) {
        const omedVal = (scmmVal - mcbVal) / mctMcbDiff;
        omed.push(omedVal);
      } else {
        omed.push(0.5); // Default to middle if no range
      }
    } else {
      omed.push(null);
    }

    // Fast oscillator (oshort)
    const closeVal = closesList[i];
    const mcbVal2 = mcb[i];
    const mctVal2 = mct[i];
    if (closeVal !== null && mcbVal2 !== null && mctVal2 !== null) {
      const mctMcbDiff = mctVal2 - mcbVal2;
      if (mctMcbDiff !== 0) {
        const oshortVal = (closeVal - mcbVal2) / mctMcbDiff;
        oshort.push(oshortVal);
      } else {
        oshort.push(0.5); // Default to middle if no range
      }
    } else {
      oshort.push(null);
    }
  }

  return {
    fast_osc: oshort,
    slow_osc: omed,
    short_cycle_top: sct,
    short_cycle_bottom: scb,
    short_cycle_midline: scmm,
    medium_cycle_top: mct,
    medium_cycle_bottom: mcb,
  };
}
