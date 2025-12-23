#!/usr/bin/env python3
"""
Test script to debug TSLA ORB filter issue.
Tests why TSLA is not passing the ORB filter when volume in first 5 mins is not over 100% of average.
"""

import asyncio
import logging
import os
from datetime import datetime

import pytz

from core.types_registry import AssetClass, AssetSymbol
from nodes.core.market.filters.orb_filter_node import OrbFilter
from services.indicator_calculators.orb_calculator import calculate_orb
from services.polygon_service import fetch_bars

# Set up logging to see detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_tsla_orb():
    """Test TSLA ORB calculation with detailed logging."""
    
    # Create TSLA symbol
    tsla_symbol = AssetSymbol("TSLA", AssetClass.STOCKS)
    
    print("=" * 80)
    print("TESTING TSLA ORB FILTER")
    print("=" * 80)
    print()
    
    # Get API key
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("❌ POLYGON_API_KEY not set")
        return
    
    # Create ORB filter node with default params (matching your UI settings)
    orb_node = OrbFilter(
        id=1,
        params={
            "or_minutes": 5,
            "rel_vol_threshold": 100.0,
            "direction": "both",
            "avg_period": 14,
            "filter_above_orh": "true",  # Match your UI setting
            "filter_below_orl": "false",
            "max_concurrent": 10,
            "rate_limit_per_second": 95,
        }
    )
    
    # Fetch bars for TSLA
    print("📥 Fetching 5-minute bars for TSLA (last 15 days)...")
    fetch_params = {
        "multiplier": 5,
        "timespan": "minute",
        "lookback_period": "15 days",
        "adjusted": True,
        "sort": "asc",
        "limit": 50000,
    }
    
    bars, metadata = await fetch_bars(tsla_symbol, api_key, fetch_params)
    
    if not bars:
        print("❌ No bars fetched for TSLA")
        return
    
    print(f"✅ Fetched {len(bars)} bars for TSLA")
    print()
    
    # Calculate ORB using the calculator directly
    print("📊 Calculating ORB indicator...")
    print()
    
    result = calculate_orb(
        bars=bars,
        symbol=tsla_symbol,
        or_minutes=5,
        avg_period=14,
    )
    
    print()
    print("=" * 80)
    print("ORB CALCULATION RESULTS")
    print("=" * 80)
    print(f"Relative Volume: {result.get('rel_vol', 'N/A')}%")
    print(f"Direction: {result.get('direction', 'N/A')}")
    print(f"OR High: {result.get('or_high', 'N/A')}")
    print(f"OR Low: {result.get('or_low', 'N/A')}")
    if result.get('error'):
        print(f"Error: {result.get('error')}")
    print()
    
    # Check if it would pass the filter
    print("=" * 80)
    print("FILTER CHECK")
    print("=" * 80)
    
    rel_vol = result.get('rel_vol')
    direction = result.get('direction', 'doji')
    threshold = 100.0
    
    print(f"Relative Volume: {rel_vol}%")
    print(f"Threshold: {threshold}%")
    print(f"Direction: {direction}")
    print(f"OR High: {result.get('or_high', 'N/A')}")
    print(f"OR Low: {result.get('or_low', 'N/A')}")
    print()
    
    if rel_vol is None:
        print("❌ Cannot check filter - rel_vol is None")
        return
    
    # Check all filter conditions
    fails = []
    if direction == "doji":
        fails.append("Direction is 'doji'")
    if rel_vol < threshold:
        fails.append(f"Relative volume ({rel_vol}%) is below threshold ({threshold}%)")
    
    if fails:
        print("❌ FAILS:")
        for reason in fails:
            print(f"   - {reason}")
    else:
        print(f"✅ PASSES: Relative volume ({rel_vol}%) meets threshold ({threshold}%)")
    
    print()
    
    # Now test with the filter node
    print("=" * 80)
    print("TESTING WITH ORB FILTER NODE")
    print("=" * 80)
    print()
    
    # Create a mock OHLCV bundle
    from core.types_registry import OHLCVBar
    ohlcv_bundle = {
        tsla_symbol: [
            OHLCVBar(
                timestamp=bar["timestamp"],
                open=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar["volume"],
            )
            for bar in bars[-10:]  # Just use last 10 bars for the bundle
        ]
    }
    
    # Mock API key vault
    from unittest.mock import patch
    with patch("core.api_key_vault.APIKeyVault.get", return_value=api_key):
        filter_result = await orb_node.execute({"ohlcv_bundle": ohlcv_bundle})
    
    print(f"Filtered bundle size: {len(filter_result.get('filtered_ohlcv_bundle', {}))}")
    if tsla_symbol in filter_result.get('filtered_ohlcv_bundle', {}):
        print("✅ TSLA PASSED the filter")
    else:
        print("❌ TSLA FAILED the filter")
        print()
        print("Checking why it failed...")
        # Get the indicator result to see why it failed
        from unittest.mock import patch
        with patch("core.api_key_vault.APIKeyVault.get", return_value=api_key):
            indicator_result = await orb_node._calculate_orb_indicator(tsla_symbol, api_key)
            print(f"   Relative Volume: {indicator_result.values.lines.get('rel_vol', 'N/A')}%")
            print(f"   Direction: {indicator_result.values.series[0].get('direction', 'N/A') if indicator_result.values.series else 'N/A'}")
            print(f"   Current Price: {indicator_result.values.lines.get('current_price', 'N/A')}")
            print(f"   OR High: {indicator_result.values.lines.get('or_high', 'N/A')}")
            print(f"   OR Low: {indicator_result.values.lines.get('or_low', 'N/A')}")
            if indicator_result.error:
                print(f"   Error: {indicator_result.error}")
    
    print()


if __name__ == "__main__":
    asyncio.run(test_tsla_orb())

