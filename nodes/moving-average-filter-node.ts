// src/nodes/core/market/filters/moving-average-filter-node.ts

import { ParamType, type NodeDefinition } from '@sosa/core';
import { IndicatorType, createIndicatorResult, createIndicatorValue, type OHLCVBar, type OHLCVBundle, type IndicatorResult } from './types';
import { BaseIndicatorFilter } from './base-indicator-filter';
import { calculateSma } from './sma-calculator';
import { calculateEma } from './ema-calculator';

/**
 * Moving Average Filter - filters assets based on price relative to moving average and MA slope.
 */
export class MovingAverageFilter extends BaseIndicatorFilter {
  static override definition: NodeDefinition = {
    ...BaseIndicatorFilter.definition,
    params: [
      { name: 'period', type: ParamType.NUMBER, default: 200, min: 2, step: 1 },
      {
        name: 'prior_bars',
        type: ParamType.NUMBER,
        default: 1,
        min: 0,
        step: 1,
        description: 'Number of bars to look back for slope calculation (works with any interval: 15min, 1hr, daily, etc.)',
      },
      { name: 'ma_type', type: ParamType.COMBO, default: 'SMA', options: ['SMA', 'EMA'] },
      {
        name: 'require_price_above_ma',
        type: ParamType.COMBO,
        default: 'true',
        options: ['true', 'false'],
        description: 'If true, requires price > MA. If false, only checks for rising MA slope.',
      },
    ],
  };

  private period: number = 200;
  private priorBars: number = 1;
  private maType: 'SMA' | 'EMA' = 'SMA';
  private requirePriceAboveMa: boolean = true;
  private currentSymbol: string = 'UNKNOWN';

  protected override validateIndicatorParams(): void {
    const periodParam = this.params.period ?? 200;
    const priorBarsParam = this.params.prior_bars ?? 1;
    const maTypeParam = this.params.ma_type ?? 'SMA';
    const requirePriceAboveMaParam = this.params.require_price_above_ma ?? 'true';

    // Convert period to integer
    let periodValue: number;
    if (typeof periodParam === 'string') {
      periodValue = parseInt(periodParam, 10);
    } else if (typeof periodParam === 'number') {
      periodValue = Math.floor(periodParam);
    } else {
      throw new Error('period must be an integer');
    }

    // Convert prior_bars to integer
    let priorBarsValue: number;
    if (typeof priorBarsParam === 'string') {
      priorBarsValue = parseInt(priorBarsParam, 10);
    } else if (typeof priorBarsParam === 'number') {
      priorBarsValue = Math.floor(priorBarsParam);
    } else {
      throw new Error('prior_bars must be an integer');
    }

    if (maTypeParam !== 'SMA' && maTypeParam !== 'EMA') {
      throw new Error("ma_type must be 'SMA' or 'EMA'");
    }

    // Convert string "true"/"false" to boolean
    let requirePriceAboveMaValue: boolean;
    if (typeof requirePriceAboveMaParam === 'string') {
      requirePriceAboveMaValue = requirePriceAboveMaParam.toLowerCase() === 'true';
    } else if (typeof requirePriceAboveMaParam === 'boolean') {
      requirePriceAboveMaValue = requirePriceAboveMaParam;
    } else {
      throw new Error("require_price_above_ma must be 'true' or 'false'");
    }

    this.period = periodValue;
    this.priorBars = priorBarsValue;
    this.maType = maTypeParam as 'SMA' | 'EMA';
    this.requirePriceAboveMa = requirePriceAboveMaValue;
  }

  private getIndicatorType(): IndicatorType {
    return this.maType === 'SMA' ? IndicatorType.SMA : IndicatorType.EMA;
  }

  private calculateMa(closePrices: number[], period: number): { sma?: (number | null)[]; ema?: (number | null)[] } {
    if (this.maType === 'SMA') {
      return calculateSma(closePrices, period);
    } else {
      return calculateEma(closePrices, period);
    }
  }

  private getMaKey(): string {
    return this.maType === 'SMA' ? 'sma' : 'ema';
  }

  protected calculateIndicator(ohlcvData: OHLCVBar[]): IndicatorResult {
    const indicatorType = this.getIndicatorType();
    const maKey = this.getMaKey();

    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult({
        indicatorType: indicatorType,
        timestamp: 0,
        values: createIndicatorValue({ single: 0, lines: {} }),
        params: {},
        error: 'No OHLCV data',
      });
    }

