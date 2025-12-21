"""
Green Expansion Rising Filter Node

Dedicated filter for green expansion rising signals from the Squeeze-Expansion indicator.
Based on TradingView Pine Script "Squeeze - Expansion Indicator - JD" by Joris Duyck (JD).

Filters for symbols showing green expansion line rising, matching TradingView's top_color green logic:
- Bright green: rising(top,1) AND top>sq AND price>=0 (strong bullish expansion)
- Dim green: falling(sq,1) AND price>=0 (weak bullish, squeeze falling)

Filter modes:
- green_expansion_rising: Any green expansion rising (bright OR dim green that's rising)
- green_expansion_rising_strong_only: Only strong/bright green expansion rising (excludes dim green)
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


def _check_green_expansion_condition(
    expansion_bullish: List[bool] | None = None,
    expansion_bullish_rising: List[bool] | None = None,
    expansion_bullish_rising_any: List[bool] | None = None,
    squeeze_release: List[bool] | None = None,
    filter_mode: str = "green_expansion_rising",
    check_last_bar_only: bool = True,
    lookback_bars: int = 5,
) -> bool:
    """
    Check if green expansion rising condition passes.
    
    Args:
        expansion_bullish: Any green expansion (bright or dim)
        expansion_bullish_rising: Strong/bright green expansion rising only
        expansion_bullish_rising_any: Any green expansion rising (bright or dim, as long as top is rising)
        squeeze_release: Yellow diamond signals (expansion crosses above squeeze)
        filter_mode: Filter mode - "green_expansion_rising", "green_expansion_rising_strong_only", or "yellow_diamond_green_rising"
        check_last_bar_only: If True, check only last bar
        lookback_bars: Number of bars to check if check_last_bar_only is False
    
    Returns:
        True if condition passes, False otherwise
    """
    if check_last_bar_only:
        # Check only the last bar
        if filter_mode == "green_expansion_rising":
            # Any green expansion rising (bright OR dim green that's rising)
            if expansion_bullish_rising_any and len(expansion_bullish_rising_any) > 0:
                return expansion_bullish_rising_any[-1]
        elif filter_mode == "green_expansion_rising_strong_only":
            # Only strong/bright green expansion rising (excludes dim green)
            if expansion_bullish_rising and len(expansion_bullish_rising) > 0:
                return expansion_bullish_rising[-1]
        elif filter_mode == "yellow_diamond_green_rising":
            # Yellow diamond (squeeze release) AND any green expansion rising (bright OR dim)
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
            return last_squeeze_release and last_expansion_bullish_rising_any
        elif filter_mode == "yellow_diamond_bright_green_only":
            # Yellow diamond (squeeze release) AND only bright green expansion rising (excludes dim green)
            last_squeeze_release = (
                squeeze_release[-1] 
                if squeeze_release and len(squeeze_release) > 0 
                else False
            )
            last_expansion_bullish_rising = (
                expansion_bullish_rising[-1] 
                if expansion_bullish_rising and len(expansion_bullish_rising) > 0 
                else False
            )
            return last_squeeze_release and last_expansion_bullish_rising
        
        return False
    else:
        # Check if condition is true for any bar in lookback range
        lookback = min(lookback_bars, 100)  # Cap at reasonable limit
        
        if filter_mode == "yellow_diamond_green_rising":
            # Yellow diamond AND any green expansion rising (bright OR dim)
            if not squeeze_release or not expansion_bullish_rising_any:
                return False
            lookback = min(lookback, len(squeeze_release), len(expansion_bullish_rising_any))
            start_idx = max(0, len(squeeze_release) - lookback)
            for i in range(start_idx, len(squeeze_release)):
                if squeeze_release[i] and expansion_bullish_rising_any[i]:
                    return True
            return False
        elif filter_mode == "yellow_diamond_bright_green_only":
            # Yellow diamond AND only bright green expansion rising (excludes dim green)
            if not squeeze_release or not expansion_bullish_rising:
                return False
            lookback = min(lookback, len(squeeze_release), len(expansion_bullish_rising))
            start_idx = max(0, len(squeeze_release) - lookback)
            for i in range(start_idx, len(squeeze_release)):
                if squeeze_release[i] and expansion_bullish_rising[i]:
                    return True
            return False
        else:
            # Determine which list to check based on filter mode
            check_list = None
            if filter_mode == "green_expansion_rising":
                check_list = expansion_bullish_rising_any
            elif filter_mode == "green_expansion_rising_strong_only":
                check_list = expansion_bullish_rising
            
            if not check_list or len(check_list) == 0:
                return False
            
            lookback = min(lookback, len(check_list))
            start_idx = max(0, len(check_list) - lookback)
            
            for i in range(start_idx, len(check_list)):
                if check_list[i]:
                    return True
        
        return False


class GreenExpansionRisingFilter(BaseIndicatorFilter):
    """
    Dedicated filter for green expansion rising signals from Squeeze-Expansion indicator.
    
    Filter modes:
    - green_expansion_rising: Any green expansion rising (bright OR dim green that's rising)
      Matches TradingView: top_color is green AND top is rising
    - green_expansion_rising_strong_only: Only strong/bright green expansion rising
      Matches TradingView: rising(top,1) AND top>sq AND price>=0 (bright green only)
    - yellow_diamond_green_rising: Yellow diamond (squeeze release) AND any green expansion rising (bright OR dim)
      Matches TradingView: yellow diamond appears AND green expansion line is rising (any green)
    - yellow_diamond_bright_green_only: Yellow diamond (squeeze release) AND only bright green expansion rising
      Matches TradingView: yellow diamond appears AND bright green expansion line is rising (excludes dim green)
    
    Based on TradingView Pine Script "Squeeze - Expansion Indicator - JD" by Joris Duyck (JD).
    
    Inherits inputs/outputs from BaseFilter:
    - Input: 'ohlcv_bundle' (OHLCVBundle)
    - Output: 'filtered_ohlcv_bundle' (OHLCVBundle)
    - Output: 'indicator_data' (ConfigDict) - Indicator values for charting
    """

    description = "Filter symbols by green expansion rising signals (Squeeze-Expansion indicator)"

    default_params = {
        "anchor": 1,  # 1 = SMA, 2 = EMA
        "bblength": 50,  # Bollinger Band length
        "mult": 2.0,  # Bollinger Band multiplier
        "timeframe_multiplier": 1,  # Timeframe multiplier for calculation (multiplies bblength)
        "filter_mode": "green_expansion_rising",  # Filter mode
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
            "name": "filter_mode",
            "type": "combo",
            "options": [
                "green_expansion_rising",
                "green_expansion_rising_strong_only",
                "yellow_diamond_green_rising",
                "yellow_diamond_bright_green_only",
            ],
            "default": "green_expansion_rising",
            "description": "Filter mode: 'green_expansion_rising' = any green rising (bright or dim), 'green_expansion_rising_strong_only' = only bright green rising, 'yellow_diamond_green_rising' = yellow diamond + any green rising (bright or dim), 'yellow_diamond_bright_green_only' = yellow diamond + only bright green rising",
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
        Filter OHLCV bundle by green expansion rising signals.
        
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
        filter_mode = str(self.params.get("filter_mode", "green_expansion_rising"))
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
                    
                    # Filter out disabled timeframes (0 or None)
                    active_multipliers = [m for m in multipliers if m is not None and m > 0]
                    
                    if not active_multipliers:
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
                                coloring_sensitivity=2,  # Not used for this filter
                            )
                            
                            timeframe_passes = _check_green_expansion_condition(
                                expansion_bullish=result.get("expansion_bullish"),
                                expansion_bullish_rising=result.get("expansion_bullish_rising"),
                                expansion_bullish_rising_any=result.get("expansion_bullish_rising_any"),
                                squeeze_release=result.get("squeeze_release"),
                                filter_mode=filter_mode,
                                check_last_bar_only=check_last_bar_only,
                                lookback_bars=lookback_bars,
                            )
                            timeframe_results.append((multiplier, timeframe_passes))
                            
                            # Debug logging for BCH
                            if str(symbol).startswith("BCH"):
                                expansion_bullish_rising_any_list = result.get("expansion_bullish_rising_any", [])
                                expansion_bullish_list = result.get("expansion_bullish", [])
                                expansion_bullish_rising_list = result.get("expansion_bullish_rising", [])
                                last_expansion_bullish_rising_any = expansion_bullish_rising_any_list[-1] if expansion_bullish_rising_any_list else False
                                last_expansion_bullish = expansion_bullish_list[-1] if expansion_bullish_list else False
                                last_expansion_bullish_rising = expansion_bullish_rising_list[-1] if expansion_bullish_rising_list else False
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(
                                    f"GREEN_EXPANSION_RISING: BCH TF{multiplier}x - "
                                    f"passes={timeframe_passes}, "
                                    f"expansion_bullish_rising_any[-1]={last_expansion_bullish_rising_any}, "
                                    f"expansion_bullish[-1]={last_expansion_bullish}, "
                                    f"expansion_bullish_rising[-1]={last_expansion_bullish_rising}"
                                )
                        
                        if not timeframe_results:
                            passes_filter = False
                            passing_timeframes = []
                            failing_timeframes = []
                        else:
                            passing_timeframes = [mult for mult, passes in timeframe_results if passes]
                            failing_timeframes = [mult for mult, passes in timeframe_results if not passes]
                            
                            if multi_timeframe_mode == "all":
                                passes_filter = all(passes for _, passes in timeframe_results)
                                required_passes = len(timeframe_results)
                            elif multi_timeframe_mode == "any":
                                passes_filter = any(passes for _, passes in timeframe_results)
                                required_passes = 1
                            elif multi_timeframe_mode == "majority":
                                required_passes = (len(timeframe_results) + 1) // 2
                                passes_filter = sum(passes for _, passes in timeframe_results) >= required_passes
                            else:
                                passes_filter = all(passes for _, passes in timeframe_results)
                                required_passes = len(timeframe_results)
                            
                            # Debug logging for BCH
                            if str(symbol).startswith("BCH"):
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(
                                    f"GREEN_EXPANSION_RISING: BCH multi-timeframe result - "
                                    f"mode={multi_timeframe_mode}, "
                                    f"passing_tfs={passing_timeframes}, "
                                    f"failing_tfs={failing_timeframes}, "
                                    f"required={required_passes}, "
                                    f"actual_passes={sum(passes for _, passes in timeframe_results)}, "
                                    f"passes_filter={passes_filter}"
                                )
                    
                    # Multi-timeframe filtering complete
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
                        coloring_sensitivity=2,  # Not used for this filter
                    )
                    
                    passes_filter = _check_green_expansion_condition(
                        expansion_bullish=result.get("expansion_bullish"),
                        expansion_bullish_rising=result.get("expansion_bullish_rising"),
                        expansion_bullish_rising_any=result.get("expansion_bullish_rising_any"),
                        squeeze_release=result.get("squeeze_release"),
                        filter_mode=filter_mode,
                        check_last_bar_only=check_last_bar_only,
                        lookback_bars=lookback_bars,
                    )
                    
                    # Debug logging for BCH
                    if str(symbol).startswith("BCH"):
                        expansion_bullish_rising_any_list = result.get("expansion_bullish_rising_any", [])
                        expansion_bullish_list = result.get("expansion_bullish", [])
                        expansion_bullish_rising_list = result.get("expansion_bullish_rising", [])
                        last_expansion_bullish_rising_any = expansion_bullish_rising_any_list[-1] if expansion_bullish_rising_any_list else False
                        last_expansion_bullish = expansion_bullish_list[-1] if expansion_bullish_list else False
                        last_expansion_bullish_rising = expansion_bullish_rising_list[-1] if expansion_bullish_rising_list else False
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(
                            f"GREEN_EXPANSION_RISING: BCH single-timeframe - "
                            f"passes={passes_filter}, "
                            f"expansion_bullish_rising_any[-1]={last_expansion_bullish_rising_any}, "
                            f"expansion_bullish[-1]={last_expansion_bullish}, "
                            f"expansion_bullish_rising[-1]={last_expansion_bullish_rising}"
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
                        coloring_sensitivity=2,
                    )
                    
                    # Convert boolean lists to numeric for charting (1 = True, 0 = False)
                    expansion_bullish_numeric = [1.0 if x else 0.0 for x in dm_result.get("expansion_bullish", [])]
                    expansion_bullish_rising_numeric = [1.0 if x else 0.0 for x in dm_result.get("expansion_bullish_rising", [])]
                    expansion_bullish_rising_any_numeric = [1.0 if x else 0.0 for x in dm_result.get("expansion_bullish_rising_any", [])]
                    
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
                                "expansion_bullish": expansion_bullish_numeric,
                                "expansion_bullish_rising": expansion_bullish_rising_numeric,
                                "expansion_bullish_rising_any": expansion_bullish_rising_any_numeric,
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

