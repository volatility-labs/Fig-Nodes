#!/usr/bin/env python3
"""
Detailed test to compare our RVOL calculation with TradingView's approach.
TradingView compares volume at the SAME time of day across past N days.
"""

import asyncio
import os
from datetime import datetime

import pytz

from core.types_registry import AssetClass, AssetSymbol
from services.indicator_calculators.orb_calculator import calculate_orb
from services.polygon_service import fetch_bars

async def test_detailed():
    tsla_symbol = AssetSymbol("TSLA", AssetClass.STOCKS)
    api_key = os.getenv("POLYGON_API_KEY")
    
    if not api_key:
        print("❌ POLYGON_API_KEY not set")
        return
    
    print("=" * 80)
    print("DETAILED TSLA RVOL ANALYSIS")
    print("=" * 80)
    print()
    
    # Fetch more days to ensure we have 14 trading days
    print("📥 Fetching 5-minute bars for TSLA (last 20 days to ensure 14 trading days)...")
    fetch_params = {
        "multiplier": 5,
        "timespan": "minute",
        "lookback_period": "20 days",  # Get more days to ensure we have 14 trading days
        "adjusted": True,
        "sort": "asc",
        "limit": 50000,
    }
    
    bars, metadata = await fetch_bars(tsla_symbol, api_key, fetch_params)
    
    if not bars:
        print("❌ No bars fetched")
        return
    
    print(f"✅ Fetched {len(bars)} bars")
    print()
    
    # Calculate ORB
    result = calculate_orb(
        bars=bars,
        symbol=tsla_symbol,
        or_minutes=5,
        avg_period=14,
    )
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Relative Volume: {result.get('rel_vol', 'N/A')}%")
    print(f"Direction: {result.get('direction', 'N/A')}")
    print(f"OR High: {result.get('or_high', 'N/A')}")
    print(f"OR Low: {result.get('or_low', 'N/A')}")
    print()
    
    # Now let's manually check the opening range volumes for each day
    print("=" * 80)
    print("MANUAL VERIFICATION - Opening Range Volumes by Day")
    print("=" * 80)
    print()
    
    from services.time_utils import utc_timestamp_ms_to_et_datetime, create_market_open_time
    
    # Group bars by date
    daily_groups = {}
    for bar in bars:
        dt_et = utc_timestamp_ms_to_et_datetime(bar["timestamp"])
        bar_date = dt_et.date()
        if bar_date not in daily_groups:
            daily_groups[bar_date] = []
        daily_groups[bar_date].append({
            "timestamp": dt_et,
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["volume"],
        })
    
    # Calculate opening range volume for each day
    or_volumes = {}
    for date_key, day_bars in sorted(daily_groups.items()):
        day_bars_sorted = sorted(day_bars, key=lambda b: b["timestamp"])
        
        # Opening range: 9:30 AM ET
        open_time = create_market_open_time(date_key, hour=9, minute=30)
        open_range_end = open_time + timedelta(minutes=5)
        
        # Find bars in opening range
        or_candidates = [
            bar for bar in day_bars_sorted 
            if open_time <= bar["timestamp"] < open_range_end
        ]
        
        if or_candidates:
            or_volume = sum(bar["volume"] for bar in or_candidates)
            or_volumes[date_key] = or_volume
            print(f"{date_key}: {or_volume:,.0f} (from {len(or_candidates)} bars)")
        else:
            print(f"{date_key}: NO OPENING RANGE DATA")
    
    print()
    print("=" * 80)
    print("CALCULATING AVERAGE")
    print("=" * 80)
    
    sorted_dates = sorted(or_volumes.keys())
    today_date = datetime.now(pytz.timezone("US/Eastern")).date()
    
    # Find today's date in the list
    if today_date in sorted_dates:
        target_date = today_date
        print(f"Target date (today): {target_date}")
    else:
        target_date = sorted_dates[-1] if sorted_dates else today_date
        print(f"Target date (latest): {target_date}")
    
    # Get past 14 days (excluding target date)
    if len(sorted_dates) > 14:
        past_dates = sorted_dates[-15:-1]  # Last 14 days excluding today
    else:
        past_dates = sorted_dates[:-1]  # All except today
    
    print(f"Using {len(past_dates)} past days for average:")
    past_volumes = [or_volumes[d] for d in past_dates]
    for d, v in zip(past_dates, past_volumes):
        print(f"  {d}: {v:,.0f}")
    
    avg_vol = sum(past_volumes) / len(past_volumes) if past_volumes else 0.0
    current_vol = or_volumes.get(target_date, 0.0)
    
    print()
    print(f"Current day ({target_date}) volume: {current_vol:,.0f}")
    print(f"Average volume (last {len(past_volumes)} days): {avg_vol:,.0f}")
    print(f"Relative Volume: {(current_vol / avg_vol * 100) if avg_vol > 0 else 0:.2f}%")
    print()
    
    # Compare with TradingView's expected value
    print("=" * 80)
    print("COMPARISON WITH TRADINGVIEW")
    print("=" * 80)
    print(f"TradingView RVOL: 1.76 (176%)")
    print(f"Our RVOL: {(current_vol / avg_vol * 100) if avg_vol > 0 else 0:.2f}%")
    print()
    print(f"If TradingView is correct, average should be: {current_vol / 1.76:,.0f}")
    print(f"Our calculated average: {avg_vol:,.0f}")
    print(f"Difference: {avg_vol - (current_vol / 1.76):,.0f}")
    print()

if __name__ == "__main__":
    from datetime import timedelta
    asyncio.run(test_detailed())

