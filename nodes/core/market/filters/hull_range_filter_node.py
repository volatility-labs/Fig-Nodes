"""
Hull Range Filter Node

Filters symbols based on Hull Range Filter signals.
Based on TradingView Pine Script "Hull-rangefilter" by RafaelZioni.

Combines XAvi range filter with Hull Moving Average and Fibonacci ATR bands.
"""

from typing import Any, Dict, List

from core.types_registry import AssetSymbol, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.hull_range_filter_calculator import (
    calculate_hull_range_filter,
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


def _check_hull_range_condition(
    long_condition: List[bool],
    short_condition: List[bool],
    signal_buy: List[bool],
    signal_sell: List[bool],
    upward: List[int],
    downward: List[int],
    filter_condition: str,
    check_last_bar_only: bool,
    lookback_bars: int,
    require_signal_within_bars: bool = False,
    signal_lookback_bars: int = 10,
    required_signal_type: str = "any",
) -> bool:
    """
    Check if Hull Range Filter condition passes.
    
    Args:
        require_signal_within_bars: If True, also require a signal within signal_lookback_bars
        signal_lookback_bars: Number of bars to look back for signals
        required_signal_type: Type of signal required: "buy", "sell", or "any"
    
    Returns:
        True if condition passes, False otherwise
    """
    if not long_condition:
        return False
    
    # Check main condition first
    main_condition_passes = False
    
    if check_last_bar_only:
        # Check only the last bar
        last_long = long_condition[-1] if len(long_condition) > 0 else False
        last_short = short_condition[-1] if len(short_condition) > 0 else False
        last_buy = signal_buy[-1] if len(signal_buy) > 0 else False
        last_sell = signal_sell[-1] if len(signal_sell) > 0 else False
        last_upward = upward[-1] if len(upward) > 0 else 0
        last_downward = downward[-1] if len(downward) > 0 else 0

        if filter_condition == "bullish" or filter_condition == "long":
            main_condition_passes = last_long or last_upward > 0
        elif filter_condition == "bearish" or filter_condition == "short":
            main_condition_passes = last_short or last_downward > 0
        elif filter_condition == "buy_signal":
            main_condition_passes = last_buy
        elif filter_condition == "sell_signal":
            main_condition_passes = last_sell
        elif filter_condition == "any_signal":
            main_condition_passes = last_buy or last_sell
        elif filter_condition == "upward":
            main_condition_passes = last_upward > 0
        elif filter_condition == "downward":
            main_condition_passes = last_downward > 0
    else:
        # Check if condition is true for any bar in lookback range
        lookback = min(lookback_bars, len(long_condition))
        start_idx = max(0, len(long_condition) - lookback)

        for i in range(start_idx, len(long_condition)):
            current_long = long_condition[i]
            current_short = short_condition[i] if i < len(short_condition) else False
            current_buy = signal_buy[i] if i < len(signal_buy) else False
            current_sell = signal_sell[i] if i < len(signal_sell) else False
            current_upward = upward[i] if i < len(upward) else 0
            current_downward = downward[i] if i < len(downward) else 0

            if filter_condition == "bullish" or filter_condition == "long":
                if current_long or current_upward > 0:
                    main_condition_passes = True
                    break
            elif filter_condition == "bearish" or filter_condition == "short":
                if current_short or current_downward > 0:
                    main_condition_passes = True
                    break
            elif filter_condition == "buy_signal" and current_buy:
                main_condition_passes = True
                break
            elif filter_condition == "sell_signal" and current_sell:
                main_condition_passes = True
                break
            elif filter_condition == "any_signal" and (current_buy or current_sell):
                main_condition_passes = True
                break
            elif filter_condition == "upward" and current_upward > 0:
                main_condition_passes = True
                break
            elif filter_condition == "downward" and current_downward > 0:
                main_condition_passes = True
                break
    
    # If main condition doesn't pass, return False
    if not main_condition_passes:
        return False
    
    # If signal requirement is enabled, check for signals within lookback period
    if require_signal_within_bars:
        signal_lookback = min(signal_lookback_bars, len(signal_buy))
        signal_start_idx = max(0, len(signal_buy) - signal_lookback)
        
        signal_found = False
        for i in range(signal_start_idx, len(signal_buy)):
            if required_signal_type == "buy" and signal_buy[i]:
                signal_found = True
                break
            elif required_signal_type == "sell" and signal_sell[i]:
                signal_found = True
                break
            elif required_signal_type == "any" and (signal_buy[i] or signal_sell[i]):
                signal_found = True
                break
        
        if not signal_found:
            return False
    
    return True


class HullRangeFilter(BaseIndicatorFilter):
    """
    Filters OHLCV bundle based on Hull Range Filter signals.
    
    Filter conditions:
    - bullish/long: Long condition is true or upward direction > 0
    - bearish/short: Short condition is true or downward direction > 0
    - buy_signal: Buy signal occurred
    - sell_signal: Sell signal occurred
    - any_signal: Any signal (buy or sell) occurred
    - upward: Upward direction count > 0
    - downward: Downward direction count > 0
    
    Inherits inputs/outputs from BaseFilter:
    - Input: 'ohlcv_bundle' (OHLCVBundle)
    - Output: 'filtered_ohlcv_bundle' (OHLCVBundle)
    """

    description = "Filter symbols by Hull Range Filter signals"

    default_params = {
        "sampling_period": 14,  # Sampling period for smooth range
        "range_multiplier": 5.0,  # Range multiplier
        "hull_period": 16,  # Hull Moving Average period
        "fib_atr_length": 20,  # ATR length for Fibonacci bands
        "fib_ratio1": 1.618,  # Fibonacci ratio 1
        "fib_ratio2": 2.618,  # Fibonacci ratio 2
        "fib_ratio3": 4.236,  # Fibonacci ratio 3
        "filter_condition": "bullish",  # Filter condition
        "check_last_bar_only": True,  # Check only last bar vs any bar in lookback
        "lookback_bars": 5,  # Number of bars to check if check_last_bar_only is False
        "require_signal_within_bars": False,  # Require signal within N bars
        "signal_lookback_bars": 10,  # Number of bars to look back for signals
        "required_signal_type": "any",  # Type of signal required: buy, sell, or any
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
            "name": "sampling_period",
            "type": "number",
            "default": 14,
            "min": 1,
            "step": 1,
            "description": "Sampling period for smooth range calculation",
        },
        {
            "name": "range_multiplier",
            "type": "number",
            "default": 5.0,
            "min": 0,
            "step": 0.1,
            "description": "Range multiplier for smooth range",
        },
        {
            "name": "hull_period",
            "type": "number",
            "default": 16,
            "min": 1,
            "step": 1,
            "description": "Period for Hull Moving Average",
        },
        {
            "name": "fib_atr_length",
            "type": "number",
            "default": 20,
            "min": 1,
            "step": 1,
            "description": "ATR length for Fibonacci bands",
        },
        {
            "name": "fib_ratio1",
            "type": "number",
            "default": 1.618,
            "min": 0,
            "step": 0.001,
            "description": "Fibonacci ratio 1",
        },
        {
            "name": "fib_ratio2",
            "type": "number",
            "default": 2.618,
            "min": 0,
            "step": 0.001,
            "description": "Fibonacci ratio 2",
        },
        {
            "name": "fib_ratio3",
            "type": "number",
            "default": 4.236,
            "min": 0,
            "step": 0.001,
            "description": "Fibonacci ratio 3",
        },
        {
            "name": "filter_condition",
            "type": "combo",
            "options": [
                "bullish",
                "bearish",
                "long",
                "short",
                "buy_signal",
                "sell_signal",
                "any_signal",
                "upward",
                "downward",
            ],
            "default": "bullish",
            "description": "Filter condition: bullish/long (long condition or upward), bearish/short (short condition or downward), buy_signal, sell_signal, any_signal, upward, downward",
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
            "description": "Number of bars to check if check_last_bar_only is False (for trend/bullish/bearish conditions)",
        },
        {
            "name": "require_signal_within_bars",
            "type": "boolean",
            "default": False,
            "description": "Require a buy/sell signal to have occurred within the last N bars (in addition to main filter condition)",
        },
        {
            "name": "signal_lookback_bars",
            "type": "number",
            "default": 10,
            "min": 1,
            "step": 1,
            "description": "Number of bars to look back for a signal when require_signal_within_bars is True",
        },
        {
            "name": "required_signal_type",
            "type": "combo",
            "options": ["buy", "sell", "any"],
            "default": "any",
            "description": "Type of signal required when require_signal_within_bars is True: buy, sell, or any",
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
            "description": "First timeframe multiplier (1 = base timeframe)",
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
        Filter OHLCV bundle by Hull Range Filter signals.
        
        Args:
            inputs: Dictionary containing 'ohlcv_bundle' key
            
        Returns:
            Dictionary with 'filtered_ohlcv_bundle' containing only passing symbols
        """
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})
        
        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        # Get parameters
        sampling_period = int(self.params.get("sampling_period", 14))
        range_multiplier = float(self.params.get("range_multiplier", 5.0))
        hull_period = int(self.params.get("hull_period", 16))
        fib_atr_length = int(self.params.get("fib_atr_length", 20))
        fib_ratio1 = float(self.params.get("fib_ratio1", 1.618))
        fib_ratio2 = float(self.params.get("fib_ratio2", 2.618))
        fib_ratio3 = float(self.params.get("fib_ratio3", 4.236))
        filter_condition = str(self.params.get("filter_condition", "bullish"))
        check_last_bar_only = bool(self.params.get("check_last_bar_only", True))
        lookback_bars = int(self.params.get("lookback_bars", 5))
        require_signal_within_bars = bool(self.params.get("require_signal_within_bars", False))
        signal_lookback_bars = int(self.params.get("signal_lookback_bars", 10))
        required_signal_type = str(self.params.get("required_signal_type", "any"))
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

        min_required = max(sampling_period * 2, hull_period, fib_atr_length) + 10

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
                    
                    for multiplier in multipliers:
                        if multiplier <= 1:
                            aggregated_data = ohlcv_data
                        else:
                            aggregated_data = _aggregate_bars(ohlcv_data, multiplier)
                        
                        if len(aggregated_data) < min_required:
                            continue
                        
                        closes = [bar["close"] for bar in aggregated_data]
                        highs = [bar["high"] for bar in aggregated_data]
                        lows = [bar["low"] for bar in aggregated_data]
                        
                        result = calculate_hull_range_filter(
                            closes=closes,
                            highs=highs,
                            lows=lows,
                            sampling_period=sampling_period,
                            range_multiplier=range_multiplier,
                            hull_period=hull_period,
                            fib_atr_length=fib_atr_length,
                            fib_ratio1=fib_ratio1,
                            fib_ratio2=fib_ratio2,
                            fib_ratio3=fib_ratio3,
                        )
                        
                        timeframe_passes = _check_hull_range_condition(
                            long_condition=result.get("long_condition", []),
                            short_condition=result.get("short_condition", []),
                            signal_buy=result.get("signal_buy", []),
                            signal_sell=result.get("signal_sell", []),
                            upward=result.get("upward", []),
                            downward=result.get("downward", []),
                            filter_condition=filter_condition,
                            check_last_bar_only=check_last_bar_only,
                            lookback_bars=lookback_bars,
                            require_signal_within_bars=require_signal_within_bars,
                            signal_lookback_bars=signal_lookback_bars,
                            required_signal_type=required_signal_type,
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
                    
                    # Log which timeframes signaled for this symbol (only for symbols that pass)
                    if passes_filter:
                        if passing_timeframes:
                            print(f"HullRangeFilter: {symbol.ticker} PASSED - timeframe(s) that passed: {passing_timeframes}", flush=True)
                            if failing_timeframes:
                                print(f"HullRangeFilter: {symbol.ticker} - timeframe(s) that failed: {failing_timeframes}", flush=True)
                        else:
                            print(f"HullRangeFilter: {symbol.ticker} PASSED (no timeframe results)", flush=True)
                else:
                    # Single timeframe filtering
                    passing_timeframes = []
                    closes = [bar["close"] for bar in ohlcv_data]
                    highs = [bar["high"] for bar in ohlcv_data]
                    lows = [bar["low"] for bar in ohlcv_data]
                    
                    result = calculate_hull_range_filter(
                        closes=closes,
                        highs=highs,
                        lows=lows,
                        sampling_period=sampling_period,
                        range_multiplier=range_multiplier,
                        hull_period=hull_period,
                        fib_atr_length=fib_atr_length,
                        fib_ratio1=fib_ratio1,
                        fib_ratio2=fib_ratio2,
                        fib_ratio3=fib_ratio3,
                    )
                    
                    passes_filter = _check_hull_range_condition(
                        long_condition=result.get("long_condition", []),
                        short_condition=result.get("short_condition", []),
                        signal_buy=result.get("signal_buy", []),
                        signal_sell=result.get("signal_sell", []),
                        upward=result.get("upward", []),
                        downward=result.get("downward", []),
                        filter_condition=filter_condition,
                        check_last_bar_only=check_last_bar_only,
                        lookback_bars=lookback_bars,
                        require_signal_within_bars=require_signal_within_bars,
                        signal_lookback_bars=signal_lookback_bars,
                        required_signal_type=required_signal_type,
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
                    closes = [bar["close"] for bar in ohlcv_data]
                    highs = [bar["high"] for bar in ohlcv_data]
                    lows = [bar["low"] for bar in ohlcv_data]
                    
                    hrf_result = calculate_hull_range_filter(
                        closes=closes,
                        highs=highs,
                        lows=lows,
                        sampling_period=sampling_period,
                        range_multiplier=range_multiplier,
                        hull_period=hull_period,
                        fib_atr_length=fib_atr_length,
                        fib_ratio1=fib_ratio1,
                        fib_ratio2=fib_ratio2,
                        fib_ratio3=fib_ratio3,
                    )
                    
                    indicator_dict: Dict[str, Any] = {
                        "indicator_type": "hull_range_filter",
                        "values": {
                            "lines": {
                                "range_filter": hrf_result["range_filter"],
                                "smooth_range": hrf_result["smooth_range"],
                                "hull_ma": hrf_result["hull_ma"],
                                "fib_top1": hrf_result["fib_top1"],
                                "fib_top2": hrf_result["fib_top2"],
                                "fib_top3": hrf_result["fib_top3"],
                                "fib_bott1": hrf_result["fib_bott1"],
                                "fib_bott2": hrf_result["fib_bott2"],
                                "fib_bott3": hrf_result["fib_bott3"],
                                "sma": hrf_result["sma"],
                            },
                            "series": [],
                        },
                        "timestamp": None,
                        "params": {
                            "sampling_period": sampling_period,
                            "range_multiplier": range_multiplier,
                            "hull_period": hull_period,
                            "fib_atr_length": fib_atr_length,
                        },
                    }
                    indicator_data_output[str(symbol)] = indicator_dict
                except Exception:
                    pass
            
            result["indicator_data"] = indicator_data_output
        else:
            result["indicator_data"] = {}
        
        return result

