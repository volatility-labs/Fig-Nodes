// src/services/indicator-calculators/index.ts
// Indicator calculators module exports

// Utility functions
export {
  rollingCalculation,
  rollingMax,
  rollingMin,
  calculateRollingMean,
  calculateRollingSumStrict,
  calculateRollingStdDev,
  calculateWilderMa,
} from './utils';

// SMA
export { calculateSma, type SmaResult } from './sma-calculator';

// EMA
export { calculateEma, type EmaResult } from './ema-calculator';

// RSI
export { calculateRsi, type RsiResult } from './rsi-calculator';

// RMA
export { calculateRma, type RmaResult } from './rma-calculator';

// WMA
export { calculateWma, type WmaResult } from './wma-calculator';

// ATR
export { calculateAtr, calculateTr, type AtrResult } from './atr-calculator';

// ADX
export { calculateAdx, type AdxResult } from './adx-calculator';

// ATRX
export {
  calculateAtrx,
  calculateAtrxLastValue,
  type AtrxResult,
} from './atrx-calculator';

// LoD
export { calculateLod, type LodResult } from './lod-calculator';

// EVWMA
export {
  calculateEvwma,
  calculateRollingCorrelation,
  type EvwmaResult,
} from './evwma-calculator';

// VBP
export {
  calculateVbp,
  type VbpResult,
  type VbpHistogramBin,
} from './vbp-calculator';

// Hurst
export {
  calculateHurstOscillator,
  calculateBandpassFilter,
  detectPeaksTroughs,
  type HurstResult,
} from './hurst-calculator';

// CCO
export { calculateCco, type CcoResult } from './cco-calculator';

// MESA Stochastic
export {
  calculateMesaStochastic,
  calculateMesaStochasticMultiLength,
  type MesaStochasticResult,
  type MesaStochasticMultiResult,
} from './mesa-stochastic-calculator';

// ORB
export { calculateOrb, type OrbResult } from './orb-calculator';
