"""
THMA Filter Node

Filters symbols based on Triangular Hull Moving Average (THMA) trend signals.
Based on TradingView Pine Script by BigBeluga (https://www.tradingview.com/script/0.448/)

The indicator combines THMA with volatility overlay to provide trend-following signals.
"""

from typing import Any, Dict, List

from core.types_registry import AssetSymbol, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.thma_calculator import calculate_thma_with_volatility


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


def _check_thma_condition(
    trend: List[str],
    signal_up: List[bool],
    signal_dn: List[bool],
    filter_condition: str,
    check_last_bar_only: bool,
    lookback_bars: int,
) -> bool:
    """
    Check if THMA condition passes for given trend and signal data.
    
    Returns:
        True if condition passes, False otherwise
    """
    if not trend:
        return False
    
    if check_last_bar_only:
        # Check only the last bar
        last_trend = trend[-1]
        last_signal_up = signal_up[-1] if len(signal_up) > 0 else False
        last_signal_dn = signal_dn[-1] if len(signal_dn) > 0 else False

        if filter_condition == "bullish":
            return last_trend == "bullish"
        elif filter_condition == "bearish":
            return last_trend == "bearish"
        elif filter_condition == "signal_up":
            return last_signal_up
        elif filter_condition == "signal_dn":
            return last_signal_dn
        elif filter_condition == "any_signal":
            return last_signal_up or last_signal_dn
    else:
        # Check if condition is true for any bar in lookback range
        lookback = min(lookback_bars, len(trend))
        start_idx = max(0, len(trend) - lookback)

        for i in range(start_idx, len(trend)):
            current_trend = trend[i]
            current_signal_up = signal_up[i] if i < len(signal_up) else False
            current_signal_dn = signal_dn[i] if i < len(signal_dn) else False

            if filter_condition == "bullish" and current_trend == "bullish":
                return True
            elif filter_condition == "bearish" and current_trend == "bearish":
                return True
            elif filter_condition == "signal_up" and current_signal_up:
                return True
            elif filter_condition == "signal_dn" and current_signal_dn:
                return True
            elif filter_condition == "any_signal" and (current_signal_up or current_signal_dn):
                return True
    
    return False


