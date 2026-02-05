// src/nodes/custom/polygon/polygon-crypto-universe-node.ts
// Translated from: nodes/custom/polygon/polygon_crypto_universe_node.py

import { Base } from '../../base/base-node';
import { getVault } from '../../../core/api-key-vault';
import {
  AssetClass,
  AssetSymbol,
  InstrumentType,
  NodeCategory,
  NodeUIConfig,
  ParamMeta,
  getType,
} from '../../../core/types';
import {
  massiveBuildSnapshotTickers,
  massiveFetchSnapshot,
  massiveGetNumericFromDict,
  massiveParseTickerForMarket,
} from '../../../services/polygon-service';

interface FilterParams {
  min_change_perc: number | null;
  max_change_perc: number | null;
  min_volume: number | null;
  min_price: number | null;
  max_price: number | null;
  max_snapshot_delay_minutes: number | null;
}

interface TickerData {
  price: number;
  volume: number;
  change_perc: number | null;
  data_source: string;
}

/**
 * A node that fetches crypto symbols from the Massive.com API (formerly Polygon.io)
 * and filters them based on the provided parameters.
 *
 * Endpoint: https://api.massive.com/v2/snapshot/locale/global/markets/crypto/tickers
 *
 * Crypto markets operate 24/7, always using current intraday data from the 'day' bar.
 */
export class PolygonCryptoUniverse extends Base {
  static inputs = { filter_symbols: getType('AssetSymbolList') };
  static outputs = { symbols: getType('AssetSymbolList') };
  static required_keys = ['POLYGON_API_KEY'];
  static uiConfig: NodeUIConfig = {
    size: [280, 140],
    displayResults: false,
    resizable: true,
  };

  static paramsMeta: ParamMeta[] = [
    {
      name: 'min_change_perc',
      type: 'number',
      default: undefined,
      label: 'Min Change',
      unit: '%',
      description: 'Minimum daily percentage change (e.g., 5 for 5%)',
      step: 0.01,
    },
    {
      name: 'max_change_perc',
      type: 'number',
      default: undefined,
      label: 'Max Change',
      unit: '%',
      description: 'Maximum daily percentage change (e.g., 10 for 10%)',
      step: 0.01,
    },
    {
      name: 'min_volume',
      type: 'number',
      default: undefined,
      label: 'Min Volume',
      unit: 'shares/contracts',
      description: 'Minimum daily trading volume',
    },
    {
      name: 'min_price',
      type: 'number',
      default: undefined,
      label: 'Min Price',
      unit: 'USD',
      description: 'Minimum closing price in USD',
    },
    {
      name: 'max_price',
      type: 'number',
      default: 1000000,
      label: 'Max Price',
      unit: 'USD',
      description: 'Maximum closing price in USD',
    },
    {
      name: 'max_snapshot_delay_minutes',
      type: 'combo',
      default: '5min',
      label: 'Max Snapshot Delay',
      description:
        "Maximum allowed delay in snapshot 'updated' timestamp; None = no filter",
      options: ['None (no filter)', '5min', '15min', '120min'],
    },
  ];

  static defaultParams = {};

  static CATEGORY = NodeCategory.MARKET;

  protected async executeImpl(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    try {
      const filterSymbolsRaw = inputs.filter_symbols;
      const filterSymbols: AssetSymbol[] = Array.isArray(filterSymbolsRaw) ? filterSymbolsRaw : [];
      const symbols = await this.fetchSymbols(filterSymbols.length > 0 ? filterSymbols : null);
      return { symbols };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error(`PolygonCryptoUniverse node ${this.id} failed: ${errorMsg}`);
      throw error;
    }
  }

  private async fetchSymbols(
    filterSymbols: AssetSymbol[] | null
  ): Promise<AssetSymbol[]> {
    const apiKey = getVault().get('POLYGON_API_KEY');
    if (!apiKey) {
      throw new Error('POLYGON_API_KEY is required but not set in vault');
    }

    const market = 'crypto';
    const locale = 'global';
    const markets = 'crypto';

    let filterTickerStrings: string[] | null = null;
    if (filterSymbols && filterSymbols.length > 0) {
      filterTickerStrings = massiveBuildSnapshotTickers(filterSymbols);
    }

    const tickersData = await massiveFetchSnapshot(
      apiKey,
      locale,
      markets,
      market,
      filterTickerStrings,
      false
    );

    const filterParams = this.extractFilterParams();
    this.validateFilterParams(filterParams);

    const symbols = this.processTickers(tickersData, market, filterParams);

    return symbols;
  }

