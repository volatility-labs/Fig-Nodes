import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetClass, AssetSymbol, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


def _is_us_market_open() -> bool:
    """Check if US stock market is currently open (9:30 AM ET - 4:00 PM ET, Mon-Fri).

    Returns:
        True if market is open, False otherwise.
    """
    # Get current time in Eastern Time (handles DST automatically)
    et = ZoneInfo("America/New_York")
    now_et = datetime.now(et)

    # Check if it's a weekday (Monday=0, Sunday=6)
    if now_et.weekday() >= 5:  # Saturday or Sunday
        return False

    # Check if within market hours (9:30 AM - 4:00 PM ET)
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    is_open = market_open <= now_et <= market_close
    print(
        f"DEBUG: Market status check - Current ET time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}, Is open: {is_open}"
    )
    return is_open


class PolygonUniverse(Base):
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
            "optional": True,
            "label": "Min Change",
            "unit": "%",
            "description": "Minimum daily percentage change (e.g., 5 for 5%)",
            "step": 0.01,
        },
        {
            "name": "max_change_perc",
            "type": "number",
            "default": None,
            "optional": True,
            "label": "Max Change",
            "unit": "%",
            "description": "Maximum daily percentage change (e.g., 10 for 10%)",
            "step": 0.01,
        },
        {
            "name": "min_volume",
            "type": "number",
            "default": None,
            "optional": True,
            "label": "Min Volume",
            "unit": "shares/contracts",
            "description": "Minimum daily trading volume in shares or contracts",
        },
        {
            "name": "min_price",
            "type": "number",
            "default": None,
            "optional": True,
            "label": "Min Price",
            "unit": "USD",
            "description": "Minimum closing price in USD",
        },
        {
            "name": "max_price",
            "type": "number",
            "default": 1000000,
            "optional": True,
            "label": "Max Price",
            "unit": "USD",
            "description": "Maximum closing price in USD",
        },
        {
            "name": "include_otc",
            "type": "boolean",
            "default": False,
            "optional": True,
            "label": "Include OTC",
            "description": "Include over-the-counter symbols (stocks only)",
        },
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        print(f"DEBUG: PolygonUniverse node {self.id} starting execution")
        print(f"DEBUG: PolygonUniverse inputs: {list(inputs.keys())}")
        try:
            symbols = await self._fetch_symbols()
            print(f"DEBUG: PolygonUniverse fetched {len(symbols)} symbols")
            filter_symbols = self.collect_multi_input("filter_symbols", inputs)
            if filter_symbols:
                print(f"DEBUG: PolygonUniverse filtering with {len(filter_symbols)} filter symbols")
                filter_set = {str(s) for s in filter_symbols}
                symbols = [s for s in symbols if str(s) in filter_set]
                print(f"DEBUG: PolygonUniverse after filtering: {len(symbols)} symbols")
            print(f"DEBUG: PolygonUniverse node {self.id} completed successfully")
            return {"symbols": symbols}
        except Exception as e:
            print(
                f"ERROR_TRACE: Exception in PolygonUniverse node {self.id}: {type(e).__name__}: {str(e)}"
            )
            logger.error(f"PolygonUniverse node {self.id} failed: {str(e)}", exc_info=True)
            raise

    async def _fetch_symbols(self) -> list[AssetSymbol]:
        print(
            f"DEBUG: PolygonUniverse fetching symbols for market: {self.params.get('market', 'stocks')}"
        )
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            print("ERROR_TRACE: POLYGON_API_KEY not found in vault")
            raise ValueError("POLYGON_API_KEY is required but not set in vault")
        print(f"DEBUG: PolygonUniverse API key found, length: {len(api_key)}")
        market = self.params.get("market", "stocks")

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
        print(f"DEBUG: PolygonUniverse making API request to: {base_url}")
        print(f"DEBUG: PolygonUniverse request params: {params}")
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, headers=headers, params=params)
            print(f"DEBUG: PolygonUniverse API response status: {response.status_code}")
            if response.status_code != 200:
                error_text = response.text if response.text else response.reason_phrase
                print(
                    f"ERROR_TRACE: PolygonUniverse API error: {response.status_code} - {error_text}"
                )
                raise ValueError(f"Failed to fetch snapshot: {response.status_code} - {error_text}")
            data = response.json()
            tickers_data = data.get("tickers", [])
            print(f"DEBUG: PolygonUniverse received {len(tickers_data)} tickers from API")

            # Debug: Show sample ticker data structure
            if tickers_data:
                print(f"DEBUG: Sample ticker data (first): {tickers_data[0]}")

            min_change_perc = self.params.get("min_change_perc")
            max_change_perc = self.params.get("max_change_perc")
            min_volume = self.params.get("min_volume")
            min_price = self.params.get("min_price")
            max_price = self.params.get("max_price")

            print(
                f"DEBUG: Filter parameters - min_change_perc: {min_change_perc}, max_change_perc: {max_change_perc}, min_volume: {min_volume}, min_price: {min_price}, max_price: {max_price}"
            )

            # Validate change percentage range if both provided
            if min_change_perc is not None and max_change_perc is not None:
                assert isinstance(min_change_perc, (int, float)) and isinstance(
                    max_change_perc, (int, float)
                ), "Change bounds must be numeric"
                if min_change_perc > max_change_perc:
                    raise ValueError("min_change_perc cannot be greater than max_change_perc")

            # Check if market is open
            market_is_open = _is_us_market_open()
            use_prev_day = not market_is_open

            if use_prev_day:
                print("DEBUG: Market is closed - will use prevDay data for filtering")

            filtered_count = 0
            tickers_with_data = 0
            tickers_using_prev_day = 0
            sample_tickers_with_data = []

            for res in tickers_data:
                ticker = res["ticker"]

                # Determine which data to use: current day or previous day
                day = res.get("day", {})
                prev_day = res.get("prevDay", {})

                # Use prevDay if market is closed OR if current day has no volume
                volume_day = day.get("v", 0)
                if use_prev_day or volume_day == 0:
                    # Use previous day data
                    source_name = "prevDay"
                    if use_prev_day and volume_day == 0:
                        tickers_using_prev_day += 1

                    # For prevDay, we don't have change percentage readily available
                    # Skip change percentage filtering when using prevDay during closed hours
                    change_perc = None  # Will skip change filtering when None

                    price = prev_day.get("c", 0)
                    volume = prev_day.get("v", 0)
                else:
                    # Use current day data
                    source_name = "day"
                    change_perc = res.get("todaysChangePerc", 0)
                    price = day.get("c", 0)
                    volume = day.get("v", 0)

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
                    if filtered_count <= 5:
                        print(f"DEBUG: Filtered {ticker} - no trading data (volume=0)")
                    continue

                # Apply filters - skip change filters when using prevDay (change_perc is None)
                if change_perc is not None:
                    if min_change_perc is not None and change_perc < min_change_perc:
                        filtered_count += 1
                        if filtered_count <= 5:
                            print(
                                f"DEBUG: Filtered {ticker} by min_change_perc: {change_perc} < {min_change_perc}"
                            )
                        continue
                    if max_change_perc is not None and change_perc > max_change_perc:
                        filtered_count += 1
                        if filtered_count <= 5:
                            print(
                                f"DEBUG: Filtered {ticker} by max_change_perc: {change_perc} > {max_change_perc}"
                            )
                        continue
                else:
                    # Using prevDay data - skip change percentage filters
                    if filtered_count <= 5:
                        print(f"DEBUG: Skipping change filters for {ticker} (using prevDay data)")

                if min_volume is not None and volume < min_volume:
                    filtered_count += 1
                    if filtered_count <= 5:
                        print(f"DEBUG: Filtered {ticker} by min_volume: {volume} < {min_volume}")
                    continue

                if min_price is not None and price < min_price:
                    filtered_count += 1
                    if filtered_count <= 5:
                        print(f"DEBUG: Filtered {ticker} by min_price: {price} < {min_price}")
                    continue
                if max_price is not None and price > max_price:
                    filtered_count += 1
                    if filtered_count <= 5:
                        print(f"DEBUG: Filtered {ticker} by max_price: {price} > {max_price}")
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

        print(
            f"DEBUG: PolygonUniverse filtering complete - {len(symbols)} symbols passed all filters out of {len(tickers_data)} total"
        )
        print(f"DEBUG: Tickers with trading data: {tickers_with_data}")
        if tickers_using_prev_day > 0:
            print(f"DEBUG: Tickers using prevDay data: {tickers_using_prev_day}")
        if sample_tickers_with_data:
            print(f"DEBUG: Sample tickers with data: {sample_tickers_with_data}")

        # Warn if no symbols passed filters due to no trading data
        if tickers_with_data == 0 and len(tickers_data) > 0:
            if use_prev_day:
                print(
                    f"WARNING: Using prevDay data (market closed), but all {len(tickers_data)} tickers have zero volume even in prevDay."
                )
            else:
                print(
                    f"WARNING: All {len(tickers_data)} tickers have zero volume for current day. Market may be closed or data unavailable."
                )
            print("Consider: Removing volume filter or checking market hours.")

        return symbols
