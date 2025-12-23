#!/usr/bin/env python3
"""
Compare our ORB calculation with TradingView's RVOL script logic.

TradingView script:
1. Tracks cumulative volume at each minute of the day
2. For relative volume at time T, compares:
   - Current volume at time T today
   - Average volume at time T over past N days
3. Uses cumulative volume (volume up to that minute)

Our ORB calculator:
1. Gets opening range volume (first 5 minutes: 9:30-9:35)
2. Compares:
   - Today's opening range volume
   - Average opening range volume over past N days
3. Uses aggregated volume (sum of volumes in that 5-minute window)
"""

import asyncio
import os
from datetime import datetime, timedelta

import pytz

from core.types_registry import AssetClass, AssetSymbol
from services.indicator_calculators.orb_calculator import calculate_orb
from services.polygon_service import fetch_bars
from services.time_utils import utc_timestamp_ms_to_et_datetime, create_market_open_time

async def compare():
    tsla_symbol = AssetSymbol("TSLA", AssetClass.STOCKS)
    api_key = os.getenv("POLYGON_API_KEY")
    
    print("=" * 80)
    print("COMPARING OUR CALCULATION WITH TRADINGVIEW LOGIC")
    print("=" * 80)
    print()
    
    fetch_params = {
        "multiplier": 5,
        "timespan": "minute",
        "lookback_period": "20 days",
        "adjusted": True,
        "sort": "asc",
        "limit": 50000,
    }
    
    bars, _ = await fetch_bars(tsla_symbol, api_key, fetch_params)
    
    # Our current calculation
    result = calculate_orb(bars, tsla_symbol, or_minutes=5, avg_period=14)
    
    print("OUR CURRENT CALCULATION:")
    print(f"  Relative Volume: {result.get('rel_vol', 'N/A'):.2f}%")
    print()
    
    # Simulate TradingView's approach
    print("TRADINGVIEW APPROACH (simulated):")
    print("  TradingView compares volume at SPECIFIC TIME (e.g., 9:35 AM)")
    print("  vs average volume at that SAME TIME over past N days")
    print()
    
    # Group bars by date and time
    daily_bars_by_time = {}
    for bar in bars:
        dt_et = utc_timestamp_ms_to_et_datetime(bar["timestamp"])
        bar_date = dt_et.date()
        bar_time = dt_et.time()
        
        if bar_date not in daily_bars_by_time:
            daily_bars_by_time[bar_date] = {}
        
        # For 5-minute bars, the timestamp is the START of the bar
        # So a bar at 9:30 covers 9:30-9:35
        # TradingView would compare volume at 9:35 (end of first 5-min bar)
        daily_bars_by_time[bar_date][bar_time] = bar["volume"]
    
    # Find opening range bars (9:30-9:35)
    or_volumes_by_date = {}
    for date_key in sorted(daily_bars_by_time.keys()):
        day_bars = daily_bars_by_time[date_key]
        
        # Get the 9:30 bar (which covers 9:30-9:35)
        open_time = datetime.strptime("09:30", "%H:%M").time()
        if open_time in day_bars:
            or_volumes_by_date[date_key] = day_bars[open_time]
        else:
            # Try to find closest bar
            closest_time = None
            min_diff = float('inf')
            for time_key in day_bars.keys():
                if time_key.hour == 9 and 30 <= time_key.minute < 35:
                    diff = abs((time_key.hour * 60 + time_key.minute) - (9 * 60 + 30))
                    if diff < min_diff:
                        min_diff = diff
                        closest_time = time_key
            
            if closest_time:
                or_volumes_by_date[date_key] = day_bars[closest_time]
    
    sorted_dates = sorted(or_volumes_by_date.keys())
    today_date = datetime.now(pytz.timezone("US/Eastern")).date()
    target_date = today_date if today_date in sorted_dates else sorted_dates[-1]
    
    # Get past 14 days
    if len(sorted_dates) > 14:
        past_14_dates = sorted_dates[-15:-1]
    else:
        past_14_dates = sorted_dates[:-1]
    
    past_14_volumes = [or_volumes_by_date[d] for d in past_14_dates]
    avg_14 = sum(past_14_volumes) / len(past_14_volumes) if past_14_volumes else 0.0
    current_vol = or_volumes_by_date.get(target_date, 0.0)
    rvol_14 = (current_vol / avg_14 * 100) if avg_14 > 0 else 0.0
    
    print("SIMULATED TRADINGVIEW CALCULATION:")
    print(f"  Current volume (first 5-min bar): {current_vol:,.0f}")
    print(f"  Average (last 14 days, first 5-min bar): {avg_14:,.0f}")
    print(f"  Relative Volume: {rvol_14:.2f}%")
    print()
    
    print("=" * 80)
    print("KEY DIFFERENCES:")
    print("=" * 80)
    print("1. TradingView: Compares volume at SPECIFIC TIME (e.g., 9:35)")
    print("   vs average at that SAME TIME over past days")
    print()
    print("2. Our ORB: Compares FIRST 5 MINUTES (9:30-9:35) volume today")
    print("   vs average FIRST 5 MINUTES volume over past days")
    print()
    print("3. If TradingView is showing RVOL for the 9:30-9:35 bar,")
    print("   it should match our calculation (both use first 5-min bar)")
    print()
    print("4. TradingView uses CUMULATIVE volume (volume up to that minute)")
    print("   Our ORB uses AGGREGATED volume (sum of volumes in 5-min window)")
    print("   For a single 5-minute bar, these should be the same")
    print()
    
    print("=" * 80)
    print("COMPARISON:")
    print("=" * 80)
    print(f"Our ORB calculation: {result.get('rel_vol', 0):.2f}%")
    print(f"Simulated TradingView: {rvol_14:.2f}%")
    print(f"Difference: {abs(result.get('rel_vol', 0) - rvol_14):.2f} percentage points")
    print()
    
    if abs(result.get('rel_vol', 0) - rvol_14) < 1.0:
        print("✅ Calculations match closely!")
    else:
        print("⚠️  Calculations differ - investigating...")
        print()
        print("Possible reasons:")
        print("  1. Different data sources/timing")
        print("  2. TradingView uses cumulative vs our aggregated")
        print("  3. TradingView may handle missing data differently")

if __name__ == "__main__":
    asyncio.run(compare())

