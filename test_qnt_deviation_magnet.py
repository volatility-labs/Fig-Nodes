#!/usr/bin/env python3
"""
Test script to check QNT with Deviation Magnet filter
- 1 minute base timeframe
- 2 weeks of data
- Multi-timeframe: 1min, 5min, 15min
- Filter: expansion_bullish_rising_green_only
"""

import asyncio
import logging
from datetime import datetime, timedelta
from services.polygon_service import fetch_bars
from nodes.core.market.filters.deviation_magnet_filter_node import DeviationMagnetFilter
from core.types_registry import AssetSymbol, OHLCVBar, AssetClass
from core.api_key_vault import APIKeyVault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_qnt():
    """Test QNT with Deviation Magnet filter"""
    
    # Get API key
    api_key_vault = APIKeyVault()
    api_key = api_key_vault.get("POLYGON_API_KEY")
    
    if not api_key:
        logger.error("POLYGON_API_KEY not found in vault")
        return
    
    # Calculate date range (2 weeks ago to now)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)
    
    print(f"Fetching QNT data from {start_date.date()} to {end_date.date()}")
    print(f"Timeframe: 1 minute")
    print(f"Multi-timeframe multipliers: 1, 5, 15 (1min, 5min, 15min)")
    print(f"Filter: expansion_bullish_rising_green_only")
    print("-" * 60)
    
    # Fetch QNT data
    symbol = AssetSymbol("QNTUSD", AssetClass.CRYPTO)
    try:
        params = {
            "multiplier": 1,
            "timespan": "minute",
            "lookback_period": "14 days",
            "adjusted": True,
            "sort": "asc",
            "limit": 5000,  # Max per request
        }
        
        bars, metadata = await fetch_bars(symbol, api_key, params)
        
        if not bars:
            print(f"❌ No data returned for {symbol}")
            return
        
        print(f"✓ Fetched {len(bars)} bars for {symbol}")
        print(f"  First bar: {bars[0]['timestamp']}")
        print(f"  Last bar: {bars[-1]['timestamp']}")
        print(f"  Data status: {metadata.get('data_status', 'unknown')}")
        print()
        
        # Create OHLCV bundle (use string symbol for bundle key)
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = {
            "QNTUSD": bars
        }
        
        # Create filter node
        params = {
            "anchor": 1,  # SMA
            "bblength": 50,
            "mult": 2.0,
            "timeframe_multiplier": 1,
            "coloring_sensitivity": 2,
            "filter_condition": "expansion_bullish_rising_green_only",
            "check_last_bar_only": True,
            "lookback_bars": 5,
            "max_symbols": 500,
            "enable_multi_timeframe": True,
            "timeframe_multiplier_1": 1,   # 1 minute
            "timeframe_multiplier_2": 5,   # 5 minutes
            "timeframe_multiplier_3": 15,  # 15 minutes
            "timeframe_multiplier_4": 0,   # Disabled
            "timeframe_multiplier_5": 0,   # Disabled
            "multi_timeframe_mode": "majority",  # At least 2 out of 3 timeframes must pass
        }
        filter_node = DeviationMagnetFilter(id=1, params=params)
        
        print("Running Deviation Magnet filter...")
        print(f"  Filter condition: {filter_node.params['filter_condition']}")
        print(f"  Multi-timeframe mode: {filter_node.params['multi_timeframe_mode']}")
        print(f"  Timeframes: {filter_node.params['timeframe_multiplier_1']}, "
              f"{filter_node.params['timeframe_multiplier_2']}, "
              f"{filter_node.params['timeframe_multiplier_3']}")
        print()
        
        # Add debug logging
        import logging
        logging.getLogger("nodes.core.market.filters.deviation_magnet_filter_node").setLevel(logging.DEBUG)
        
        # Execute filter
        result = await filter_node._execute_impl({"ohlcv_bundle": ohlcv_bundle})
        
        filtered_bundle = result.get("filtered_ohlcv_bundle", {})
        
        if "QNTUSD" in filtered_bundle:
            print(f"✅ QNTUSD PASSED the filter!")
            print(f"   Filtered bundle contains {len(filtered_bundle)} symbols")
            
            # Get indicator data to see what timeframes passed
            indicator_data = result.get("indicator_data", {})
            if indicator_data:
                print(f"\nIndicator data keys: {list(indicator_data.keys())}")
        else:
            print(f"❌ QNTUSD FAILED the filter")
            print(f"   No symbols passed")
            
            # Let's check individual timeframes to see what's happening
            print("\n" + "=" * 60)
            print("DEBUGGING: Checking individual timeframes...")
            print("=" * 60)
            
            # Test each timeframe individually
            for tf_mult in [1, 5, 15]:
                print(f"\n--- Testing {tf_mult} minute timeframe ---")
                
                # Aggregate bars if needed
                if tf_mult == 1:
                    test_bars = bars
                else:
                    from nodes.core.market.filters.deviation_magnet_filter_node import _aggregate_bars
                    test_bars = _aggregate_bars(bars, tf_mult)
                
                if len(test_bars) < 100:
                    print(f"  ⚠️  Not enough bars ({len(test_bars)}) for {tf_mult}min timeframe")
                    continue
                
                print(f"  Bars: {len(test_bars)}")
                
                # Calculate indicator
                from services.indicator_calculators.deviation_magnet_calculator import calculate_deviation_magnet
                
                opens = [b["open"] for b in test_bars]
                highs = [b["high"] for b in test_bars]
                lows = [b["low"] for b in test_bars]
                closes = [b["close"] for b in test_bars]
                
                result_tf = calculate_deviation_magnet(
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
                
                # Check the signals
                expansion_bullish_rising_any = result_tf.get("expansion_bullish_rising_any", [])
                squeeze_release = result_tf.get("squeeze_release", [])
                
                if expansion_bullish_rising_any:
                    last_expansion = expansion_bullish_rising_any[-1] if expansion_bullish_rising_any else False
                    last_release = squeeze_release[-1] if squeeze_release else False
                    
                    print(f"  Last bar expansion_bullish_rising_any: {last_expansion}")
                    print(f"  Last bar squeeze_release: {last_release}")
                    print(f"  Green only (no release): {last_expansion and not last_release}")
                    
                    # Check last 5 bars
                    if len(expansion_bullish_rising_any) >= 5:
                        recent_expansion = expansion_bullish_rising_any[-5:]
                        recent_release = squeeze_release[-5:] if len(squeeze_release) >= 5 else []
                        
                        expansion_count = sum(recent_expansion)
                        release_count = sum(recent_release) if recent_release else 0
                        
                        print(f"  Last 5 bars - Expansion rising: {expansion_count}/5")
                        print(f"  Last 5 bars - Release (yellow): {release_count}/5")
                else:
                    print(f"  ⚠️  No expansion_bullish_rising_any data")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_qnt())

