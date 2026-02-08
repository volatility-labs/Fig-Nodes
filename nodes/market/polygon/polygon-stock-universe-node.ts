// src/nodes/custom/polygon/polygon-stock-universe-node.ts

import { Node, NodeCategory, port, type NodeDefinition } from '@sosa/core';
import { AssetClass, AssetSymbol, InstrumentType } from '../types';
import {
  isUSMarketOpen,
  massiveFetchFilteredTickers,
  massiveFetchSnapshot,
  massiveGetNumericFromDict,
  massiveParseTickerForMarket,
} from '../services/polygon-service';

interface FilterParams {
  min_change_perc: number | null;
  max_change_perc: number | null;
  min_volume: number | null;
  min_price: number | null;
  max_price: number | null;
}

interface TickerData {
  price: number;
  volume: number;
  change_perc: number | null;
  data_source: string;
}

/**
 * A node that fetches stock symbols from the Massive.com API (formerly Polygon.io)
 * and filters them based on the provided parameters.
 *
 * Endpoint: https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers
 */
export class PolygonStockUniverse extends Node {
  static definition: NodeDefinition = {
    inputs: {},
    outputs: { symbols: port('AssetSymbolList') },
    ui: {},
    category: NodeCategory.MARKET,
    requiredCredentials: ['POLYGON_API_KEY'],

    params: [
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
        description: 'Minimum daily trading volume in shares or contracts',
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
        name: 'include_otc',
        type: 'combo',
        default: false,
        options: [true, false],
        label: 'Include OTC',
        description: 'Include over-the-counter symbols',
      },
      {
        name: 'exclude_etfs',
        type: 'combo',
        default: true,
        options: [true, false],
        label: 'Exclude ETFs',
        description:
          'If true, filters out ETFs (keeps only stocks). If false, keeps only ETFs.',
      },
      {
        name: 'data_day',
        type: 'combo',
        default: 'auto',
        options: ['auto', 'today', 'prev_day'],
        label: 'Data Day',
        description:
          'Use intraday (today), previous day, or auto-select based on US market hours',
      },
    ],
  };

  protected async run(
    _inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    try {
      const symbols = await this.fetchSymbols();
      return { symbols };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error(`PolygonStockUniverse node ${this.nodeId} failed: ${errorMsg}`);
      throw error;
    }
  }

  private async fetchSymbols(): Promise<AssetSymbol[]> {
    const apiKey = this.credentials.get('POLYGON_API_KEY');
    if (!apiKey) {
      throw new Error('POLYGON_API_KEY is required but not configured');
    }

    const market = 'stocks';
    const locale = 'us';
    const markets = 'stocks';
    const excludeEtfs = this.getBoolParam('exclude_etfs', true);
    const includeOtc = this.getBoolParam('include_otc', false);

    const filteredTickerSet = await massiveFetchFilteredTickers(
      apiKey,
      market,
      excludeEtfs,
      includeOtc,
      (pct, text) => this.progress(pct, text)
    );

    const tickersData = await massiveFetchSnapshot(
      apiKey,
      locale,
      markets,
      market,
      null,
      includeOtc
    );

    const filterParams = this.extractFilterParams();
    this.validateFilterParams(filterParams);

    const symbols = this.processTickers(tickersData, market, filteredTickerSet, filterParams);

    return symbols;
  }

  private getBoolParam(paramName: string, defaultValue: boolean): boolean {
    const paramRaw = this.params[paramName];
    return typeof paramRaw === 'boolean' ? paramRaw : defaultValue;
  }

  private getNumericParam(paramName: string): number | null {
    const paramRaw = this.params[paramName];
    return typeof paramRaw === 'number' ? paramRaw : null;
  }

  private extractFilterParams(): FilterParams {
    return {
      min_change_perc: this.getNumericParam('min_change_perc'),
      max_change_perc: this.getNumericParam('max_change_perc'),
      min_volume: this.getNumericParam('min_volume'),
      min_price: this.getNumericParam('min_price'),
      max_price: this.getNumericParam('max_price'),
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
    filteredTickerSet: Set<string> | null,
    filterParams: FilterParams
  ): AssetSymbol[] {
    const symbols: AssetSymbol[] = [];
    const totalTickers = tickersData.length;

    for (const tickerItem of tickersData) {
      const ticker = this.extractTicker(tickerItem);
      if (!ticker) continue;

      if (filteredTickerSet !== null && !filteredTickerSet.has(ticker)) {
        continue;
      }

      const tickerData = this.extractTickerData(tickerItem, market);
      if (!tickerData) continue;

      if (!this.passesFilters(tickerData, filterParams)) {
        continue;
      }

      const symbol = this.createAssetSymbol(ticker, tickerItem, market, tickerData);
      symbols.push(symbol);
    }

    this.progress(100.0, `Completed: ${symbols.length} symbols from ${totalTickers} tickers`);
    return symbols;
  }

  private extractTicker(tickerItem: Record<string, unknown>): string | null {
    const tickerValue = tickerItem.ticker;
    return typeof tickerValue === 'string' ? tickerValue : null;
  }

  private extractTickerData(
    tickerItem: Record<string, unknown>,
    _market: string
  ): TickerData | null {
    const dayValue = tickerItem.day;
    const prevDayValue = tickerItem.prevDay;

    const day: Record<string, unknown> =
      typeof dayValue === 'object' && dayValue !== null
        ? (dayValue as Record<string, unknown>)
        : {};

    const prevDay: Record<string, unknown> =
      typeof prevDayValue === 'object' && prevDayValue !== null
        ? (prevDayValue as Record<string, unknown>)
        : {};

    const marketIsOpen = isUSMarketOpen();
    const dataDayParamRaw = this.params.data_day;
    const dataDayParam =
      typeof dataDayParamRaw === 'string' ? dataDayParamRaw : 'auto';

    let usePrevDay: boolean;
    if (dataDayParam === 'today') {
      usePrevDay = false;
    } else if (dataDayParam === 'prev_day') {
      usePrevDay = true;
    } else {
      // auto
      usePrevDay = !marketIsOpen;
      if (usePrevDay && !marketIsOpen) {
        usePrevDay = false;
      }
    }

    // Extract todaysChangePerc
    const changePercRaw = tickerItem.todaysChangePerc;
    const todaysChangePerc =
      typeof changePercRaw === 'number' ? changePercRaw : null;

    let price: number;
    let volume: number;
    let changePerc: number | null;
    let dataSource: string;

    if (usePrevDay) {
      price = massiveGetNumericFromDict(prevDay, 'c', 0.0);
      volume = massiveGetNumericFromDict(prevDay, 'v', 0.0);
      const prevOpen = massiveGetNumericFromDict(prevDay, 'o', 0.0);
      if (prevOpen > 0) {
        changePerc = ((price - prevOpen) / prevOpen) * 100.0;
      } else {
        changePerc = null;
      }
      dataSource = 'prevDay_intra';
    } else {
      price = massiveGetNumericFromDict(day, 'c', 0.0);
      volume = massiveGetNumericFromDict(day, 'v', 0.0);
      changePerc = todaysChangePerc;
      dataSource = 'day';
      if (dataDayParam === 'auto' && !marketIsOpen) {
        dataSource = 'lastTradingDay';
      } else if (dataDayParam === 'today' && !marketIsOpen) {
        dataSource = 'lastTradingDay';
      }
    }

    if (price <= 0) {
      console.warn(`Invalid price (<=0) for ticker ${tickerItem.ticker}`);
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
    const assetClass = AssetClass.STOCKS;

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
}
