"""
Stochastic Heatmap Filter Node

Filters symbols based on Stochastic Heatmap indicator crossover conditions.
Only symbols that meet the specified filter condition will be passed through.

Based on TradingView Pine Script by Violent (https://www.tradingview.com/v/7PRbCBjk/)
"""

import logging
from typing import Any, Dict, List

from core.types_registry import AssetSymbol, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.stochastic_heatmap_calculator import calculate_stochastic_heatmap

logger = logging.getLogger(__name__)


class StochasticHeatmapFilter(BaseIndicatorFilter):
    """
    Filters OHLCV bundle based on Stochastic Heatmap crossover conditions.
    
    Filter conditions:
    - fast_above_slow: Bullish (fast line > slow line)
    - slow_above_fast: Bearish (slow line > fast line)
    
    Inherits inputs/outputs from BaseFilter:
    - Input: 'ohlcv_bundle' (OHLCVBundle)
    - Output: 'filtered_ohlcv_bundle' (OHLCVBundle)
    """

    description = "Filter symbols by Stochastic Heatmap crossover (fast > slow or slow > fast)"

    default_params = {
        "ma_type": "EMA",  # Moving average type
        "increment": 10,  # Stochastic period increment
        "smooth_fast": 2,  # Fast line smoothing
        "smooth_slow": 21,  # Slow line smoothing
        "plot_number": 28,  # Number of stochastics to plot
        "waves": True,  # Use weighted increments (True) or linear increments (False)
        "filter_crossover": "fast_above_slow",  # Filter condition
        "check_last_bar_only": True,  # Check only last bar vs any bar in lookback
        "lookback_bars": 5,  # Number of bars to check if check_last_bar_only is False
        "max_symbols": 500,  # Maximum number of symbols to pass through
    }

    params_meta = [
        {
            "name": "ma_type",
            "type": "select",
            "options": ["SMA", "EMA", "WMA"],
            "default": "EMA",
            "description": "Moving average type for smoothing",
        },
        {
            "name": "increment",
            "type": "number",
            "default": 10,
            "min": 1,
            "step": 1,
            "description": "Stochastic period increment (K and D periods)",
        },
        {
            "name": "smooth_fast",
            "type": "number",
            "default": 2,
            "min": 1,
            "step": 1,
            "description": "Fast line smoothing period",
        },
        {
            "name": "smooth_slow",
            "type": "number",
            "default": 21,
            "min": 1,
            "step": 1,
            "description": "Slow line smoothing period",
        },
        {
            "name": "plot_number",
            "type": "number",
            "default": 28,
            "min": 1,
            "max": 100,
            "step": 1,
            "description": "Number of stochastic periods to calculate (Theme 3 = 28)",
        },
        {
            "name": "waves",
            "type": "boolean",
            "default": True,
            "description": "Use weighted increments (True) or linear increments (False)",
        },
        {
            "name": "filter_crossover",
            "type": "combo",
            "options": ["fast_above_slow", "slow_above_fast"],
            "default": "fast_above_slow",
            "description": "Filter condition: fast_above_slow (bullish), slow_above_fast (bearish)",
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
    ]

    async def _execute_impl(
        self,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Filter OHLCV bundle by Stochastic Heatmap crossover condition.
        
        Args:
            inputs: Dictionary containing 'ohlcv_bundle' key
            
        Returns:
            Dictionary with 'filtered_ohlcv_bundle' containing only passing symbols
        """
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})
        
        if not ohlcv_bundle:
            logger.info("StochasticHeatmapFilter: Empty input bundle")
            return {"filtered_ohlcv_bundle": {}}

        # Get parameters
        ma_type = str(self.params.get("ma_type", "EMA"))
        increment = int(self.params.get("increment", 10))
        smooth_fast = int(self.params.get("smooth_fast", 2))
        smooth_slow = int(self.params.get("smooth_slow", 21))
        plot_number = int(self.params.get("plot_number", 28))
        waves = bool(self.params.get("waves", True))
        filter_crossover = str(self.params.get("filter_crossover", "fast_above_slow"))
        check_last_bar_only = bool(self.params.get("check_last_bar_only", True))
        lookback_bars = int(self.params.get("lookback_bars", 5))
        max_symbols = int(self.params.get("max_symbols", 500))

        total_symbols = len(ohlcv_bundle)
        logger.info(
            f"🔵 StochasticHeatmapFilter: Starting filter on {total_symbols} symbols "
            f"(condition: {filter_crossover}, check_last_bar: {check_last_bar_only}, max_symbols: {max_symbols})"
        )

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
            if not ohlcv_data or len(ohlcv_data) < 100:
                logger.debug(f"⏭️  StochasticHeatmapFilter: Skipping {symbol} - insufficient data ({len(ohlcv_data)} bars)")
                failed_count += 1
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{passed_count}/{total_symbols}")
                except Exception:
                    pass
                continue

            try:
                # Calculate stochastic heatmap
                closes = [bar["close"] for bar in ohlcv_data]
                highs = [bar["high"] for bar in ohlcv_data]
                lows = [bar["low"] for bar in ohlcv_data]

                shm_result = calculate_stochastic_heatmap(
                    closes=closes,
                    highs=highs,
                    lows=lows,
                    ma_type=ma_type,
                    increment=increment,
                    smooth_fast=smooth_fast,
                    smooth_slow=smooth_slow,
                    plot_number=plot_number,
                    waves=waves,
                )

                fast_line = shm_result["fast_line"]
                slow_line = shm_result["slow_line"]

                # Check filter condition
                passes_filter = False

                if check_last_bar_only:
                    # Check only the last bar
                    if len(fast_line) > 0 and len(slow_line) > 0:
                        last_fast = fast_line[-1]
                        last_slow = slow_line[-1]

                        if last_fast is not None and last_slow is not None:
                            if filter_crossover == "fast_above_slow":
                                passes_filter = last_fast > last_slow
                            elif filter_crossover == "slow_above_fast":
                                passes_filter = last_slow > last_fast
                else:
                    # Check if condition is true for any bar in lookback range
                    lookback = min(lookback_bars, len(fast_line))
                    start_idx = max(0, len(fast_line) - lookback)

                    for i in range(start_idx, len(fast_line)):
                        fast_val = fast_line[i]
                        slow_val = slow_line[i]

                        if fast_val is not None and slow_val is not None:
                            if filter_crossover == "fast_above_slow" and fast_val > slow_val:
                                passes_filter = True
                                break
                            elif filter_crossover == "slow_above_fast" and slow_val > fast_val:
                                passes_filter = True
                                break

                if passes_filter:
                    filtered_bundle[symbol] = ohlcv_data
                    passed_count += 1
                    logger.debug(f"✅ StochasticHeatmapFilter: {symbol} passes ({filter_crossover})")
                    
                    # Stop if we've reached the maximum number of symbols
                    if passed_count >= max_symbols:
                        logger.info(
                            f"🔵 StochasticHeatmapFilter: Reached max_symbols limit ({max_symbols}). "
                            f"Stopping filter processing."
                        )
                        break
                else:
                    failed_count += 1
                    logger.debug(f"⏭️  StochasticHeatmapFilter: {symbol} fails ({filter_crossover})")

            except Exception as e:
                logger.error(f"❌ StochasticHeatmapFilter: Error processing {symbol}: {e}", exc_info=True)
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

        logger.info(
            f"✅ StochasticHeatmapFilter: Completed. Passed: {passed_count}/{total_symbols}, "
            f"Failed: {failed_count}/{total_symbols}"
        )

        # Final status update
        try:
            self.report_progress(100.0, f"{passed_count}/{total_symbols}")
        except Exception:
            pass

        return {"filtered_ohlcv_bundle": filtered_bundle}

