// src/services/indicator-calculators/hurst-calculator.ts
// Translated from: services/indicator_calculators/hurst_calculator.py

/**
 * Hurst Spectral Analysis Oscillator Calculator
 *
 * Implements bandpass filters and cycle analysis based on J.M. Hurst's spectral analysis.
 * Adapted from PineScript indicator by BarefootJoey.
 *
 * Reference: J.M. Hurst's "Profit Magic" - Spectral Analysis chapter
 */

export interface HurstResult {
  bandpasses: Record<string, (number | null)[]>;
  composite: (number | null)[];
  peaks: number[];
  troughs: number[];
  wavelength: number | null;
  amplitude: number | null;
}

/**
 * Calculate bandpass filter using the HPotter/Ehlers formula.
 *
 * This is a recursive filter that isolates specific frequency components.
 *
 * @param series - Input price series (e.g., HL2, close, etc.)
 * @param period - Period in bars (can be float/decimal)
 * @param bandwidth - Bandwidth parameter (default 0.025)
 * @returns List of filtered values (same length as input)
 */
export function calculateBandpassFilter(
  series: readonly (number | null)[],
  period: number,
  bandwidth: number = 0.025
): (number | null)[] {
  if (period < 2.0 || bandwidth <= 0.0) {
    return new Array(series.length).fill(null);
  }

  const result: (number | null)[] = new Array(series.length).fill(null);

  // Pre-calculate constants
  // IMPORTANT: Pinescript uses 3.14 as approximation of pi, not Math.PI!
  // To match TradingView exactly, we must use the same approximation
  const piApprox = 3.14; // Pinescript approximation (not Math.PI!)
  const beta = Math.cos((piApprox * (360.0 / period)) / 180.0);
  const gamma = 1.0 / Math.cos((piApprox * ((720.0 * bandwidth) / period)) / 180.0);
  const alpha = gamma - Math.sqrt(gamma * gamma - 1.0);

  // Initialize state variables for filtered values (not raw prices)
  // These store the previous filtered bandpass values (tmpbpf[1] and tmpbpf[2] in Pinescript)
  // In Pinescript: nz(tmpbpf[1]) returns 0 if tmpbpf[1] is na, so we start at 0.0
  let prevBpf1: number = 0.0; // tmpbpf[1] - previous filtered value
  let prevBpf2: number = 0.0; // tmpbpf[2] - two bars ago filtered value

  for (let i = 0; i < series.length; i++) {
    const current = series[i];

    if (current === null) {
      result[i] = null;
      // Don't update prev values when current is null (keep previous filtered values)
      continue;
    }

    // Need at least 2 previous bars for the filter
    if (i < 2) {
      result[i] = null;
      // Keep prev values at 0.0 for initial bars (matches Pinescript nz() behavior)
      continue;
    }

    // Get current and 2-bars-ago raw price values
    const currentVal: number = current;
    const twoBarsAgoRaw = series[i - 2];
    const twoBarsAgoVal: number = twoBarsAgoRaw !== null ? twoBarsAgoRaw : currentVal;

    // Bandpass filter formula (matching Pinescript exactly)
    // tmpbpf := 0.5 * (1 - alpha) * (Series - Series[2]) + beta * (1 + alpha) * nz(tmpbpf[1]) - alpha * nz(tmpbpf[2])
    const bpf: number =
      0.5 * (1.0 - alpha) * (currentVal - twoBarsAgoVal) +
      beta * (1.0 + alpha) * prevBpf1 -
      alpha * prevBpf2;

    result[i] = bpf;

    // Update state for next iteration (shift filtered values)
    prevBpf2 = prevBpf1;
    prevBpf1 = bpf;
  }

  return result;
}

/**
 * Detect peaks and troughs in a series.
 *
 * Peak: value is higher than both previous and next values
 * Trough: value is lower than both previous and next values
 *
 * @param series - Input series
 * @returns Tuple of [peak_indices, trough_indices]
 */
export function detectPeaksTroughs(
  series: readonly (number | null)[]
): [number[], number[]] {
  const peaks: number[] = [];
  const troughs: number[] = [];

  for (let i = 1; i < series.length - 1; i++) {
    if (
      series[i] === null ||
      series[i - 1] === null ||
      series[i + 1] === null
    ) {
      continue;
    }

    const val = series[i]!;
    const prevVal = series[i - 1]!;
    const nextVal = series[i + 1]!;

    if (val > prevVal && val > nextVal) {
      peaks.push(i);
    } else if (val < prevVal && val < nextVal) {
      troughs.push(i);
    }
  }

  return [peaks, troughs];
}

