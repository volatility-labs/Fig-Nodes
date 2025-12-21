#!/usr/bin/env python3
"""
Test script to analyze TONUSD Fractal Resonance filter results.
Shows which bars have all-green timeframes and why it passes/fails.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from core.types_registry import AssetClass, AssetSymbol, InstrumentType
from nodes.custom.polygon.polygon_batch_custom_bars_node import PolygonBatchCustomBars
from nodes.core.market.filters.fractal_resonance_filter_node import FractalResonanceFilter
from services.indicator_calculators.fractal_resonance_calculator import calculate_fractal_resonance

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TIMEFRAMES = [1, 2, 4, 8, 16, 32, 64, 128]


async def test_ton_filter():
    """Test TONUSD filter with detailed logging."""
    
    # Create TONUSD symbol
    ton_symbol = AssetSymbol(
        ticker="TON",
        asset_class=AssetClass.CRYPTO,
        quote_currency="USD",
        instrument_type=InstrumentType.SPOT,
    )
    
    print(f"🔵 Testing TONUSD filter...")
    print(f"   Symbol: {ton_symbol}")
    print()
    
    # Fetch OHLCV data (3 months, hourly)
    print("📥 Fetching OHLCV data (3 months, hourly)...")
    from services.polygon_service import fetch_bars
    import os
    
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("❌ POLYGON_API_KEY not set")
        return
    
    # Fetch data
    fetch_params = {
        "multiplier": 1,
        "timespan": "hour",
        "lookback_period": "3 months",  # Change to "6 months" to get WT128
        "limit": 50000,
    }
    ton_data, metadata = await fetch_bars(ton_symbol, api_key, fetch_params)
    
    if not ton_data:
        print("❌ No data fetched for TONUSD")
        return
    
    print(f"✅ Fetched {len(ton_data)} bars for TONUSD")
    print()
    
    # Calculate Fractal Resonance
    print("📊 Calculating Fractal Resonance...")
    closes = [bar["close"] for bar in ton_data]
    
    # Forward-fill None/zero closes
    for i in range(len(closes)):
        if closes[i] is None or closes[i] == 0:
            for j in range(i - 1, -1, -1):
                if closes[j] is not None and closes[j] != 0:
                    closes[i] = closes[j]
                    break
            if closes[i] is None or closes[i] == 0:
                for j in range(i + 1, len(closes)):
                    if closes[j] is not None and closes[j] != 0:
                        closes[i] = closes[j]
                        break
    
    fr_result = calculate_fractal_resonance(
        closes=closes,
        n1=10,
        n2=21,
        crossover_sma_len=3,
        ob_level=75.0,
        ob_embed_level=88.0,
        ob_extreme_level=100.0,
        cross_separation=3.0,
    )
    
    wt_a_dict = fr_result.get("wt_a", {})
    wt_b_dict = fr_result.get("wt_b", {})
    
    print(f"✅ Calculated FR for {len(closes)} bars")
    print(f"   Timeframes available: {list(wt_a_dict.keys())}")
    print()
    
    # Show which timeframes have data at the last bar
    print("📊 Timeframe data availability at last bar:")
    last_bar_idx = len(ton_data) - 1
    valid_tfs = []
    missing_tfs = []
    for tm in TIMEFRAMES:
        tm_key = str(tm)
        wt_a_list = wt_a_dict.get(tm_key, [])
        wt_b_list = wt_b_dict.get(tm_key, [])
        
        if last_bar_idx < len(wt_a_list) and last_bar_idx < len(wt_b_list):
            a_val = wt_a_list[last_bar_idx]
            b_val = wt_b_list[last_bar_idx]
            if a_val is not None and b_val is not None:
                valid_tfs.append(tm)
            else:
                missing_tfs.append(f"WT{tm}(None)")
        else:
            missing_tfs.append(f"WT{tm}(missing)")
    
    print(f"   ✅ Valid timeframes ({len(valid_tfs)}): {valid_tfs}")
    if missing_tfs:
        print(f"   ❌ Missing timeframes: {', '.join(missing_tfs)}")
    
    # Calculate minimum bars needed
    n2 = 21  # From filter params
    print(f"\n📊 Data requirements (n2={n2}):")
    for tm in TIMEFRAMES:
        min_bars = n2 * tm
        has_data = tm in valid_tfs
        status = "✅" if has_data else "❌"
        print(f"   {status} WT{tm}: needs {min_bars} bars minimum (you have {len(closes)} bars)")
    print()
    
    # Check last 10 bars for all-green condition
    print("🔍 Checking last 10 bars for all-green timeframes...")
    print()
    
    check_bars = min(10, len(ton_data))
    start_idx = len(ton_data) - check_bars
    
    for bar_idx in range(start_idx, len(ton_data)):
        bar = ton_data[bar_idx]
        timestamp = bar["timestamp"]
        dt = datetime.fromtimestamp(timestamp / 1000) if timestamp > 1e10 else datetime.fromtimestamp(timestamp)
        
        green_count = 0
        valid_count = 0
        failed_timeframes = []
        
        for tm in TIMEFRAMES:
            tm_key = str(tm)
            wt_a_list = wt_a_dict.get(tm_key, [])
            wt_b_list = wt_b_dict.get(tm_key, [])
            
            if bar_idx >= len(wt_a_list) or bar_idx >= len(wt_b_list):
                failed_timeframes.append(f"WT{tm}(missing)")
                continue
            
            a_val = wt_a_list[bar_idx]
            b_val = wt_b_list[bar_idx]
            
            if a_val is None or b_val is None:
                failed_timeframes.append(f"WT{tm}(None)")
                continue
            
            valid_count += 1
            
            if a_val > b_val:
                green_count += 1
            else:
                failed_timeframes.append(f"WT{tm}(a={a_val:.2f}<=b={b_val:.2f})")
        
        status = "✅ ALL GREEN" if green_count == valid_count and valid_count >= 6 else "❌ NOT ALL GREEN"
        
        print(f"Bar {bar_idx} ({dt.strftime('%Y-%m-%d %H:%M')}): {status}")
        print(f"   Green: {green_count}/{valid_count} timeframes")
        if failed_timeframes:
            print(f"   Failed: {', '.join(failed_timeframes[:5])}")
        print()
    
    # Test with filter node
    print("🔍 Testing with FractalResonanceFilter node...")
    print()
    
    filter_node = FractalResonanceFilter(id="test", params={
        "n1": 10,
        "n2": 21,
        "crossover_sma_len": 3,
        "ob_level": 75.0,
        "ob_embed_level": 88.0,
        "ob_extreme_level": 100.0,
        "cross_separation": 3.0,
        "check_last_bar_only": True,
        "lookback_bars": 5,
        "min_green_timeframes": 6,  # Require at least 6 valid timeframes
    })
    filter_node._validate_indicator_params()
    
    indicator_result = filter_node._calculate_indicator(ton_data)
    
    if indicator_result.error:
        print(f"❌ Filter error: {indicator_result.error}")
    else:
        signals = indicator_result.values.lines if hasattr(indicator_result.values, "lines") else {}
        has_signal = signals.get("has_fractal_resonance_signal", 0.0) > 0.0
        total_matching = signals.get("total_matching_bars", 0.0)
        last_match_idx = signals.get("last_matching_bar_idx", -1.0)
        green_at_last = signals.get("green_timeframes_at_last_bar", 0.0)
        
        print(f"Filter Result:")
        print(f"   Passed: {'✅ YES' if has_signal else '❌ NO'}")
        print(f"   Matching bars: {int(total_matching)}")
        if last_match_idx >= 0:
            last_bar = ton_data[int(last_match_idx)]
            last_ts = last_bar["timestamp"]
            last_dt = datetime.fromtimestamp(last_ts / 1000) if last_ts > 1e10 else datetime.fromtimestamp(last_ts)
            print(f"   Last matching bar: {int(last_match_idx)} ({last_dt.strftime('%Y-%m-%d %H:%M')})")
        print(f"   Green timeframes at last bar: {int(green_at_last)}")
        print()
    
    # Test with lookback (check last 5 bars)
    print("🔍 Testing with lookback (check last 5 bars)...")
    print()
    
    filter_node.params = {
        "n1": 10,
        "n2": 21,
        "crossover_sma_len": 3,
        "ob_level": 75.0,
        "ob_embed_level": 88.0,
        "ob_extreme_level": 100.0,
        "cross_separation": 3.0,
        "check_last_bar_only": False,
        "lookback_bars": 5,
        "min_green_timeframes": 6,
    }
    filter_node._validate_indicator_params()
    
    indicator_result = filter_node._calculate_indicator(ton_data)
    
    if indicator_result.error:
        print(f"❌ Filter error: {indicator_result.error}")
    else:
        signals = indicator_result.values.lines if hasattr(indicator_result.values, "lines") else {}
        has_signal = signals.get("has_fractal_resonance_signal", 0.0) > 0.0
        total_matching = signals.get("total_matching_bars", 0.0)
        last_match_idx = signals.get("last_matching_bar_idx", -1.0)
        green_at_last = signals.get("green_timeframes_at_last_bar", 0.0)
        
        print(f"Filter Result (with lookback):")
        print(f"   Passed: {'✅ YES' if has_signal else '❌ NO'}")
        print(f"   Matching bars: {int(total_matching)}")
        if last_match_idx >= 0:
            last_bar = ton_data[int(last_match_idx)]
            last_ts = last_bar["timestamp"]
            last_dt = datetime.fromtimestamp(last_ts / 1000) if last_ts > 1e10 else datetime.fromtimestamp(last_ts)
            print(f"   Last matching bar: {int(last_match_idx)} ({last_dt.strftime('%Y-%m-%d %H:%M')})")
        print(f"   Green timeframes at last bar: {int(green_at_last)}")
        print()
    
    # Final summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"✅ TONUSD has {len(valid_tfs)} valid timeframes: {valid_tfs}")
    print(f"❌ Missing timeframes: {len(missing_tfs)} ({', '.join(missing_tfs)})")
    print()
    print("Why WT64/WT128 are missing:")
    print(f"  - You have {len(closes)} bars of data")
    print(f"  - WT64 needs: {21*64} = 1344 bars minimum")
    print(f"  - WT128 needs: {21*128} = 2688 bars minimum")
    print()
    if len(closes) < 2688:
        print("💡 SOLUTION: Increase lookback period to 6 months or more")
        print(f"   - 6 months hourly ≈ {6*30*24} = 4320 bars (enough for WT128)")
        print(f"   - This will give you all 8 timeframes to check")
    else:
        print("✅ You have enough data for all timeframes!")
    print()


if __name__ == "__main__":
    asyncio.run(test_ton_filter())

