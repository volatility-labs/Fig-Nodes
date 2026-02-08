// src/nodes/custom/polygon/polygon-batch-custom-bars-node.ts

import { Node, NodeCategory, ProgressState, port, type NodeDefinition } from '@sosa/core';
import { AssetSymbol, type OHLCVBar } from '../types';
import { RateLimiter } from '../rate-limiter';
import { fetchBars } from '../services/polygon-service';

/**
 * Fetches custom aggregate bars (OHLCV) for multiple symbols from Massive.com API in batch.
 * Outputs a bundle (Map of symbol.key to list of bars).
 *
 * Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
 * to use api.massive.com, but the API routes remain unchanged.
 */
export class PolygonBatchCustomBars extends Node {
  static definition: NodeDefinition = {
    inputs: { symbols: port('AssetSymbolList') },
    outputs: { ohlcv_bundle: port('OHLCVBundle') },
    ui: {},
    category: NodeCategory.MARKET,
    requiredCredentials: ['POLYGON_API_KEY'],

    params: [
      { name: 'multiplier', type: 'number', default: 1, min: 1, step: 1 },
      {
        name: 'timespan',
        type: 'combo',
        default: 'day',
        options: ['minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'],
      },
      {
        name: 'lookback_period',
        type: 'combo',
        default: '3 months',
        options: [
          '1 day',
          '3 days',
          '1 week',
          '2 weeks',
          '1 month',
          '2 months',
          '3 months',
          '4 months',
          '6 months',
          '9 months',
          '1 year',
          '18 months',
          '2 years',
          '3 years',
          '5 years',
          '10 years',
        ],
      },
      { name: 'adjusted', type: 'combo', default: true, options: [true, false] },
      { name: 'sort', type: 'combo', default: 'asc', options: ['asc', 'desc'] },
      { name: 'limit', type: 'number', default: 5000, min: 1, max: 50000, step: 1 },
    ],
  };

  private maxSafeConcurrency = 5;

  protected async run(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const symbols = (inputs.symbols as AssetSymbol[]) || [];

    if (symbols.length === 0) {
      return { ohlcv_bundle: new Map<string, OHLCVBar[]>() };
    }

    const apiKey = this.credentials.get('POLYGON_API_KEY');
    if (!apiKey) {
      throw new Error('Polygon API key not found in vault');
    }

    const maxConcurrentRaw = this.params.max_concurrent;
    const rateLimitRaw = this.params.rate_limit_per_second;

    const maxConcurrent =
      typeof maxConcurrentRaw === 'number' ? maxConcurrentRaw : 10;
    const rateLimit = typeof rateLimitRaw === 'number' ? rateLimitRaw : 95;

    const rateLimiter = new RateLimiter(rateLimit);
    const effectiveConcurrency = Math.min(maxConcurrent, this.maxSafeConcurrency);

    // Track statuses
    const statusTracker: Record<string, number> = {
      'real-time': 0,
      'delayed': 0,
      'market-closed': 0,
    };

    // Process symbols with concurrency control
    const bundle = new Map<string, OHLCVBar[]>();
    const total = symbols.length;
    let completed = 0;

    // Process in batches
    for (let i = 0; i < symbols.length; i += effectiveConcurrency) {
      if (this.cancelled) {
        break;
      }

      const batch = symbols.slice(i, i + effectiveConcurrency);

      const batchResults = await Promise.all(
        batch.map(async (sym) => {
          await rateLimiter.acquire();

          if (this.cancelled) {
            return null;
          }

          try {
            const [bars, metadata] = await fetchBars(sym, apiKey, this.params);

            if (bars.length > 0) {
              const dataStatus = metadata.data_status || 'unknown';
              if (dataStatus in statusTracker && statusTracker[dataStatus] !== undefined) {
                statusTracker[dataStatus] = (statusTracker[dataStatus] ?? 0) + 1;
              }

              // Determine current overall status
              let overallStatus = 'real-time';
              if ((statusTracker['market-closed'] ?? 0) > 0) {
                overallStatus = 'market-closed';
              } else if ((statusTracker['delayed'] ?? 0) > 0) {
                overallStatus = 'delayed';
              }

              // Send incremental status update
              this.emitProgress(
                ProgressState.UPDATE,
                undefined,
                'Fetching symbols...',
                { polygon_data_status: overallStatus }
              );
            }

            return { symbol: sym, bars };
          } catch (error) {
            console.error(`Error fetching bars for ${sym.ticker}:`, error);
            return null;
          }
        })
      );

      // Add results to bundle
      for (const result of batchResults) {
        if (result && result.bars.length > 0) {
          bundle.set(result.symbol.key, result.bars);
        }
      }

      completed += batch.length;
      const progressPct = (completed / total) * 100;
      this.progress(progressPct, `Fetched ${completed}/${total} symbols`);
    }

    // Determine overall status
    let overallStatus = 'real-time';
    if ((statusTracker['market-closed'] ?? 0) > 0) {
      overallStatus = 'market-closed';
    } else if ((statusTracker['delayed'] ?? 0) > 0) {
      overallStatus = 'delayed';
    }

    // Send final status update
    this.emitProgress(ProgressState.UPDATE, undefined, `Fetched ${bundle.size} symbols`, {
      polygon_data_status: overallStatus,
    });

    return { ohlcv_bundle: bundle };
  }
}