  private getNumericParam(paramName: string): number | null {
    const paramRaw = this.params[paramName];
    return typeof paramRaw === 'number' ? paramRaw : null;
  }

  private extractFilterParams(): FilterParams {
    // Parse max_snapshot_delay_minutes from combo string
    const delayRaw = this.params.max_snapshot_delay_minutes;
    let maxSnapshotDelayMinutes: number | null = null;

    if (delayRaw === 'None (no filter)') {
      maxSnapshotDelayMinutes = null;
    } else if (typeof delayRaw === 'string' && delayRaw.endsWith('min')) {
      const parsed = parseFloat(delayRaw.slice(0, -3));
      if (!isNaN(parsed)) {
        maxSnapshotDelayMinutes = parsed;
      }
    } else if (typeof delayRaw === 'number') {
      maxSnapshotDelayMinutes = delayRaw;
    }

    return {
      min_change_perc: this.getNumericParam('min_change_perc'),
      max_change_perc: this.getNumericParam('max_change_perc'),
      min_volume: this.getNumericParam('min_volume'),
      min_price: this.getNumericParam('min_price'),
      max_price: this.getNumericParam('max_price'),
      max_snapshot_delay_minutes: maxSnapshotDelayMinutes,
    };
  }

  private validateFilterParams(filterParams: FilterParams): void {
    const { min_change_perc, max_change_perc } = filterParams;
    if (
      min_change_perc !== null &&
      max_change_perc !== null &&
      min_change_perc > max_change_perc
    ) {
      throw new Error('min_change_perc cannot be greater than max_change_perc');
    }
  }

  private processTickers(
    tickersData: Record<string, unknown>[],
    market: string,
    filterParams: FilterParams
  ): AssetSymbol[] {
    const symbols: AssetSymbol[] = [];
    const totalTickers = tickersData.length;
    let filteredStale = 0;

    const currentUtc = Date.now();

    for (const tickerItem of tickersData) {
      const ticker = this.extractTicker(tickerItem);
      if (!ticker) continue;

      // Filter: Only include USD-quoted crypto pairs
      if (!this.isUsdQuoted(ticker, market)) {
        continue;
      }

      const tickerData = this.extractTickerData(tickerItem, market);
      if (!tickerData) continue;

      // Check snapshot update delay if filter enabled
      const maxDelayMin = filterParams.max_snapshot_delay_minutes;
      if (maxDelayMin !== null) {
        const updatedRaw = tickerItem.updated;
        if (typeof updatedRaw === 'number') {
          const updatedUtc = this.parseTimestampFlex(updatedRaw);
          if (updatedUtc === null) {
            filteredStale++;
            console.warn(`Filtered ticker ${ticker} due to invalid 'updated' timestamp`);
            continue;
          }
          const delayMinutes = (currentUtc - updatedUtc) / 60000;
          if (delayMinutes > maxDelayMin) {
            filteredStale++;
            console.info(
              `Filtered stale snapshot for ${ticker}: ${delayMinutes.toFixed(1)} min delay`
            );
            continue;
          }
        } else {
          filteredStale++;
          console.warn(`Filtered ticker ${ticker} due to missing 'updated' timestamp`);
          continue;
        }
      }

      if (!this.passesFilters(tickerData, filterParams)) {
        continue;
      }

      const symbol = this.createAssetSymbol(ticker, tickerItem, market, tickerData);
      symbols.push(symbol);
    }

    // Update progress with stale filter info if applied
    const staleMsg = filteredStale > 0 ? `; filtered ${filteredStale} stale snapshots` : '';
    this.reportProgress(
      95.0,
      `Completed: ${symbols.length} symbols from ${totalTickers} tickers${staleMsg}`
    );

    return symbols;
  }

  private extractTicker(tickerItem: Record<string, unknown>): string | null {
    const tickerValue = tickerItem.ticker;
    return typeof tickerValue === 'string' ? tickerValue : null;
  }

