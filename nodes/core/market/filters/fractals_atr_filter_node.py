"""
Fractals ATR Filter Node

Filters assets based on Fractals ATR Block indicator signals.
Can filter for bullish (up fractals, ATR up breaks, fractal ROC up) or bearish (down fractals, ATR down breaks, fractal ROC down) signals.
"""

import logging
from typing import Any

import numpy as np

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.fractals_atr_calculator import calculate_fractals_atr

logger = logging.getLogger(__name__)


class FractalsATRFilter(BaseIndicatorFilter):
    """
    Filters assets based on Fractals ATR Block indicator signals.
    
    Can filter for:
    - Bullish: Up fractals, ATR up breaks, or fractal ROC up signals
    - Bearish: Down fractals, ATR down breaks, or fractal ROC down signals
    """

    default_params = {
        "filter_type": "bullish",  # "bullish" or "bearish"
        "atr_period": 325,
        "fractals_periods": 1,
        "roc_break_level": 2.0,
        "atr_break_level": 1.5,
        "require_fractals": False,  # If True, require fractals to be present
        "require_atr_breaks": False,  # If True, require ATR breaks
        "require_roc": False,  # If True, require ROC signals
        "check_last_bar_only": True,  # If True, only check the last bar; if False, check last 5 bars
    }

    params_meta = [
        {
            "name": "filter_type",
            "type": "string",
            "default": "bullish",
            "options": ["bullish", "bearish"],
            "description": "Filter for bullish or bearish signals",
        },
        {
            "name": "atr_period",
            "type": "number",
            "default": 325,
            "min": 1,
            "step": 1,
            "description": "ATR period for break detection",
        },
        {
            "name": "fractals_periods",
            "type": "number",
            "default": 1,
            "min": 1,
            "step": 1,
            "description": "Fractals periods",
        },
        {
            "name": "roc_break_level",
            "type": "number",
            "default": 2.0,
            "min": 0.0,
            "step": 0.1,
            "description": "ROC break level threshold",
        },
        {
            "name": "atr_break_level",
            "type": "number",
            "default": 1.5,
            "min": 0.0,
            "step": 0.1,
            "description": "ATR break level threshold",
        },
        {
            "name": "require_fractals",
            "type": "boolean",
            "default": False,
            "description": "Require fractals to be present for signal",
        },
        {
            "name": "require_atr_breaks",
            "type": "boolean",
            "default": False,
            "description": "Require ATR breaks for signal",
        },
        {
            "name": "require_roc",
            "type": "boolean",
            "default": False,
            "description": "Require ROC signals for signal",
        },
        {
            "name": "check_last_bar_only",
            "type": "boolean",
            "default": True,
            "description": "If True, only check the last bar for signals; if False, check last 5 bars",
        },
    ]

    def _validate_indicator_params(self):
        filter_type_value = self.params.get("filter_type", "bullish")
        if filter_type_value not in ["bullish", "bearish"]:
            raise ValueError("filter_type must be 'bullish' or 'bearish'")

        self.filter_type = str(filter_type_value)
        self.atr_period = int(self.params.get("atr_period", 325))
        self.fractals_periods = int(self.params.get("fractals_periods", 1))
        self.roc_break_level = float(self.params.get("roc_break_level", 2.0))
        self.atr_break_level = float(self.params.get("atr_break_level", 1.5))
        self.require_fractals = bool(self.params.get("require_fractals", False))
        self.require_atr_breaks = bool(self.params.get("require_atr_breaks", False))
        self.require_roc = bool(self.params.get("require_roc", False))
        self.check_last_bar_only = bool(self.params.get("check_last_bar_only", True))

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate Fractals ATR and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="No data",
            )

        # Extract OHLC data
        opens = [bar["open"] for bar in ohlcv_data]
        highs = [bar["high"] for bar in ohlcv_data]
        lows = [bar["low"] for bar in ohlcv_data]
        closes = [bar["close"] for bar in ohlcv_data]

        # Calculate Fractals ATR
        try:
            fractals_atr_result = calculate_fractals_atr(
                highs=highs,
                lows=lows,
                opens=opens,
                closes=closes,
                atr_period=self.atr_period,
                fractals_periods=self.fractals_periods,
                roc_break_level=self.roc_break_level,
                atr_break_level=self.atr_break_level,
            )

            # Find the most recent signal (going backwards from the last bar)
            # According to PineScript:
            # - Bullish: downFractal AND rocup > roclevel OR atrup > atrlevel
            # - Bearish: upFractal AND rocdn > roclevel OR atrdn > atrlevel
            # We need to find the SINGLE most recent signal of any type
            last_signal_idx = -1
            last_signal_was_bullish = False
            last_signal_was_bearish = False
            
            # Search backwards from the end to find the most recent signal of ANY type
            for i in range(len(ohlcv_data) - 1, -1, -1):
                # Check for bullish signals at this bar (matching PineScript logic)
                has_bullish = False
                # Bullish: ATR up break OR (down fractal with ROC up)
                if fractals_atr_result["atr_up_breaks"][i] is not None and fractals_atr_result["atr_up_breaks"][i] > 0:
                    has_bullish = True
                # downFractal AND rocup > roclevel (stored in fractal_roc_up)
                if fractals_atr_result["down_fractals"][i] and fractals_atr_result["fractal_roc_up"][i] is not None and fractals_atr_result["fractal_roc_up"][i] > 0:
                    has_bullish = True
                
                # Check for bearish signals at this bar (matching PineScript logic)
                has_bearish = False
                # Bearish: ATR down break OR (up fractal with ROC down)
                if fractals_atr_result["atr_down_breaks"][i] is not None and fractals_atr_result["atr_down_breaks"][i] > 0:
                    has_bearish = True
                # upFractal AND rocdn > roclevel (stored in fractal_roc_down)
                if fractals_atr_result["up_fractals"][i] and fractals_atr_result["fractal_roc_down"][i] is not None and fractals_atr_result["fractal_roc_down"][i] > 0:
                    has_bearish = True
                
                # If we found ANY signal at this bar, record it and stop (most recent)
                if has_bullish or has_bearish:
                    last_signal_idx = i
                    last_signal_was_bullish = has_bullish
                    last_signal_was_bearish = has_bearish
                    break
            
            # Store indices for backward compatibility with the rest of the code
            last_bullish_signal_idx = last_signal_idx if last_signal_was_bullish else -1
            last_bearish_signal_idx = last_signal_idx if last_signal_was_bearish else -1
            
            # For backward compatibility with the old logic (if check_last_bar_only is False)
            if not self.check_last_bar_only:
                # Check last 5 bars for any signals
                lookback = min(5, len(ohlcv_data))
                start_idx = max(0, len(ohlcv_data) - lookback)
                has_up_fractal = any(fractals_atr_result["up_fractals"][start_idx:])
                has_atr_up_break = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["atr_up_breaks"][start_idx:]
                )
                has_fractal_roc_up = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["fractal_roc_up"][start_idx:]
                )
                has_down_fractal = any(fractals_atr_result["down_fractals"][start_idx:])
                has_atr_down_break = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["atr_down_breaks"][start_idx:]
                )
                has_fractal_roc_down = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["fractal_roc_down"][start_idx:]
                )
            else:
                # Use the last signal logic - check what type of signal it was
                # For bullish: could be ATR up break OR fractal ROC up (down fractal + ROC)
                # For bearish: could be ATR down break OR fractal ROC down (up fractal + ROC)
                has_up_fractal = False
                has_atr_up_break = False
                has_fractal_roc_up = False
                has_down_fractal = False
                has_atr_down_break = False
                has_fractal_roc_down = False
                
                if last_signal_was_bullish and last_bullish_signal_idx >= 0:
                    # Check what type of bullish signal it was
                    idx = last_bullish_signal_idx
                    if fractals_atr_result["atr_up_breaks"][idx] is not None and fractals_atr_result["atr_up_breaks"][idx] > 0:
                        has_atr_up_break = True
                    if fractals_atr_result["down_fractals"][idx] and fractals_atr_result["fractal_roc_up"][idx] is not None and fractals_atr_result["fractal_roc_up"][idx] > 0:
                        has_down_fractal = True  # Down fractal is part of bullish signal
                        has_fractal_roc_up = True
                
                if last_signal_was_bearish and last_bearish_signal_idx >= 0:
                    # Check what type of bearish signal it was
                    idx = last_bearish_signal_idx
                    if fractals_atr_result["atr_down_breaks"][idx] is not None and fractals_atr_result["atr_down_breaks"][idx] > 0:
                        has_atr_down_break = True
                    if fractals_atr_result["up_fractals"][idx] and fractals_atr_result["fractal_roc_down"][idx] is not None and fractals_atr_result["fractal_roc_down"][idx] > 0:
                        has_up_fractal = True  # Up fractal is part of bearish signal
                        has_fractal_roc_down = True

            # Store signals in lines dict (IndicatorValue supports lines dict)
            signals_dict = {
                "bullish_up_fractal": 1.0 if has_up_fractal else 0.0,
                "bullish_atr_up_break": 1.0 if has_atr_up_break else 0.0,
                "bullish_fractal_roc_up": 1.0 if has_fractal_roc_up else 0.0,
                "bearish_down_fractal": 1.0 if has_down_fractal else 0.0,
                "bearish_atr_down_break": 1.0 if has_atr_down_break else 0.0,
                "bearish_fractal_roc_down": 1.0 if has_fractal_roc_down else 0.0,
            }

            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines=signals_dict),
                params=self.params,
            )

        except Exception as e:
            logger.warning(f"Failed to calculate Fractals ATR: {e}")
            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=ohlcv_data[-1]["timestamp"] if ohlcv_data else 0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error=str(e),
            )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter based on bullish/bearish signals."""
        if indicator_result.error:
            return False

        if not hasattr(indicator_result.values, "lines"):
            return False

        signals = indicator_result.values.lines
        if not isinstance(signals, dict):
            return False

        if self.filter_type == "bullish":
            has_fractal = signals.get("bullish_up_fractal", 0.0) > 0.0
            has_atr_break = signals.get("bullish_atr_up_break", 0.0) > 0.0
            has_roc = signals.get("bullish_fractal_roc_up", 0.0) > 0.0

            # Check requirements
            if self.require_fractals and not has_fractal:
                return False
            if self.require_atr_breaks and not has_atr_break:
                return False
            if self.require_roc and not has_roc:
                return False

            # Pass if any bullish signal is present (or all required ones)
            return has_fractal or has_atr_break or has_roc

        else:  # bearish
            has_fractal = signals.get("bearish_down_fractal", 0.0) > 0.0
            has_atr_break = signals.get("bearish_atr_down_break", 0.0) > 0.0
            has_roc = signals.get("bearish_fractal_roc_down", 0.0) > 0.0

            # Check requirements
            if self.require_fractals and not has_fractal:
                return False
            if self.require_atr_breaks and not has_atr_break:
                return False
            if self.require_roc and not has_roc:
                return False

            # Pass if any bearish signal is present (or all required ones)
            return has_fractal or has_atr_break or has_roc

