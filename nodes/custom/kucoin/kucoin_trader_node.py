import asyncio
import logging
from typing import Any

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    AssetClass,
    AssetSymbol,
    NodeCategory,
    get_type,
)
from nodes.base.base_node import Base


logger = logging.getLogger(__name__)


class KucoinTraderNode(Base):
    """
    Places spot market orders on Kucoin for a list of symbols.

    Inputs:
      - symbols: AssetSymbolList

    Outputs:
      - orders: list[dict[str, Any]] (order placement results)

    Notes:
      - Requires environment keys: KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE
      - Uses lazy import of ccxt to avoid hard dependency at import time
    """

    CATEGORY = NodeCategory.IO
    inputs = {
        "symbols": get_type("AssetSymbolList"),
    }
    outputs = {
        "orders": get_type("AnyList"),
    }

    # Advertise required API keys to the UI/APIKey manager
    required_keys = [
        "KUCOIN_API_KEY",
        "KUCOIN_API_SECRET",
        "KUCOIN_API_PASSPHRASE",
    ]

    default_params = {
        "side": "buy",  # "buy" | "sell"
        "order_type": "market",  # currently only market supported
        "order_amount_mode": "quote",  # "quote" | "base"
        "amount": 25.0,  # amount in quote or base as per mode
        "default_quote_currency": "USDT",
        "convert_usd_to_usdt": True,
        "dry_run": True,
        "concurrency": 3,
    }

    params_meta = [
        {"name": "side", "type": "combo", "default": "buy", "options": ["buy", "sell"], "label": "Side"},
        {
            "name": "order_amount_mode",
            "type": "combo",
            "default": "quote",
            "options": ["quote", "base"],
            "label": "Amount Mode",
            "description": "Interpret amount as quote (e.g., USDT) or base units",
        },
        {"name": "amount", "type": "number", "default": 25.0, "label": "Amount"},
        {
            "name": "default_quote_currency",
            "type": "text",
            "default": "USDT",
            "label": "Default Quote",
            "description": "Used when symbol quote is missing",
        },
        {
            "name": "convert_usd_to_usdt",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "USD→USDT",
        },
        {"name": "dry_run", "type": "combo", "default": True, "options": [True, False], "label": "Dry Run"},
        {"name": "concurrency", "type": "integer", "default": 3, "label": "Concurrency"},
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        symbols: list[AssetSymbol] = inputs.get("symbols", []) or []

        if not symbols:
            return {"orders": []}

        params = self.params
        side = str(params.get("side", "buy")).lower()
        amount_mode = str(params.get("order_amount_mode", "quote")).lower()
        amount = float(params.get("amount", 25.0))
        default_quote = str(params.get("default_quote_currency", "USDT")).upper()
        convert_usd_to_usdt = bool(params.get("convert_usd_to_usdt", True))
        dry_run = bool(params.get("dry_run", True))
        concurrency = max(1, int(params.get("concurrency", 3)))

        vault = APIKeyVault()
        api_key = vault.get("KUCOIN_API_KEY")
        api_secret = vault.get("KUCOIN_API_SECRET")
        api_passphrase = vault.get("KUCOIN_API_PASSPHRASE")

        async def place_for_symbol(sym: AssetSymbol) -> dict[str, Any]:
            # Build Kucoin symbol format: TICKER-QUOTE
            ticker = sym.ticker.upper()
            quote = (sym.quote_currency or default_quote or "USDT").upper()
            if convert_usd_to_usdt and quote == "USD":
                quote = "USDT"
            market_symbol = f"{ticker}-{quote}"

            if dry_run:
                return {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "side": side,
                    "amount_mode": amount_mode,
                    "amount": amount,
                    "status": "dry_run",
                }

            if not (api_key and api_secret and api_passphrase):
                return {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "error": "Missing KUCOIN_API_* credentials",
                    "status": "error",
                }

            # Lazy import ccxt
            try:
                import ccxt  # type: ignore
            except Exception as e:  # pragma: no cover
                return {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "error": f"ccxt not available: {e}",
                    "status": "error",
                }

            try:
                exchange = ccxt.kucoin({
                    "apiKey": api_key,
                    "secret": api_secret,
                    "password": api_passphrase,
                    "enableRateLimit": True,
                })

                # Compute base amount if operating in quote terms
                order_amount = amount
                if amount_mode == "quote":
                    ticker_info = exchange.fetch_ticker(market_symbol)
                    last = float(ticker_info.get("last") or ticker_info.get("close") or 0.0)
                    if last <= 0:
                        raise ValueError(f"Cannot determine price for {market_symbol}")
                    order_amount = amount / last

                order = exchange.create_order(
                    market_symbol,
                    "market",
                    side,
                    exchange.amount_to_precision(market_symbol, order_amount),
                )
                return {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "side": side,
                    "amount": order_amount,
                    "status": "filled_or_submitted",
                    "order": order,
                }
            except Exception as e:  # pragma: no cover
                logger.exception("Kucoin order failed")
                return {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "error": str(e),
                    "status": "error",
                }

        # Concurrency-limited execution
        semaphore = asyncio.Semaphore(concurrency)

        async def sem_task(s: AssetSymbol):
            async with semaphore:
                return await place_for_symbol(s)

        tasks = [asyncio.create_task(sem_task(s)) for s in symbols if s.asset_class == AssetClass.CRYPTO]
        results = await asyncio.gather(*tasks) if tasks else []
        return {"orders": results}