/**
 * Calculate Hurst Spectral Analysis Oscillator with multiple bandpass filters.
 *
 * @param closes - Close prices
 * @param highs - High prices (optional, for HL2 calculation)
 * @param lows - Low prices (optional, for HL2 calculation)
 * @param source - Source type - "close", "hl2", "open", "high", "low"
 * @param bandwidth - Bandwidth parameter for filters (default 0.025)
 * @param periods - Dict of period names to period values (bars)
 * @param compositeSelection - Dict of period names to bool (which to include in composite)
 * @returns Dictionary with bandpasses, composite, peaks, troughs, wavelength, amplitude
 */
export function calculateHurstOscillator(
  closes: readonly (number | null)[],
  highs: readonly (number | null)[] | null = null,
  lows: readonly (number | null)[] | null = null,
  source: 'close' | 'hl2' | 'open' | 'high' | 'low' = 'hl2',
  bandwidth: number = 0.025,
  periods: Record<string, number> | null = null,
  compositeSelection: Record<string, boolean> | null = null
): HurstResult {
  if (!closes || closes.length === 0) {
    return {
      bandpasses: {},
      composite: [],
      peaks: [],
      troughs: [],
      wavelength: null,
      amplitude: null,
    };
  }

  // Default periods matching TradingView Hurst Spectral Analysis Oscillator
  // All 11 cycles from 5 Day to 18 Year
  const defaultPeriods: Record<string, number> = {
    '5_day': 4.3,
    '10_day': 8.5,
    '20_day': 17.0,
    '40_day': 34.1,
    '80_day': 68.2,
    '20_week': 136.4,
    '40_week': 272.8,
    '18_month': 545.6,
    '54_month': 1636.8,
    '9_year': 3273.6,
    '18_year': 6547.2,
  };

  if (periods === null) {
    periods = defaultPeriods;
  }

  // Default composite selection (all enabled)
  if (compositeSelection === null) {
    compositeSelection = Object.fromEntries(
      Object.keys(periods).map((name) => [name, true])
    );
  }

  // Calculate source series
  let sourceSeries: (number | null)[];

  if (source === 'close') {
    sourceSeries = [...closes];
  } else if (source === 'hl2') {
    if (highs === null || lows === null) {
      // Fallback to close if HL2 not available
      sourceSeries = [...closes];
    } else {
      sourceSeries = highs.map((h, i) => {
        const low = lows[i];
        if (h !== null && low !== null) {
          return (h + low) / 2.0;
        }
        return null;
      });
    }
  } else {
    sourceSeries = [...closes];
  }

  // Calculate all bandpass filters
  const bandpasses: Record<string, (number | null)[]> = {};

  for (const [periodName, periodValue] of Object.entries(periods)) {
    const bpfValues = calculateBandpassFilter(sourceSeries, periodValue, bandwidth);
    bandpasses[periodName] = bpfValues;
  }

  // Calculate composite (sum of selected bandpasses)
  const composite: (number | null)[] = [];

  if (Object.keys(bandpasses).length > 0) {
    for (let i = 0; i < sourceSeries.length; i++) {
      let compValue: number = 0.0;
      let hasValue = false;

      for (const [periodName, bpfValues] of Object.entries(bandpasses)) {
        if (compositeSelection[periodName]) {
          if (i < bpfValues.length) {
            const bpfVal = bpfValues[i];
            if (bpfVal !== null) {
              compValue += bpfVal;
              hasValue = true;
            }
          }
        }
      }

      composite.push(hasValue ? compValue : null);
    }
  } else {
    for (let i = 0; i < sourceSeries.length; i++) {
      composite.push(null);
    }
  }

  // Detect peaks and troughs in composite
  const [peaks, troughs] = detectPeaksTroughs(composite);

  // Calculate wavelength (average distance between peaks and troughs)
  let wavelength: number | null = null;
  if (peaks.length > 1) {
    const peakDistances = peaks.slice(1).map((p, i) => p - peaks[i]);
    if (peakDistances.length > 0) {
      wavelength = peakDistances.reduce((a, b) => a + b, 0) / peakDistances.length;
    }
  } else if (troughs.length > 1) {
    const troughDistances = troughs.slice(1).map((t, i) => t - troughs[i]);
    if (troughDistances.length > 0) {
      wavelength = troughDistances.reduce((a, b) => a + b, 0) / troughDistances.length;
    }
  }

  // Calculate amplitude (peak - trough) from composite
  let amplitude: number | null = null;
  if (composite.length > 0) {
    const validValues = composite.filter((v): v is number => v !== null);
    if (validValues.length > 0) {
      const maxVal = Math.max(...validValues);
      const minVal = Math.min(...validValues);
      amplitude = maxVal - minVal;
    }
  }

  return {
    bandpasses,
    composite,
    peaks,
    troughs,
    wavelength,
    amplitude,
  };
}
