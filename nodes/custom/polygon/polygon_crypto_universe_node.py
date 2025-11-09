import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetClass, AssetSymbol, get_type
from nodes.base.base_node import Base
from services.polygon_service import (
    massive_build_snapshot_tickers,
    massive_fetch_snapshot,
    massive_get_numeric_from_dict,
    massive_parse_ticker_for_market,
)

logger = logging.getLogger(__name__)


class PolygonCryptoUniverse(Base):
    """
    A node that fetches crypto symbols from the Massive.com API (formerly Polygon.io) and filters them
    based on the provided parameters.

    Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
    to use api.massive.com, but the API routes remain unchanged.

    Endpoint: https://api.massive.com/v2/snapshot/locale/global/markets/crypto/tickers
    
    Crypto markets operate 24/7, so data_day logic always uses today's intraday data
    unless explicitly set to prev_day for historical analysis.
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
            "name": "data_day",
            "type": "combo",
            "default": "auto",
            "options": ["auto", "today", "prev_day"],
            "label": "Data Day",
            "description": "Use intraday (today), previous day, or auto-select. Crypto markets are 24/7, so auto defaults to today.",
        },
    ]
    default_params = {}

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

        async with httpx.AsyncClient() as client:
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

            symbols = self._process_tickers(
                tickers_data, market, filter_params
            )

        return symbols

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
        filter_params: dict[str, float | None],
    ) -> list[AssetSymbol]:
        """Process ticker data and apply filters to produce AssetSymbol list."""
        symbols: list[AssetSymbol] = []
        total_tickers = len(tickers_data)

        for ticker_item in tickers_data:
            ticker = self._extract_ticker(ticker_item)
            if not ticker:
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
        
        For crypto, markets are 24/7, so auto mode defaults to today's intraday data.
        Only use prev_day if explicitly requested.
        """
        day_value = ticker_item.get("day")
        prev_day_value = ticker_item.get("prevDay")

        if not isinstance(day_value, dict):
            day: dict[str, Any] = {}
        else:
            day = day_value

        if not isinstance(prev_day_value, dict):
            prev_day: dict[str, Any] = {}
        else:
            prev_day = prev_day_value

        data_day_param_raw = self.params.get("data_day", "auto")
        data_day_param = data_day_param_raw if isinstance(data_day_param_raw, str) else "auto"

        # Crypto markets are 24/7, so auto defaults to today (intraday data)
        if data_day_param == "prev_day":
            use_prev_day = True
        else:
            # auto or today both use today's intraday data for crypto
            use_prev_day = False

        if use_prev_day:
            price = massive_get_numeric_from_dict(prev_day, "c", 0.0)
            volume = massive_get_numeric_from_dict(prev_day, "v", 0.0)
            change_perc_raw = ticker_item.get("prevDayChangePerc")
            if isinstance(change_perc_raw, int | float):
                change_perc = float(change_perc_raw)
            else:
                change_perc = 0.0
        else:
            # Use today's intraday data (crypto markets are always open)
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

        asset_class = AssetClass.CRYPTO

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




