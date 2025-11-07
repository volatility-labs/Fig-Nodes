# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false
import asyncio
import json
import logging
import os
import time
from typing import Any, cast

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
        "place_brackets": True,
        "stop_loss_percent": 2.0,
        "trading_mode": "spot",  # spot | futures
        # Scaling and persistence
        "allow_scaling": False,
        "max_scale_entries": 1,
        "scale_cooldown_s": 1800,
        "persist_state": False,
        "state_path": "results/kucoin_trader_state.json",
        # Market validation
        "skip_unsupported_markets": True,
    }

    params_meta = [
        {"name": "risk_per_trade_usd", "type": "number", "default": 10.0, "label": "Risk per trade (USD)"},
        {"name": "sl_buffer_percent_above_liquidation", "type": "number", "default": 0.5, "label": "SL buffer % above liq"},
        {"name": "take_profit_percent", "type": "number", "default": 3.0, "label": "TP %"},
        {"name": "trading_mode", "type": "combo", "default": "spot", "options": ["spot", "futures"], "label": "Trading mode"},
        {"name": "place_brackets", "type": "combo", "default": True, "options": [True, False], "label": "Place TP/SL after fill"},
        {"name": "stop_loss_percent", "type": "number", "default": 2.0, "label": "SL % (spot)"},
        {"name": "leverage", "type": "integer", "default": 40, "label": "Desired leverage"},
        {"name": "max_concurrent_positions", "type": "integer", "default": 25, "label": "Max concurrent positions"},
        {"name": "dry_run", "type": "combo", "default": True, "options": [True, False], "label": "Dry run (no real orders)"},
        {"name": "skip_unsupported_markets", "type": "combo", "default": True, "options": [True, False], "label": "Skip unsupported markets"},
        {"name": "allow_scaling", "type": "combo", "default": False, "options": [True, False], "label": "Allow scaling"},
        {"name": "max_scale_entries", "type": "integer", "default": 1, "label": "Max scale entries"},
        {"name": "scale_cooldown_s", "type": "integer", "default": 1800, "label": "Scale cooldown (s)"},
        {"name": "persist_state", "type": "combo", "default": False, "options": [True, False], "label": "Persist state"},
        {"name": "state_path", "type": "text", "default": "results/kucoin_trader_state.json", "label": "State path"},
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        def _as_float(val: Any, default: float) -> float:
            try:
                return float(val)
            except Exception:
                return default

        def _as_int(val: Any, default: int) -> int:
            try:
                return int(val)
            except Exception:
                return default

        symbols: list[AssetSymbol] = inputs.get("symbols", []) or []

        if not symbols:
            return {"orders": []}

        params = self.params
        amount_mode = "quote"
        # Always use risk per trade for quote sizing
        risk_usd = _as_float(params.get("risk_per_trade_usd", 0.0) or 0.0, 0.0)
        amount = risk_usd if risk_usd > 0 else _as_float(params.get("amount", 0.0) or 0.0, 0.0)
        default_quote = "USDT"
        convert_usd_to_usdt = True
        dry_run = bool(params.get("dry_run", True))
        # Tie concurrency to max_concurrent_positions if provided
        concurrency = max(1, _as_int(params.get("max_concurrent_positions", params.get("concurrency", 3)), 3))
        # Optional leverage param (currently informational for spot; required for futures builds)
        leverage = _as_int(params.get("leverage", 1) or 1, 1)
        # Scaling and persistence
        allow_scaling = bool(params.get("allow_scaling", False))
        max_scale_entries = max(1, _as_int(params.get("max_scale_entries", 1), 1))
        scale_cooldown_s = max(0, _as_int(params.get("scale_cooldown_s", 1800), 1800))
        persist_state = bool(params.get("persist_state", False))
        state_path = str(params.get("state_path", "results/kucoin_trader_state.json"))
        skip_unsupported = bool(params.get("skip_unsupported_markets", True))
        place_brackets = bool(params.get("place_brackets", True))
        stop_loss_percent = _as_float(params.get("stop_loss_percent", 2.0) or 2.0, 2.0)
        trading_mode = str(params.get("trading_mode", "spot")).lower()

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

        # Cache markets set across tasks to avoid repeated load_markets()
        markets_loaded = False
        markets_set: set[str] = set()
        markets_lock = asyncio.Lock()

        async def place_for_symbol(sym: AssetSymbol) -> dict[str, Any]:
            # Build Kucoin symbol format: TICKER-QUOTE
            ticker = sym.ticker.upper()
            quote = (sym.quote_currency or default_quote or "USDT").upper()
            if convert_usd_to_usdt and quote == "USD":
                quote = "USDT"
            if trading_mode == "futures":
                # ccxt unified futures symbol for Kucoin is like "BTC/USDT:USDT"
                market_symbol = f"{ticker}/{quote}:{quote}"
            else:
                market_symbol = f"{ticker}-{quote}"

            # Optional precheck: skip unsupported markets
            if skip_unsupported:
                try:
                    import ccxt  # type: ignore
                except Exception as e:  # pragma: no cover
                    return {
                        "symbol": str(sym),
                        "kucoin_symbol": market_symbol,
                        "error": f"ccxt not available: {e}",
                        "status": "error",
                        "filled": False,
                        "message": "ccxt not installed for market check",
                    }

                nonlocal markets_loaded, markets_set
                if not markets_loaded:
                    async with markets_lock:
                        if not markets_loaded:
                            try:
                                ex_pre: Any = ccxt.kucoinfutures() if trading_mode == "futures" else ccxt.kucoin()
                                loaded: dict[str, Any] = cast(dict[str, Any], ex_pre.load_markets())
                                markets_set = set(map(str, loaded.keys()))
                                markets_loaded = True
                            except Exception as e:
                                return {
                                    "symbol": str(sym),
                                    "kucoin_symbol": market_symbol,
                                    "error": str(e),
                                    "status": "error",
                                    "filled": False,
                                    "message": "failed to load markets",
                                }

                if market_symbol not in markets_set:
                    return {
                        "symbol": str(sym),
                        "kucoin_symbol": market_symbol,
                        "status": "unsupported_market",
                        "filled": False,
                        "message": "market not listed on Kucoin",
                    }

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
                    "filled": False,
                    "message": "dry_run",
                }
                # Attach bracket preview if enabled
                tp_pct = _as_float(params.get("take_profit_percent", 3.0), 3.0)
                sl_buf = _as_float(params.get("sl_buffer_percent_above_liquidation", 0.0) or 0.0, 0.0)
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
                exchange: Any = (ccxt.kucoinfutures if trading_mode == "futures" else ccxt.kucoin)({
                    "apiKey": api_key,
                    "secret": api_secret,
                    "password": api_passphrase,
                    "enableRateLimit": True,
                })
                if trading_mode == "futures":
                    try:
                        exchange.set_leverage(leverage, market_symbol)
                    except Exception:  # pragma: no cover
                        pass

                # Compute base amount if operating in quote terms
                order_amount = amount
                if amount_mode == "quote":
                    ticker_info: dict[str, Any] = cast(dict[str, Any], exchange.fetch_ticker(market_symbol))
                    last = float(cast(float | int | str, ticker_info.get("last") or ticker_info.get("close") or 0.0))
                    if last <= 0:
                        raise ValueError(f"Cannot determine price for {market_symbol}")
                    order_amount = amount / last

                # Place entry
                order_params: dict[str, Any] = {}
                if trading_mode == "futures":
                    order_params["reduceOnly"] = False

                amt_prec = exchange.amount_to_precision(market_symbol, order_amount)
                order_amount_num = float(amt_prec) if isinstance(amt_prec, str) else float(amt_prec)
                order: dict[str, Any] | Any = exchange.create_order(
                    market_symbol,
                    "market",
                    "buy",
                    order_amount_num,
                    None if trading_mode == "futures" else None,
                    order_params,
                )
                # Update state (scale count + timestamp)
                async with lock:
                    entries = state.setdefault("entries", {})
                    info = entries.get(market_symbol) or {"scale_count": 0, "last_scale_time": 0.0}
                    info["scale_count"] = int(info.get("scale_count", 0)) + 1
                    info["last_scale_time"] = now_ts
                    entries[market_symbol] = info

                order_status = str((cast(dict[str, Any], order) or {}).get("status", "")).lower()
                is_filled = order_status in {"closed", "filled"}

                order_result: dict[str, Any] = {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "side": "buy",
                    "amount": order_amount,
                    "status": "filled_or_submitted",
                    "order": order,
                    "filled": is_filled,
                    "message": ("filled" if is_filled else (order_status or "submitted")),
                }
                # Return computed target percentages; order management handled externally
                order_result["tp_percent"] = _as_float(params.get("take_profit_percent", 3.0), 3.0)
                order_result["sl_buffer_percent_above_liquidation"] = _as_float(params.get("sl_buffer_percent_above_liquidation", 0.0) or 0.0, 0.0)
                order_result["leverage"] = leverage

                # Optional bracket placement
                if place_brackets:
                    try:
                        # Determine entry price
                        entry_price: float | None = None
                        if isinstance(order, dict):
                            entry_price = cast(float | int | str | None, order.get("average") or order.get("price") or cast(dict[str, Any], order.get("info", {})).get("price"))  # type: ignore[reportUnknownMemberType]
                        if entry_price is None or float(entry_price) <= 0:
                            tkr: dict[str, Any] = cast(dict[str, Any], exchange.fetch_ticker(market_symbol))
                            entry_price = float(cast(float | int | str, tkr.get("last") or tkr.get("close") or 0.0))
                        entry_price = float(entry_price)
                        if entry_price <= 0:
                            raise ValueError("cannot determine entry price for bracket calc")

                        qty_prec = exchange.amount_to_precision(market_symbol, order_amount)
                        qty_num = float(qty_prec) if isinstance(qty_prec, str) else float(qty_prec)
                        tp_pct = _as_float(params.get("take_profit_percent", 3.0), 3.0)
                        tp_price = entry_price * (1.0 + tp_pct / 100.0)
                        if trading_mode == "futures":
                            # Try to fetch liquidation price to compute SL buffer
                            sl_price: float | None = None
                            try:
                                positions = []
                                try:
                                    positions = exchange.fetch_positions([market_symbol]) or []
                                except Exception:
                                    positions = exchange.fetch_positions() or []
                                liq = None
                                for p in positions:
                                    sym = p.get("symbol") or p.get("info", {}).get("symbol")
                                    if sym == market_symbol:
                                        liq = p.get("liquidationPrice") or p.get("info", {}).get("liquidationPrice")
                                        break
                                if liq:
                                    liq_f = float(liq)
                                    # Long only for now
                                    sl_price = liq_f * (1.0 + _as_float(params.get("sl_buffer_percent_above_liquidation", 0.5), 0.5) / 100.0)
                            except Exception:
                                sl_price = None
                            if not sl_price:
                                # Fallback to percent-of-entry if no liq price available
                                sl_price = entry_price * (1.0 - _as_float(params.get("stop_loss_percent", 2.0), 2.0) / 100.0)
                        else:
                            sl_pct_spot = float(stop_loss_percent)
                            sl_price = entry_price * (1.0 - sl_pct_spot / 100.0)

                        tp_price_p: str = cast(str, exchange.price_to_precision(market_symbol, tp_price))
                        sl_price_p: str = cast(str, exchange.price_to_precision(market_symbol, sl_price))

                        tp_params: dict[str, Any] = {}
                        if trading_mode == "futures":
                            tp_params["reduceOnly"] = True

                        tp_order: dict[str, Any] | Any = exchange.create_order(
                            market_symbol,
                            "limit",
                            "sell",
                            qty_num,
                            float(tp_price_p),
                            tp_params,
                        )
                        order_result["tp_order"] = tp_order

                        # Try to place a stop or stop-limit order for SL. If unsupported, capture error.
                        sl_order = None
                        sl_error = None
                        try:
                            # Many exchanges require stop params; Kucoin may accept 'stop'/'stopPrice'.
                            sl_params: dict[str, Any] = {"stop": "loss", "stopPrice": float(sl_price_p)}
                            if trading_mode == "futures":
                                sl_params["reduceOnly"] = True
                            # Prefer market stop; if rejected, fall back to stop-limit with price
                            try:
                                sl_order = exchange.create_order(
                                    market_symbol,
                                    "market",
                                    "sell",
                                    qty_num,
                                    None,
                                    sl_params,
                                )
                            except Exception:
                                sl_params_lim = {"stop": "loss", "stopPrice": float(sl_price_p)}
                                if trading_mode == "futures":
                                    sl_params_lim["reduceOnly"] = True
                                sl_order = exchange.create_order(
                                    market_symbol,
                                    "limit",
                                    "sell",
                                    qty_num,
                                    float(sl_price_p),
                                    sl_params_lim,
                                )
                        except Exception as e_sl:  # pragma: no cover
                            sl_error = str(e_sl)

                        if sl_order is not None:
                            order_result["sl_order"] = sl_order
                        if sl_error is not None:
                            order_result["sl_error"] = sl_error
                    except Exception as e_br:  # pragma: no cover
                        order_result["brackets_error"] = str(e_br)

                return order_result
            except Exception as e:  # pragma: no cover
                logger.exception("Kucoin order failed")
                return {
                    "symbol": str(sym),
                    "kucoin_symbol": market_symbol,
                    "error": str(e),
                    "status": "error",
                    "filled": False,
                    "message": "order_error",
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


