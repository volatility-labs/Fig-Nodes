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
        # Fixed behavior: market BUY orders, quote-sized by risk_per_trade_usd
        # ICP-bot style runtime prompts
        "risk_per_trade_usd": 10.0,
        "sl_buffer_percent_above_liquidation": 0.5,
        "leverage": 40,
        "max_concurrent_positions": 25,
        # Hidden controls
        "dry_run": True,
        "concurrency": 3,
        # Bracket configuration (spot only)
        "take_profit_percent": 3.0,   # e.g., +3%
    }

    params_meta = [
        {"name": "risk_per_trade_usd", "type": "number", "default": 10.0, "label": "Risk per trade (USD)"},
        {"name": "sl_buffer_percent_above_liquidation", "type": "number", "default": 0.5, "label": "SL buffer % above liq"},
        {"name": "take_profit_percent", "type": "number", "default": 3.0, "label": "TP %"},
        {"name": "leverage", "type": "integer", "default": 40, "label": "Desired leverage"},
        {"name": "max_concurrent_positions", "type": "integer", "default": 25, "label": "Max concurrent positions"},
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        symbols: list[AssetSymbol] = inputs.get("symbols", []) or []

        if not symbols:
            return {"orders": []}

        params = self.params
        side = str(params.get("side", "buy")).lower()
        amount_mode = "quote"
        # Always use risk per trade for quote sizing
        risk_usd = float(params.get("risk_per_trade_usd", 0.0) or 0.0)
        amount = risk_usd if risk_usd > 0 else float(params.get("amount", 0.0) or 0.0)
        default_quote = "USDT"
        convert_usd_to_usdt = True
        dry_run = bool(params.get("dry_run", True))
        # Tie concurrency to max_concurrent_positions if provided
        concurrency = max(1, int(params.get("max_concurrent_positions", params.get("concurrency", 3))))
        # Optional leverage param (currently informational for spot; required for futures builds)
        leverage = int(params.get("leverage", 1) or 1)

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
                result: dict[str, Any] = {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "side": "buy",
                    "amount_mode": amount_mode,
                    "amount": amount,
                    "status": "dry_run",
                }
                # Attach bracket preview if enabled
                tp_pct = float(params.get("take_profit_percent", 3.0))
                sl_buf = float(params.get("sl_buffer_percent_above_liquidation", 0.0) or 0.0)
                result["tp_percent"] = tp_pct
                result["sl_buffer_percent_above_liquidation"] = sl_buf
                result["leverage"] = leverage
                return result

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

                # Prevent immediate duplicate entries per session
                active_key = "kucoin_active_symbols"
                active: set[str] = self.graph_context.setdefault(active_key, set())  # type: ignore
                if market_symbol in active:
                    return {
                        "symbol": str(sym),
                        "kucoin_symbol": market_symbol,
                        "status": "skipped_existing_position",
                    }

                order = exchange.create_order(
                    market_symbol,
                    "market",
                    "buy",
                    exchange.amount_to_precision(market_symbol, order_amount),
                )
                # Mark as active to avoid immediate re-entry
                active.add(market_symbol)

                result: dict[str, Any] = {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "side": "buy",
                    "amount": order_amount,
                    "status": "filled_or_submitted",
                    "order": order,
                }
                # Return computed target percentages; order management handled externally
                result["tp_percent"] = float(params.get("take_profit_percent", 3.0))
                result["sl_buffer_percent_above_liquidation"] = float(params.get("sl_buffer_percent_above_liquidation", 0.0) or 0.0)
                result["leverage"] = leverage

                return result
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