    if (ohlcvData.length < this.period) {
      console.warn(`Insufficient data: ${ohlcvData.length} bars < ${this.period}`);
      return createIndicatorResult({
        indicatorType: indicatorType,
        timestamp: 0,
        values: createIndicatorValue({ single: 0, lines: {} }),
        params: {},
        error: `Insufficient data: ${ohlcvData.length} bars < ${this.period}`,
      });
    }

    const lastTs = ohlcvData[ohlcvData.length - 1].timestamp;

    // Calculate current MA using the calculator
    const currentClosePrices = ohlcvData.map((bar) => bar.close);
    const currentMaResult = this.calculateMa(currentClosePrices, this.period);
    const currentMaValues = (currentMaResult as Record<string, (number | null)[]>)[maKey] ?? [];
    const currentMaRaw = currentMaValues.length > 0 ? currentMaValues[currentMaValues.length - 1] : null;
    const currentMa = currentMaRaw !== null ? currentMaRaw : NaN;

    if (Number.isNaN(currentMa)) {
      return createIndicatorResult({
        indicatorType: indicatorType,
        timestamp: lastTs,
        values: createIndicatorValue({ single: 0, lines: {} }),
        params: {},
        error: `Unable to compute current ${this.maType}`,
      });
    }

    // Handle prior_bars = 0 case (no slope requirement)
    if (this.priorBars === 0) {
      const currentPrice = ohlcvData[ohlcvData.length - 1].close;
      return createIndicatorResult({
        indicatorType: indicatorType,
        timestamp: lastTs,
        values: createIndicatorValue({ single: 0, lines: { current: currentMa, previous: NaN, price: currentPrice } }),
        params: { period: this.period, ma_type: this.maType },
      });
    }

    // Use bar-based lookback instead of calendar days
    const lookbackIndex = ohlcvData.length - this.priorBars;

    // Ensure we have enough data for the lookback
    if (lookbackIndex < this.period) {
      const currentPrice = ohlcvData[ohlcvData.length - 1].close;
      return createIndicatorResult({
        indicatorType: indicatorType,
        timestamp: lastTs,
        values: createIndicatorValue({ single: 0, lines: { current: NaN, previous: NaN, price: currentPrice } }),
        params: {},
        error: `Insufficient data for ${this.priorBars} bar lookback with ${this.period} period MA`,
      });
    }

    // Get previous data up to (and including) the lookback point
    const previousData = ohlcvData.slice(0, lookbackIndex);

    if (previousData.length < this.period) {
      const currentPrice = ohlcvData[ohlcvData.length - 1].close;
      return createIndicatorResult({
        indicatorType: indicatorType,
        timestamp: lastTs,
        values: createIndicatorValue({ single: 0, lines: { current: NaN, previous: NaN, price: currentPrice } }),
        params: {},
        error: `Insufficient data for previous ${this.maType}`,
      });
    }

    // Calculate previous MA using the calculator
    const previousClosePrices = previousData.map((bar) => bar.close);
    const previousMaResult = this.calculateMa(previousClosePrices, this.period);
    const previousMaValues = (previousMaResult as Record<string, (number | null)[]>)[maKey] ?? [];
    const previousMaRaw = previousMaValues.length > 0 ? previousMaValues[previousMaValues.length - 1] : null;
    const previousMa = previousMaRaw !== null ? previousMaRaw : NaN;

    if (Number.isNaN(previousMa)) {
      const currentPrice = ohlcvData[ohlcvData.length - 1].close;
      return createIndicatorResult({
        indicatorType: indicatorType,
        timestamp: lastTs,
        values: createIndicatorValue({ single: 0, lines: { current: currentMa, previous: NaN, price: currentPrice } }),
        params: {},
        error: `Unable to compute previous ${this.maType}`,
      });
    }

    const currentPrice = ohlcvData[ohlcvData.length - 1].close;

    // Debug logging
    const currentBarIndex = ohlcvData.length - 1;
    const previousBarIndex = lookbackIndex - 1;
    const barsDifference = currentBarIndex - previousBarIndex;

    console.warn(
      `📊 MA Filter [${this.currentSymbol}]: period=${this.period}, prior_bars=${this.priorBars}, ` +
      `current_MA@${currentBarIndex}=${currentMa.toFixed(4)}, ` +
      `previous_MA@${previousBarIndex}=${previousMa.toFixed(4)}, ` +
      `bars_diff=${barsDifference}, ` +
      `slope=${currentMa > previousMa ? 'POSITIVE' : 'NEGATIVE'}, ` +
      `price=${currentPrice.toFixed(4)}, diff=${(currentMa - previousMa).toFixed(6)}`
    );

