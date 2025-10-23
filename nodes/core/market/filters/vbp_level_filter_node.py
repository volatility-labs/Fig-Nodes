import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar, AssetSymbol
from core.api_key_vault import APIKeyVault
from services.polygon_service import fetch_bars
import asyncio

logger = logging.getLogger(__name__)


class VBPLevelFilter(BaseIndicatorFilter):
    """
    Filters assets based on Volume Profile (VBP) levels and distance from support/resistance.
    
    Calculates significant price levels based on volume distribution and checks if current price
    is within specified distance from support (below) and resistance (above).
    
    Can either use weekly bars (fetched directly from Polygon) or aggregate daily bars to weekly.
    
    Parameters:
    - bins: Number of bins for volume histogram (default: 50)
    - lookback_years: Number of years to look back for volume data (default: 2)
    - num_levels: Number of significant volume levels to identify (default: 5)
    - max_distance_to_support: Maximum % distance to nearest support level (default: 5.0)
    - min_distance_to_resistance: Minimum % distance to nearest resistance level (default: 5.0)
    - use_weekly: If True, fetch weekly bars from Polygon (default: False, uses daily bars from upstream)
    """
    
    default_params = {
        "bins": 50,
        "lookback_years": 2,
        "num_levels": 5,
        "max_distance_to_support": 5.0,
        "min_distance_to_resistance": 5.0,
        "use_weekly": False,
    }
    
    params_meta = [
        {
            "name": "bins",
            "type": "number",
            "default": 50,
            "min": 10,
            "max": 200,
            "step": 5,
            "label": "Number of Bins",
            "description": "Number of bins for volume histogram. More bins = finer granularity"
        },
        {
            "name": "lookback_years",
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 10,
            "step": 1,
            "label": "Lookback Period (Years)",
            "description": "Number of years to look back for volume data"
        },
        {
            "name": "num_levels",
            "type": "number",
            "default": 5,
            "min": 1,
            "max": 20,
            "step": 1,
            "label": "Number of Levels",
            "description": "Number of significant volume levels to identify"
        },
        {
            "name": "max_distance_to_support",
            "type": "number",
            "default": 5.0,
            "min": 0.0,
            "max": 50.0,
            "step": 0.1,
            "precision": 2,
            "label": "Max Distance to Support (%)",
            "description": "Maximum % distance to nearest support level"
        },
        {
            "name": "min_distance_to_resistance",
            "type": "number",
            "default": 5.0,
            "min": 0.0,
            "max": 50.0,
            "step": 0.1,
            "precision": 2,
            "label": "Min Distance to Resistance (%)",
            "description": "Minimum % distance to nearest resistance level"
        },
        {
            "name": "use_weekly",
            "type": "boolean",
            "default": False,
            "label": "Use Weekly Bars",
            "description": "If true, fetch weekly bars from Polygon. If false, aggregate daily bars to weekly"
        },
    ]
    
    def _validate_indicator_params(self):
        if self.params["bins"] < 10:
            raise ValueError("Number of bins must be at least 10")
        if self.params["lookback_years"] < 1:
            raise ValueError("Lookback period must be at least 1 year")
        if self.params["num_levels"] < 1:
            raise ValueError("Number of levels must be at least 1")
    
    async def _fetch_weekly_bars(self, symbol: AssetSymbol, api_key: str) -> List[OHLCVBar]:
        """Fetch weekly bars directly from Polygon API."""
        lookback_years = self.params["lookback_years"]
        lookback_days = lookback_years * 365
        
        fetch_params = {
            "multiplier": 1,
            "timespan": "week",
            "lookback_period": f"{lookback_days} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }
        
        bars = await fetch_bars(symbol, api_key, fetch_params)
        return bars
    
    def _aggregate_to_weekly(self, ohlcv_data: List[OHLCVBar]) -> List[OHLCVBar]:
        """Aggregate daily bars to weekly bars."""
        if not ohlcv_data:
            return []
        
        df = pd.DataFrame(ohlcv_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Group by week (Monday-Sunday)
        df['week'] = df['timestamp'].dt.to_period('W').apply(lambda r: r.start_time)
        
        weekly_bars = []
        for week, group in df.groupby('week'):
            weekly_bar = {
                'timestamp': int(week.timestamp() * 1000),
                'open': group['open'].iloc[0],
                'high': group['high'].max(),
                'low': group['low'].min(),
                'close': group['close'].iloc[-1],
                'volume': group['volume'].sum()
            }
            weekly_bars.append(weekly_bar)
        
        return weekly_bars
    
    def _calculate_vbp_levels(self, ohlcv_data: List[OHLCVBar]) -> Dict[str, Any]:
        """
        Calculate Volume Profile levels from OHLCV data.
        
        Uses the same logic as the standalone script: bins volume by closing price.
        
        Returns a dict with:
        - levels: List of significant price levels with their volume
        - current_price: Current price
        - highest_level: Highest resistance level
        - lowest_level: Lowest support level
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
        
        # Create bins - same logic as standalone script
        bins = self.params["bins"]
        price_range = price_max - price_min
        bin_size = price_range / bins
        
        # Calculate volume_usd (volume * close) for each bar
        df['volume_usd'] = df['volume'] * df['close']
        
        # Bin by close price (same as standalone script)
        df['price_bin'] = ((df['close'] - price_min) / bin_size).astype(int) * bin_size + price_min
        
        # Group by price bin and sum volume_usd
        volume_profile = df.groupby('price_bin')['volume_usd'].sum().sort_index()
        
        # Find significant levels (top volume bins)
        num_levels = self.params["num_levels"]
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
    
    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate VBP levels and return IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=0,
                values=IndicatorValue(lines={}),
                params=self.params,
                error="No OHLCV data"
            )
        
    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate VBP levels and return IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=0,
                values=IndicatorValue(lines={}),
                params=self.params,
                error="No OHLCV data"
            )
        
        # Filter data based on lookback period
        lookback_years = self.params["lookback_years"]
        cutoff_timestamp = ohlcv_data[-1]['timestamp'] - (lookback_years * 365 * 24 * 60 * 60 * 1000)  # Approximate milliseconds
        
        filtered_data = [bar for bar in ohlcv_data if bar['timestamp'] >= cutoff_timestamp]
        
        if len(filtered_data) < 10:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]['timestamp'],
                values=IndicatorValue(lines={}),
                params=self.params,
                error=f"Insufficient data: need at least 10 bars, got {len(filtered_data)}"
            )
        
    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate VBP levels and return IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=0,
                values=IndicatorValue(lines={}),
                params=self.params,
                error="No OHLCV data"
            )
        
        # Filter data based on lookback period
        lookback_years = self.params["lookback_years"]
        cutoff_timestamp = ohlcv_data[-1]['timestamp'] - (lookback_years * 365 * 24 * 60 * 60 * 1000)  # Approximate milliseconds
        
        filtered_data = [bar for bar in ohlcv_data if bar['timestamp'] >= cutoff_timestamp]
        
        if len(filtered_data) < 10:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]['timestamp'],
                values=IndicatorValue(lines={}),
                params=self.params,
                error=f"Insufficient data: need at least 10 bars, got {len(filtered_data)}"
            )
        
        # Aggregate to weekly if we're not already using weekly bars
        if not self.params.get("use_weekly", False):
            filtered_data = self._aggregate_to_weekly(filtered_data)
        
        if len(filtered_data) < 10:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]['timestamp'],
                values=IndicatorValue(lines={}),
                params=self.params,
                error=f"Insufficient data after processing: need at least 10 bars, got {len(filtered_data)}"
            )
        
        # Calculate VBP levels
        vbp_data = self._calculate_vbp_levels(filtered_data)
        
        if "error" in vbp_data:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]['timestamp'],
                values=IndicatorValue(lines={}),
                params=self.params,
                error=vbp_data["error"]
            )
        
        # Calculate distances
        current_price = vbp_data["current_price"]
        closest_support = vbp_data["lowest_level"]
        closest_resistance = vbp_data["highest_level"]
        
        # Check if there are any resistance levels above current price
        all_levels = vbp_data["levels"]
        resistance_levels = [level for level in all_levels if level["price"] > current_price]
        has_resistance_above = len(resistance_levels) > 0
        
        distance_to_support = abs(current_price - closest_support) / current_price * 100 if current_price > 0 else 0
        
        # If no resistance levels above, set distance to resistance to a very large value
        if has_resistance_above:
            distance_to_resistance = abs(closest_resistance - current_price) / current_price * 100 if current_price > 0 else 0
        else:
            # No resistance levels above - set to infinity to indicate "above all levels"
            distance_to_resistance = float('inf')
        
        return IndicatorResult(
            indicator_type=IndicatorType.VBP,
            timestamp=ohlcv_data[-1]['timestamp'],
            values=IndicatorValue(lines={
                "current_price": current_price,
                "closest_support": closest_support,
                "closest_resistance": closest_resistance,
                "distance_to_support": distance_to_support,
                "distance_to_resistance": distance_to_resistance,
                "num_levels": len(vbp_data["levels"]),
                "price_range": vbp_data["price_range"],
                "has_resistance_above": has_resistance_above
            }),
            params=self.params
        )
    
    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if distance to support and resistance meet criteria."""
        if indicator_result.error:
            return False
        
        lines = indicator_result.values.lines
        
        distance_to_support = lines.get("distance_to_support", 0)
        distance_to_resistance = lines.get("distance_to_resistance", 0)
        has_resistance_above = lines.get("has_resistance_above", True)
        
        if not np.isfinite(distance_to_support):
            return False
        
        max_distance_support = self.params["max_distance_to_support"]
        min_distance_resistance = self.params["min_distance_to_resistance"]
        
        # Check if within max distance to support
        if distance_to_support > max_distance_support:
            return False
        
        # If no resistance levels above, automatically pass (price is above all levels)
        if not has_resistance_above:
            return True
        
        # Check if at least min distance to resistance (only if resistance exists)
        if not np.isfinite(distance_to_resistance):
            return False
        
        if distance_to_resistance < min_distance_resistance:
            return False
        
        return True
    
    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Override to handle weekly bar fetching when use_weekly=True."""
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})
        
        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}
        
        # If use_weekly is True, fetch weekly bars from Polygon for each symbol
        if self.params.get("use_weekly", False):
            api_key = APIKeyVault().get("POLYGON_API_KEY")
            if not api_key:
                raise ValueError("Polygon API key not found in vault")
            
            updated_bundle = {}
            for symbol, ohlcv_data in ohlcv_bundle.items():
                try:
                    weekly_bars = await self._fetch_weekly_bars(symbol, api_key)
                    if weekly_bars:
                        updated_bundle[symbol] = weekly_bars
                    else:
                        updated_bundle[symbol] = ohlcv_data  # Fallback to original data
                except Exception as e:
                    logger.warning(f"Failed to fetch weekly bars for {symbol}: {e}")
                    updated_bundle[symbol] = ohlcv_data  # Fallback to original data
            
            ohlcv_bundle = updated_bundle
        
        # Call parent's execute implementation
        return await super()._execute_impl({"ohlcv_bundle": ohlcv_bundle})

