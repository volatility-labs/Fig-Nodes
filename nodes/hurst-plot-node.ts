// src/nodes/core/market/utils/hurst-plot-node.ts
//
// NOTE: This TypeScript version computes chart data but does NOT render images.
// The Python version used matplotlib for server-side rendering.
// In this architecture, we return computed data for frontend rendering.

import { Node, NodeCategory, port, type NodeDefinition } from '@sosa/core';
import type { OHLCVBar } from './types';
import { calculateHurstOscillator } from './hurst-calculator';
import { calculateEma } from './ema-calculator';
import { calculateCco } from './cco-calculator';
import { calculateMesaStochasticMultiLength } from './mesa-stochastic-calculator';

interface NormalizedBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface HurstChartData {
  symbol: string;
  bars: NormalizedBar[];
  ema10: Array<number | null>;
  ema30: Array<number | null>;
  ema100: Array<number | null>;
  hurstData: {
    bandpasses: Record<string, Array<number | null>>;
    composite: Array<number | null>;
    peaks: number[];
    troughs: number[];
    wavelength: number | null;
    amplitude: number | null;
  };
  mesaData?: {
    mesa1: Array<number | null>;
    mesa2: Array<number | null>;
    mesa3: Array<number | null>;
    mesa4: Array<number | null>;
  };
  ccoData?: {
    fast_osc: Array<number | null>;
    slow_osc: Array<number | null>;
  };
  currentPrice?: number;
}

/**
 * Normalize OHLCV bars to consistent format.
 */
function normalizeBars(bars: OHLCVBar[]): NormalizedBar[] {
  const timestampMap = new Map<number, NormalizedBar>();

  for (const bar of bars) {
    const ts = Number(bar.timestamp ?? 0);
    const open = Number(bar.open ?? 0);
    const high = Number(bar.high ?? 0);
    const low = Number(bar.low ?? 0);
    const close = Number(bar.close ?? 0);
    const volume = Number(bar.volume ?? 0);

    timestampMap.set(ts, { timestamp: ts, open, high, low, close, volume });
  }

  return Array.from(timestampMap.values()).sort((a, b) => a.timestamp - b.timestamp);
}

/**
 * Hurst Spectral Analysis Oscillator Plot Node
 *
 * NOTE: This TypeScript version returns computed chart data for frontend rendering
 * instead of generating images server-side like the Python/matplotlib version.
 *
 * Creates computed data for:
 * - Top panel: Price OHLC bars with EMAs
 * - Middle panel: Hurst bandpass waves (selected periods + composite)
 * - Optional: MESA Stochastic panel
 * - Optional: CCO (Cycle Channel Oscillator) panel
 *
 * Inputs: 'ohlcv_bundle' (Map<string, OHLCVBar[]>)
 * Output: 'chart_data' -> structured data for frontend charting
 */
