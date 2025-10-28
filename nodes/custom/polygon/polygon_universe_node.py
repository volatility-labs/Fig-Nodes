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
    A node that fetches symbols from the Polygon API and filters them based on the provided parameters.

    Polygon endpoint: https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers
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
    ]

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

        base_url = f"https://api.polygon.io/v2/snapshot/locale/{locale}/markets/{markets}/tickers"
        params: dict[str, Any] = {}
        if market == "otc" or (market == "stocks" and self.params.get("include_otc", False)):
            params["include_otc"] = True

        headers = {"Authorization": f"Bearer {api_key}"}
        symbols: list[AssetSymbol] = []
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, headers=headers, params=params)
            if response.status_code != 200:
                error_text = response.text if response.text else response.reason_phrase
                raise ValueError(f"Failed to fetch snapshot: {response.status_code} - {error_text}")
            data = response.json()
            tickers_data = data.get("tickers", [])

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

            for res_item in tickers_data:
                # Type guard: ensure res is a dict with string keys
                if not isinstance(res_item, dict):
                    continue

                res: dict[str, Any] = res_item

                ticker_value = res.get("ticker")
                if not isinstance(ticker_value, str):
                    continue
                ticker: str = ticker_value

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

                # Use prevDay if market is closed OR if current day has no volume
                volume_day_raw = day.get("v", 0)
                volume_day = volume_day_raw if isinstance(volume_day_raw, int | float) else 0

                if use_prev_day or volume_day == 0:
                    # Use previous day data
                    source_name = "prevDay"
                    if use_prev_day and volume_day == 0:
                        tickers_using_prev_day += 1

                    # For prevDay, we don't have change percentage readily available
                    # Skip change percentage filtering when using prevDay during closed hours
                    change_perc: float | None = None  # Will skip change filtering when None

                    price_raw = prev_day.get("c", 0)
                    price = price_raw if isinstance(price_raw, int | float) else 0.0

                    volume_raw = prev_day.get("v", 0)
                    volume = volume_raw if isinstance(volume_raw, int | float) else 0
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

                # Track tickers with trading data
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

                # Create AssetSymbol
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

        return symbols
