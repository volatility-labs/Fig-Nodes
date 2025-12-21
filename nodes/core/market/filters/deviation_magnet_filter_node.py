"""
Deviation Magnet Filter Node

Filters symbols based on Deviation Magnet signals.
Based on TradingView Pine Script "Deviation Magnet - JD" by Joris Duyck (JD).

Shows price in relation to standard deviations in a normalized way.
Highlights "MAGNET MOVES" where price sticks to deviation levels.
"""

from typing import Any, Dict, List

from core.types_registry import AssetSymbol, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.deviation_magnet_calculator import (
    calculate_deviation_magnet,
)


def _aggregate_bars(bars: list[OHLCVBar], group_size: int) -> list[OHLCVBar]:
    """
    Aggregate consecutive bars into larger bars of size `group_size`.
    Example: aggregate 1h bars into 4h bars when group_size=4.
    """
    if group_size <= 1 or len(bars) <= 1:
        return bars

    aggregated: list[OHLCVBar] = []
    for i in range(0, len(bars), group_size):
        chunk = bars[i : i + group_size]
        if not chunk:
            continue
        open_price = chunk[0]["open"]
        close_price = chunk[-1]["close"]
        high_price = max(b["high"] for b in chunk)
        low_price = min(b["low"] for b in chunk)
        volume_sum = sum(b.get("volume", 0.0) or 0.0 for b in chunk)
        timestamp = chunk[-1]["timestamp"]
        agg_bar: OHLCVBar = {
            "timestamp": timestamp,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume_sum,
        }
        aggregated.append(agg_bar)
    return aggregated


