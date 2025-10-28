"""
CORRECTED VBP Logic - Using volume_usd (dollar-weighted volume)

This file demonstrates the correct implementation of VBP (Volume Profile) calculation.

Key Differences from incorrect implementation:
1. Uses volume_usd = volume * close (dollar-weighted) instead of raw volume
2. Bins by close price only, not proportional distribution across high-low range
3. Matches the feature branch implementation from GitHub
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any


def _calculate_vbp_levels_correct(ohlcv_data: List[Dict], bins: int = 50, num_levels: int = 5) -> Dict[str, Any]:
    """
    CORRECT VBP calculation using volume_usd and close price binning.
    
    Args:
        ohlcv_data: List of OHLCV bars
        bins: Number of price bins
        num_levels: Number of significant levels to return
        
    Returns:
        Dictionary with levels, current_price, support/resistance levels
    """
    if not ohlcv_data:
        return {
            "levels": [],
            "current_price": 0.0,
            "highest_level": 0.0,
            "lowest_level": 0.0,
            "error": "No data"
        }
    
    # Convert to DataFrame
    df = pd.DataFrame(ohlcv_data)
    
    # Get current price (last close)
    current_price = df['close'].iloc[-1]
    
    # Get price range
    price_min = df['low'].min()
    price_max = df['high'].max()
    
    # Create bins
    price_range = price_max - price_min
    bin_size = price_range / bins
    
    # ============================================================================
    # CRITICAL: Use volume_usd (volume * close) for dollar-weighted VBP
    # ============================================================================
    df['volume_usd'] = df['volume'] * df['close']
    
    # ============================================================================
    # CRITICAL: Bin by close price only (not high-low range)
    # ============================================================================
    df['price_bin'] = ((df['close'] - price_min) / bin_size).astype(int) * bin_size + price_min
    
    # Group by price bin and sum volume_usd
    volume_profile = df.groupby('price_bin')['volume_usd'].sum().sort_index()
    
    # Find significant levels (top volume bins)
    significant_levels = volume_profile.nlargest(num_levels)
    
    # Create level list sorted by volume
    levels = []
    for price, volume in significant_levels.items():
        levels.append({
            "price": float(price),
            "volume": float(volume)
        })
    
    # Sort by volume descending
    levels.sort(key=lambda x: x["volume"], reverse=True)
    
    # Find support and resistance levels
    support_levels = [level for level in levels if level["price"] < current_price]
    resistance_levels = [level for level in levels if level["price"] > current_price]
    
    # Get closest support and resistance
    closest_support = max(support_levels, key=lambda x: x["price"])["price"] if support_levels else price_min
    closest_resistance = min(resistance_levels, key=lambda x: x["price"])["price"] if resistance_levels else price_max
    
    return {
        "levels": levels,
        "current_price": float(current_price),
        "highest_level": float(closest_resistance),
        "lowest_level": float(closest_support),
        "price_range": float(price_max - price_min),
        "num_data_points": len(df)
    }


# ============================================================================
# INCORRECT IMPLEMENTATION (for comparison)
# ============================================================================

def _calculate_vbp_levels_incorrect(ohlcv_data: List[Dict], bins: int = 50, num_levels: int = 5) -> Dict[str, Any]:
    """
    INCORRECT VBP calculation - DO NOT USE.
    
    Problems:
    1. Uses raw volume instead of volume_usd
    2. Distributes volume proportionally across high-low range instead of binning by close
    """
    df = pd.DataFrame(ohlcv_data)
    current_price = df['close'].iloc[-1]
    price_min = df['low'].min()
    price_max = df['high'].max()
    
    # Create bins
    bin_edges = np.linspace(price_min, price_max, bins + 1)
    
    # ❌ WRONG: Uses raw volume
    volume_profile = np.zeros(bins)
    
    for _, row in df.iterrows():
        high = row['high']
        low = row['low']
        volume = row['volume']  # ❌ RAW VOLUME
        
        if high == low:
            bin_idx = np.digitize(high, bin_edges) - 1
            bin_idx = np.clip(bin_idx, 0, bins - 1)
            volume_profile[bin_idx] += volume
        else:
            # ❌ WRONG: Distributes volume across high-low range
            price_range = high - low
            for i in range(bins):
                bin_low = bin_edges[i]
                bin_high = bin_edges[i + 1]
                
                overlap_low = max(low, bin_low)
                overlap_high = min(high, bin_high)
                
                if overlap_low < overlap_high:
                    overlap_pct = (overlap_high - overlap_low) / price_range
                    volume_profile[i] += volume * overlap_pct  # ❌ RAW VOLUME
    
    # Rest of implementation...
    return {}


# ============================================================================
# KEY DIFFERENCES SUMMARY
# ============================================================================

CORRECT_IMPLEMENTATION = """
✅ CORRECT:
1. df['volume_usd'] = df['volume'] * df['close']  # Dollar-weighted
2. df['price_bin'] = ((df['close'] - price_min) / bin_size).astype(int) * bin_size + price_min  # Bin by close
3. volume_profile = df.groupby('price_bin')['volume_usd'].sum()  # Sum volume_usd per bin
"""

INCORRECT_IMPLEMENTATION = """
❌ INCORRECT:
1. volume = row['volume']  # Raw volume
2. Distributes volume proportionally across high-low range
3. volume_profile[i] += volume * overlap_pct  # Uses raw volume
"""

print("=" * 80)
print("CORRECTED VBP LOGIC")
print("=" * 80)
print("\n✅ Use volume_usd (volume * close) for dollar-weighted VBP")
print("✅ Bin by close price only")
print("❌ DO NOT use raw volume")
print("❌ DO NOT distribute volume across high-low range proportionally")
print("\nSee implementation in _calculate_vbp_levels_correct() above")
print("=" * 80)