export class HurstPlot extends Node {
  static definition: NodeDefinition = {
    inputs: {
      ohlcv_bundle: port('OHLCVBundle', { optional: true }),
    },
    outputs: {
      chart_data: port('ConfigDict'),
      hurst_data: port('ConfigDict'),
      ohlcv_bundle: port('OHLCVBundle'),
      mesa_data: port('ConfigDict'),
      cco_data: port('ConfigDict'),
    },
    category: NodeCategory.MARKET,
    ui: {
      outputDisplay: {
        type: 'chart-preview',
        bind: 'chart_data',
        options: {
          chartType: 'candlestick',
          modalEnabled: true,
          symbolSelector: true,
        },
      },
    },
    params: [
      { name: 'max_symbols', type: 'integer', default: 20, min: 1, max: 50, step: 1 },
      { name: 'lookback_bars', type: 'number', default: 100, min: 10, max: 10000, step: 100 },
      { name: 'zoom_to_recent', type: 'combo', default: false, options: [true, false] },
      { name: 'y_axis_scale', type: 'combo', default: 'symlog', options: ['linear', 'symlog', 'log'] },
      { name: 'show_current_price', type: 'combo', default: true, options: [true, false] },
      { name: 'source', type: 'combo', default: 'hl2', options: ['close', 'hl2', 'open', 'high', 'low'] },
      { name: 'bandwidth', type: 'number', default: 0.025, min: 0.001, max: 1.0, step: 0.001 },
      { name: 'show_5_day', type: 'combo', default: true, options: [true, false] },
      { name: 'show_10_day', type: 'combo', default: true, options: [true, false] },
      { name: 'show_20_day', type: 'combo', default: true, options: [true, false] },
      { name: 'show_40_day', type: 'combo', default: true, options: [true, false] },
      { name: 'show_80_day', type: 'combo', default: true, options: [true, false] },
      { name: 'show_20_week', type: 'combo', default: false, options: [true, false] },
      { name: 'show_40_week', type: 'combo', default: false, options: [true, false] },
      { name: 'show_18_month', type: 'combo', default: false, options: [true, false] },
      { name: 'show_54_month', type: 'combo', default: false, options: [true, false] },
      { name: 'show_9_year', type: 'combo', default: false, options: [true, false] },
      { name: 'show_18_year', type: 'combo', default: false, options: [true, false] },
      { name: 'show_composite', type: 'combo', default: true, options: [true, false] },
      { name: 'show_mesa_stochastic', type: 'combo', default: false, options: [true, false] },
      { name: 'mesa_length1', type: 'number', default: 50, min: 2, max: 200, step: 1 },
      { name: 'mesa_length2', type: 'number', default: 21, min: 2, max: 200, step: 1 },
      { name: 'mesa_length3', type: 'number', default: 14, min: 2, max: 200, step: 1 },
      { name: 'mesa_length4', type: 'number', default: 9, min: 2, max: 200, step: 1 },
      { name: 'mesa_trigger_length', type: 'number', default: 2, min: 1, max: 20, step: 1 },
      { name: 'show_cco', type: 'combo', default: false, options: [true, false] },
      { name: 'cco_short_cycle_length', type: 'integer', default: 10, min: 2, max: 100, step: 1 },
      { name: 'cco_medium_cycle_length', type: 'integer', default: 30, min: 2, max: 200, step: 1 },
      { name: 'cco_short_cycle_multiplier', type: 'number', default: 1.0, min: 0.1, max: 10.0, step: 0.1 },
      { name: 'cco_medium_cycle_multiplier', type: 'number', default: 3.0, min: 0.1, max: 10.0, step: 0.1 },
    ],
  };

