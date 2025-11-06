"""
Polygon Snapshot Service - Fetches current price data from snapshot API
"""
import logging
from datetime import datetime
from typing import Any, cast

import httpx
import pytz

from core.types_registry import AssetClass, AssetSymbol, OHLCVBar

logger = logging.getLogger(__name__)


async def fetch_current_snapshot(
    symbol: AssetSymbol, api_key: str
) -> tuple[float | None, dict[str, Any]]:
    """
    Fetches current price from Polygon snapshot API.
    
    Args:
        symbol: AssetSymbol to fetch snapshot for
        api_key: API key for Massive.com (POLYGON_API_KEY)
    
    Returns:
        Tuple of (current_price, metadata dict)
    """
    # Determine the correct snapshot endpoint based on asset class
    if symbol.asset_class == AssetClass.CRYPTO:
        # Use single-ticker snapshot endpoint for crypto to avoid pagination issues
        ticker_with_prefix = f"X:{symbol.ticker}"
        snapshot_url = (
            f"https://api.massive.com/v2/snapshot/locale/global/markets/crypto/tickers/{ticker_with_prefix}"
        )
    else:
        ticker_with_prefix = str(symbol.ticker)
        snapshot_url = (
            f"https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/{ticker_with_prefix}"
        )
    
    # Massive/Polygon REST docs show using apiKey query param for auth
    query_params = {"apiKey": api_key}
    
    logger.info(f"SNAPSHOT: Fetching snapshot for {symbol.ticker} from {snapshot_url}")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(snapshot_url, params=query_params)
            logger.info(f"SNAPSHOT: Got response status {response.status_code} for {symbol.ticker}")
            
            if response.status_code != 200:
                logger.error(f"Snapshot API failed for {symbol.ticker}: {response.status_code}")
                return None, {"error": f"HTTP {response.status_code}"}
            
            data: dict[str, Any] = response.json()
            
            ticker_data_dict: dict[str, Any] = {}
            if symbol.asset_class == AssetClass.CRYPTO:
                # For crypto single-ticker endpoint, data should be under 'ticker'
                ticker_data: dict[str, Any] | None = data.get("ticker")  # type: ignore[assignment]
                if not ticker_data:
                    # Fallback: some responses might wrap results differently
                    # Try to find by checking common fields
                    possible_any = data.get("results") or data.get("tickers")
                    if isinstance(possible_any, list) and possible_any:
                        possible: list[dict[str, Any]] = []
                        possible_list = cast(list[Any], possible_any)
                        for item_any in possible_list:
                            item: Any = item_any
                            if isinstance(item, dict):
                                possible.append(cast(dict[str, Any], item))
                        found_item: dict[str, Any] | None = None
                        for t in possible:
                            if t.get("ticker") in {ticker_with_prefix, symbol.ticker}:
                                found_item = t
                                break
                        ticker_data = found_item
                if not ticker_data:
                    logger.error(
                        f"SNAPSHOT: ❌ Ticker data not found for {ticker_with_prefix}. Keys: {list(data.keys())}"
                    )
                    return None, {"error": f"Ticker {ticker_with_prefix} not found"}
                # ensure type for downstream access
                assert isinstance(ticker_data, dict)
                ticker_data_dict = ticker_data
            else:
                # For stocks, we got a single ticker response
                td = data.get("ticker", {})
                td_dict: dict[str, Any]
                if isinstance(td, dict):
                    td_dict = cast(dict[str, Any], td)
                else:
                    td_dict = {}
                ticker_data_dict = td_dict
            
            # Extract current price from preferred fields
            day_data: dict[str, Any] = ticker_data_dict.get("day", {})
            current_price: float | None = day_data.get("c")  # closing price
            
            if current_price is None:
                # Try previous day if current day has no data
                prev_day: dict[str, Any] = ticker_data_dict.get("prevDay", {})
                current_price = prev_day.get("c")
            
            if current_price is None:
                # Try min/lastTrade as additional fallbacks
                min_data: dict[str, Any] = ticker_data_dict.get("min", {})
                current_price = min_data.get("c")
                
                if current_price is None:
                    last_trade: dict[str, Any] = ticker_data_dict.get("lastTrade", {})
                    current_price = last_trade.get("p")
            
            # Get quote timestamp for freshness check
            last_quote: dict[str, Any] = ticker_data_dict.get("lastQuote", {})
            quote_timestamp: Any = last_quote.get("t")
            
            metadata: dict[str, Any] = {
                "data_source": "snapshot",
                "quote_timestamp": quote_timestamp,
                "ticker_data": ticker_data_dict
            }
            
            if current_price is not None:
                logger.info(f"SNAPSHOT: ✅ Got price ${current_price} for {symbol.ticker}")
            else:
                logger.error(f"SNAPSHOT: ❌ No price found in ticker data for {symbol.ticker}")
                
            return current_price, metadata
            
    except Exception as e:
        logger.error(f"Error fetching snapshot for {symbol.ticker}: {e}")
        return None, {"error": str(e)}


async def create_current_bar_from_snapshot(
    symbol: AssetSymbol, api_key: str
) -> tuple[list[OHLCVBar], dict[str, Any]]:
    """
    Creates a current OHLCV bar using snapshot data.
    This is a fallback when aggregates API returns stale data.
    
    Args:
        symbol: AssetSymbol to create bar for
        api_key: API key for Massive.com
    
    Returns:
        Tuple of (list with single current bar, metadata dict)
    """
    current_price, snapshot_metadata = await fetch_current_snapshot(symbol, api_key)
    
    if current_price is None:
        return [], {"error": "No current price available"}
    
    # Create a synthetic bar with current price as OHLC
    # This is not ideal but provides current data when aggregates are stale
    current_time = datetime.now(pytz.UTC)
    current_timestamp_ms = int(current_time.timestamp() * 1000)
    
    # Use current price for all OHLC values (not ideal but current)
    # Volume is 0.0 since snapshot doesn't provide volume data
    synthetic_bar: OHLCVBar = {
        "timestamp": current_timestamp_ms,
        "open": current_price,
        "high": current_price,
        "low": current_price,
        "close": current_price,
        "volume": 0.0,  # Volume not available from snapshot
    }
    
    metadata = {
        "data_status": "synthetic_current",
        "data_source": "snapshot_fallback",
        "note": "Synthetic bar created from current snapshot due to stale aggregates",
        **snapshot_metadata
    }
    
    logger.info(f"Created synthetic current bar for {symbol.ticker}: ${current_price}")
    
    return [synthetic_bar], metadata