  private isUsdQuoted(ticker: string, market: string): boolean {
    if (market !== 'crypto') {
      return true;
    }

    const [, quoteCurrency] = massiveParseTickerForMarket(ticker, market);
    return quoteCurrency === 'USD';
  }

  private extractTickerData(
    tickerItem: Record<string, unknown>,
    _market: string
  ): TickerData | null {
    const dayValue = tickerItem.day;
    const day: Record<string, unknown> =
      typeof dayValue === 'object' && dayValue !== null
        ? (dayValue as Record<string, unknown>)
        : {};

    // Extract todaysChangePerc
    const changePercRaw = tickerItem.todaysChangePerc;
    const todaysChangePerc =
      typeof changePercRaw === 'number' ? changePercRaw : null;

    // Crypto uses current day data (24/7 market)
    const price = massiveGetNumericFromDict(day, 'c', 0.0);
    const volume = massiveGetNumericFromDict(day, 'v', 0.0);
    const changePerc = todaysChangePerc;
    const dataSource = 'day';

    if (price <= 0) {
      const tickerLog = tickerItem.ticker;
      console.warn(
        `Invalid price (<=0) for ticker ${typeof tickerLog === 'string' ? tickerLog : '(unknown)'}`
      );
      return null;
    }

    return {
      price,
      volume,
      change_perc: changePerc,
      data_source: dataSource,
    };
  }

  private passesFilters(tickerData: TickerData, filterParams: FilterParams): boolean {
    const { price, volume, change_perc } = tickerData;
    const { min_change_perc, max_change_perc, min_volume, min_price, max_price } =
      filterParams;

    if (change_perc !== null) {
      if (min_change_perc !== null && change_perc < min_change_perc) {
        return false;
      }
      if (max_change_perc !== null && change_perc > max_change_perc) {
        return false;
      }
    }

    if (min_volume !== null && volume < min_volume) {
      return false;
    }

    if (min_price !== null && price < min_price) {
      return false;
    }

    if (max_price !== null && price > max_price) {
      return false;
    }

    return true;
  }

  private createAssetSymbol(
    ticker: string,
    tickerItem: Record<string, unknown>,
    market: string,
    tickerData: TickerData
  ): AssetSymbol {
    const [baseTicker, quoteCurrency] = massiveParseTickerForMarket(ticker, market);
    const assetClass = AssetClass.CRYPTO;

    const dataSource = tickerData.data_source;
    const changeAvailable = tickerData.change_perc !== null;

    const metadata = {
      original_ticker: ticker,
      snapshot: tickerItem,
      market,
      data_source: dataSource,
      change_available: changeAvailable,
    };

    return new AssetSymbol(
      baseTicker,
      assetClass,
      quoteCurrency ?? undefined,
      InstrumentType.SPOT,
      metadata
    );
  }

  /**
   * Parse timestamp with auto-detection of unit (s, ms, ns).
   */
  private parseTimestampFlex(ts: number): number | null {
    if (ts <= 0) {
      return null;
    }

    const tsStr = String(ts);
    const digitCount = tsStr.length;

    // Try to determine unit based on digit count
    let divisor: number;
    if (digitCount < 11) {
      divisor = 1000; // seconds -> ms
    } else if (digitCount >= 11 && digitCount <= 14) {
      divisor = 1; // already ms
    } else if (digitCount >= 15 && digitCount <= 19) {
      divisor = 1000000; // ns -> ms
    } else {
      divisor = 1; // default to ms
    }

    const timestampMs = ts / divisor;
    const date = new Date(timestampMs);

    // Validate: Unix epoch range (1970-2100)
    const year = date.getUTCFullYear();
    if (year >= 1970 && year <= 2100) {
      return timestampMs;
    }

    // Try other units
    const candidates = [
      { unit: 'ns', divisor: 1000000 },
      { unit: 'ms', divisor: 1 },
      { unit: 's', divisor: 0.001 },
    ];

    for (const { divisor: d } of candidates) {
      const tryMs = ts / d;
      const tryDate = new Date(tryMs);
      const tryYear = tryDate.getUTCFullYear();
      if (tryYear >= 1970 && tryYear <= 2100) {
        return tryMs;
      }
    }

    return null;
  }
}