  private parseParams(): Record<string, unknown> {
    const lookbackRaw = this.params.lookback_bars;
    let lookback: number | null = null;
    if (typeof lookbackRaw === 'number' && lookbackRaw > 0) {
      lookback = Math.floor(lookbackRaw);
    }

    const maxSymsRaw = this.params.max_symbols;
    const maxSyms = typeof maxSymsRaw === 'number' ? Math.floor(maxSymsRaw) : 20;

    const source = String(this.params.source || 'hl2');
    const bandwidthRaw = this.params.bandwidth;
    const bandwidth = typeof bandwidthRaw === 'number' ? bandwidthRaw : 0.025;

    // Period configurations
    const periodDefaults: Record<string, number> = {
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

    const periods: Record<string, number> = {};
    for (const [key, defaultVal] of Object.entries(periodDefaults)) {
      const raw = this.params[`period_${key}`];
      periods[key] = typeof raw === 'number' ? raw : defaultVal;
    }

    const compositeSelection: Record<string, boolean> = {};
    for (const key of Object.keys(periods)) {
      const raw = this.params[`composite_${key}`];
      compositeSelection[key] = raw !== false;
    }

    const showPeriods = Object.keys(periodDefaults).filter((k) => {
      const defaultShow = ['5_day', '10_day', '20_day', '40_day', '80_day'].includes(k);
      return Boolean(this.params[`show_${k}`] ?? defaultShow);
    });

    const showComposite = this.params.show_composite !== false;
    const showMesa = Boolean(this.params.show_mesa_stochastic);
    const showCco = Boolean(this.params.show_cco);
    const zoomToRecent = Boolean(this.params.zoom_to_recent);
    const yAxisScale = String(this.params.y_axis_scale || 'symlog');
    const showCurrentPrice = this.params.show_current_price !== false;

    const mesaParams = showMesa
      ? {
          length1: Number(this.params.mesa_length1) || 50,
          length2: Number(this.params.mesa_length2) || 21,
          length3: Number(this.params.mesa_length3) || 14,
          length4: Number(this.params.mesa_length4) || 9,
          triggerLength: Number(this.params.mesa_trigger_length) || 2,
        }
      : {};

    const ccoParams = showCco
      ? {
          shortCycleLength: Number(this.params.cco_short_cycle_length) || 10,
          mediumCycleLength: Number(this.params.cco_medium_cycle_length) || 30,
          shortCycleMultiplier: Number(this.params.cco_short_cycle_multiplier) || 1.0,
          mediumCycleMultiplier: Number(this.params.cco_medium_cycle_multiplier) || 3.0,
        }
      : {};

    return {
      lookback,
      maxSyms,
      source,
      bandwidth,
      periods,
      compositeSelection,
      showPeriods,
      showComposite,
      showMesa,
      showCco,
      zoomToRecent,
      yAxisScale,
      showCurrentPrice,
      mesaParams,
      ccoParams,
    };
  }

  private determineDisplayRange(
    norm: NormalizedBar[],
    lookback: number | null,
    zoomToRecent: boolean
  ): NormalizedBar[] {
    if (zoomToRecent && norm.length > 300) {
      return norm.slice(-300);
    } else if (lookback && norm.length > lookback) {
      return norm.slice(-lookback);
    } else if (norm.length > 2000) {
      return norm.slice(-2000);
    }
    return norm;
  }

  private calculateEmas(
    closes: number[]
  ): [Array<number | null>, Array<number | null>, Array<number | null>] {
    const ema10 = closes.length >= 10 ? calculateEma(closes, 10).ema || [] : [];
    const ema30 = closes.length >= 30 ? calculateEma(closes, 30).ema || [] : [];
    const ema100 = closes.length >= 100 ? calculateEma(closes, 100).ema || [] : [];
    return [ema10, ema30, ema100];
  }

  protected async run(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    let bundle = inputs.ohlcv_bundle as Map<string, OHLCVBar[]> | undefined;
    const singleBundle = inputs.ohlcv as Map<string, OHLCVBar[]> | undefined;

    if (bundle && singleBundle) {
      bundle = new Map([...bundle, ...singleBundle]);
    } else if (singleBundle) {
      bundle = singleBundle;
    }

    if (!bundle || bundle.size === 0) {
      throw new Error("Provide either 'ohlcv_bundle' or 'ohlcv'");
    }

    const params = this.parseParams();

    const chartDataBySymbol: Record<string, HurstChartData> = {};
    const hurstDataBySymbol: Record<string, Record<string, unknown>> = {};
    const ohlcvBundleOutput = new Map<string, OHLCVBar[]>();
    const mesaDataBySymbol: Record<string, Record<string, unknown>> = {};
    const ccoDataBySymbol: Record<string, Record<string, unknown>> = {};

    const entries = Array.from(bundle.entries()).slice(0, params.maxSyms as number);

    for (const [symbolKey, bars] of entries) {
      if (!bars || bars.length < 10) {
        continue;
      }

      const fullNorm = normalizeBars(bars);
      const displayNorm = this.determineDisplayRange(
        fullNorm,
        params.lookback as number | null,
        params.zoomToRecent as boolean
      );

      if (displayNorm.length < 10) {
        continue;
      }

      // Extract price data
      const fullCloses = fullNorm.map((b) => b.close);
      const fullHighs = fullNorm.map((b) => b.high);
      const fullLows = fullNorm.map((b) => b.low);

      const displayCloses = displayNorm.map((b) => b.close);

      // Calculate Hurst oscillator
      try {
        const hurstResult = calculateHurstOscillator(
          fullCloses,
          fullHighs,
          fullLows,
          params.source as 'close' | 'hl2' | 'open' | 'high' | 'low',
          params.bandwidth as number,
          params.periods as Record<string, number>,
          params.compositeSelection as Record<string, boolean>
        );

        hurstDataBySymbol[symbolKey] = {
          bandpasses: hurstResult.bandpasses || {},
          composite: hurstResult.composite || [],
          peaks: hurstResult.peaks || [],
          troughs: hurstResult.troughs || [],
          wavelength: hurstResult.wavelength,
          amplitude: hurstResult.amplitude,
          timestamps: fullNorm.map((b) => b.timestamp),
        };

        ohlcvBundleOutput.set(symbolKey, bars);

        // Trim Hurst data to display range
        const startIdx = Math.max(0, fullNorm.length - displayNorm.length);
        const displayBandpasses: Record<string, Array<number | null>> = {};
        for (const [key, values] of Object.entries(hurstResult.bandpasses || {})) {
          displayBandpasses[key] = (values as Array<number | null>).slice(startIdx);
        }
        const displayComposite = (hurstResult.composite || []).slice(startIdx);

        // Calculate EMAs for display
        const [ema10, ema30, ema100] = this.calculateEmas(displayCloses);

        // Prepare chart data
        const chartData: HurstChartData = {
          symbol: symbolKey,
          bars: displayNorm,
          ema10,
          ema30,
          ema100,
          hurstData: {
            bandpasses: displayBandpasses,
            composite: displayComposite,
            peaks: hurstResult.peaks || [],
            troughs: hurstResult.troughs || [],
            wavelength: hurstResult.wavelength,
            amplitude: hurstResult.amplitude,
          },
        };

        // MESA Stochastic
        if (params.showMesa) {
          const mesaParams = params.mesaParams as {
            length1: number;
            length2: number;
            length3: number;
            length4: number;
          };

          try {
            const fullHl2 = fullHighs.map((h, i) => (h + fullLows[i]!) / 2);
            const mesaResult = calculateMesaStochasticMultiLength(
              fullHl2,
              mesaParams.length1,
              mesaParams.length2,
              mesaParams.length3,
              mesaParams.length4
            );

            mesaDataBySymbol[symbolKey] = {
              mesa1: mesaResult.mesa1,
              mesa2: mesaResult.mesa2,
              mesa3: mesaResult.mesa3,
              mesa4: mesaResult.mesa4,
              timestamps: fullNorm.map((b) => b.timestamp),
            };

            chartData.mesaData = {
              mesa1: (mesaResult.mesa1 || []).slice(startIdx),
              mesa2: (mesaResult.mesa2 || []).slice(startIdx),
              mesa3: (mesaResult.mesa3 || []).slice(startIdx),
              mesa4: (mesaResult.mesa4 || []).slice(startIdx),
            };
          } catch (error) {
            console.error(`Error calculating MESA Stochastic for ${symbolKey}: ${error}`);
          }
        }

        // CCO
        if (params.showCco) {
          const ccoParams = params.ccoParams as {
            shortCycleLength: number;
            mediumCycleLength: number;
            shortCycleMultiplier: number;
            mediumCycleMultiplier: number;
          };

          try {
            const ccoResult = calculateCco(
              fullCloses,
              fullHighs,
              fullLows,
              ccoParams.shortCycleLength,
              ccoParams.mediumCycleLength,
              ccoParams.shortCycleMultiplier,
              ccoParams.mediumCycleMultiplier
            );

            ccoDataBySymbol[symbolKey] = {
              fast_osc: ccoResult.fast_osc,
              slow_osc: ccoResult.slow_osc,
              timestamps: fullNorm.map((b) => b.timestamp),
            };

            chartData.ccoData = {
              fast_osc: (ccoResult.fast_osc || []).slice(startIdx),
              slow_osc: (ccoResult.slow_osc || []).slice(startIdx),
            };
          } catch (error) {
            console.error(`Error calculating CCO for ${symbolKey}: ${error}`);
          }
        }

        // Current price
        if (params.showCurrentPrice && displayNorm.length > 0) {
          chartData.currentPrice = displayNorm[displayNorm.length - 1]?.close;
        }

        chartDataBySymbol[symbolKey] = chartData;
      } catch (error) {
        console.error(`Error calculating Hurst for ${symbolKey}: ${error}`);
        continue;
      }
    }

    return {
      chart_data: chartDataBySymbol,
      hurst_data: hurstDataBySymbol,
      ohlcv_bundle: ohlcvBundleOutput,
      mesa_data: mesaDataBySymbol,
      cco_data: ccoDataBySymbol,
    };
  }
}
