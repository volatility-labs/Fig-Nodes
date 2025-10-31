import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetClass, AssetSymbol, get_type
from nodes.base.base_node import Base
from services.time_utils import is_us_market_open

# Type aliases for better readability
TickerInfo = dict[str, Any]

logger = logging.getLogger(__name__)


class PolygonUniverse(Base):
    """
    A node that fetches symbols from the Massive.com API (formerly Polygon.io) and filters them
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
            "name": "market",
            "type": "combo",
            "default": "stocks",
            "options": ["stocks", "crypto", "fx", "otc", "indices"],
            "label": "Market Type",
            "description": "Select the market type to fetch symbols from",
        },
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
            "description": "Include over-the-counter symbols (stocks only)",
        },
        {
            "name": "exclude_etfs",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Exclude ETFs",
            "description": "If true, filters out ETFs (keeps only stocks). If false, keeps only ETFs.",
        },
    ]
    default_params = {}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        try:
            symbols = await self._fetch_symbols()
            filter_symbols = self.collect_multi_input("filter_symbols", inputs)
            if filter_symbols:
                filter_set = {str(s) for s in filter_symbols}
                symbols = [s for s in symbols if str(s) in filter_set]
            return {"symbols": symbols}
        except Exception as e:
            logger.error(f"PolygonUniverse node {self.id} failed: {str(e)}", exc_info=True)
            raise

    async def _fetch_symbols(self) -> list[AssetSymbol]:
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("POLYGON_API_KEY is required but not set in vault")
        market_raw = self.params.get("market", "stocks")
        market = market_raw if isinstance(market_raw, str) else "stocks"

        if market == "stocks" or market == "otc":
            locale = "us"
            markets = "stocks"
        elif market == "indices":
            locale = "us"
            markets = "indices"
        else:
            locale = "global"
            markets = market

        exclude_etfs_raw = self.params.get("exclude_etfs", True)
        exclude_etfs = exclude_etfs_raw if isinstance(exclude_etfs_raw, bool) else True
        needs_etf_filter = market in ["stocks", "otc"]

        async with httpx.AsyncClient() as client:
            # Step 1: Fetch filtered ticker list with server-side ETF filtering
            filtered_ticker_set: set[str] | None = None
            if needs_etf_filter:
                self.report_progress(5.0, "Fetching ticker metadata...")
                filtered_ticker_set = await self._fetch_filtered_tickers(
                    client, api_key, market, exclude_etfs
                )
                self.report_progress(30.0, f"Found {len(filtered_ticker_set)} filtered tickers")

            # Step 2: Fetch snapshot data
            snapshot_url = (
                f"https://api.massive.com/v2/snapshot/locale/{locale}/markets/{markets}/tickers"
            )
            snapshot_params: dict[str, Any] = {}
            if market == "otc" or (market == "stocks" and self.params.get("include_otc", False)):
                snapshot_params["include_otc"] = True

            headers = {"Authorization": f"Bearer {api_key}"}
            self.report_progress(35.0, "Fetching snapshot data...")
            response = await client.get(snapshot_url, headers=headers, params=snapshot_params)
            if response.status_code != 200:
                error_text = response.text if response.text else response.reason_phrase
                raise ValueError(f"Failed to fetch snapshot: {response.status_code} - {error_text}")
            data = response.json()
            tickers_data = data.get("tickers", [])
            total_tickers = len(tickers_data)

            self.report_progress(
                40.0, f"Fetched {total_tickers} tickers from snapshot, processing..."
            )

            min_change_perc_raw = self.params.get("min_change_perc")
            min_change_perc = (
                min_change_perc_raw if isinstance(min_change_perc_raw, int | float) else None
            )

            max_change_perc_raw = self.params.get("max_change_perc")
            max_change_perc = (
                max_change_perc_raw if isinstance(max_change_perc_raw, int | float) else None
            )

            min_volume_raw = self.params.get("min_volume")
            min_volume = min_volume_raw if isinstance(min_volume_raw, int | float) else None

            min_price_raw = self.params.get("min_price")
            min_price = min_price_raw if isinstance(min_price_raw, int | float) else None

            max_price_raw = self.params.get("max_price")
            max_price = max_price_raw if isinstance(max_price_raw, int | float) else None

            # Validate change percentage range if both provided
            if min_change_perc is not None and max_change_perc is not None:
                if min_change_perc > max_change_perc:
                    raise ValueError("min_change_perc cannot be greater than max_change_perc")

            # Check if market is open
            market_is_open = is_us_market_open()
            use_prev_day = not market_is_open

            filtered_count = 0
            tickers_with_data = 0
            tickers_using_prev_day = 0
            sample_tickers_with_data: list[TickerInfo] = []
            processed_count = 0
            symbols: list[AssetSymbol] = []

            for res_item in tickers_data:
                processed_count += 1
                # Type guard: ensure res is a dict with string keys
                if not isinstance(res_item, dict):
                    continue

                res: dict[str, Any] = res_item

                ticker_value = res.get("ticker")
                if not isinstance(ticker_value, str):
                    continue
                ticker: str = ticker_value

                # Apply ETF filter using pre-fetched filtered ticker set
                if filtered_ticker_set is not None:
                    if ticker not in filtered_ticker_set:
                        filtered_count += 1
                        continue

                # Determine which data to use: current day or previous day
                day_value = res.get("day", {})
                prev_day_value = res.get("prevDay", {})

                # Type guard: ensure day and prev_day are dicts
                if not isinstance(day_value, dict):
                    day: dict[str, Any] = {}
                else:
                    day = day_value

                if not isinstance(prev_day_value, dict):
                    prev_day: dict[str, Any] = {}
                else:
                    prev_day = prev_day_value

                # Use prevDay if market is closed. During market hours, only use current day data.
                volume_day_raw = day.get("v", 0)
                volume_day = volume_day_raw if isinstance(volume_day_raw, int | float) else 0

                if use_prev_day:
                    # Market is closed - use previous day data
                    source_name = "prevDay"
                    tickers_using_prev_day += 1

                    # For prevDay, we don't have change percentage readily available
                    # Skip change percentage filtering when using prevDay during closed hours
                    change_perc: float | None = None  # Will skip change filtering when None

                    price_raw = prev_day.get("c", 0)
                    price = price_raw if isinstance(price_raw, int | float) else 0.0

                    volume_raw = prev_day.get("v", 0)
                    volume = volume_raw if isinstance(volume_raw, int | float) else 0
                elif volume_day == 0:
                    # During market hours, if stock hasn't traded yet today, skip it
                    # Don't fall back to previous day data as that would use yesterday's volume
                    filtered_count += 1
                    continue
                else:
                    # Use current day data
                    source_name = "day"
                    change_perc_raw = res.get("todaysChangePerc", 0)
                    change_perc = (
                        change_perc_raw if isinstance(change_perc_raw, int | float) else 0.0
                    )

                    price_raw = day.get("c", 0)
                    price = price_raw if isinstance(price_raw, int | float) else 0.0

                    volume_raw = day.get("v", 0)
                    volume = volume_raw if isinstance(volume_raw, int | float) else 0

                # Track tickers with trading data (only count if we have volume data)
                if volume > 0:
                    tickers_with_data += 1
                    if len(sample_tickers_with_data) < 3:
                        sample_tickers_with_data.append(
                            {
                                "ticker": ticker,
                                "volume": volume,
                                "price": price,
                                "change": change_perc,
                                "source": source_name,
                            }
                        )

                # If volume is 0 even in prevDay, skip this ticker
                if volume == 0:
                    filtered_count += 1
                    continue

                # Apply filters - skip change filters when using prevDay (change_perc is None)
                if change_perc is not None:
                    if min_change_perc is not None and change_perc < min_change_perc:
                        filtered_count += 1
                        continue
                    if max_change_perc is not None and change_perc > max_change_perc:
                        filtered_count += 1
                        continue

                if min_volume is not None and volume < min_volume:
                    filtered_count += 1
                    continue

                if min_price is not None and price < min_price:
                    filtered_count += 1
                    continue
                if max_price is not None and price > max_price:
                    filtered_count += 1
                    continue

                # Parse ticker for crypto/fx markets
                quote_currency = None
                base_ticker = ticker
                if market in ["crypto", "fx"] and ":" in ticker:
                    _, tick = ticker.split(":", 1)
                    if len(tick) > 3 and tick[-3:].isalpha() and tick[-3:].isupper():
                        base_ticker = tick[:-3]
                        quote_currency = tick[-3:]

                # Map market names to existing AssetClass values
                market_mapping = {
                    "crypto": AssetClass.CRYPTO,
                    "stocks": AssetClass.STOCKS,
                    "stock": AssetClass.STOCKS,
                    "otc": AssetClass.STOCKS,
                }
                asset_class = market_mapping.get(market.lower(), AssetClass.STOCKS)

                metadata = {
                    "original_ticker": ticker,
                    "snapshot": res,
                }

                symbols.append(
                    AssetSymbol(
                        ticker=base_ticker,
                        asset_class=asset_class,
                        quote_currency=quote_currency,
                        metadata=metadata,
                    )
                )

            # Report final progress
            self.report_progress(
                95.0, f"Completed: {len(symbols)} symbols from {total_tickers} tickers"
            )

        return symbols

    async def _fetch_ticker_types(self, client: httpx.AsyncClient, api_key: str) -> set[str]:
        """
        Fetch ticker types from Massive.com API (formerly Polygon.io) and identify ETF-related type codes.

        Args:
            client: httpx AsyncClient instance
            api_key: Massive.com API key (POLYGON_API_KEY)

        Returns:
            Set of type codes that represent ETFs/ETNs/ETPs
        """
        url = "https://api.massive.com/v3/reference/tickers/types"
        params: dict[str, str] = {"apiKey": api_key}

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            etf_type_codes: set[str] = set()
            for item in results:
                if not isinstance(item, dict):
                    continue

                # Extract code field with type guard - skip if missing or wrong type
                if "code" not in item:
                    continue
                code_raw: Any = item["code"]
                if not isinstance(code_raw, str):
                    continue
                code: str = code_raw

                # Extract description field with type guard
                description_raw: Any = item["description"] if "description" in item else None
                description: str = (
                    description_raw.lower() if isinstance(description_raw, str) else ""
                )

                type_code: str = code.lower()

                # Identify ETF-related types
                if (
                    "etf" in type_code
                    or "etn" in type_code
                    or "etp" in type_code
                    or "exchange traded" in description
                ):
                    etf_type_codes.add(code)

            logger.debug(f"Identified ETF type codes: {etf_type_codes}")
            return etf_type_codes
        except Exception as e:
            logger.warning(f"Failed to fetch ticker types: {e}, using fallback ETF detection")
            # Fallback: common ETF type codes
            return {"ETF", "ETN", "ETP"}

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
            market: Market type (stocks, otc, etc.)
            exclude_etfs: Whether to exclude ETFs

        Returns:
            Set of ticker symbols that pass the filters
        """
        # Determine market parameter for reference endpoint
        ref_market = "otc" if market == "otc" else market
        needs_etf_filter = market in ["stocks", "otc"]

        # Build query parameters
        ref_params: dict[str, Any] = {
            "active": True,
            "limit": 1000,
            "apiKey": api_key,
        }

        if market in ["stocks", "otc", "crypto", "fx", "indices"]:
            ref_params["market"] = ref_market

        # Fetch ETF type codes if we need ETF filtering (either exclude or include only)
        etf_types: set[str] = set()
        if needs_etf_filter:
            etf_types = await self._fetch_ticker_types(client, api_key)
            # We'll fetch all and filter client-side since Massive.com API doesn't support
            # type exclusion, only inclusion

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
                if market == "stocks" and not include_otc:
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
