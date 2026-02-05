// src/nodes/core/market/indicators/orb-indicator-node.ts
// Translated from: nodes/core/market/indicators/orb_indicator_node.py

import { BaseIndicator } from './base/base-indicator-node';
import {
  IndicatorType,
  createIndicatorResult,
  createIndicatorValue,
  getType,
  AssetSymbol,
} from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  NodeInputs,
  NodeOutputs,
  IndicatorValue,
  NodeUIConfig,
} from '../../../../core/types';
import { calculateOrb } from '../../../../services/indicator-calculators';
import { fetchBars } from '../../../../services/polygon-service';
import { APIKeyVault } from '../../../../core/api-key-vault';

/**
 * Computes the ORB (Opening Range Breakout) indicator for a single asset.
 * Outputs relative volume (RVOL) and direction (bullish/bearish/doji).
 */
export class OrbIndicator extends BaseIndicator {
  static uiConfig: NodeUIConfig = {
    size: [220, 100],
    displayResults: false,
    resizable: false,
  };

  static override inputs: Record<string, unknown> = {
    symbol: getType('AssetSymbol'),
  };

  static override outputs: Record<string, unknown> = {
    results: Array, // list[IndicatorResult]
  };

  static override defaultParams: DefaultParams = {
    or_minutes: 5,
    avg_period: 14,
  };

  static override paramsMeta: ParamMeta[] = [
    { name: 'or_minutes', type: 'number', default: 5, min: 1, step: 1 },
    { name: 'avg_period', type: 'number', default: 14, min: 1, step: 1 },
  ];

  protected mapToIndicatorValue(
    _indType: IndicatorType,
    _raw: Record<string, unknown>
  ): IndicatorValue {
    // ORB node uses its own _executeImpl path and does not rely on base mapping.
    return createIndicatorValue({ single: NaN });
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    console.log('='.repeat(80));
    console.log('ORB INDICATOR: Starting execution');
    console.log('='.repeat(80));

    const symbolRaw = inputs.symbol;
    if (!symbolRaw || !(symbolRaw instanceof AssetSymbol)) {
      console.warn('No symbol provided to ORB indicator');
      return { results: [] };
    }
    const symbol = symbolRaw;

    console.log(`ORB INDICATOR: Processing symbol ${symbol.ticker}`);

    // Get API key
    const vault = APIKeyVault.getInstance();
    const apiKey = vault.get('POLYGON_API_KEY');
    if (!apiKey || !apiKey.trim()) {
      console.error('Polygon API key not found in vault');
      return { results: [] };
    }

    // Get parameters
    const avgPeriodRaw = this.params.avg_period ?? 14;
    const orMinutesRaw = this.params.or_minutes ?? 5;

    // Type guards
    if (typeof avgPeriodRaw !== 'number') {
      console.error(`avg_period must be a number, got ${typeof avgPeriodRaw}`);
      return { results: [] };
    }

    if (typeof orMinutesRaw !== 'number') {
      console.error(`or_minutes must be a number, got ${typeof orMinutesRaw}`);
      return { results: [] };
    }

    const avgPeriod = Math.floor(avgPeriodRaw);
    const orMinutes = Math.floor(orMinutesRaw);

    // Fetch 5-min bars for last avg_period + 1 days
    const fetchParams = {
      multiplier: 5,
      timespan: 'minute' as const,
      lookback_period: `${avgPeriod + 1} days`,
      adjusted: true,
      sort: 'asc' as const,
      limit: 50000,
    };

    try {
      console.log(`ORB INDICATOR: Fetching bars with params:`, fetchParams);

      const [bars] = await fetchBars(symbol, apiKey, fetchParams);

      if (!bars || bars.length === 0) {
        console.log(`ORB INDICATOR: No bars fetched for ${symbol.ticker}`);
        console.warn(`No bars fetched for ${symbol.ticker}`);
        return { results: [] };
      }

      console.log(`ORB INDICATOR: Fetched ${bars.length} bars for ${symbol.ticker}`);
      console.log(
        `ORB INDICATOR: First bar timestamp: ${bars[0].timestamp}, last bar timestamp: ${bars[bars.length - 1].timestamp}`
      );

      // Use the calculator to calculate ORB indicators
      console.log('ORB INDICATOR: Calling calculateOrb...');
      const result = calculateOrb(bars, symbol, orMinutes, avgPeriod);
      console.log(`ORB INDICATOR: Got result:`, result);

      if (result.error) {
        console.warn(`ORB calculation error for ${symbol.ticker}: ${result.error}`);
        return { results: [] };
      }

      const relVolRaw = result.rel_vol;
      const direction = result.direction ?? 'doji';

      // Type guard for rel_vol
      if (typeof relVolRaw !== 'number') {
        console.error(`rel_vol must be a number, got ${typeof relVolRaw}`);
        return { results: [] };
      }

      const relVol = relVolRaw;

      // Get the latest timestamp from bars for the result
      const latestTimestamp = bars.length > 0 ? bars[bars.length - 1].timestamp : 0;

      // Return values in lines (for RVOL) and series (for direction)
      const values = createIndicatorValue({
        single: 0,
        lines: { rel_vol: relVol },
        series: [{ direction }],
      });

      const indicatorResult = createIndicatorResult({
        indicatorType: IndicatorType.ORB,
        timestamp: latestTimestamp,
        values: values,
        params: this.params,
      });

      return { results: [indicatorResult] };
    } catch (error) {
      console.error(`Error calculating ORB for ${symbol.ticker}:`, error);
      return { results: [] };
    }
  }
}
