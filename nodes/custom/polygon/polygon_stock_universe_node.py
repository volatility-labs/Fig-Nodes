import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetClass, AssetSymbol, get_type
from nodes.base.base_node import Base
from services.polygon_service import (
    massive_build_snapshot_tickers,
    massive_fetch_snapshot,
    massive_fetch_ticker_types,
    massive_get_numeric_from_dict,
    massive_parse_ticker_for_market,
)
from services.time_utils import is_us_market_open

logger = logging.getLogger(__name__)


class PolygonStockUniverse(Base):
    """
    A node that fetches stock symbols from the Massive.com API (formerly Polygon.io) and filters them
    based on the provided parameters.

    Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
    to use api.massive.com, but the API routes remain unchanged.

    Endpoint: https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers
    """

    inputs = {"filter_symbols": get_type("AssetSymbolList") | None}
    outputs = {"symbols": get_type("AssetSymbolList")}
    required_keys = ["POLYGON_API_KEY"]
    params_meta = [
        {
            "name": "min_change_perc",
            "type": "number",
            "default": None,
            "label": "Min Change",
            "unit": "%",
            "description": "Minimum daily percentage change (e.g., 5 for 5%)",
            "step": 0.01,
        },
        {
            "name": "max_change_perc",
            "type": "number",
            "default": None,
            "label": "Max Change",
            "unit": "%",
            "description": "Maximum daily percentage change (e.g., 10 for 10%)",
            "step": 0.01,
        },
        {
            "name": "min_volume",
            "type": "number",
            "default": None,
            "label": "Min Volume",
            "unit": "shares/contracts",
            "description": "Minimum daily trading volume in shares or contracts",
        },
        {
            "name": "min_price",
            "type": "number",
            "default": None,
            "label": "Min Price",
            "unit": "USD",
            "description": "Minimum closing price in USD",
        },
        {
            "name": "max_price",
            "type": "number",
            "default": 1000000,
            "label": "Max Price",
            "unit": "USD",
            "description": "Maximum closing price in USD",
        },
        {
            "name": "market_filter",
            "type": "combo",
            "default": "stocks_only",
            "options": ["stocks_only", "include_otc", "otc_only", "all"],
            "label": "Market Filter",
            "description": "stocks_only: Regular exchange stocks only | include_otc: Regular + OTC | otc_only: Only OTC stocks | all: Everything",
        },
        {
            "name": "asset_type_filter",
            "type": "combo",
            "default": "stocks_no_etf",
            "options": ["stocks_no_etf", "etf_only", "all"],
            "label": "Asset Type",
            "description": "stocks_no_etf: Regular stocks (no ETFs) | etf_only: Only ETFs | all: Stocks + ETFs",
        },
        {
            "name": "data_day",
            "type": "combo",
            "default": "auto",
            "options": ["auto", "today", "prev_day"],
            "label": "Data Day",
            "description": "Use intraday (today), previous day, or auto-select based on US market hours",
        },
    ]
    default_params = {}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        try:
            filter_symbols = self.collect_multi_input("filter_symbols", inputs)
            symbols = await self._fetch_symbols(filter_symbols)
            return {"symbols": symbols}
        except Exception as e:
            logger.error(f"PolygonStockUniverse node {self.id} failed: {str(e)}", exc_info=True)
            raise

    async def _fetch_symbols(
        self, filter_symbols: list[AssetSymbol] | None = None
    ) -> list[AssetSymbol]:
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("POLYGON_API_KEY is required but not set in vault")

        market = "stocks"
        locale, markets = "us", "stocks"
        
        # Get new filtering parameters
        market_filter = self.params.get("market_filter", "stocks_only")
        asset_type_filter = self.params.get("asset_type_filter", "stocks_no_etf")
        
        # Determine if we should fetch OTC data from snapshot API
        include_otc_in_snapshot = market_filter in ["include_otc", "otc_only", "all"]

        filter_ticker_strings: list[str] | None = None
        if filter_symbols:
            filter_ticker_strings = massive_build_snapshot_tickers(filter_symbols)

        # Add timeout configuration to prevent hanging requests
        timeout = httpx.Timeout(30.0, connect=10.0)  # 30s total, 10s connect
        async with httpx.AsyncClient(timeout=timeout) as client:
            if filter_ticker_strings:
                filtered_ticker_set = await self._fetch_filtered_tickers_for_list(
                    client, api_key, market, market_filter, asset_type_filter, filter_ticker_strings
                )
            else:
                filtered_ticker_set = await self._fetch_filtered_tickers(
                    client, api_key, market, market_filter, asset_type_filter
                )

            tickers_data = await massive_fetch_snapshot(
                client,
                api_key,
                locale,
                markets,
                market,
                filter_ticker_strings,
                include_otc_in_snapshot,  # Use new parameter
            )

            filter_params = self._extract_filter_params()
            self._validate_filter_params(filter_params)

            symbols = self._process_tickers(
                tickers_data, market, filtered_ticker_set, filter_params, market_filter, asset_type_filter
            )

        return symbols

    def _get_bool_param(self, param_name: str, default: bool) -> bool:
        """Extract and validate boolean parameter."""
        param_raw = self.params.get(param_name, default)
        return param_raw if isinstance(param_raw, bool) else default

    def _get_numeric_param(self, param_name: str) -> float | None:
        """Extract and validate numeric parameter."""
        param_raw = self.params.get(param_name)
        return param_raw if isinstance(param_raw, int | float) else None

    def _extract_filter_params(self) -> dict[str, float | None]:
        """Extract all filter parameters."""
        return {
            "min_change_perc": self._get_numeric_param("min_change_perc"),
            "max_change_perc": self._get_numeric_param("max_change_perc"),
            "min_volume": self._get_numeric_param("min_volume"),
            "min_price": self._get_numeric_param("min_price"),
            "max_price": self._get_numeric_param("max_price"),
        }

    def _validate_filter_params(self, filter_params: dict[str, float | None]) -> None:
        """Validate filter parameters for logical consistency."""
        min_change_perc = filter_params["min_change_perc"]
        max_change_perc = filter_params["max_change_perc"]
        if min_change_perc is not None and max_change_perc is not None:
            if min_change_perc > max_change_perc:
                raise ValueError("min_change_perc cannot be greater than max_change_perc")

    def _process_tickers(
        self,
        tickers_data: list[dict[str, Any]],
        market: str,
        filtered_ticker_set: set[str] | None,
        filter_params: dict[str, float | None],
        market_filter: str,
        asset_type_filter: str,
    ) -> list[AssetSymbol]:
        """Process ticker data and apply filters to produce AssetSymbol list."""
        symbols: list[AssetSymbol] = []
        total_tickers = len(tickers_data)

        for ticker_item in tickers_data:
            ticker = self._extract_ticker(ticker_item)
            if not ticker:
                continue

            if filtered_ticker_set is not None and ticker not in filtered_ticker_set:
                continue

            # Apply market filter (OTC vs regular exchange)
            # Note: snapshot API doesn't include market field, so we can't filter OTC here
            # The filtering happens in _fetch_filtered_tickers during reference API call
            # For now, we rely on the filtered_ticker_set to handle OTC filtering

            ticker_data = self._extract_ticker_data(ticker_item, market)
            if not ticker_data:
                continue

            if not self._passes_filters(ticker_data, filter_params):
                continue

            symbol = self._create_asset_symbol(ticker, ticker_item, market, ticker_data)
            symbols.append(symbol)

        self.report_progress(
            100.0, f"Completed: {len(symbols)} symbols from {total_tickers} tickers"
        )
        return symbols

    def _extract_ticker(self, ticker_item: dict[str, Any]) -> str | None:
        """Extract ticker string from ticker item."""
        ticker_value = ticker_item.get("ticker")
        return ticker_value if isinstance(ticker_value, str) else None

    def _extract_ticker_data(
        self, ticker_item: dict[str, Any], market: str
    ) -> dict[str, Any] | None:
        """Extract price, volume, and change percentage from ticker data.

        For stocks, uses US market hours logic to determine whether to use today's intraday
        data or previous day's closing data.
        """
        day_value = ticker_item.get("day")
        prev_day_value = ticker_item.get("prevDay")
        last_trade_value = ticker_item.get("lastTrade")

        if not isinstance(day_value, dict):
            day: dict[str, Any] = {}
            logger.warning(f"Invalid 'day' data for ticker {ticker_item.get('ticker')}")
        else:
            day = day_value

        if not isinstance(prev_day_value, dict):
            prev_day: dict[str, Any] = {}
            logger.warning(f"Invalid 'prevDay' data for ticker {ticker_item.get('ticker')}")
        else:
            prev_day = prev_day_value

        market_is_open = is_us_market_open()
        data_day_param_raw = self.params.get("data_day", "auto")
        data_day_param = data_day_param_raw if isinstance(data_day_param_raw, str) else "auto"

        if data_day_param == "today":
            use_prev_day = False
        elif data_day_param == "prev_day":
            use_prev_day = True
        else:  # auto
            use_prev_day = not market_is_open
            if use_prev_day and not market_is_open:
                # For auto-closed: treat as 'today' but label as lastTradingDay
                use_prev_day = False

        # Extract todaysChangePerc (always available, reflects change since prevDay.c)
        change_perc_raw = ticker_item.get("todaysChangePerc")
        if isinstance(change_perc_raw, int | float):
            todays_change_perc = float(change_perc_raw)
        else:
            todays_change_perc = None
            logger.warning(
                f"Missing or invalid todaysChangePerc for ticker {ticker_item.get('ticker')}"
            )

        if use_prev_day:
            # Explicit prev_day: Use prevDay bar fully, compute intra-day change %
            price = massive_get_numeric_from_dict(prev_day, "c", 0.0)
            volume = massive_get_numeric_from_dict(prev_day, "v", 0.0)
            prev_open = massive_get_numeric_from_dict(prev_day, "o", 0.0)
            if prev_open > 0:
                change_perc = ((price - prev_open) / prev_open) * 100.0
            else:
                change_perc = None  # Skip filters if uncomputable
            data_source = "prevDay_intra"
        else:
            # Today/open (or auto-closed: use day as last full day)
            price = massive_get_numeric_from_dict(day, "c", 0.0)
            volume = massive_get_numeric_from_dict(day, "v", 0.0)
            change_perc = todays_change_perc  # API-provided, from prevDay to day.c
            data_source = "day"
            if data_day_param == "auto" and not market_is_open:
                # Auto-closed: day is last full trading day
                data_source = "lastTradingDay"
            elif data_day_param == "today" and not market_is_open:
                data_source = "lastTradingDay"

        if price <= 0:
            logger.warning(f"Invalid price (<=0) for ticker {ticker_item.get('ticker')}")
            return None

        return {
            "price": price,
            "volume": volume,
            "change_perc": change_perc,
            "data_source": data_source,  # For metadata
        }

    def _passes_filters(
        self, ticker_data: dict[str, Any], filter_params: dict[str, float | None]
    ) -> bool:
        """Check if ticker data passes all configured filters."""
        price = ticker_data["price"]
        volume = ticker_data["volume"]
        change_perc = ticker_data["change_perc"]

        min_change_perc = filter_params["min_change_perc"]
        max_change_perc = filter_params["max_change_perc"]
        min_volume = filter_params["min_volume"]
        min_price = filter_params["min_price"]
        max_price = filter_params["max_price"]

        if change_perc is not None:
            if min_change_perc is not None and change_perc < min_change_perc:
                return False
            if max_change_perc is not None and change_perc > max_change_perc:
                return False

        if min_volume is not None and volume < min_volume:
            return False

        if min_price is not None and price < min_price:
            return False

        if max_price is not None and price > max_price:
            return False

        return True

    def _create_asset_symbol(
        self,
        ticker: str,
        ticker_item: dict[str, Any],
        market: str,
        ticker_data: dict[str, Any],
    ) -> AssetSymbol:
        """Create AssetSymbol from ticker data."""
        base_ticker, quote_currency = massive_parse_ticker_for_market(ticker, market)

        asset_class = AssetClass.STOCKS

        data_source = ticker_data.get("data_source", "unknown")
        change_available = ticker_data.get("change_perc") is not None

        metadata = {
            "original_ticker": ticker,
            "snapshot": ticker_item,
            "market": market,
            "data_source": data_source,
            "change_available": change_available,
        }

        return AssetSymbol(
            ticker=base_ticker,
            asset_class=asset_class,
            quote_currency=quote_currency,
            metadata=metadata,
        )

    async def _fetch_filtered_tickers_for_list(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        market: str,
        market_filter: str,
        asset_type_filter: str,
        tickers: list[str],
    ) -> set[str]:
        """Fetch ticker classification and filter by market and asset type."""
        etf_types: set[str] = set()
        etf_types = await massive_fetch_ticker_types(client, api_key)

        ref_market = market
        allowed: set[str] = set()

        for ticker in tickers:
            # Build query for a single ticker
            params: dict[str, Any] = {
                "active": True,
                "limit": 1,
                "apiKey": api_key,
                "market": ref_market,
                "ticker": ticker,
            }

            response = await client.get(
                "https://api.massive.com/v3/reference/tickers", params=params
            )
            if response.status_code != 200:
                # If the lookup fails, conservatively include the ticker
                allowed.add(ticker)
                continue

            data = response.json()
            results = data.get("results", [])
            if not isinstance(results, list) or not results:
                allowed.add(ticker)
                continue
            results_list: list[Any] = results
            first_item_raw = results_list[0]
            if not isinstance(first_item_raw, dict):
                allowed.add(ticker)
                continue
            first_item: dict[str, Any] = first_item_raw
            type_val: Any = first_item.get("type")
            market_val: Any = first_item.get("market")
            type_str = type_val if isinstance(type_val, str) else ""
            market_str = market_val if isinstance(market_val, str) else ""

            # Check if it's an ETF
            is_etf = (
                (type_str in etf_types)
                or ("etf" in type_str.lower())
                or ("etn" in type_str.lower())
                or ("etp" in type_str.lower())
                or (market_str == "etp")
            )
            
            # Check if it's OTC
            is_otc = market_str.lower() == "otc"

            # Apply asset type filter (ETF vs stocks)
            if asset_type_filter == "stocks_no_etf" and is_etf:
                continue  # Exclude ETFs
            elif asset_type_filter == "etf_only" and not is_etf:
                continue  # Only ETFs
            # "all" includes everything

            # Apply market filter (OTC vs regular exchange)
            if market_filter == "stocks_only" and is_otc:
                continue  # Exclude OTC
            elif market_filter == "otc_only" and not is_otc:
                continue  # Only OTC
            # "include_otc" and "all" include everything

            allowed.add(ticker)

        return allowed

    async def _fetch_filtered_tickers(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        market: str,
        market_filter: str,
        asset_type_filter: str,
    ) -> set[str]:
        """
        Fetch filtered ticker list from Massive.com API (formerly Polygon.io) with market and asset type filtering.

        Args:
            client: httpx AsyncClient instance
            api_key: Massive.com API key (POLYGON_API_KEY)
            market: Market type (stocks)
            market_filter: Market filter mode (stocks_only, include_otc, otc_only, all)
            asset_type_filter: Asset type filter (stocks_no_etf, etf_only, all)

        Returns:
            Set of ticker symbols that pass the filters
        """
        ref_market = market

        # Build query parameters - query specific market if needed
        ref_params: dict[str, Any] = {
            "active": True,
            "limit": 1000,
            "apiKey": api_key,
        }
        
        # If only OTC, query the OTC market directly
        if market_filter == "otc_only":
            ref_params["market"] = "otc"
        else:
            ref_params["market"] = ref_market

        # Fetch ETF type codes for asset type filtering
        etf_types: set[str] = set()
        etf_types = await massive_fetch_ticker_types(client, api_key)

        ticker_set: set[str] = set()
        ref_url = "https://api.massive.com/v3/reference/tickers"
        next_url: str | None = ref_url
        page_count = 0

        while next_url:
            if page_count > 0:
                # Use next_url with apiKey appended
                if "?" in next_url:
                    url_to_fetch = f"{next_url}&apiKey={api_key}"
                else:
                    url_to_fetch = f"{next_url}?apiKey={api_key}"
                response = await client.get(url_to_fetch)
            else:
                response = await client.get(ref_url, params=ref_params)

            if response.status_code != 200:
                logger.warning(
                    f"Failed to fetch ticker metadata page {page_count + 1}: {response.status_code}"
                )
                break

            data = response.json()
            results = data.get("results", [])

            for item in results:
                if not isinstance(item, dict):
                    continue

                # Extract ticker field with type guard - skip if missing or wrong type
                if "ticker" not in item:
                    continue
                ticker_raw: Any = item["ticker"]
                if not isinstance(ticker_raw, str) or not ticker_raw:
                    continue
                ticker: str = ticker_raw

                # Extract type field with type guard
                ticker_type_raw: Any = item["type"] if "type" in item else None
                ticker_type: str = ticker_type_raw if isinstance(ticker_type_raw, str) else ""

                # Extract market field with type guard
                ticker_market_raw: Any = item["market"] if "market" in item else None
                ticker_market: str = ticker_market_raw if isinstance(ticker_market_raw, str) else ""

                # Check if it's an ETF
                is_etf = (
                    ticker_type in etf_types
                    or "etf" in ticker_type.lower()
                    or "etn" in ticker_type.lower()
                    or "etp" in ticker_type.lower()
                    or ticker_market == "etp"
                )
                
                # Check if it's OTC
                is_otc = ticker_market.lower() == "otc"

                # Apply asset type filter (ETF vs stocks)
                if asset_type_filter == "stocks_no_etf" and is_etf:
                    continue  # Exclude ETFs
                elif asset_type_filter == "etf_only" and not is_etf:
                    continue  # Only ETFs
                # "all" includes everything

                # Apply market filter (OTC vs regular exchange)
                if market_filter == "stocks_only" and is_otc:
                    continue  # Exclude OTC
                elif market_filter == "otc_only" and not is_otc:
                    continue  # Only OTC
                # "include_otc" and "all" include everything

                ticker_set.add(ticker)

            # Check for next page
            next_url = data.get("next_url")
            page_count += 1

            # Progress reporting
            if page_count % 5 == 0:
                self.report_progress(
                    5.0 + (min(page_count * 20, 25)),
                    f"Fetched metadata for {len(ticker_set)} tickers (page {page_count})...",
                )

        return ticker_set
