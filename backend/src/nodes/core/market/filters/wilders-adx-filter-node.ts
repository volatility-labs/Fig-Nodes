// src/nodes/core/market/filters/wilders-adx-filter-node.ts
// Translated from: nodes/core/market/filters/wilders_adx_filter_node.py

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import { IndicatorType, createIndicatorResult, createIndicatorValue } from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  IndicatorResult,
} from '../../../../core/types';
import { calculateAdx } from '../../../../services/indicator-calculators';

/**
 * Wilder's ADX-based filter with optional +DI/-DI direction and crossover requirements.
 *
 * Parameters:
 * - min_adx: Minimum ADX threshold to qualify as trending (default: 25.0)
 * - timeperiod: ADX period (default: 14)
 * - direction: 'any' | 'bullish' | 'bearish' (default: 'any')
 * - require_crossover: Require recent +DI/-DI crossover consistent with direction (default: false)
 * - di_lookback_bars: Lookback bars to detect crossover (default: 3)
 * - require_adx_rising: Require ADX rising vs previous bar (default: false)
 */
export class WildersADXFilter extends BaseIndicatorFilter {
  static override defaultParams: DefaultParams = {
    min_adx: 25.0,
    timeperiod: 14,
    direction: 'any',
    require_crossover: false,
    di_lookback_bars: 3,
    require_adx_rising: false,
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'min_adx',
      type: 'number',
      default: 25.0,
      min: 0.0,
      max: 100.0,
      step: 0.1,
    },
    { name: 'timeperiod', type: 'number', default: 14, min: 1, step: 1 },
    {
      name: 'direction',
      type: 'combo',
      default: 'any',
      options: ['any', 'bullish', 'bearish'],
    },
    { name: 'require_crossover', type: 'combo', default: false, options: [true, false] },
    { name: 'di_lookback_bars', type: 'number', default: 3, min: 1, step: 1 },
    { name: 'require_adx_rising', type: 'combo', default: false, options: [true, false] },
  ];

  protected override validateIndicatorParams(): void {
    const minAdx = this.params.min_adx ?? 25.0;
    const timeperiod = this.params.timeperiod ?? 14;
    const lookback = this.params.di_lookback_bars ?? 3;
    const direction = this.params.direction ?? 'any';

    if (typeof minAdx !== 'number' || minAdx < 0) {
      throw new Error('Minimum ADX cannot be negative');
    }
    if (typeof timeperiod !== 'number' || timeperiod <= 0) {
      throw new Error('Time period must be positive');
    }
    if (typeof lookback !== 'number' || lookback <= 0) {
      throw new Error('di_lookback_bars must be positive');
    }
    if (direction !== 'any' && direction !== 'bullish' && direction !== 'bearish') {
      throw new Error('direction must be one of: any, bullish, bearish');
    }
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult(
        IndicatorType.ADX,
        0,
        createIndicatorValue(0.0),
        this.params,
        'No data'
      );
    }

    let timeperiodValue = this.params.timeperiod ?? 14;
    if (typeof timeperiodValue !== 'number') {
      timeperiodValue = 14;
    }
    const timeperiod = Math.floor(timeperiodValue);

    if (ohlcvData.length < timeperiod) {
      return createIndicatorResult(
        IndicatorType.ADX,
        ohlcvData[ohlcvData.length - 1].timestamp,
        createIndicatorValue(0.0),
        this.params,
        'Insufficient data'
      );
    }

    const highs = ohlcvData.map((bar) => bar.high);
    const lows = ohlcvData.map((bar) => bar.low);
    const closes = ohlcvData.map((bar) => bar.close);

    const result = calculateAdx(highs, lows, closes, timeperiod);
    const adxSeries = result.adx;
    const pdiSeries = result.pdi;
    const ndiSeries = result.ndi;

    const latestAdx = adxSeries.length > 0 ? adxSeries[adxSeries.length - 1] : null;
    const latestPdi = pdiSeries.length > 0 ? pdiSeries[pdiSeries.length - 1] : null;
    const latestNdi = ndiSeries.length > 0 ? ndiSeries[ndiSeries.length - 1] : null;

    // Build a small tail series for downstream logic (last N bars)
    let lookback = this.params.di_lookback_bars ?? 3;
    if (typeof lookback !== 'number') {
      lookback = 3;
    }
    const lb = Math.max(1, Math.floor(lookback));

    const tailStart = Math.max(0, adxSeries.length - lb - 1);
    const tail: Array<Record<string, unknown>> = [];
    for (let i = tailStart; i < adxSeries.length; i++) {
      const adxVal = i < adxSeries.length ? adxSeries[i] : null;
      const pdiVal = i < pdiSeries.length ? pdiSeries[i] : null;
      const ndiVal = i < ndiSeries.length ? ndiSeries[i] : null;
      tail.push({ adx: adxVal, '+di': pdiVal, '-di': ndiVal });
    }

    return createIndicatorResult(
      IndicatorType.ADX,
      ohlcvData[ohlcvData.length - 1].timestamp,
      createIndicatorValue(
        latestAdx ?? 0.0,
        { pdi: latestPdi ?? 0.0, ndi: latestNdi ?? 0.0 },
        tail
      ),
      this.params
    );
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    const minAdx = this.params.min_adx ?? 25.0;
    const direction = this.params.direction ?? 'any';
    const requireCrossover = this.params.require_crossover ?? false;
    const requireAdxRising = this.params.require_adx_rising ?? false;

    const latestAdx = indicatorResult.values.single;
    const lines = indicatorResult.values.lines;
    const series = indicatorResult.values.series;

    if (typeof minAdx === 'number' && latestAdx < minAdx) {
      return false;
    }

    const pdi = lines.pdi ?? 0;
    const ndi = lines.ndi ?? 0;

    // Direction filter
    if (direction === 'bullish' && !(pdi > ndi)) {
      return false;
    }
    if (direction === 'bearish' && !(ndi > pdi)) {
      return false;
    }

    // ADX rising requirement
    if (requireAdxRising && series.length >= 2) {
      const prevAdx = series[series.length - 2]?.adx;
      if (typeof prevAdx === 'number' && !(latestAdx > prevAdx)) {
        return false;
      }
    }

    // Crossover requirement within tail series
    if (requireCrossover && series.length >= 2) {
      let crossed = false;
      for (let i = 1; i < series.length; i++) {
        const prev = series[i - 1];
        const curr = series[i];
        const pPrev = prev['+di'] as number | null;
        const nPrev = prev['-di'] as number | null;
        const pCurr = curr['+di'] as number | null;
        const nCurr = curr['-di'] as number | null;

        if (
          typeof pPrev !== 'number' ||
          typeof nPrev !== 'number' ||
          typeof pCurr !== 'number' ||
          typeof nCurr !== 'number'
        ) {
          continue;
        }

        const prevSign = pPrev > nPrev ? 1 : pPrev < nPrev ? -1 : 0;
        const currSign = pCurr > nCurr ? 1 : pCurr < nCurr ? -1 : 0;

        if (prevSign !== currSign && currSign !== 0) {
          // A crossover occurred at step i
          if (direction === 'any') {
            crossed = true;
            break;
          }
          if (direction === 'bullish' && currSign === 1) {
            crossed = true;
            break;
          }
          if (direction === 'bearish' && currSign === -1) {
            crossed = true;
            break;
          }
        }
      }
      if (!crossed) {
        return false;
      }
    }

    return true;
  }
}