    return createIndicatorResult({
      indicatorType: indicatorType,
      timestamp: lastTs,
      values: createIndicatorValue({ single: 0, lines: { current: currentMa, previous: previousMa, price: currentPrice } }),
      params: { period: this.period, ma_type: this.maType },
    });
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      console.warn(
        `❌ MA Filter [${this.currentSymbol}]: Failed due to error: ${indicatorResult.error}`
      );
      return false;
    }

    const lines = indicatorResult.values.lines;
    const currentMa = lines.current ?? NaN;
    const currentPrice = lines.price ?? NaN;

    // Check for NaN values
    if (Number.isNaN(currentPrice) || Number.isNaN(currentMa)) {
      console.warn(
        `❌ MA Filter [${this.currentSymbol}]: Failed - NaN values (price=${currentPrice}, MA=${currentMa})`
      );
      return false;
    }

    // If require_price_above_ma is True, check price > MA
    if (this.requirePriceAboveMa) {
      if (!(currentPrice > currentMa)) {
        console.warn(
          `❌ MA Filter [${this.currentSymbol}]: Failed - price ${currentPrice.toFixed(4)} <= MA ${currentMa.toFixed(4)}`
        );
        return false;
      }
    }

    // If prior_bars is 0, only check price > MA (if required) or just pass if only slope is needed
    if (this.priorBars === 0) {
      if (this.requirePriceAboveMa) {
        console.warn(
          `✅ MA Filter [${this.currentSymbol}]: Passed - price ${currentPrice.toFixed(4)} > MA ${currentMa.toFixed(4)} (no slope check)`
        );
      } else {
        console.warn(
          `✅ MA Filter [${this.currentSymbol}]: Passed - no price/MA requirement and no slope check (prior_bars=0)`
        );
      }
      return true;
    }

    // For prior_bars > 0, check that current MA > previous MA (upward slope)
    const previous = lines.previous ?? NaN;
    if (Number.isNaN(previous)) {
      console.warn(`❌ MA Filter [${this.currentSymbol}]: Failed - previous MA is NaN`);
      return false;
    }

    const slopePositive = currentMa > previous;
    const slopeDiff = currentMa - previous;

    if (slopePositive) {
      console.warn(
        `✅ MA Filter [${this.currentSymbol}]: Passed - slope POSITIVE (${currentMa.toFixed(4)} > ${previous.toFixed(4)}, diff=${slopeDiff.toFixed(6)})`
      );
    } else {
      console.warn(
        `❌ MA Filter [${this.currentSymbol}]: Failed - slope NEGATIVE (${currentMa.toFixed(4)} <= ${previous.toFixed(4)}, diff=${slopeDiff.toFixed(6)})`
      );
    }

    return slopePositive;
  }

  protected override async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();
    const totalSymbols = ohlcvBundle.size;
    let processedSymbols = 0;

    // Initial progress signal
    try {
      this.progress(0.0, `0/${totalSymbols}`);
    } catch {
      // Ignore progress reporting errors
    }

    for (const [symbolKey, ohlcvData] of ohlcvBundle) {
      // Set current symbol for logging context
      this.currentSymbol = symbolKey.ticker;

      if (!ohlcvData || ohlcvData.length === 0) {
        processedSymbols++;
        try {
          const pct = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
          this.progress(pct, `${processedSymbols}/${totalSymbols}`);
        } catch {
          // Ignore progress reporting errors
        }
        continue;
      }

      try {
        const indicatorResult = this.calculateIndicator(ohlcvData);

        if (this.shouldPassFilter(indicatorResult)) {
          filteredBundle.set(symbolKey, ohlcvData);
        }
      } catch (e) {
        console.warn(`Failed to process indicator for ${symbolKey}: ${e}`);
        processedSymbols++;
        try {
          const pct = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
          this.progress(pct, `${processedSymbols}/${totalSymbols}`);
        } catch {
          // Ignore progress reporting errors
        }
        continue;
      }

      // Advance progress after successful processing
      processedSymbols++;
      try {
        const pct = (processedSymbols / Math.max(1, totalSymbols)) * 100.0;
        this.progress(pct, `${processedSymbols}/${totalSymbols}`);
      } catch {
        // Ignore progress reporting errors
      }
    }

    // Clear symbol context
    this.currentSymbol = 'UNKNOWN';

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}
