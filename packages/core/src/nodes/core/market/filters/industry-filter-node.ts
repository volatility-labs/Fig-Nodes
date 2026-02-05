// src/nodes/core/market/filters/industry-filter-node.ts
// Translated from: nodes/core/market/filters/industry_filter_node.py

import { BaseFilter } from './base/base-filter-node';
import { AssetSymbol } from '../../../../core/types';
import type {
  ParamMeta,
  DefaultParams,
  OHLCVBar,
  NodeInputs,
  NodeOutputs,
  OHLCVBundle,
  NodeUIConfig,
} from '../../../../core/types';
import { APIKeyVault } from '../../../../core/api-key-vault';

/**
 * Filters OHLCV bundles based on company industry from Polygon API Ticker Overview API.
 * Uses sic_description for matching (e.g., 'Computer Programming Services').
 *
 * Requires Polygon API key (POLYGON_API_KEY) from vault.
 */
export class IndustryFilter extends BaseFilter {
  private allowedIndustries: string[] = [];

  static override defaultParams: DefaultParams = {
    allowed_industries: [],
    date: null,
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'allowed_industries',
      type: 'combo',
      default: [],
      options: [],
      description: 'List of industry sic_description strings to match (exact, case-insensitive)',
    },
    {
      name: 'date',
      type: 'text',
      default: null,
      description: 'Optional date for historical overview (YYYY-MM-DD)',
    },
  ];

  static uiConfig: NodeUIConfig = {
    size: [220, 100],
    displayResults: false,
    resizable: false,
  };

  constructor(
    id: number,
    params: Record<string, unknown> = {},
    graphContext?: Record<string, unknown>
  ) {
    super(id, params, graphContext ?? {});
    const allowedIndustriesParam = this.params.allowed_industries ?? [];
    if (Array.isArray(allowedIndustriesParam)) {
      this.allowedIndustries = allowedIndustriesParam.map((ind) =>
        String(ind).toLowerCase()
      );
    } else {
      this.allowedIndustries = [];
    }
  }

  private async fetchIndustry(symbol: AssetSymbol, apiKey: string): Promise<string> {
    const url = new URL(`https://api.polygon.io/v3/reference/tickers/${symbol.ticker}`);
    url.searchParams.set('apiKey', apiKey);

    const dateValue = this.params.date;
    if (dateValue && typeof dateValue === 'string') {
      url.searchParams.set('date', dateValue);
    }

    try {
      const response = await fetch(url.toString());
      if (!response.ok) {
        console.warn(`Failed to fetch industry for ${symbol.ticker}: ${response.status}`);
        return '';
      }

      const data = await response.json();
      const sicDescription = data?.results?.sic_description ?? '';
      return String(sicDescription).toLowerCase();
    } catch (error) {
      console.warn(`Failed to fetch industry for ${symbol.ticker}:`, error);
      return '';
    }
  }

  protected override async filterConditionAsync(
    symbol: AssetSymbol,
    _ohlcvData: OHLCVBar[]
  ): Promise<boolean> {
    const vault = APIKeyVault.getInstance();
    const apiKey = vault.get('POLYGON_API_KEY');
    if (!apiKey) {
      throw new Error('Polygon API key (POLYGON_API_KEY) not found in vault');
    }

    const industry = await this.fetchIndustry(symbol, apiKey);
    return this.allowedIndustries.includes(industry);
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const ohlcvBundle = (inputs.ohlcv_bundle as OHLCVBundle) ?? new Map();

    if (ohlcvBundle.size === 0) {
      return { filtered_ohlcv_bundle: new Map() };
    }

    const filteredBundle: OHLCVBundle = new Map();

    for (const [symbol, ohlcvData] of ohlcvBundle) {
      if (!ohlcvData || ohlcvData.length === 0) {
        continue;
      }

      try {
        if (await this.filterConditionAsync(symbol, ohlcvData)) {
          filteredBundle.set(symbol, ohlcvData);
        }
      } catch (error) {
        console.warn(`Failed to process filter for ${symbol.ticker}:`, error);
        continue;
      }
    }

    return { filtered_ohlcv_bundle: filteredBundle };
  }
}
