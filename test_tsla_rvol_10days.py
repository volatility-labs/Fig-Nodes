#!/usr/bin/env python3
"""Test with 10 days to match TradingView default"""

import asyncio
import os
from datetime import datetime, timedelta

import pytz

from core.types_registry import AssetClass, AssetSymbol
from services.indicator_calculators.orb_calculator import calculate_orb
from services.polygon_service import fetch_bars

async def test():
    tsla_symbol = AssetSymbol("TSLA", AssetClass.STOCKS)
    api_key = os.getenv("POLYGON_API_KEY")
    
    print("=" * 80)
    print("TESTING WITH 10 DAYS (TradingView default)")
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
    
    # Test with 10 days (TradingView default)
    result_10 = calculate_orb(bars, tsla_symbol, or_minutes=5, avg_period=10)
    
    # Test with 14 days (current filter setting)
    result_14 = calculate_orb(bars, tsla_symbol, or_minutes=5, avg_period=14)
    
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print(f"TradingView RVOL (10 days): 1.76 (176%)")
    print(f"Our RVOL (10 days): {result_10.get('rel_vol', 'N/A'):.2f}%")
    print(f"Our RVOL (14 days): {result_14.get('rel_vol', 'N/A'):.2f}%")
    print()
    
    # Calculate what average would give us 176%
    current_vol = result_10.get('rel_vol', 0) / 100 * (sum([v for v in []]))  # Need to extract this
    
    print("If TradingView uses 10 days and shows 176%,")
    print("then the average of last 10 days opening range volumes should be:")
    print(f"Current volume / 1.76 = ???")
    print()
    
    # Manual calculation with 10 days
    from services.time_utils import utc_timestamp_ms_to_et_datetime, create_market_open_time
    
    daily_groups = {}
    for bar in bars:
        dt_et = utc_timestamp_ms_to_et_datetime(bar["timestamp"])
        bar_date = dt_et.date()
        if bar_date not in daily_groups:
            daily_groups[bar_date] = []
        daily_groups[bar_date].append({
            "timestamp": dt_et,
            "volume": bar["volume"],
        })
    
    or_volumes = {}
    for date_key, day_bars in sorted(daily_groups.items()):
        day_bars_sorted = sorted(day_bars, key=lambda b: b["timestamp"])
        open_time = create_market_open_time(date_key, hour=9, minute=30)
        open_range_end = open_time + timedelta(minutes=5)
        or_candidates = [
            bar for bar in day_bars_sorted 
            if open_time <= bar["timestamp"] < open_range_end
        ]
        if or_candidates:
            or_volumes[date_key] = sum(bar["volume"] for bar in or_candidates)
    
    sorted_dates = sorted(or_volumes.keys())
    today_date = datetime.now(pytz.timezone("US/Eastern")).date()
    target_date = today_date if today_date in sorted_dates else sorted_dates[-1]
    
    # Last 10 days
    if len(sorted_dates) > 10:
        past_10_dates = sorted_dates[-11:-1]
    else:
        past_10_dates = sorted_dates[:-1]
    
    past_10_volumes = [or_volumes[d] for d in past_10_dates]
    avg_10 = sum(past_10_volumes) / len(past_10_volumes) if past_10_volumes else 0.0
    current_vol = or_volumes.get(target_date, 0.0)
    rvol_10 = (current_vol / avg_10 * 100) if avg_10 > 0 else 0.0
    
    print("Manual calculation with last 10 days:")
    print(f"  Current volume: {current_vol:,.0f}")
    print(f"  Average (last 10): {avg_10:,.0f}")
    print(f"  RVOL: {rvol_10:.2f}%")
    print()
    print(f"TradingView shows: 176%")
    print(f"Our calculation: {rvol_10:.2f}%")
    print(f"Difference: {abs(176 - rvol_10):.2f} percentage points")

if __name__ == "__main__":
    asyncio.run(test())

