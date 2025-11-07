import asyncio
import json
import logging
import os
import time
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
        # Scaling and persistence
        "allow_scaling": False,
        "max_scale_entries": 1,
        "scale_cooldown_s": 1800,
        "persist_state": False,
        "state_path": "results/kucoin_trader_state.json",
    }

    params_meta = [
        {"name": "risk_per_trade_usd", "type": "number", "default": 10.0, "label": "Risk per trade (USD)"},
        {"name": "sl_buffer_percent_above_liquidation", "type": "number", "default": 0.5, "label": "SL buffer % above liq"},
        {"name": "take_profit_percent", "type": "number", "default": 3.0, "label": "TP %"},
        {"name": "leverage", "type": "integer", "default": 40, "label": "Desired leverage"},
        {"name": "max_concurrent_positions", "type": "integer", "default": 25, "label": "Max concurrent positions"},
        {"name": "dry_run", "type": "combo", "default": True, "options": [True, False], "label": "Dry run (no real orders)"},
        {"name": "allow_scaling", "type": "combo", "default": False, "options": [True, False], "label": "Allow scaling"},
        {"name": "max_scale_entries", "type": "integer", "default": 1, "label": "Max scale entries"},
        {"name": "scale_cooldown_s", "type": "integer", "default": 1800, "label": "Scale cooldown (s)"},
        {"name": "persist_state", "type": "combo", "default": False, "options": [True, False], "label": "Persist state"},
        {"name": "state_path", "type": "text", "default": "results/kucoin_trader_state.json", "label": "State path"},
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
        # Scaling and persistence
        allow_scaling = bool(params.get("allow_scaling", False))
        max_scale_entries = max(1, int(params.get("max_scale_entries", 1)))
        scale_cooldown_s = max(0, int(params.get("scale_cooldown_s", 1800)))
        persist_state = bool(params.get("persist_state", False))
        state_path = str(params.get("state_path", "results/kucoin_trader_state.json"))

        # Load state
        state_key = "kucoin_trader_state"
        state: dict[str, Any] = self.graph_context.get(state_key) or {"entries": {}}
        if persist_state:
            try:
                if os.path.exists(state_path):
                    with open(state_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict) and "entries" in loaded:
                            state = loaded
            except Exception as e:
                logger.warning("Failed to load state from %s: %s", state_path, e)
        self.graph_context[state_key] = state

        vault = APIKeyVault()
        api_key = vault.get("KUCOIN_API_KEY")
        api_secret = vault.get("KUCOIN_API_SECRET")
        api_passphrase = vault.get("KUCOIN_API_PASSPHRASE")

        lock = asyncio.Lock()

        async def place_for_symbol(sym: AssetSymbol) -> dict[str, Any]:
            # Build Kucoin symbol format: TICKER-QUOTE
            ticker = sym.ticker.upper()
            quote = (sym.quote_currency or default_quote or "USDT").upper()
            if convert_usd_to_usdt and quote == "USD":
                quote = "USDT"
            market_symbol = f"{ticker}-{quote}"

            # Scaling guards (and duplicate prevention)
            now_ts = time.time()
            async with lock:
                entries: dict[str, Any] = state.setdefault("entries", {})
                info = entries.get(market_symbol) or {"scale_count": 0, "last_scale_time": 0.0}
                scale_count = int(info.get("scale_count", 0))
                last_scale_time = float(info.get("last_scale_time", 0.0))

                if not allow_scaling and scale_count >= 1:
                    return {
                        "symbol": str(sym),
                        "kucoin_symbol": market_symbol,
                        "status": "skipped_existing_position",
                        "reason": "scaling_disabled",
                    }
                if allow_scaling:
                    if scale_count >= max_scale_entries:
                        return {
                            "symbol": str(sym),
                            "kucoin_symbol": market_symbol,
                            "status": "skipped_max_scale",
                            "scale_count": scale_count,
                        }
                    if last_scale_time > 0 and (now_ts - last_scale_time) < scale_cooldown_s:
                        return {
                            "symbol": str(sym),
                            "kucoin_symbol": market_symbol,
                            "status": "skipped_cooldown",
                            "cooldown_remaining_s": int(scale_cooldown_s - (now_ts - last_scale_time)),
                        }

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

                order = exchange.create_order(
                    market_symbol,
                    "market",
                    "buy",
                    exchange.amount_to_precision(market_symbol, order_amount),
                )
                # Update state (scale count + timestamp)
                async with lock:
                    entries = state.setdefault("entries", {})
                    info = entries.get(market_symbol) or {"scale_count": 0, "last_scale_time": 0.0}
                    info["scale_count"] = int(info.get("scale_count", 0)) + 1
                    info["last_scale_time"] = now_ts
                    entries[market_symbol] = info

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

        # Save state if persistence enabled after all tasks
        async def save_state_if_needed():
            if not persist_state:
                return
            try:
                os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
            except Exception as e:
                logger.warning("Failed to save state to %s: %s", state_path, e)

        # Concurrency-limited execution
        semaphore = asyncio.Semaphore(concurrency)

        async def sem_task(s: AssetSymbol):
            async with semaphore:
                return await place_for_symbol(s)

        tasks = [asyncio.create_task(sem_task(s)) for s in symbols if s.asset_class == AssetClass.CRYPTO]
        results = await asyncio.gather(*tasks) if tasks else []
        await save_state_if_needed()
        return {"orders": results}


