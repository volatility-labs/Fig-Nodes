// src/nodes/custom/polygon/polygon-stock-universe-node.ts

import { Node, NodeCategory, port, type NodeDefinition } from '@sosa/core';
import { AssetClass, AssetSymbol, InstrumentType } from './types';

// ======================== Inlined from polygon-service.ts ========================

function isUSMarketOpen(): boolean {
  const now = new Date();
  const etFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
    weekday: 'short',
  });
  const parts = etFormatter.formatToParts(now);
  const weekday = parts.find((p) => p.type === 'weekday')?.value || '';
  const hour = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10);
  const minute = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10);
  if (['Sat', 'Sun'].includes(weekday)) {
    return false;
  }
  const currentMinutes = hour * 60 + minute;
  const marketOpenMinutes = 9 * 60 + 30;
  const marketCloseMinutes = 16 * 60;
  return currentMinutes >= marketOpenMinutes && currentMinutes <= marketCloseMinutes;
}

function massiveGetNumericFromDict(
  data: Record<string, unknown>,
  key: string,
  defaultValue: number
): number {
  const value = data[key];
  if (typeof value === 'number') {
    return value;
  }
  return defaultValue;
}

function massiveParseTickerForMarket(
  ticker: string,
  market: string
): [string, string | null] {
  if (!['crypto', 'fx'].includes(market) || !ticker.includes(':')) {
    return [ticker, null];
  }

  const parts = ticker.split(':', 2);
  const tick = parts[1];

  if (tick && tick.length > 3) {
    const possibleQuote = tick.slice(-3);
    if (/^[A-Z]{3}$/.test(possibleQuote)) {
      return [tick.slice(0, -3), possibleQuote];
    }
  }

  return [ticker, null];
}

async function massiveFetchTickerTypes(apiKey: string): Promise<Set<string>> {
  const url = 'https://api.massive.com/v3/reference/tickers/types';

  try {
    const response = await fetch(`${url}?apiKey=${apiKey}`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const results = data.results || [];
    const etfTypeCodes = new Set<string>();

    for (const item of results) {
      if (typeof item !== 'object' || item === null) continue;

      const code = typeof item.code === 'string' ? item.code : '';
      const description = typeof item.description === 'string' ? item.description.toLowerCase() : '';
      const typeCode = code.toLowerCase();

      if (
        typeCode.includes('etf') ||
        typeCode.includes('etn') ||
        typeCode.includes('etp') ||
        description.includes('exchange traded')
      ) {
        etfTypeCodes.add(code);
      }
    }

    return etfTypeCodes;
  } catch (error) {
    console.warn('Failed to fetch ticker types, using defaults:', error);
    return new Set(['ETF', 'ETN', 'ETP']);
  }
}

async function massiveFetchSnapshot(
  apiKey: string,
  locale: string,
  markets: string,
  market: string,
  tickers: string[] | null,
  includeOtc: boolean
): Promise<Record<string, unknown>[]> {
  const url = `https://api.massive.com/v2/snapshot/locale/${locale}/markets/${markets}/tickers`;

  const params = new URLSearchParams();
  params.set('apiKey', apiKey);

  if (includeOtc && ['stocks', 'otc'].includes(market)) {
    params.set('include_otc', 'true');
  }

  if (tickers && tickers.length > 0) {
    params.set('tickers', tickers.join(','));
  }

  const response = await fetch(`${url}?${params.toString()}`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch snapshot: ${response.status} - ${errorText}`);
  }

  const data = await response.json();
  const tickersRaw = data.tickers || [];

  if (!Array.isArray(tickersRaw)) {
    return [];
  }

  return tickersRaw.filter(
    (t: unknown): t is Record<string, unknown> =>
      typeof t === 'object' && t !== null
  );
}

async function massiveFetchFilteredTickers(
  apiKey: string,
  market: string,
  excludeEtfs: boolean,
  includeOtc: boolean = false,
  progressCallback?: (progress: number, text: string) => void
): Promise<Set<string>> {
  const refMarket = market === 'otc' ? 'otc' : market;
  const needsEtfFilter = ['stocks', 'otc'].includes(market);

  let etfTypes = new Set<string>();
  if (needsEtfFilter) {
    etfTypes = await massiveFetchTickerTypes(apiKey);
  }

  const tickerSet = new Set<string>();
  let nextUrl: string | null = 'https://api.massive.com/v3/reference/tickers';
  let pageCount = 0;

  const baseParams = new URLSearchParams();
  baseParams.set('active', 'true');
  baseParams.set('limit', '1000');
  baseParams.set('apiKey', apiKey);
  if (['stocks', 'otc', 'crypto', 'fx', 'indices'].includes(market)) {
    baseParams.set('market', refMarket);
  }

  while (nextUrl) {
    let response: Response;

    if (pageCount > 0) {
      const separator = nextUrl.includes('?') ? '&' : '?';
      response = await fetch(`${nextUrl}${separator}apiKey=${apiKey}`);
    } else {
      response = await fetch(`${nextUrl}?${baseParams.toString()}`);
    }

    if (!response.ok) {
      console.warn(`Failed to fetch ticker metadata page ${pageCount + 1}: ${response.status}`);
      break;
    }

    const data = await response.json();
    const results = data.results || [];

    for (const item of results) {
      if (typeof item !== 'object' || item === null) continue;

      const tickerRaw = item.ticker;
      if (typeof tickerRaw !== 'string' || !tickerRaw) continue;

      const ticker = tickerRaw;
      const tickerType = typeof item.type === 'string' ? item.type : '';
      const tickerMarket = typeof item.market === 'string' ? item.market : '';

      if (etfTypes.size > 0) {
        const isEtf =
          etfTypes.has(tickerType) ||
          tickerType.toLowerCase().includes('etf') ||
          tickerType.toLowerCase().includes('etn') ||
          tickerType.toLowerCase().includes('etp') ||
          tickerMarket === 'etp';

        if (excludeEtfs && isEtf) continue;
        if (!excludeEtfs && !isEtf) continue;
      }

      if (!includeOtc) {
        if (tickerMarket === 'otc' || tickerMarket === 'OTC') {
          continue;
        }
      }

      tickerSet.add(ticker);
    }

    nextUrl = data.next_url || null;
    pageCount++;

    if (pageCount % 5 === 0 && progressCallback) {
      progressCallback(
        5.0 + Math.min(pageCount * 20, 25),
        `Fetched metadata for ${tickerSet.size} tickers (page ${pageCount})...`
      );
    }
  }

  return tickerSet;
}

// ======================== End inlined code ========================

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
        default: 0,
        label: 'Min Change',
        unit: '%',
        description: 'Minimum daily percentage change (e.g., 5 for 5%)',
        step: 0.01,
      },
      {
        name: 'max_change_perc',
        type: 'number',
        default: 999,
        label: 'Max Change',
        unit: '%',
        description: 'Maximum daily percentage change (e.g., 10 for 10%)',
        step: 0.01,
      },
      {
        name: 'min_volume',
        type: 'number',
        default: 0,
        label: 'Min Volume',
        unit: 'shares/contracts',
        description: 'Minimum daily trading volume in shares or contracts',
      },
      {
        name: 'min_price',
        type: 'number',
        default: 0,
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
