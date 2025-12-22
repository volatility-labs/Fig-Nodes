"""Watchlist streaming API endpoints."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetClass, AssetSymbol
from services.polygon_service import fetch_current_snapshot, massive_fetch_snapshot

logger = logging.getLogger(__name__)

router = APIRouter()


class SubscribeMessage(BaseModel):
    """Subscribe message from client."""
    type: str
    symbols: list[dict[str, str]]  # [{"symbol": "AAPL", "assetClass": "stocks"}, ...]


class WatchlistUpdate(BaseModel):
    """Watchlist update message to client."""
    type: str
    symbol: str
    assetClass: str
    price: float | None
    change: float | None
    changePercent: float | None
    volume: float | None


async def fetch_symbol_snapshot(symbol: str, asset_class: str, api_key: str) -> dict[str, Any]:
    """Fetch current snapshot for a symbol."""
    try:
        # Create AssetSymbol object
        asset_class_enum = AssetClass.CRYPTO if asset_class == "crypto" else AssetClass.STOCKS
        
        # Parse crypto symbols (e.g., "BTCUSD" -> ticker="BTC", quote="USD")
        if asset_class == "crypto":
            # Handle USD suffix (BTCUSD -> BTC + USD)
            symbol_upper = symbol.upper()
            if symbol_upper.endswith("USD") and len(symbol_upper) > 3:
                ticker = symbol_upper[:-3]
                quote = "USD"
                asset_symbol = AssetSymbol(ticker=ticker, asset_class=asset_class_enum, quote_currency=quote)
            else:
                # Use AssetSymbol.from_string for USDT and other cases
                asset_symbol = AssetSymbol.from_string(symbol, asset_class_enum)
        else:
            asset_symbol = AssetSymbol(ticker=symbol, asset_class=asset_class_enum)

        # Fetch snapshot
        price, metadata = await fetch_current_snapshot(asset_symbol, api_key)
        
        if price is None:
            return {
                "symbol": symbol,
                "assetClass": asset_class,
                "price": None,
                "change": None,
                "changePercent": None,
                "volume": None,
            }

        # For change calculation, we need previous day close
        # Use massive_fetch_snapshot to get full snapshot data
        ticker = symbol
        if asset_class == "crypto":
            ticker = f"X:{ticker}"
            locale = "global"
            markets = "crypto"
        else:
            ticker = ticker.upper()
            locale = "us"
            markets = "stocks"

        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            snapshots = await massive_fetch_snapshot(
                client, api_key, locale, markets, asset_class, [ticker], False
            )

        change = None
        change_percent = None
        volume = None

        if snapshots:
            snapshot = snapshots[0]
            
            # Get volume
            day_data = snapshot.get("day", {})
            if isinstance(day_data, dict):
                volume_val = day_data.get("v")
                if isinstance(volume_val, (int, float)):
                    volume = float(volume_val)

            # Calculate change from previous day
            prev_day = snapshot.get("prevDay", {})
            if isinstance(prev_day, dict):
                prev_close = prev_day.get("c")
                if isinstance(prev_close, (int, float)) and prev_close > 0:
                    change = price - float(prev_close)
                    change_percent = (change / float(prev_close)) * 100.0

        return {
            "symbol": symbol,
            "assetClass": asset_class,
            "price": price,
            "change": change,
            "changePercent": change_percent,
            "volume": volume,
        }
    except Exception as e:
        logger.error(f"Error fetching snapshot for {symbol}: {e}", exc_info=True)
        return {
            "symbol": symbol,
            "assetClass": asset_class,
            "price": None,
            "change": None,
            "changePercent": None,
            "volume": None,
        }


async def watchlist_stream_worker(websocket: WebSocket, symbols: list[dict[str, str]]):
    """Worker that streams watchlist updates."""
    api_key = APIKeyVault().get("POLYGON_API_KEY")
    if not api_key:
        await websocket.send_json({
            "type": "error",
            "message": "POLYGON_API_KEY is required but not set in vault"
        })
        return

    update_interval = 5.0  # Update every 5 seconds

    try:
        while True:
            # Fetch all symbols in parallel
            tasks = [
                fetch_symbol_snapshot(sym["symbol"], sym["assetClass"], api_key)
                for sym in symbols
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Send updates for each symbol (always send, even if data is None)
            # This ensures symbols stay in the watchlist even if fetch fails
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in watchlist update for {symbols[i]}: {result}")
                    # Send update with None values to keep symbol in list
                    update = WatchlistUpdate(
                        type="update",
                        symbol=symbols[i]["symbol"],
                        assetClass=symbols[i]["assetClass"],
                        price=None,
                        change=None,
                        changePercent=None,
                        volume=None,
                    )
                else:
                    update = WatchlistUpdate(
                        type="update",
                        symbol=result["symbol"],
                        assetClass=result["assetClass"],
                        price=result["price"],
                        change=result["change"],
                        changePercent=result["changePercent"],
                        volume=result["volume"],
                    )
                await websocket.send_json(update.model_dump())

            # Wait before next update
            await asyncio.sleep(update_interval)

    except asyncio.CancelledError:
        logger.info("Watchlist stream worker cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in watchlist stream worker: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


@router.websocket("/watchlist/stream")
async def watchlist_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming watchlist data."""
    await websocket.accept()
    logger.info("Watchlist WebSocket connection established")

    symbols: list[dict[str, str]] = []
    worker_task: asyncio.Task[None] | None = None

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()

            try:
                message = SubscribeMessage(**data)
            except ValidationError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid message format: {e.errors()[0]['msg']}"
                })
                continue

            if message.type == "subscribe":
                # Cancel existing worker if any
                if worker_task:
                    worker_task.cancel()
                    try:
                        await worker_task
                    except asyncio.CancelledError:
                        pass

                # Update symbols list
                symbols = message.symbols

                # Start new worker
                worker_task = asyncio.create_task(
                    watchlist_stream_worker(websocket, symbols)
                )
                logger.info(f"Subscribed to {len(symbols)} symbols")

            elif message.type == "unsubscribe":
                # Cancel worker
                if worker_task:
                    worker_task.cancel()
                    try:
                        await worker_task
                    except asyncio.CancelledError:
                        pass
                    worker_task = None
                symbols = []
                logger.info("Unsubscribed from watchlist")

    except WebSocketDisconnect:
        logger.info("Watchlist WebSocket disconnected")
        if worker_task:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        logger.error(f"Error in watchlist stream: {e}", exc_info=True)
        if worker_task:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

