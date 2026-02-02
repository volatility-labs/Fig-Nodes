// src/nodes/core/market/filters/evwma-filter-node.ts
// Translated from: nodes/core/market/filters/evwma_filter_node.py

import { BaseIndicatorFilter } from './base/base-indicator-filter-node';
import {
  IndicatorType,
  createIndicatorResult,
  createIndicatorValue,
  AssetSymbol,
} from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  IndicatorResult,
  NodeInputs,
  NodeOutputs,
  OHLCVBundle,
} from '../../../../core/types';
import { calculateEvwma, calculateRollingCorrelation } from '../../../../services/indicator-calculators';
import { fetchBars } from '../../../../services/polygon-service';
import { RateLimiter } from '../../../../services/rate-limiter';
import { APIKeyVault } from '../../../../core/api-key-vault';

/**
 * EVWMA (Exponential Volume Weighted Moving Average) Filter
 *
 * Filters symbols based on EVWMA alignment and correlation across multiple timeframes.
 *
 * Requires warm-up period for accurate calculations.
 *
 * Note: Higher timeframes (4hr, 1day, weekly) are less accurate than shorter ones (1min, 5min, 15min).
 */
export class EVWMAFilter extends BaseIndicatorFilter {
  private maxSafeConcurrency = 5;

  static override defaultParams: DefaultParams = {
    evwma1_timeframe: '1min',
    evwma2_timeframe: '5min',
    evwma3_timeframe: '15min',
    length: 325,
    use_cum_volume: false,
    roll_window: 325,
    corr_smooth_window: 1,
    correlation_threshold: 0.6,
    require_alignment: true,
    require_price_above_evwma: true,
    max_concurrent: 10,
    rate_limit_per_second: 95,
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'evwma1_timeframe',
      type: 'combo',
      default: '1min',
      options: ['', '1min', '5min', '15min', '30min', '1hr', '4hr', '1day', 'weekly'],
      label: 'EVWMA 1 Timeframe',
      description: 'First EVWMA timeframe (leave blank to skip).',
    },
    {
      name: 'evwma2_timeframe',
      type: 'combo',
      default: '5min',
      options: ['', '1min', '5min', '15min', '30min', '1hr', '4hr', '1day', 'weekly'],
      label: 'EVWMA 2 Timeframe',
      description: 'Second EVWMA timeframe (leave blank to skip).',
    },
    {
      name: 'evwma3_timeframe',
      type: 'combo',
      default: '15min',
      options: ['', '1min', '5min', '15min', '30min', '1hr', '4hr', '1day', 'weekly'],
      label: 'EVWMA 3 Timeframe',
      description: 'Third EVWMA timeframe (leave blank to skip).',
    },
    {
      name: 'length',
      type: 'number',
      default: 325,
      min: 1,
      step: 1,
      label: 'EVWMA Length',
      description: 'Period for EVWMA calculation',
    },
    {
      name: 'correlation_threshold',
      type: 'number',
      default: 0.6,
      min: 0.0,
      max: 1.0,
      step: 0.01,
      label: 'Correlation Threshold',
      description: 'Minimum correlation between EVWMAs to pass filter',
    },
  ];

  protected override validateIndicatorParams(): void {
    const length = this.params.length ?? 325;
    if (typeof length !== 'number' || length <= 0) {
      throw new Error('length must be a positive number');
    }

    const rollWindow = this.params.roll_window ?? 325;
    if (typeof rollWindow !== 'number' || rollWindow <= 0) {
      throw new Error('roll_window must be a positive number');
    }

    const corrSmoothWindow = this.params.corr_smooth_window ?? 1;
    if (typeof corrSmoothWindow !== 'number' || corrSmoothWindow <= 0) {
      throw new Error('corr_smooth_window must be a positive number');
    }

    const correlationThreshold = this.params.correlation_threshold ?? 0.6;
    if (typeof correlationThreshold !== 'number' || correlationThreshold < 0 || correlationThreshold > 1) {
      throw new Error('correlation_threshold must be between 0 and 1');
    }
  }

  private timeframeToMultiplierTimespan(timeframe: string): [number, string] {
    const timeframeMap: Record<string, [number, string]> = {
      '1min': [1, 'minute'],
      '5min': [5, 'minute'],
      '15min': [15, 'minute'],
      '30min': [30, 'minute'],
      '1hr': [1, 'hour'],
      '4hr': [4, 'hour'],
      '1day': [1, 'day'],
      weekly: [1, 'week'],
    };
    return timeframeMap[timeframe] ?? [1, 'minute'];
  }

  private calculateLookbackDays(timeframe: string, length: number): number {
    if (timeframe === '1min') {
      return Math.max(1, Math.floor(length / (390 * 60))) + 1;
    } else if (timeframe.endsWith('min')) {
      const mins = parseInt(timeframe.replace('min', ''), 10);
      return Math.max(1, Math.floor((length * mins) / (390 * 60))) + 1;
    } else if (timeframe === '1hr') {
      return Math.max(1, Math.floor(length / 390)) + 1;
    } else if (timeframe === '4hr') {
      return Math.max(1, Math.floor((length * 4) / 390)) + 1;
    } else if (timeframe === '1day') {
      return Math.max(1, length) + 1;
    } else if (timeframe === 'weekly') {
      return Math.max(7, length * 7) + 1;
    }
    return 30;
  }

  private smoothCorrelation(correlations: (number | null)[], window: number): (number | null)[] {
    if (window <= 1) {
      return correlations;
    }

    const results: (number | null)[] = new Array(correlations.length).fill(null);

    for (let i = 0; i < correlations.length; i++) {
      const windowStart = Math.max(0, i - window + 1);
      const windowValues = correlations.slice(windowStart, i + 1);
      const validValues = windowValues.filter((v): v is number => v !== null);

      if (validValues.length > 0) {
        results[i] = validValues.reduce((a, b) => a + b, 0) / validValues.length;
      }
    }

    return results;
  }

  private async calculateEvwmaIndicator(
    symbol: AssetSymbol,
    apiKey: string,
    ohlcvData: OHLCVBar[]
  ): Promise<IndicatorResult> {
    const evwma1Tf = String(this.params.evwma1_timeframe ?? '1min');
    const evwma2Tf = String(this.params.evwma2_timeframe ?? '5min');
    const evwma3Tf = String(this.params.evwma3_timeframe ?? '15min');
    const length = typeof this.params.length === 'number' ? Math.floor(this.params.length) : 325;
    const useCumVolume = Boolean(this.params.use_cum_volume ?? false);
    const rollWindow = typeof this.params.roll_window === 'number' ? Math.floor(this.params.roll_window) : 325;
    const corrSmoothWindow = typeof this.params.corr_smooth_window === 'number' ? Math.floor(this.params.corr_smooth_window) : 1;
    const threshold = typeof this.params.correlation_threshold === 'number' ? this.params.correlation_threshold : 0.6;
    const requireAlignment = Boolean(this.params.require_alignment ?? true);
    const requirePriceAboveEvwma = Boolean(this.params.require_price_above_evwma ?? true);

    const selectedTimeframes = [evwma1Tf, evwma2Tf, evwma3Tf].filter((tf) => tf);

    if (selectedTimeframes.length === 0) {
      return createIndicatorResult(
        IndicatorType.EVWMA,
        0,
        createIndicatorValue(),
        this.params,
        'No EVWMA timeframes selected'
      );
    }

    if (!ohlcvData || ohlcvData.length === 0) {
      return createIndicatorResult(
        IndicatorType.EVWMA,
        0,
        createIndicatorValue(),
        this.params,
        'No OHLCV data provided'
      );
    }

    const currentPrice = ohlcvData[ohlcvData.length - 1].close;
    const latestTimestamp = ohlcvData[ohlcvData.length - 1].timestamp;

    const evwmaSeries: Record<string, (number | null)[]> = {};
    const evwmaLatestValues: Record<string, number> = {};

    for (let i = 0; i < selectedTimeframes.length; i++) {
      const timeframe = selectedTimeframes[i];
      const [multiplier, timespan] = this.timeframeToMultiplierTimespan(timeframe);
      const lookbackDays = this.calculateLookbackDays(timeframe, length);

      const fetchParams = {
        multiplier,
        timespan: timespan as 'minute' | 'hour' | 'day' | 'week',
        lookback_period: `${lookbackDays} days`,
        adjusted: true,
        sort: 'asc' as const,
        limit: 50000,
      };

      const [bars] = await fetchBars(symbol, apiKey, fetchParams);

      if (!bars || bars.length < length) {
        return createIndicatorResult(
          IndicatorType.EVWMA,
          latestTimestamp,
          createIndicatorValue(),
          this.params,
          `Insufficient data for ${timeframe} EVWMA: ${bars?.length ?? 0} bars`
        );
      }

      const evwmaResult = calculateEvwma(bars, length, useCumVolume, rollWindow);
      const evwmaValues = evwmaResult.evwma;

      if (!evwmaValues || evwmaValues.length < length) {
        return createIndicatorResult(
          IndicatorType.EVWMA,
          latestTimestamp,
          createIndicatorValue(),
          this.params,
          `Insufficient EVWMA data for ${timeframe}`
        );
      }

      const evwmaName = `evwma${i + 1}`;
      evwmaSeries[evwmaName] = evwmaValues;

      // Get latest EVWMA value
      let latestEvwma: number | null = null;
      for (let j = evwmaValues.length - 1; j >= 0; j--) {
        if (evwmaValues[j] !== null) {
          latestEvwma = evwmaValues[j];
          break;
        }
      }

      if (latestEvwma !== null) {
        evwmaLatestValues[evwmaName] = latestEvwma;
      }
    }

    // Check price above EVWMA if required
    if (requirePriceAboveEvwma) {
      for (const [evwmaName, latestEvwma] of Object.entries(evwmaLatestValues)) {
        if (currentPrice <= latestEvwma) {
          return createIndicatorResult(
            IndicatorType.EVWMA,
            latestTimestamp,
            createIndicatorValue(),
            this.params,
            `Price ${currentPrice} not above ${evwmaName} ${latestEvwma}`
          );
        }
      }
    }

    // Check alignment if required
    if (requireAlignment && Object.keys(evwmaLatestValues).length >= 2) {
      const latestValues = selectedTimeframes.map((_, i) => evwmaLatestValues[`evwma${i + 1}`]).filter((v) => v !== undefined);
      if (latestValues.length >= 2) {
        for (let i = 0; i < latestValues.length - 1; i++) {
          if (latestValues[i] <= latestValues[i + 1]) {
            return createIndicatorResult(
              IndicatorType.EVWMA,
              latestTimestamp,
              createIndicatorValue(),
              this.params,
              `EVWMAs not aligned: ${latestValues}`
            );
          }
        }
      }
    }

    // Calculate correlations if we have at least 2 EVWMAs
    let correlationPassed = true;
    if (Object.keys(evwmaSeries).length >= 2) {
      const evwmaNames = Object.keys(evwmaSeries);
      const allCorrelations: (number | null)[][] = [];

      for (let i = 0; i < evwmaNames.length; i++) {
        for (let j = i + 1; j < evwmaNames.length; j++) {
          const corr = calculateRollingCorrelation(
            evwmaSeries[evwmaNames[i]],
            evwmaSeries[evwmaNames[j]],
            rollWindow
          );
          allCorrelations.push(corr);
        }
      }

      if (allCorrelations.length > 0) {
        // Average correlations
        const avgCorrelations: (number | null)[] = [];
        const maxLen = Math.max(...allCorrelations.map((c) => c.length));
        for (let k = 0; k < maxLen; k++) {
          const valuesAtK = allCorrelations.map((c) => (k < c.length ? c[k] : null)).filter((v): v is number => v !== null);
          if (valuesAtK.length > 0) {
            avgCorrelations.push(valuesAtK.reduce((a, b) => a + b, 0) / valuesAtK.length);
          } else {
            avgCorrelations.push(null);
          }
        }

        const smoothedCorrelations = this.smoothCorrelation(avgCorrelations, corrSmoothWindow);

        // Get final correlation
        let finalCorr: number | null = null;
        for (let j = smoothedCorrelations.length - 1; j >= 0; j--) {
          if (smoothedCorrelations[j] !== null) {
            finalCorr = smoothedCorrelations[j];
            break;
          }
        }

        if (finalCorr === null || finalCorr < threshold) {
          correlationPassed = false;
        }
      }
    }

    const lines: Record<string, number> = { current_price: currentPrice };
    for (const [name, value] of Object.entries(evwmaLatestValues)) {
      lines[name] = value;
    }
    if (Object.keys(evwmaSeries).length >= 2) {
      lines.correlation_passed = correlationPassed ? 1.0 : 0.0;
    }

    return createIndicatorResult(
      IndicatorType.EVWMA,
      latestTimestamp,
      createIndicatorValue(0, lines),
      this.params,
      correlationPassed ? null : 'Correlation below threshold'
    );
  }

  protected calculateIndicator(_ohlcvData: OHLCVBar[]): IndicatorResult {
    throw new Error('Use async calculateEvwmaIndicator instead');
  }

  protected shouldPassFilter(indicatorResult: IndicatorResult): boolean {
    if (indicatorResult.error) {
      return false;
    }

    if (!indicatorResult.values.lines) {
      return false;
    }

    const correlationPassed = indicatorResult.values.lines.correlation_passed ?? 1.0;
    return correlationPassed > 0.5;
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const vault = APIKeyVault.getInstance();
    const apiKey = vault.get('POLYGON_API_KEY');
    if (!apiKey) {
      throw new Error('Polygon API key not found in vault');
    }

    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    let maxConcurrentRaw = this.params.max_concurrent ?? 10;
    const maxConcurrent = typeof maxConcurrentRaw === 'number' ? Math.floor(maxConcurrentRaw) : 10;

    let rateLimitRaw = this.params.rate_limit_per_second ?? 95;
    const rateLimit = typeof rateLimitRaw === 'number' ? Math.floor(rateLimitRaw) : 95;

    const filteredBundle: OHLCVBundle = new Map();
    const rateLimiter = new RateLimiter(rateLimit);
    const totalSymbols = ohlcvBundle.size;
    let completedCount = 0;

    const queue: Array<[string, OHLCVBar[]]> = [];
    for (const [symbolKey, ohlcvData] of ohlcvBundle) {
      if (ohlcvData && ohlcvData.length > 0) {
        queue.push([symbolKey, ohlcvData]);
      }
    }

    const effectiveConcurrency = Math.min(maxConcurrent, this.maxSafeConcurrency);

    const processSymbol = async (symbolKey: string, ohlcvData: OHLCVBar[]): Promise<void> => {
      try {
        await rateLimiter.acquire();

        const parts = symbolKey.split(':');
        const symbol = new AssetSymbol(
          parts[0],
          parts[1] as any,
          parts[2] || undefined,
          parts[3] as any
        );

        const indicatorResult = await this.calculateEvwmaIndicator(symbol, apiKey, ohlcvData);
        if (this.shouldPassFilter(indicatorResult)) {
          filteredBundle.set(symbolKey, ohlcvData);
        }

        completedCount++;
        const progress = (completedCount / totalSymbols) * 100;
        this.reportProgress(progress, `${completedCount}/${totalSymbols}`);
      } catch (error) {
        console.error(`Error processing EVWMA for ${symbolKey}:`, error);
      }
    };

    for (let i = 0; i < queue.length; i += effectiveConcurrency) {
      const batch = queue.slice(i, i + effectiveConcurrency);
      await Promise.all(batch.map(([symbolKey, ohlcvData]) => processSymbol(symbolKey, ohlcvData)));
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}
