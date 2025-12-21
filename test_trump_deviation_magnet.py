#!/usr/bin/env python3
"""
Test script to verify Deviation Magnet filter on TRUMP coin with 1-minute bars.
"""

import asyncio
import logging
from core.types_registry import AssetClass, AssetSymbol
from nodes.core.market.filters.deviation_magnet_filter_node import DeviationMagnetFilter
from services.polygon_service import fetch_bars
from core.api_key_vault import APIKeyVault
from services.indicator_calculators.deviation_magnet_calculator import calculate_deviation_magnet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_trump_deviation_magnet():
    """Test Deviation Magnet filter on TRUMP coin with 1-minute bars."""
    
    # Create TRUMP symbol (crypto)
    symbol = AssetSymbol("TRUMPUSD", AssetClass.CRYPTO)
    logger.info(f"Testing Deviation Magnet filter on {symbol}")
    
    # Fetch 1-minute bars
    api_key_vault = APIKeyVault()
    api_key = api_key_vault.get("POLYGON_API_KEY")
    
    if not api_key:
        logger.error("POLYGON_API_KEY not found in vault")
        return
    
    logger.info("Fetching 1-minute bars for TRUMPUSD...")
    params = {
        "multiplier": 1,
        "timespan": "minute",
        "lookback_period": "1 day",  # Get recent data
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
    }
    
    bars, metadata = await fetch_bars(symbol, api_key, params)
    logger.info(f"Fetched {len(bars)} bars")
    logger.info(f"Data status: {metadata.get('data_status', 'unknown')}")
    
    if not bars or len(bars) < 50:
        logger.error(f"Not enough bars: {len(bars)} (need at least 50)")
        return
    
    # Calculate indicator values directly to see what's happening
    logger.info("\nCalculating Deviation Magnet indicator values...")
    opens = [bar["open"] for bar in bars]
    highs = [bar["high"] for bar in bars]
    lows = [bar["low"] for bar in bars]
    closes = [bar["close"] for bar in bars]
    
    indicator_result = calculate_deviation_magnet(
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        anchor=1,
        bblength=50,
        mult=2.0,
        timeframe_multiplier=1,
        coloring_sensitivity=2,
    )
    
    # Show last bar values
    logger.info("\nLast bar indicator values:")
    last_idx = len(bars) - 1
    logger.info(f"  price: {indicator_result['price'][last_idx]}")
    logger.info(f"  sq: {indicator_result['sq'][last_idx]}")
    logger.info(f"  top: {indicator_result['top'][last_idx]}")
    logger.info(f"  expansion_bullish: {indicator_result['expansion_bullish'][last_idx]}")
    logger.info(f"  expansion_bullish_rising: {indicator_result['expansion_bullish_rising'][last_idx]}")
    if 'expansion_bullish_rising_any' in indicator_result:
        logger.info(f"  expansion_bullish_rising_any: {indicator_result['expansion_bullish_rising_any'][last_idx]}")
    logger.info(f"  expansion_bearish: {indicator_result['expansion_bearish'][last_idx]}")
    
    # Check if top is rising on last bar
    if last_idx > 0:
        top_prev = indicator_result['top'][last_idx - 1]
        top_curr = indicator_result['top'][last_idx]
        top_rising_check = top_curr is not None and top_prev is not None and top_curr > top_prev
        logger.info(f"  top_rising (last bar): {top_rising_check} (prev={top_prev:.6f}, curr={top_curr:.6f})")
    
    # Show last 10 bars for trend analysis
    logger.info("\nLast 10 bars (top, sq, price, expansion_bullish_rising, top_rising check):")
    for i in range(max(0, last_idx - 9), last_idx + 1):
        top_val = indicator_result['top'][i]
        sq_val = indicator_result['sq'][i]
        price_val = indicator_result['price'][i]
        exp_rising = indicator_result['expansion_bullish_rising'][i]
        
        # Check if top is actually rising
        top_rising_check = False
        if i > 0:
            prev_top = indicator_result['top'][i-1]
            if top_val is not None and prev_top is not None:
                top_rising_check = top_val > prev_top
        
        logger.info(f"  Bar {i}: top={top_val:.6f}, sq={sq_val:.6f}, price={price_val:.6f}, exp_rising={exp_rising}, top_rising={top_rising_check}, top>sq={top_val > sq_val if (top_val is not None and sq_val is not None) else 'N/A'}")
    
    # Create OHLCV bundle
    ohlcv_bundle = {symbol: bars}
    
    # Create Deviation Magnet filter node
    filter_node = DeviationMagnetFilter("test_deviation_magnet", {})
    
    # Test with different filter conditions
    test_conditions = [
        "expansion_bullish_rising_any",  # NEW: Green line rising (any green)
        "expansion_bullish_rising",
        "expansion_bullish",
        "bullish",
        "price_above_zero",
    ]
    
    for condition in test_conditions:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing filter condition: {condition}")
        logger.info(f"{'='*60}")
        
        # Set filter condition
        filter_node.params = {
            "anchor": 1,
            "bblength": 50,
            "mult": 2.0,
            "timeframe_multiplier": 1,
            "coloring_sensitivity": 2,
            "filter_condition": condition,
            "check_last_bar_only": True,
            "lookback_bars": 5,
            "max_symbols": 500,
            "enable_multi_timeframe": False,
        }
        
            # Execute filter
        try:
            # Check what the filter will see
            logger.info(f"\nFilter will check condition: {condition}")
            logger.info(f"Direct calculation shows expansion_bullish[-1] = {indicator_result['expansion_bullish'][-1]}")
            logger.info(f"Direct calculation shows expansion_bullish_rising[-1] = {indicator_result['expansion_bullish_rising'][-1]}")
            
            result = await filter_node._execute_impl({"ohlcv_bundle": ohlcv_bundle})
            filtered_bundle = result.get("filtered_ohlcv_bundle", {})
            indicator_data = result.get("indicator_data", {})
            
            passed = symbol in filtered_bundle
            logger.info(f"Result: {'✅ PASSED' if passed else '❌ FAILED'}")
            
            if passed:
                logger.info(f"Symbol {symbol} passed the filter!")
                filtered_bars = filtered_bundle[symbol]
                logger.info(f"Filtered bars count: {len(filtered_bars)}")
                
                # Show last bar info
                if filtered_bars:
                    last_bar = filtered_bars[-1]
                    logger.info(f"Last bar timestamp: {last_bar['timestamp']}")
                    logger.info(f"Last bar close: {last_bar['close']}")
            else:
                logger.info(f"Symbol {symbol} did NOT pass the filter")
            
            # Show indicator data for last bar
            logger.info(f"\nIndicator data keys: {list(indicator_data.keys()) if indicator_data else 'None'}")
            if indicator_data and symbol in indicator_data:
                symbol_data = indicator_data[symbol]
                logger.info(f"Symbol data keys: {list(symbol_data.keys())}")
                logger.info("\nLast bar indicator values:")
                important_keys = [
                    "price", "sq", "top", "expansion_bullish", "expansion_bullish_rising",
                    "expansion_bearish", "sq_rising", "top_rising", "sq_falling", "top_falling"
                ]
                for key in important_keys:
                    if key in symbol_data:
                        values = symbol_data[key]
                        if isinstance(values, list) and len(values) > 0:
                            last_value = values[-1]
                            logger.info(f"  {key}: {last_value}")
                        else:
                            logger.info(f"  {key}: {values}")
                
                # Show last few values for debugging
                if "top" in symbol_data and "sq" in symbol_data:
                    top_vals = symbol_data["top"]
                    sq_vals = symbol_data["sq"]
                    if isinstance(top_vals, list) and isinstance(sq_vals, list) and len(top_vals) >= 3:
                        logger.info("\nLast 3 bars (top, sq, price, expansion_bullish_rising):")
                        for i in range(-3, 0):
                            idx = len(top_vals) + i
                            if idx >= 0:
                                top_val = top_vals[idx] if idx < len(top_vals) else None
                                sq_val = sq_vals[idx] if idx < len(sq_vals) else None
                                price_val = symbol_data.get("price", [None])[idx] if idx < len(symbol_data.get("price", [])) else None
                                exp_rising = symbol_data.get("expansion_bullish_rising", [False])[idx] if idx < len(symbol_data.get("expansion_bullish_rising", [])) else False
                                logger.info(f"  Bar {idx}: top={top_val}, sq={sq_val}, price={price_val}, exp_rising={exp_rising}")
            else:
                logger.info("No indicator data found for symbol")
                        
        except Exception as e:
            logger.error(f"Error testing condition {condition}: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_trump_deviation_magnet())