def _check_deviation_magnet_condition(
    magnet_up: List[bool],
    magnet_down: List[bool],
    bounce_up: List[bool],
    bounce_down: List[bool],
    explode_up: List[bool],
    explode_down: List[bool],
    up_break: List[bool],
    low_break: List[bool],
    up_break1: List[bool],
    low_break1: List[bool],
    up_break3: List[bool],
    low_break3: List[bool],
    price: List[float | None],
    bar_coloring_bullish: List[bool] | None = None,
    bar_coloring_bearish: List[bool] | None = None,
    squeeze_release: List[bool] | None = None,
    squeeze_contract: List[bool] | None = None,
    squeeze_active: List[bool] | None = None,
    expansion_bullish: List[bool] | None = None,
    expansion_bullish_rising: List[bool] | None = None,
    expansion_bullish_rising_any: List[bool] | None = None,  # Green line rising (any green)
    expansion_bearish: List[bool] | None = None,
    expansion_bearish_rising: List[bool] | None = None,
    filter_condition: str = "bullish",
    check_last_bar_only: bool = True,
    lookback_bars: int = 5,
) -> bool:
    """
    Check if Deviation Magnet condition passes.
    
    Args:
        magnet_up: Magnet up signals
        magnet_down: Magnet down signals
        bounce_up: Bounce up signals
        bounce_down: Bounce down signals
        explode_up: Explosion up signals
        explode_down: Explosion down signals
        up_break: Upper band breaks
        low_break: Lower band breaks
        up_break1: Upper half deviation breaks
        low_break1: Lower half deviation breaks
        up_break3: Upper 1.5x deviation breaks
        low_break3: Lower 1.5x deviation breaks
        price: Normalized price values
        filter_condition: Filter condition type
        check_last_bar_only: If True, check only last bar
        lookback_bars: Number of bars to check if check_last_bar_only is False
    
    Returns:
        True if condition passes, False otherwise
    """
    if not magnet_up:
        return False
    
    if check_last_bar_only:
        # Check only the last bar
        last_magnet_up = magnet_up[-1] if len(magnet_up) > 0 else False
        last_magnet_down = magnet_down[-1] if len(magnet_down) > 0 else False
        last_bounce_up = bounce_up[-1] if len(bounce_up) > 0 else False
        last_bounce_down = bounce_down[-1] if len(bounce_down) > 0 else False
        last_explode_up = explode_up[-1] if len(explode_up) > 0 else False
        last_explode_down = explode_down[-1] if len(explode_down) > 0 else False
        last_up_break = up_break[-1] if len(up_break) > 0 else False
        last_low_break = low_break[-1] if len(low_break) > 0 else False
        last_up_break1 = up_break1[-1] if len(up_break1) > 0 else False
        last_low_break1 = low_break1[-1] if len(low_break1) > 0 else False
        last_up_break3 = up_break3[-1] if len(up_break3) > 0 else False
        last_low_break3 = low_break3[-1] if len(low_break3) > 0 else False
        last_price = price[-1] if len(price) > 0 else None
        
        if filter_condition == "magnet_up":
            return last_magnet_up
        elif filter_condition == "magnet_down":
            return last_magnet_down
        elif filter_condition == "bullish" or filter_condition == "long":
            return last_magnet_up or last_bounce_up or last_explode_up or (last_price is not None and last_price > 0)
        elif filter_condition == "bearish" or filter_condition == "short":
            return last_magnet_down or last_bounce_down or last_explode_down or (last_price is not None and last_price < 0)
        elif filter_condition == "price_above_zero" or filter_condition == "price_green":
            return last_price is not None and last_price > 0
        elif filter_condition == "price_below_zero" or filter_condition == "price_red":
            return last_price is not None and last_price < 0
        elif filter_condition == "bullish_pinescript":
            if bar_coloring_bullish and len(bar_coloring_bullish) > 0:
                return bar_coloring_bullish[-1]
            return False
        elif filter_condition == "bearish_pinescript":
            if bar_coloring_bearish and len(bar_coloring_bearish) > 0:
                return bar_coloring_bearish[-1]
            return False
        elif filter_condition == "squeeze_release":
            if squeeze_release and len(squeeze_release) > 0:
                return squeeze_release[-1]
            return False
        elif filter_condition == "squeeze_contract":
            if squeeze_contract and len(squeeze_contract) > 0:
                return squeeze_contract[-1]
            return False
        elif filter_condition == "squeeze_active":
            if squeeze_active and len(squeeze_active) > 0:
                return squeeze_active[-1]
            return False
        elif filter_condition == "expansion_bullish":
            if expansion_bullish and len(expansion_bullish) > 0:
                return expansion_bullish[-1]
            return False
        elif filter_condition == "expansion_bearish":
            if expansion_bearish and len(expansion_bearish) > 0:
                return expansion_bearish[-1]
            return False
        elif filter_condition == "expansion_bullish_rising":
            if expansion_bullish_rising and len(expansion_bullish_rising) > 0:
                return expansion_bullish_rising[-1]
            return False
        elif filter_condition == "expansion_bullish_rising_any":
            if expansion_bullish_rising_any and len(expansion_bullish_rising_any) > 0:
                return expansion_bullish_rising_any[-1]
            return False
        elif filter_condition == "expansion_bullish_rising_green_only":
            # Green rising WITHOUT yellow/release (excludes late signals)
            # This ensures we only get green expansion rising, not yellow release signals
            last_expansion_bullish_rising_any = (
                expansion_bullish_rising_any[-1] 
                if expansion_bullish_rising_any and len(expansion_bullish_rising_any) > 0 
                else False
            )
            last_squeeze_release = (
                squeeze_release[-1] 
                if squeeze_release and len(squeeze_release) > 0 
                else False
            )
            # Green rising AND NOT yellow release
            return last_expansion_bullish_rising_any and not last_squeeze_release
        elif filter_condition == "squeeze_release_green_rising":
            # Yellow diamond (squeeze release) AND green expansion rising
            # This combines the volatility breakout signal with bullish expansion confirmation
            last_squeeze_release = (
                squeeze_release[-1] 
                if squeeze_release and len(squeeze_release) > 0 
                else False
            )
            last_expansion_bullish_rising_any = (
                expansion_bullish_rising_any[-1] 
                if expansion_bullish_rising_any and len(expansion_bullish_rising_any) > 0 
                else False
            )
            # Yellow diamond AND green expansion rising
            return last_squeeze_release and last_expansion_bullish_rising_any
        elif filter_condition == "expansion_bearish_rising":
            if expansion_bearish_rising and len(expansion_bearish_rising) > 0:
                return expansion_bearish_rising[-1]
            return False
        elif filter_condition == "upper_break":
            return last_up_break or last_up_break1 or last_up_break3
        elif filter_condition == "lower_break":
            return last_low_break or last_low_break1 or last_low_break3
        elif filter_condition == "any_break":
            return last_up_break or last_low_break or last_up_break1 or last_low_break1 or last_up_break3 or last_low_break3
        elif filter_condition == "explosion_up":
            return last_explode_up
        elif filter_condition == "explosion_down":
            return last_explode_down
        elif filter_condition == "any_signal":
            return last_magnet_up or last_magnet_down or last_bounce_up or last_bounce_down or last_explode_up or last_explode_down
        else:
            return False
    else:
        # Check if condition is true for any bar in lookback range
        lookback = min(lookback_bars, len(magnet_up))
        start_idx = max(0, len(magnet_up) - lookback)
        
        for i in range(start_idx, len(magnet_up)):
            current_magnet_up = magnet_up[i]
            current_magnet_down = magnet_down[i] if i < len(magnet_down) else False
            current_bounce_up = bounce_up[i] if i < len(bounce_up) else False
            current_bounce_down = bounce_down[i] if i < len(bounce_down) else False
            current_explode_up = explode_up[i] if i < len(explode_up) else False
            current_explode_down = explode_down[i] if i < len(explode_down) else False
            current_up_break = up_break[i] if i < len(up_break) else False
            current_low_break = low_break[i] if i < len(low_break) else False
            current_up_break1 = up_break1[i] if i < len(up_break1) else False
            current_low_break1 = low_break1[i] if i < len(low_break1) else False
            current_up_break3 = up_break3[i] if i < len(up_break3) else False
            current_low_break3 = low_break3[i] if i < len(low_break3) else False
            current_price = price[i] if i < len(price) else None
            current_squeeze_release = squeeze_release[i] if squeeze_release and i < len(squeeze_release) else False
            current_squeeze_contract = squeeze_contract[i] if squeeze_contract and i < len(squeeze_contract) else False
            current_squeeze_active = squeeze_active[i] if squeeze_active and i < len(squeeze_active) else False
            current_expansion_bullish = expansion_bullish[i] if expansion_bullish and i < len(expansion_bullish) else False
            current_expansion_bearish = expansion_bearish[i] if expansion_bearish and i < len(expansion_bearish) else False
            current_expansion_bullish_rising = expansion_bullish_rising[i] if expansion_bullish_rising and i < len(expansion_bullish_rising) else False
            current_expansion_bullish_rising_any = expansion_bullish_rising_any[i] if expansion_bullish_rising_any and i < len(expansion_bullish_rising_any) else False
            current_expansion_bearish_rising = expansion_bearish_rising[i] if expansion_bearish_rising and i < len(expansion_bearish_rising) else False
            
            if filter_condition == "magnet_up" and current_magnet_up:
                return True
            elif filter_condition == "magnet_down" and current_magnet_down:
                return True
            elif filter_condition == "bullish" or filter_condition == "long":
                if current_magnet_up or current_bounce_up or current_explode_up or (current_price is not None and current_price > 0):
                    return True
            elif filter_condition == "bearish" or filter_condition == "short":
                if current_magnet_down or current_bounce_down or current_explode_down or (current_price is not None and current_price < 0):
                    return True
            elif filter_condition == "price_above_zero" or filter_condition == "price_green":
                if current_price is not None and current_price > 0:
                    return True
            elif filter_condition == "price_below_zero" or filter_condition == "price_red":
                if current_price is not None and current_price < 0:
                    return True
            elif filter_condition == "bullish_pinescript":
                if bar_coloring_bullish and i < len(bar_coloring_bullish) and bar_coloring_bullish[i]:
                    return True
            elif filter_condition == "bearish_pinescript":
                if bar_coloring_bearish and i < len(bar_coloring_bearish) and bar_coloring_bearish[i]:
                    return True
            elif filter_condition == "squeeze_release":
                if squeeze_release and i < len(squeeze_release) and squeeze_release[i]:
                    return True
            elif filter_condition == "squeeze_contract":
                if squeeze_contract and i < len(squeeze_contract) and squeeze_contract[i]:
                    return True
            elif filter_condition == "squeeze_active":
                if squeeze_active and i < len(squeeze_active) and squeeze_active[i]:
                    return True
            elif filter_condition == "expansion_bullish":
                if expansion_bullish and i < len(expansion_bullish) and expansion_bullish[i]:
                    return True
            elif filter_condition == "expansion_bearish":
                if expansion_bearish and i < len(expansion_bearish) and expansion_bearish[i]:
                    return True
            elif filter_condition == "expansion_bullish_rising":
                if expansion_bullish_rising and i < len(expansion_bullish_rising) and expansion_bullish_rising[i]:
                    return True
            elif filter_condition == "expansion_bullish_rising_any":
                if expansion_bullish_rising_any and i < len(expansion_bullish_rising_any) and expansion_bullish_rising_any[i]:
                    return True
            elif filter_condition == "expansion_bullish_rising_green_only":
                # Green rising WITHOUT yellow/release (excludes late signals)
                current_expansion_bullish_rising_any = (
                    expansion_bullish_rising_any[i] 
                    if expansion_bullish_rising_any and i < len(expansion_bullish_rising_any) 
                    else False
                )
                current_squeeze_release = (
                    squeeze_release[i] 
                    if squeeze_release and i < len(squeeze_release) 
                    else False
                )
                # Green rising AND NOT yellow release
                if current_expansion_bullish_rising_any and not current_squeeze_release:
                    return True
            elif filter_condition == "squeeze_release_green_rising":
                # Yellow diamond (squeeze release) AND green expansion rising
                current_squeeze_release = (
                    squeeze_release[i] 
                    if squeeze_release and i < len(squeeze_release) 
                    else False
                )
                current_expansion_bullish_rising_any = (
                    expansion_bullish_rising_any[i] 
                    if expansion_bullish_rising_any and i < len(expansion_bullish_rising_any) 
                    else False
                )
                # Yellow diamond AND green expansion rising
                if current_squeeze_release and current_expansion_bullish_rising_any:
                    return True
            elif filter_condition == "expansion_bearish_rising":
                if expansion_bearish_rising and i < len(expansion_bearish_rising) and expansion_bearish_rising[i]:
                    return True
            elif filter_condition == "upper_break" and (current_up_break or current_up_break1 or current_up_break3):
                return True
            elif filter_condition == "lower_break" and (current_low_break or current_low_break1 or current_low_break3):
                return True
            elif filter_condition == "any_break" and (current_up_break or current_low_break or current_up_break1 or current_low_break1 or current_up_break3 or current_low_break3):
                return True
            elif filter_condition == "explosion_up" and current_explode_up:
                return True
            elif filter_condition == "explosion_down" and current_explode_down:
                return True
            elif filter_condition == "any_signal" and (current_magnet_up or current_magnet_down or current_bounce_up or current_bounce_down or current_explode_up or current_explode_down):
                return True
        
        return False


