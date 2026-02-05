// src/services/indicator-calculators/adx-calculator.ts
// Translated from: services/indicator_calculators/adx_calculator.py

export interface AdxResult {
  adx: (number | null)[];
  pdi: (number | null)[];
  ndi: (number | null)[];
}

/**
 * Calculate Wilder's Moving Average (exponential moving average with alpha = 1/period).
 */
function calculateWilderMa(
  arr: readonly (number | null)[],
  period: number
): (number | null)[] {
  const ma: (number | null)[] = [];
  let sumVal = 0.0;
  let count = 0;
  let started = false;
  let hasBroken = false;

  for (let i = 0; i < arr.length; i++) {
    if (hasBroken) {
      ma.push(null);
      continue;
    }

    const currentVal = arr[i];
    if (currentVal === null) {
      if (count > 0 || started) {
        hasBroken = true;
      }
      sumVal = 0.0;
      count = 0;
      ma.push(null);
      continue;
    }

    sumVal += currentVal;
    count += 1;

    if (count < period) {
      ma.push(null);
      continue;
    }

    if (count === period) {
      ma.push(sumVal / period);
      started = true;
      continue;
    }

    // Subsequent values use Wilder's smoothing formula
    const prev = ma[i - 1];
    if (prev !== null) {
      ma.push((prev * (period - 1) + currentVal) / period);
    } else {
      ma.push(null);
    }
  }

  return ma;
}

/**
 * Calculate ADX (Average Directional Index) indicator.
 *
 * @param highs - List of high prices (can contain null values)
 * @param lows - List of low prices (can contain null values)
 * @param closes - List of close prices (can contain null values)
 * @param period - Period for ADX calculation (default: 14)
 * @returns Dictionary with 'adx', 'pdi', 'ndi' as lists of calculated values
 */
export function calculateAdx(
  highs: readonly (number | null)[],
  lows: readonly (number | null)[],
  closes: readonly (number | null)[],
  period: number = 14
): AdxResult {
  const dataLength = highs.length;
  if (dataLength === 0 || dataLength < period || period <= 0) {
    return { adx: [], pdi: [], ndi: [] };
  }

  if (lows.length !== dataLength || closes.length !== dataLength) {
    return { adx: [], pdi: [], ndi: [] };
  }

  // Calculate True Range
  const tr: (number | null)[] = [];
  const pdm: (number | null)[] = [];
  const ndm: (number | null)[] = [];

  for (let i = 0; i < dataLength; i++) {
    const currentHigh = highs[i];
    const currentLow = lows[i];

    if (currentHigh === null || currentLow === null) {
      tr.push(null);
      pdm.push(null);
      ndm.push(null);
      continue;
    }

    // Previous values
    const prevHigh = i > 0 ? highs[i - 1] : null;
    const prevLow = i > 0 ? lows[i - 1] : null;
    const prevClose = i > 0 ? closes[i - 1] : null;

    // True Range calculation
    const hlRange = currentHigh - currentLow;

    let hcRange = 0.0;
    if (prevClose !== null) {
      hcRange = Math.abs(currentHigh - prevClose);
    }

    let lcRange = 0.0;
    if (prevClose !== null) {
      lcRange = Math.abs(currentLow - prevClose);
    }

    const trVal = Math.max(hlRange, hcRange, lcRange);
    tr.push(trVal);

    // Directional Movement
    if (i > 0 && prevHigh !== null && prevLow !== null) {
      const upMove = currentHigh - prevHigh;
      const downMove = prevLow - currentLow;
      pdm.push(upMove > downMove && upMove > 0 ? upMove : 0.0);
      ndm.push(downMove > upMove && downMove > 0 ? downMove : 0.0);
    } else {
      pdm.push(0.0);
      ndm.push(0.0);
    }
  }

  // Calculate smoothed values using Wilder's MA
  const smoothedTr = calculateWilderMa(tr, period);
  const smoothedPdm = calculateWilderMa(pdm, period);
  const smoothedNdm = calculateWilderMa(ndm, period);

  // Calculate PDI and NDI
  const pdi: (number | null)[] = [];
  const ndi: (number | null)[] = [];
  const dx: (number | null)[] = [];

  for (let i = 0; i < dataLength; i++) {
    const sTr = smoothedTr[i];
    const sPdm = smoothedPdm[i];
    const sNdm = smoothedNdm[i];

    if (sTr !== null && sPdm !== null && sNdm !== null && sTr > 0) {
      const currentPdi = (sPdm / sTr) * 100;
      const currentNdi = (sNdm / sTr) * 100;
      pdi.push(currentPdi);
      ndi.push(currentNdi);

      const diSum = currentPdi + currentNdi;
      const dxVal =
        diSum === 0 ? 0 : (Math.abs(currentPdi - currentNdi) / diSum) * 100;
      dx.push(dxVal);
    } else {
      pdi.push(null);
      ndi.push(null);
      dx.push(null);
    }
  }

  // Calculate ADX using Wilder's MA on DX
  const adx = calculateWilderMa(dx, period);

  return { adx, pdi, ndi };
}
