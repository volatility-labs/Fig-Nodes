import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetClass, AssetSymbol, get_type
from nodes.base.base_node import Base
from services.polygon_service import (
    massive_build_snapshot_tickers,
    massive_compute_closed_change_perc,
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
            "name": "include_otc",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Include OTC",
            "description": "Include over-the-counter symbols",
        },
        {
            "name": "exclude_etfs",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Exclude ETFs",
            "description": "If true, filters out ETFs (keeps only stocks). If false, keeps only ETFs.",
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
        exclude_etfs = self._get_bool_param("exclude_etfs", True)

        filter_ticker_strings: list[str] | None = None
        if filter_symbols:
            filter_ticker_strings = massive_build_snapshot_tickers(filter_symbols)

        async with httpx.AsyncClient() as client:
            if filter_ticker_strings:
                filtered_ticker_set = await self._fetch_filtered_tickers_for_list(
                    client, api_key, market, exclude_etfs, filter_ticker_strings
                )
            else:
                filtered_ticker_set = await self._fetch_filtered_tickers(
                    client, api_key, market, exclude_etfs
                )

            tickers_data = await massive_fetch_snapshot(
                client,
                api_key,
                locale,
                markets,
                market,
                filter_ticker_strings,
                bool(self.params.get("include_otc", False)),
            )

            filter_params = self._extract_filter_params()
            self._validate_filter_params(filter_params)

            symbols = self._process_tickers(
                tickers_data, market, filtered_ticker_set, filter_params
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

            ticker_data = self._extract_ticker_data(ticker_item, market)
            if not ticker_data:
                continue

            if not self._passes_filters(ticker_data, filter_params):
                continue

            symbol = self._create_asset_symbol(ticker, ticker_item, market, ticker_data)
            symbols.append(symbol)

        self.report_progress(
            95.0, f"Completed: {len(symbols)} symbols from {total_tickers} tickers"
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
        else:
            day = day_value

        if not isinstance(prev_day_value, dict):
            prev_day: dict[str, Any] = {}
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

        # Support pre/post-market change% by using lastTrade vs prevDay close when market is closed
        if use_prev_day:
            last_trade: dict[str, Any] = (
                last_trade_value if isinstance(last_trade_value, dict) else {}
            )
            price, change_perc = massive_compute_closed_change_perc(prev_day, last_trade)
            volume = massive_get_numeric_from_dict(prev_day, "v", 0.0)
        else:
            # During market hours, include tickers even if volume_day == 0 unless a min_volume filter is set
            price = massive_get_numeric_from_dict(day, "c", 0.0)
            volume = massive_get_numeric_from_dict(day, "v", 0.0)
            change_perc_raw = ticker_item.get("todaysChangePerc")
            if isinstance(change_perc_raw, int | float):
                change_perc = float(change_perc_raw)
            else:
                change_perc = 0.0

        return {
            "price": price,
            "volume": volume,
            "change_perc": change_perc,
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

        metadata = {
            "original_ticker": ticker,
            "snapshot": ticker_item,
            "market": market,
            "data_source": "prevDay" if ticker_data.get("change_perc") is None else "day",
            "change_available": ticker_data.get("change_perc") is not None,
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
        exclude_etfs: bool,
        tickers: list[str],
    ) -> set[str]:
        """Fetch ETF classification for a limited list of tickers and filter accordingly."""
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

            is_etf = (
                (type_str in etf_types)
                or ("etf" in type_str.lower())
                or ("etn" in type_str.lower())
                or ("etp" in type_str.lower())
                or (market_str == "etp")
            )

            if exclude_etfs and is_etf:
                # Exclude ETFs
                continue
            if not exclude_etfs and not is_etf:
                # Include only ETFs
                continue
            allowed.add(ticker)

        return allowed

    async def _fetch_filtered_tickers(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        market: str,
        exclude_etfs: bool,
    ) -> set[str]:
        """
        Fetch filtered ticker list from Massive.com API (formerly Polygon.io) with server-side ETF filtering.

        Args:
            client: httpx AsyncClient instance
            api_key: Massive.com API key (POLYGON_API_KEY)
            market: Market type (stocks)
            exclude_etfs: Whether to exclude ETFs

        Returns:
            Set of ticker symbols that pass the filters
        """
        ref_market = market

        # Build query parameters
        ref_params: dict[str, Any] = {
            "active": True,
            "limit": 1000,
            "apiKey": api_key,
            "market": ref_market,
        }

        # Fetch ETF type codes if we need ETF filtering (either exclude or include only)
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

                # Apply ETF filtering if needed
                if etf_types:
                    is_etf = (
                        ticker_type in etf_types
                        or "etf" in ticker_type.lower()
                        or "etn" in ticker_type.lower()
                        or "etp" in ticker_type.lower()
                        or ticker_market == "etp"
                    )
                    if exclude_etfs and is_etf:
                        # Exclude ETFs: skip if it's an ETF
                        continue
                    if not exclude_etfs and not is_etf:
                        # Include only ETFs: skip if it's NOT an ETF
                        continue

                # Apply OTC filtering for stocks market
                include_otc = self.params.get("include_otc", False)
                if not include_otc:
                    if ticker_market == "otc" or ticker_market == "OTC":
                        continue

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