class DeviationMagnetFilter(BaseIndicatorFilter):
    """
    Filters OHLCV bundle based on Deviation Magnet signals.
    
    Filter conditions:
    - magnet_up: Magnet up signal occurred (price broke above half deviation level)
    - magnet_down: Magnet down signal occurred (price broke below half deviation level)
    - bullish/long: Bullish condition - ANY of: magnet_up signal OR bounce_up signal OR explode_up signal OR normalized price > 0
    - bearish/short: Bearish condition - ANY of: magnet_down signal OR bounce_down signal OR explode_down signal OR normalized price < 0
    - bullish_pinescript: Matches Pine Script bar coloring logic exactly (uses coloring_sensitivity parameter)
    - bearish_pinescript: Matches Pine Script bar coloring logic exactly (uses coloring_sensitivity parameter)
    - price_above_zero/price_green: Simple filter - normalized price is above 0 (green background in Pine Script)
    - price_below_zero/price_red: Simple filter - normalized price is below 0 (red background in Pine Script)
    - squeeze_release: Expansion line crosses above squeeze line (volatility breakout - yellow diamond)
    - squeeze_release_green_rising: Yellow diamond (squeeze release) AND green expansion rising (volatility breakout with bullish confirmation)
    - squeeze_contract: Expansion line crosses below squeeze line (back into squeeze - purple diamond)
    - squeeze_active: Squeeze is active/rising (volatility compression - teal line active)
    - expansion_bullish: Bullish expansion active (green expansion line - any green: rising OR squeeze falling)
    - expansion_bullish_rising: Strong bullish expansion (bright green - expansion RISING + top > sq + price >= 0)
    - expansion_bullish_rising_any: Green line rising (any green line rising - dim or bright, like TRUMP coin)
    - expansion_bullish_rising_green_only: Green line rising WITHOUT yellow/release (excludes late yellow signals - best for early entries)
    - expansion_bearish: Bearish expansion active (red expansion line - any red: rising OR squeeze falling)
    - expansion_bearish_rising: Strong bearish expansion (bright red - expansion RISING + top > sq + price < 0)
    - upper_break: Price broke above any upper deviation level
    - lower_break: Price broke below any lower deviation level
    - any_break: Price broke above or below any deviation level
    - explosion_up: Explosion up signal occurred
    - explosion_down: Explosion down signal occurred
    - any_signal: Any signal occurred
    
    Inherits inputs/outputs from BaseFilter:
    - Input: 'ohlcv_bundle' (OHLCVBundle)
    - Output: 'filtered_ohlcv_bundle' (OHLCVBundle)
    - Output: 'indicator_data' (ConfigDict) - Indicator values for charting
    """

    description = "Filter symbols by Deviation Magnet signals"

    default_params = {
        "anchor": 1,  # 1 = SMA, 2 = EMA
        "bblength": 50,  # Bollinger Band length
        "mult": 2.0,  # Bollinger Band multiplier
        "timeframe_multiplier": 1,  # Timeframe multiplier for calculation (multiplies bblength)
        "coloring_sensitivity": 2,  # Coloring sensitivity (0-3), matches Pine Script sens parameter
        "filter_condition": "bullish",  # Filter condition
        "check_last_bar_only": True,  # Check only last bar vs any bar in lookback
        "lookback_bars": 5,  # Number of bars to check if check_last_bar_only is False
        "max_symbols": 500,  # Maximum number of symbols to pass through
        "enable_multi_timeframe": False,  # Enable multi-timeframe filtering
        "timeframe_multiplier_1": 1,  # First timeframe multiplier
        "timeframe_multiplier_2": 4,  # Second timeframe multiplier
        "timeframe_multiplier_3": 16,  # Third timeframe multiplier
        "timeframe_multiplier_4": 64,  # Fourth timeframe multiplier
        "timeframe_multiplier_5": 256,  # Fifth timeframe multiplier
        "multi_timeframe_mode": "all",  # "all", "any", "majority"
    }

    params_meta = [
        {
            "name": "anchor",
            "type": "combo",
            "options": [1, 2],
            "default": 1,
            "description": "Anchor type: 1 = SMA, 2 = EMA",
        },
        {
            "name": "bblength",
            "type": "number",
            "default": 50,
            "min": 1,
            "step": 1,
            "description": "Bollinger Band length period",
        },
        {
            "name": "mult",
            "type": "number",
            "default": 2.0,
            "min": 0.1,
            "step": 0.1,
            "description": "Bollinger Band multiplier",
        },
        {
            "name": "timeframe_multiplier",
            "type": "number",
            "default": 1,
            "min": 1,
            "step": 1,
            "description": "Timeframe multiplier (useful for quickly referencing longer timeframes). Multiplies bblength in calculation.",
        },
        {
            "name": "coloring_sensitivity",
            "type": "number",
            "default": 2,
            "min": 0,
            "max": 3,
            "step": 1,
            "description": "Coloring sensitivity (0-3). Higher number = only stronger signals. Used for 'bullish_pinescript' and 'bearish_pinescript' filters.",
        },
        {
            "name": "filter_condition",
            "type": "combo",
            "options": [
                "magnet_up",
                "magnet_down",
                "bullish",
                "bearish",
                "bullish_pinescript",
                "bearish_pinescript",
                "long",
                "short",
                "price_above_zero",
                "price_below_zero",
                "price_green",
                "price_red",
                "upper_break",
                "lower_break",
                "any_break",
                "explosion_up",
                "explosion_down",
                "any_signal",
                "squeeze_release",
                "squeeze_release_green_rising",
                "squeeze_contract",
                "squeeze_active",
                "expansion_bullish",
                "expansion_bullish_rising",
                "expansion_bullish_rising_any",
                "expansion_bullish_rising_green_only",
                "expansion_bearish",
                "expansion_bearish_rising",
            ],
            "default": "bullish",
            "description": "Filter condition type",
        },
        {
            "name": "check_last_bar_only",
            "type": "boolean",
            "default": True,
            "description": "If True, check only the last bar; if False, check last N bars",
        },
        {
            "name": "lookback_bars",
            "type": "number",
            "default": 5,
            "min": 1,
            "step": 1,
            "description": "Number of bars to check if check_last_bar_only is False",
        },
        {
            "name": "max_symbols",
            "type": "number",
            "default": 500,
            "min": 1,
            "max": 500,
            "step": 1,
            "description": "Maximum number of symbols to pass through (stops filtering once limit is reached)",
        },
        {
            "name": "enable_multi_timeframe",
            "type": "boolean",
            "default": False,
            "description": "Enable multi-timeframe filtering (check condition across multiple timeframes)",
        },
        {
            "name": "timeframe_multiplier_1",
            "type": "number",
            "default": 1,
            "min": 0,
            "step": 1,
            "description": "First timeframe multiplier (1 = base timeframe, 0 = disabled)",
        },
        {
            "name": "timeframe_multiplier_2",
            "type": "number",
            "default": 4,
            "min": 0,
            "step": 1,
            "description": "Second timeframe multiplier (4 = 4x base timeframe, 0 = disabled)",
        },
        {
            "name": "timeframe_multiplier_3",
            "type": "number",
            "default": 16,
            "min": 0,
            "step": 1,
            "description": "Third timeframe multiplier (16 = 16x base timeframe, 0 = disabled)",
        },
        {
            "name": "timeframe_multiplier_4",
            "type": "number",
            "default": 64,
            "min": 0,
            "step": 1,
            "description": "Fourth timeframe multiplier (64 = 64x base timeframe, 0 = disabled)",
        },
        {
            "name": "timeframe_multiplier_5",
            "type": "number",
            "default": 256,
            "min": 0,
            "step": 1,
            "description": "Fifth timeframe multiplier (256 = 256x base timeframe, 0 = disabled)",
        },
        {
            "name": "multi_timeframe_mode",
            "type": "combo",
            "options": ["all", "any", "majority"],
            "default": "all",
            "description": "Multi-timeframe combination mode: 'all' (all 5 timeframes must pass), 'any' (any timeframe must pass), 'majority' (3 out of 5 must pass)",
        },
    ]

    async def _execute_impl(
        self,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Filter OHLCV bundle by Deviation Magnet signals.
        
        Args:
            inputs: Dictionary containing 'ohlcv_bundle' key
            
        Returns:
            Dictionary with 'filtered_ohlcv_bundle' containing only passing symbols
        """
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})
        
        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        # Get parameters
        anchor = int(self.params.get("anchor", 1))
        bblength = int(self.params.get("bblength", 50))
        mult = float(self.params.get("mult", 2.0))
        timeframe_multiplier = int(self.params.get("timeframe_multiplier", 1))
        coloring_sensitivity = int(self.params.get("coloring_sensitivity", 2))
        filter_condition = str(self.params.get("filter_condition", "bullish"))
        check_last_bar_only = bool(self.params.get("check_last_bar_only", True))
        lookback_bars = int(self.params.get("lookback_bars", 5))
        max_symbols = int(self.params.get("max_symbols", 500))
        
        # Multi-timeframe parameters
        enable_multi_timeframe = bool(self.params.get("enable_multi_timeframe", False))
        timeframe_multiplier_1 = int(self.params.get("timeframe_multiplier_1", 1))
        timeframe_multiplier_2 = int(self.params.get("timeframe_multiplier_2", 4))
        timeframe_multiplier_3 = int(self.params.get("timeframe_multiplier_3", 16))
        timeframe_multiplier_4 = int(self.params.get("timeframe_multiplier_4", 64))
        timeframe_multiplier_5 = int(self.params.get("timeframe_multiplier_5", 256))
        multi_timeframe_mode = str(self.params.get("multi_timeframe_mode", "all"))

        total_symbols = len(ohlcv_bundle)

        filtered_bundle: Dict[AssetSymbol, List[OHLCVBar]] = {}
        passed_count = 0
        failed_count = 0
        processed_symbols = 0

        # Initial progress signal
        try:
            self.report_progress(0.0, f"0/{total_symbols}")
        except Exception:
            pass

        min_required = (bblength * timeframe_multiplier) * 2 + 10

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data or len(ohlcv_data) < min_required:
                failed_count += 1
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{passed_count}/{total_symbols}")
                except Exception:
                    pass
                continue

            try:
                if enable_multi_timeframe:
                    # Multi-timeframe filtering
                    timeframe_results = []  # List of (multiplier, passes) tuples
                    multipliers = [
                        timeframe_multiplier_1,
                        timeframe_multiplier_2,
                        timeframe_multiplier_3,
                        timeframe_multiplier_4,
                        timeframe_multiplier_5,
                    ]
                    
                    # Filter out disabled timeframes (0 or None) - allows using fewer than 5 timeframes
                    active_multipliers = [m for m in multipliers if m is not None and m > 0]
                    
                    if not active_multipliers:
                        # No active timeframes configured - skip multi-timeframe filtering
                        passes_filter = False
                        passing_timeframes = []
                        failing_timeframes = []
                    else:
                        for multiplier in active_multipliers:
                            if multiplier <= 1:
                                aggregated_data = ohlcv_data
                            else:
                                aggregated_data = _aggregate_bars(ohlcv_data, multiplier)
                            
                            if len(aggregated_data) < min_required:
                                continue
                            
                            opens = [bar["open"] for bar in aggregated_data]
                            highs = [bar["high"] for bar in aggregated_data]
                            lows = [bar["low"] for bar in aggregated_data]
                            closes = [bar["close"] for bar in aggregated_data]
                            
                            result = calculate_deviation_magnet(
                                opens=opens,
                                highs=highs,
                                lows=lows,
                                closes=closes,
                                anchor=anchor,
                                bblength=bblength,
                                mult=mult,
                                timeframe_multiplier=timeframe_multiplier,
                                coloring_sensitivity=coloring_sensitivity,
                            )
                            
                            timeframe_passes = _check_deviation_magnet_condition(
                                magnet_up=result.get("magnet_up", []),
                                magnet_down=result.get("magnet_down", []),
                                bounce_up=result.get("bounce_up", []),
                                bounce_down=result.get("bounce_down", []),
                                explode_up=result.get("explode_up", []),
                                explode_down=result.get("explode_down", []),
                                up_break=result.get("up_break", []),
                                low_break=result.get("low_break", []),
                                up_break1=result.get("up_break1", []),
                                low_break1=result.get("low_break1", []),
                                up_break3=result.get("up_break3", []),
                                low_break3=result.get("low_break3", []),
                                price=result.get("price", []),
                                bar_coloring_bullish=result.get("bar_coloring_bullish"),
                                bar_coloring_bearish=result.get("bar_coloring_bearish"),
                                squeeze_release=result.get("squeeze_release"),
                                squeeze_contract=result.get("squeeze_contract"),
                                squeeze_active=result.get("squeeze_active"),
                                expansion_bullish=result.get("expansion_bullish"),
                                expansion_bullish_rising=result.get("expansion_bullish_rising"),
                                expansion_bullish_rising_any=result.get("expansion_bullish_rising_any"),
                                expansion_bearish=result.get("expansion_bearish"),
                                expansion_bearish_rising=result.get("expansion_bearish_rising"),
                                filter_condition=filter_condition,
                                check_last_bar_only=check_last_bar_only,
                                lookback_bars=lookback_bars,
                            )
                            timeframe_results.append((multiplier, timeframe_passes))
                        
                        if not timeframe_results:
                            passes_filter = False
                            passing_timeframes = []
                            failing_timeframes = []
                        else:
                            passing_timeframes = [mult for mult, passes in timeframe_results if passes]
                            failing_timeframes = [mult for mult, passes in timeframe_results if not passes]
                            
                            if multi_timeframe_mode == "all":
                                passes_filter = all(passes for _, passes in timeframe_results)
                            elif multi_timeframe_mode == "any":
                                passes_filter = any(passes for _, passes in timeframe_results)
                            elif multi_timeframe_mode == "majority":
                                required_passes = (len(timeframe_results) + 1) // 2
                                passes_filter = sum(passes for _, passes in timeframe_results) >= required_passes
                            else:
                                passes_filter = all(passes for _, passes in timeframe_results)
                    
                    # Log which timeframes signaled for this symbol
                    symbol_name = symbol.ticker if hasattr(symbol, 'ticker') else str(symbol)
                    if passes_filter:
                        if passing_timeframes:
                            print(f"DeviationMagnet: {symbol_name} PASSED - timeframe(s) that passed: {passing_timeframes}", flush=True)
                            if failing_timeframes:
                                print(f"DeviationMagnet: {symbol_name} - timeframe(s) that failed: {failing_timeframes}", flush=True)
                        else:
                            print(f"DeviationMagnet: {symbol_name} PASSED (no timeframe results)", flush=True)
                    else:
                        # Debug: log why it failed
                        if passing_timeframes or failing_timeframes:
                            print(f"DeviationMagnet: {symbol_name} FAILED - timeframe(s) that passed: {passing_timeframes}, failed: {failing_timeframes}, mode: {multi_timeframe_mode}", flush=True)
                else:
                    # Single timeframe filtering
                    passing_timeframes = []
                    opens = [bar["open"] for bar in ohlcv_data]
                    highs = [bar["high"] for bar in ohlcv_data]
                    lows = [bar["low"] for bar in ohlcv_data]
                    closes = [bar["close"] for bar in ohlcv_data]
                    
                    result = calculate_deviation_magnet(
                        opens=opens,
                        highs=highs,
                        lows=lows,
                        closes=closes,
                        anchor=anchor,
                        bblength=bblength,
                        mult=mult,
                        timeframe_multiplier=timeframe_multiplier,
                        coloring_sensitivity=coloring_sensitivity,
                    )
                    
                    passes_filter = _check_deviation_magnet_condition(
                        magnet_up=result.get("magnet_up", []),
                        magnet_down=result.get("magnet_down", []),
                        bounce_up=result.get("bounce_up", []),
                        bounce_down=result.get("bounce_down", []),
                        explode_up=result.get("explode_up", []),
                        explode_down=result.get("explode_down", []),
                        up_break=result.get("up_break", []),
                        low_break=result.get("low_break", []),
                        up_break1=result.get("up_break1", []),
                        low_break1=result.get("low_break1", []),
                        up_break3=result.get("up_break3", []),
                        low_break3=result.get("low_break3", []),
                        price=result.get("price", []),
                        bar_coloring_bullish=result.get("bar_coloring_bullish"),
                        bar_coloring_bearish=result.get("bar_coloring_bearish"),
                        squeeze_release=result.get("squeeze_release"),
                        squeeze_contract=result.get("squeeze_contract"),
                        squeeze_active=result.get("squeeze_active"),
                        expansion_bullish=result.get("expansion_bullish"),
                        expansion_bullish_rising=result.get("expansion_bullish_rising"),
                        expansion_bullish_rising_any=result.get("expansion_bullish_rising_any"),
                        expansion_bearish=result.get("expansion_bearish"),
                        expansion_bearish_rising=result.get("expansion_bearish_rising"),
                        filter_condition=filter_condition,
                        check_last_bar_only=check_last_bar_only,
                        lookback_bars=lookback_bars,
                    )

                if passes_filter:
                    filtered_bundle[symbol] = ohlcv_data
                    passed_count += 1
                    
                    if passed_count >= max_symbols:
                        break
                else:
                    failed_count += 1

            except Exception:
                failed_count += 1
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{passed_count}/{total_symbols}")
                except Exception:
                    pass
                continue

            processed_symbols += 1
            try:
                progress = (processed_symbols / max(1, total_symbols)) * 100.0
                self.report_progress(progress, f"{passed_count}/{total_symbols}")
            except Exception:
                pass

        try:
            self.report_progress(100.0, f"{passed_count}/{total_symbols}")
        except Exception:
            pass

        # Output indicator_data if enabled
        result: Dict[str, Any] = {"filtered_ohlcv_bundle": filtered_bundle}
        output_indicator_data = self.params.get("output_indicator_data", self.default_params.get("output_indicator_data", True))
        
        if output_indicator_data:
            indicator_data_output: Dict[str, Any] = {}
            for symbol, ohlcv_data in filtered_bundle.items():
                try:
                    opens = [bar["open"] for bar in ohlcv_data]
                    highs = [bar["high"] for bar in ohlcv_data]
                    lows = [bar["low"] for bar in ohlcv_data]
                    closes = [bar["close"] for bar in ohlcv_data]
                    
                    dm_result = calculate_deviation_magnet(
                        opens=opens,
                        highs=highs,
                        lows=lows,
                        closes=closes,
                        anchor=anchor,
                        bblength=bblength,
                        mult=mult,
                        timeframe_multiplier=timeframe_multiplier,
                        coloring_sensitivity=coloring_sensitivity,
                    )
                    
                    # Convert boolean lists to numeric for charting (1 = True, 0 = False)
                    magnet_up_numeric = [1.0 if x else 0.0 for x in dm_result.get("magnet_up", [])]
                    magnet_down_numeric = [1.0 if x else 0.0 for x in dm_result.get("magnet_down", [])]
                    bounce_up_numeric = [1.0 if x else 0.0 for x in dm_result.get("bounce_up", [])]
                    bounce_down_numeric = [1.0 if x else 0.0 for x in dm_result.get("bounce_down", [])]
                    explode_up_numeric = [1.0 if x else 0.0 for x in dm_result.get("explode_up", [])]
                    explode_down_numeric = [1.0 if x else 0.0 for x in dm_result.get("explode_down", [])]
                    
                    indicator_dict: Dict[str, Any] = {
                        "indicator_type": "deviation_magnet",
                        "values": {
                            "lines": {
                                "basis": dm_result["basis"],
                                "dev": dm_result["dev"],
                                "upper": dm_result["upper"],
                                "lower": dm_result["lower"],
                                "upper1": dm_result["upper1"],
                                "lower1": dm_result["lower1"],
                                "upper3": dm_result["upper3"],
                                "lower3": dm_result["lower3"],
                                "price": dm_result["price"],
                                "sq": dm_result["sq"],
                                "top": dm_result["top"],
                                "magnet_up": magnet_up_numeric,
                                "magnet_down": magnet_down_numeric,
                                "bounce_up": bounce_up_numeric,
                                "bounce_down": bounce_down_numeric,
                                "explode_up": explode_up_numeric,
                                "explode_down": explode_down_numeric,
                            },
                            "series": [],
                        },
                        "timestamp": None,
                        "params": {
                            "anchor": anchor,
                            "bblength": bblength,
                            "mult": mult,
                            "timeframe_multiplier": timeframe_multiplier,
                        },
                        "metadata": {
                            "visualization_type": "line",
                            "panel_mode": "dedicated",
                            "requires_special_panel": True,
                        },
                    }
                    indicator_data_output[str(symbol)] = indicator_dict
                except Exception:
                    pass
            
            result["indicator_data"] = indicator_data_output
        else:
            result["indicator_data"] = {}
        
        return result

