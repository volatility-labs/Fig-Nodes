import logging
from datetime import datetime
from typing import Any

import httpx
import pytz

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetClass, AssetSymbol, get_type
from nodes.base.base_node import Base
from services.polygon_service import (
    massive_build_snapshot_tickers,
    massive_fetch_snapshot,
    massive_get_numeric_from_dict,
    massive_parse_ticker_for_market,
)
from services.time_utils import utc_timestamp_flex_to_et_datetime

logger = logging.getLogger(__name__)


class PolygonCryptoUniverse(Base):
    """
    A node that fetches crypto symbols from the Massive.com API (formerly Polygon.io) and filters them
    based on the provided parameters.

    Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
    to use api.massive.com, but the API routes remain unchanged.

    Endpoint: https://api.massive.com/v2/snapshot/locale/global/markets/crypto/tickers

    Crypto markets operate 24/7, always using current intraday data from the 'day' bar.
    """

    inputs = {"filter_symbols": get_type("AssetSymbolList") | None}
    outputs = {"symbols": get_type("AssetSymbolList")}
    required_keys = ["POLYGON_API_KEY"]
    # Common stablecoin tickers to filter out
    STABLECOIN_TICKERS = {
        "USDT",  # Tether
        "USDC",  # USD Coin
        "DAI",   # Dai
        "BUSD",  # Binance USD
        "TUSD",  # TrueUSD
        "USDP",  # Pax Dollar
        "USDD",  # USDD
        "GUSD",  # Gemini Dollar
        "HUSD",  # HUSD
        "USDX",  # USDX
        "FRAX",  # Frax
        "LUSD",  # Liquity USD
        "SUSD",  # sUSD
        "USDS",  # USDS
        "USN",   # USN
        "USDK",  # USDK
        "EURS",  # STASIS EURS
        "EURT",  # Tether EUR
        "GBPT",  # Tether GBP
    }

    params_meta = [
        {
            "name": "exclude_stablecoins",
            "type": "boolean",
            "default": True,
            "label": "Exclude Stablecoins",
            "description": "Exclude stablecoins (USDT, USDC, DAI, etc.) from results",
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
            "description": "Minimum daily trading volume",
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
            "name": "max_snapshot_delay_minutes",
            "type": "combo",
            "default": "5min",
            "label": "Max Snapshot Delay",
            "description": "Maximum allowed delay in snapshot 'updated' timestamp; None = no filter",
            "options": ["None (no filter)", "5min", "15min", "120min"],
        },
    ]
    default_params = {
        "exclude_stablecoins": True,  # Default to excluding stablecoins
    }

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        try:
            filter_symbols = self.collect_multi_input("filter_symbols", inputs)
            symbols = await self._fetch_symbols(filter_symbols)
            return {"symbols": symbols}
        except Exception as e:
            logger.error(f"PolygonCryptoUniverse node {self.id} failed: {str(e)}", exc_info=True)
            raise

    async def _fetch_symbols(
        self, filter_symbols: list[AssetSymbol] | None = None
    ) -> list[AssetSymbol]:
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("POLYGON_API_KEY is required but not set in vault")

        market = "crypto"
        locale, markets = "global", "crypto"

        filter_ticker_strings: list[str] | None = None
        if filter_symbols:
            filter_ticker_strings = massive_build_snapshot_tickers(filter_symbols)

        # Use longer timeout for snapshot fetch (can be slow with many tickers)
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            tickers_data = await massive_fetch_snapshot(
                client,
                api_key,
                locale,
                markets,
                market,
                filter_ticker_strings,
                False,
            )

            filter_params = self._extract_filter_params()
            self._validate_filter_params(filter_params)

            symbols = self._process_tickers(tickers_data, market, filter_params)

        return symbols

    def _get_numeric_param(self, param_name: str) -> float | None:
        """Extract and validate numeric parameter."""
        param_raw = self.params.get(param_name)
        if isinstance(param_raw, int | float):
            return float(param_raw)
        return None

    def _extract_filter_params(self) -> dict[str, float | None]:
        """Extract all filter parameters."""
        # Parse max_snapshot_delay_minutes from combo string
        delay_raw = self.params.get("max_snapshot_delay_minutes")
        max_snapshot_delay_minutes: float | None = None
        if delay_raw == "None (no filter)":
            max_snapshot_delay_minutes = None
        elif isinstance(delay_raw, str):
            if delay_raw.endswith("min"):
                try:
                    max_snapshot_delay_minutes = float(delay_raw[:-3])
                except ValueError:
                    logger.warning(f"Invalid delay string '{delay_raw}'; no filter applied")
        # Fallback to old numeric if present (for compatibility)
        elif isinstance(delay_raw, (int, float)):
            max_snapshot_delay_minutes = float(delay_raw)

        return {
            "min_change_perc": self._get_numeric_param("min_change_perc"),
            "max_change_perc": self._get_numeric_param("max_change_perc"),
            "min_volume": self._get_numeric_param("min_volume"),
            "min_price": self._get_numeric_param("min_price"),
            "max_price": self._get_numeric_param("max_price"),
            "max_snapshot_delay_minutes": max_snapshot_delay_minutes,
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
        filter_params: dict[str, float | None],
    ) -> list[AssetSymbol]:
        """Process ticker data and apply filters to produce AssetSymbol list."""
        symbols: list[AssetSymbol] = []
        total_tickers = len(tickers_data)
        filtered_stale = 0

        current_utc = datetime.now(pytz.UTC)

        for ticker_item in tickers_data:
            ticker = self._extract_ticker(ticker_item)
            if not ticker:
                continue

            # Filter: Only include USD-quoted crypto pairs
            if not self._is_usd_quoted(ticker, market):
                continue

            # Filter: Exclude stablecoins if enabled
            if self._should_exclude_stablecoin(ticker):
                continue

            ticker_data = self._extract_ticker_data(ticker_item, market)
            if not ticker_data:
                continue

            # Additional stablecoin filter: exclude if price is very close to $1.00
            # (catches stablecoins not in our list)
            if self._should_exclude_stablecoin_by_price(ticker_data):
                continue

            # New: Check snapshot update delay if filter enabled
            max_delay_min = filter_params.get("max_snapshot_delay_minutes")
            if max_delay_min is not None:
                updated_raw = ticker_item.get("updated")
                if isinstance(updated_raw, int):
                    updated_et = utc_timestamp_flex_to_et_datetime(updated_raw)
                    if updated_et is None:
                        # Invalid parse: treat as stale
                        filtered_stale += 1
                        logger.warning(
                            f"Filtered ticker {ticker} due to invalid 'updated' timestamp"
                        )
                        continue
                    updated_utc = updated_et.astimezone(pytz.UTC)
                    delay_minutes = (current_utc - updated_utc).total_seconds() / 60
                    if delay_minutes > max_delay_min:
                        filtered_stale += 1
                        logger.info(
                            f"Filtered stale snapshot for {ticker}: {delay_minutes:.1f} min delay"
                        )
                        continue
                else:
                    # No updated timestamp: treat as stale
                    filtered_stale += 1
                    logger.warning(f"Filtered ticker {ticker} due to missing 'updated' timestamp")
                    continue

            if not self._passes_filters(ticker_data, filter_params):
                continue

            symbol = self._create_asset_symbol(ticker, ticker_item, market, ticker_data)
            symbols.append(symbol)

        # Update progress with stale filter info if applied
        stale_msg = f"; filtered {filtered_stale} stale snapshots" if filtered_stale > 0 else ""
        self.report_progress(
            95.0, f"Completed: {len(symbols)} symbols from {total_tickers} tickers{stale_msg}"
        )
        return symbols

    def _extract_ticker(self, ticker_item: dict[str, Any]) -> str | None:
        """Extract ticker string from ticker item."""
        ticker_value = ticker_item.get("ticker")
        return ticker_value if isinstance(ticker_value, str) else None

    def _is_usd_quoted(self, ticker: str, market: str) -> bool:
        """Check if ticker is USD-quoted (for crypto filtering)."""
        if market != "crypto":
            return True  # No filtering for non-crypto markets

        _, quote_currency = massive_parse_ticker_for_market(ticker, market)
        # Only include USD-quoted pairs; None means parsing failed, exclude for safety
        return quote_currency == "USD"

    def _should_exclude_stablecoin(self, ticker: str) -> bool:
        """Check if ticker should be excluded as a stablecoin."""
        exclude_stablecoins = self.params.get("exclude_stablecoins", True)
        if not exclude_stablecoins:
            return False

        # Parse ticker to get base symbol
        base_ticker, _ = massive_parse_ticker_for_market(ticker, "crypto")
        if not base_ticker:
            return False

        # Check if base ticker is in stablecoin list (case-insensitive)
        return base_ticker.upper() in self.STABLECOIN_TICKERS

    def _should_exclude_stablecoin_by_price(self, ticker_data: dict[str, Any]) -> bool:
        """Check if ticker should be excluded based on price being very close to $1.00 (stablecoin indicator)."""
        exclude_stablecoins = self.params.get("exclude_stablecoins", True)
        if not exclude_stablecoins:
            return False

        price_raw = ticker_data.get("price")
        if not isinstance(price_raw, (int, float)):
            return False

        price = float(price_raw)
        # Exclude if price is between $0.99 and $1.01 (typical stablecoin range)
        # This catches stablecoins not in our explicit list
        return 0.99 <= price <= 1.01

    def _extract_ticker_data(
        self, ticker_item: dict[str, Any], market: str
    ) -> dict[str, Any] | None:
        """Extract price, volume, and change percentage from ticker data.

        For crypto, markets are 24/7, always using current intraday data from the 'day' bar.
        """
        day_value = ticker_item.get("day")
        if not isinstance(day_value, dict):
            ticker_log = ticker_item.get("ticker")
            if isinstance(ticker_log, str):
                logger.warning(f"Invalid 'day' data for ticker {ticker_log}")
            else:
                logger.warning("Invalid 'day' data for ticker (invalid ticker key)")
            day: dict[str, Any] = {}
        else:
            day = day_value

        # Extract todaysChangePerc (always available, reflects change since prevDay.c)
        change_perc_raw = ticker_item.get("todaysChangePerc")
        if isinstance(change_perc_raw, int | float):
            todays_change_perc = float(change_perc_raw)
        else:
            ticker_log = ticker_item.get("ticker")
            if isinstance(ticker_log, str):
                logger.warning(f"Missing or invalid todaysChangePerc for ticker {ticker_log}")
            else:
                logger.warning(
                    "Missing or invalid todaysChangePerc for ticker (invalid ticker key)"
                )
            todays_change_perc = None

        # Today (always)
        price = massive_get_numeric_from_dict(day, "c", 0.0)
        volume = massive_get_numeric_from_dict(day, "v", 0.0)
        change_perc = todays_change_perc  # API-provided, from prevDay to day.c
        data_source = "day"

        if price <= 0:
            ticker_log = ticker_item.get("ticker")
            if isinstance(ticker_log, str):
                logger.warning(f"Invalid price (<=0) for ticker {ticker_log}")
            else:
                logger.warning("Invalid price (<=0) for ticker (invalid ticker key)")
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
        # Type guards for ticker_data values
        price_raw = ticker_data.get("price")
        if not isinstance(price_raw, int | float):
            return False
        price = float(price_raw)

        volume_raw = ticker_data.get("volume")
        if not isinstance(volume_raw, int | float):
            return False
        volume = float(volume_raw)

        change_perc_raw = ticker_data.get("change_perc")
        change_perc: float | None = None
        if isinstance(change_perc_raw, int | float):
            change_perc = float(change_perc_raw)

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

        asset_class = AssetClass.CRYPTO

        # Type guards for metadata
        data_source_raw = ticker_data.get("data_source")
        data_source = data_source_raw if isinstance(data_source_raw, str) else "unknown"

        change_perc_raw = ticker_data.get("change_perc")
        change_available = isinstance(change_perc_raw, int | float)

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