class THMAFilter(BaseIndicatorFilter):
    """
    Filters OHLCV bundle based on THMA trend signals.
    
    Filter conditions:
    - bullish: THMA is above THMA[2] (bullish trend)
    - bearish: THMA is below THMA[2] (bearish trend)
    - signal_up: THMA crosses above THMA[2] (upward crossover signal)
    - signal_dn: THMA crosses below THMA[2] (downward crossunder signal)
    - any_signal: Any signal (up or down) occurred
    
    Inherits inputs/outputs from BaseFilter:
    - Input: 'ohlcv_bundle' (OHLCVBundle)
    - Output: 'filtered_ohlcv_bundle' (OHLCVBundle)
    """

    description = "Filter symbols by THMA (Triangular Hull Moving Average) trend signals"

    default_params = {
        "thma_length": 40,  # THMA period
        "volatility_length": 15,  # Volatility HMA period
        "filter_condition": "bullish",  # Filter condition
        "check_last_bar_only": True,  # Check only last bar vs any bar in lookback
        "lookback_bars": 5,  # Number of bars to check if check_last_bar_only is False
        "max_symbols": 500,  # Maximum number of symbols to pass through
        "enable_multi_timeframe": False,  # Enable multi-timeframe filtering
        "timeframe_multiplier_1": 1,  # First timeframe multiplier (1x = base timeframe)
        "timeframe_multiplier_2": 4,  # Second timeframe multiplier (4x = 4x base timeframe)
        "timeframe_multiplier_3": 16,  # Third timeframe multiplier (16x = 16x base timeframe)
        "timeframe_multiplier_4": 64,  # Fourth timeframe multiplier (64x = 64x base timeframe)
        "timeframe_multiplier_5": 256,  # Fifth timeframe multiplier (256x = 256x base timeframe)
        "multi_timeframe_mode": "all",  # "all" (all must pass), "any" (any must pass), "majority" (3/5 must pass)
    }

    params_meta = [
        {
            "name": "thma_length",
            "type": "number",
            "default": 40,
            "min": 1,
            "step": 1,
            "description": "THMA calculation period",
        },
        {
            "name": "volatility_length",
            "type": "number",
            "default": 15,
            "min": 1,
            "step": 1,
            "description": "Volatility HMA period",
        },
        {
            "name": "filter_condition",
            "type": "combo",
            "options": ["bullish", "bearish", "signal_up", "signal_dn", "any_signal"],
            "default": "bullish",
            "description": "Filter condition: bullish (THMA > THMA[2]), bearish (THMA < THMA[2]), signal_up (crossover), signal_dn (crossunder), any_signal (any signal)",
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
            "min": 1,
            "step": 1,
            "description": "First timeframe multiplier (1 = base timeframe, 4 = 4x base, etc.)",
        },
        {
            "name": "timeframe_multiplier_2",
            "type": "number",
            "default": 4,
            "min": 1,
            "step": 1,
            "description": "Second timeframe multiplier (4 = 4x base timeframe)",
        },
        {
            "name": "timeframe_multiplier_3",
            "type": "number",
            "default": 16,
            "min": 1,
            "step": 1,
            "description": "Third timeframe multiplier (16 = 16x base timeframe)",
        },
        {
            "name": "timeframe_multiplier_4",
            "type": "number",
            "default": 64,
            "min": 1,
            "step": 1,
            "description": "Fourth timeframe multiplier (64 = 64x base timeframe)",
        },
        {
            "name": "timeframe_multiplier_5",
            "type": "number",
            "default": 256,
            "min": 1,
            "step": 1,
            "description": "Fifth timeframe multiplier (256 = 256x base timeframe)",
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
        Filter OHLCV bundle by THMA trend signals.
        
        Args:
            inputs: Dictionary containing 'ohlcv_bundle' key
            
        Returns:
            Dictionary with 'filtered_ohlcv_bundle' containing only passing symbols
        """
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})
        
        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        # Get parameters
        thma_length = int(self.params.get("thma_length", 40))
        volatility_length = int(self.params.get("volatility_length", 15))
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

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data or len(ohlcv_data) < max(thma_length, volatility_length) + 10:
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
                    # Multi-timeframe filtering: check condition across multiple timeframes
                    timeframe_results = []
                    multipliers = [
                        timeframe_multiplier_1,
                        timeframe_multiplier_2,
                        timeframe_multiplier_3,
                        timeframe_multiplier_4,
                        timeframe_multiplier_5,
                    ]
                    
                    for multiplier in multipliers:
                        if multiplier <= 1:
                            # Use original data for multiplier 1
                            aggregated_data = ohlcv_data
                        else:
                            # Aggregate bars to larger timeframe
                            aggregated_data = _aggregate_bars(ohlcv_data, multiplier)
                        
                        # Check if we have enough data after aggregation
                        min_required = max(thma_length, volatility_length) + 10
                        if len(aggregated_data) < min_required:
                            # Skip this timeframe if insufficient data (don't count as False)
                            # This allows other timeframes to still pass
                            continue
                        
                        # Extract price data from aggregated bars
                        closes = [bar["close"] for bar in aggregated_data]
                        highs = [bar["high"] for bar in aggregated_data]
                        lows = [bar["low"] for bar in aggregated_data]
                        
                        # Calculate THMA for this timeframe
                        thma_result = calculate_thma_with_volatility(
                            closes=closes,
                            highs=highs,
                            lows=lows,
                            thma_length=thma_length,
                            volatility_length=volatility_length,
                        )
                        
                        trend = thma_result.get("trend", [])
                        signal_up = thma_result.get("signal_up", [])
                        signal_dn = thma_result.get("signal_dn", [])
                        
                        # Check condition for this timeframe
                        timeframe_passes = _check_thma_condition(
                            trend=trend,
                            signal_up=signal_up,
                            signal_dn=signal_dn,
                            filter_condition=filter_condition,
                            check_last_bar_only=check_last_bar_only,
                            lookback_bars=lookback_bars,
                        )
                        timeframe_results.append(timeframe_passes)
                    
                    # Combine timeframe results based on mode
                    # Only consider timeframes that were actually evaluated (had sufficient data)
                    if not timeframe_results:
                        # No timeframes had sufficient data - fail the filter
                        passes_filter = False
                    elif multi_timeframe_mode == "all":
                        # All evaluated timeframes must pass
                        passes_filter = all(timeframe_results)
                    elif multi_timeframe_mode == "any":
                        # At least one evaluated timeframe must pass
                        passes_filter = any(timeframe_results)
                    elif multi_timeframe_mode == "majority":
                        # Majority of evaluated timeframes must pass (at least half, rounded up)
                        required_passes = (len(timeframe_results) + 1) // 2
                        passes_filter = sum(timeframe_results) >= required_passes
                    else:
                        passes_filter = all(timeframe_results)  # Default to "all"
                else:
                    # Single timeframe filtering (original logic)
                    # Extract price data
                    closes = [bar["close"] for bar in ohlcv_data]
                    highs = [bar["high"] for bar in ohlcv_data]
                    lows = [bar["low"] for bar in ohlcv_data]

                    # Calculate THMA with volatility
                    thma_result = calculate_thma_with_volatility(
                        closes=closes,
                        highs=highs,
                        lows=lows,
                        thma_length=thma_length,
                        volatility_length=volatility_length,
                    )

                    trend = thma_result.get("trend", [])
                    signal_up = thma_result.get("signal_up", [])
                    signal_dn = thma_result.get("signal_dn", [])

                    # Check filter condition
                    passes_filter = _check_thma_condition(
                        trend=trend,
                        signal_up=signal_up,
                        signal_dn=signal_dn,
                        filter_condition=filter_condition,
                        check_last_bar_only=check_last_bar_only,
                        lookback_bars=lookback_bars,
                    )

                if passes_filter:
                    filtered_bundle[symbol] = ohlcv_data
                    passed_count += 1
                    
                    # Stop if we've reached the maximum number of symbols
                    if passed_count >= max_symbols:
                        break
                else:
                    failed_count += 1

            except Exception as e:
                # Silently handle errors to prevent UI clutter
                failed_count += 1
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{passed_count}/{total_symbols}")
                except Exception:
                    pass
                continue

            # Advance progress after successful processing
            processed_symbols += 1
            try:
                progress = (processed_symbols / max(1, total_symbols)) * 100.0
                self.report_progress(progress, f"{passed_count}/{total_symbols}")
            except Exception:
                pass


        # Final status update
        try:
            self.report_progress(100.0, f"{passed_count}/{total_symbols}")
        except Exception:
            pass

        # Output indicator_data if enabled (for MultiIndicatorChart compatibility)
        result: Dict[str, Any] = {"filtered_ohlcv_bundle": filtered_bundle}
        output_indicator_data = self.params.get("output_indicator_data", self.default_params.get("output_indicator_data", True))
        
        if output_indicator_data:
            # Build indicator_data output for symbols that passed
            indicator_data_output: Dict[str, Any] = {}
            for symbol, ohlcv_data in filtered_bundle.items():
                try:
                    # Calculate indicator for this symbol
                    closes = [bar["close"] for bar in ohlcv_data]
                    highs = [bar["high"] for bar in ohlcv_data]
                    lows = [bar["low"] for bar in ohlcv_data]
                    
                    thma_result = calculate_thma_with_volatility(
                        closes=closes,
                        highs=highs,
                        lows=lows,
                        thma_length=thma_length,
                        volatility_length=volatility_length,
                    )
                    
                    # Convert to IndicatorResult-like format
                    indicator_dict: Dict[str, Any] = {
                        "indicator_type": "thma",
                        "values": {
                            "lines": {
                                "thma": thma_result["thma"],
                                "thma_shifted": thma_result["thma_shifted"],
                                "volatility": thma_result["volatility"],
                            },
                            "series": [],
                        },
                        "timestamp": None,
                        "params": {
                            "thma_length": thma_length,
                            "volatility_length": volatility_length,
                        },
                    }
                    indicator_data_output[str(symbol)] = indicator_dict
                except Exception:
                    # Silently skip symbols that fail indicator_data generation
                    pass
            
            result["indicator_data"] = indicator_data_output
        else:
            result["indicator_data"] = {}
        
        return result

