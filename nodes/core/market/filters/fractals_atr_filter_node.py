"""
Fractals ATR Filter Node

Filters assets based on Fractals ATR Block indicator signals.
Can filter for bullish (up fractals, ATR up breaks, fractal ROC up) or bearish (down fractals, ATR down breaks, fractal ROC down) signals.
"""

import logging
from typing import Any

import numpy as np

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar, get_type
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
    
    # Add second output for signal debug information
    outputs = {
        "filtered_ohlcv_bundle": get_type("OHLCVBundle"),
        "signal_metadata": dict[str, Any],  # Signal debug info per symbol: {symbol: {signal_idx, timestamp, etc}}
    }

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
            "type": "combo",
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

            # Find the most recent bullish and bearish signals separately
            last_bullish_signal_idx = -1
            last_bearish_signal_idx = -1
            
            for idx in range(len(ohlcv_data) - 1, -1, -1):
                has_bullish = False
                has_bearish = False
                
                # Bullish signal: ATR up break OR down fractal + ROC up
                if fractals_atr_result["atr_up_breaks"][idx] is not None and fractals_atr_result["atr_up_breaks"][idx] > 0:
                    has_bullish = True
                if (
                    fractals_atr_result["down_fractals"][idx]
                    and fractals_atr_result["fractal_roc_up"][idx] is not None
                    and fractals_atr_result["fractal_roc_up"][idx] > 0
                ):
                    has_bullish = True
                
                # Bearish signal: ATR down break OR up fractal + ROC down
                if fractals_atr_result["atr_down_breaks"][idx] is not None and fractals_atr_result["atr_down_breaks"][idx] > 0:
                    has_bearish = True
                if (
                    fractals_atr_result["up_fractals"][idx]
                    and fractals_atr_result["fractal_roc_down"][idx] is not None
                    and fractals_atr_result["fractal_roc_down"][idx] > 0
                ):
                    has_bearish = True
                
                if has_bullish and last_bullish_signal_idx == -1:
                    last_bullish_signal_idx = idx
                if has_bearish and last_bearish_signal_idx == -1:
                    last_bearish_signal_idx = idx
                
                if last_bullish_signal_idx != -1 and last_bearish_signal_idx != -1:
                    break
            
            # Determine which signal is most recent overall (for logging/debug)
            if last_bullish_signal_idx >= 0 and last_bearish_signal_idx >= 0:
                if last_bullish_signal_idx > last_bearish_signal_idx:
                    last_signal_type = "bullish"
                    last_signal_idx = last_bullish_signal_idx
                elif last_bearish_signal_idx > last_bullish_signal_idx:
                    last_signal_type = "bearish"
                    last_signal_idx = last_bearish_signal_idx
                else:
                    last_signal_type = "both"
                    last_signal_idx = last_bullish_signal_idx
            elif last_bullish_signal_idx >= 0:
                last_signal_type = "bullish"
                last_signal_idx = last_bullish_signal_idx
            elif last_bearish_signal_idx >= 0:
                last_signal_type = "bearish"
                last_signal_idx = last_bearish_signal_idx
            else:
                last_signal_type = None
                last_signal_idx = None
            
            last_signal_was_bullish = last_signal_type in ("bullish", "both")
            last_signal_was_bearish = last_signal_type in ("bearish", "both")
            
            logger.debug(
                "FractalsATRFilter: Signal summary -> last_bullish_idx=%s, last_bearish_idx=%s, "
                "most_recent_type=%s, most_recent_idx=%s",
                last_bullish_signal_idx,
                last_bearish_signal_idx,
                last_signal_type,
                last_signal_idx,
            )
            
            # Persist indices for use in _should_pass_filter
            self.last_bullish_signal_idx = last_bullish_signal_idx
            self.last_bearish_signal_idx = last_bearish_signal_idx
            
            # For backward compatibility with the old logic (if check_last_bar_only is False)
            if not self.check_last_bar_only:
                # Check last 5 bars for any signals (per type)
                lookback = min(5, len(ohlcv_data))
                start_idx = max(0, len(ohlcv_data) - lookback)
                
                bull_has_down_fractal = any(fractals_atr_result["down_fractals"][start_idx:])
                bull_has_atr_up_break = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["atr_up_breaks"][start_idx:]
                )
                bull_has_fractal_roc_up = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["fractal_roc_up"][start_idx:]
                )
                
                bear_has_up_fractal = any(fractals_atr_result["up_fractals"][start_idx:])
                bear_has_atr_down_break = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["atr_down_breaks"][start_idx:]
                )
                bear_has_fractal_roc_down = any(
                    v is not None and v > 0
                    for v in fractals_atr_result["fractal_roc_down"][start_idx:]
                )
            else:
                # Only consider the most recent signal for each type
                bull_has_down_fractal = False
                bull_has_atr_up_break = False
                bull_has_fractal_roc_up = False
                bear_has_up_fractal = False
                bear_has_atr_down_break = False
                bear_has_fractal_roc_down = False
                
                if last_bullish_signal_idx >= 0:
                    idx = last_bullish_signal_idx
                    if (
                        fractals_atr_result["down_fractals"][idx]
                        and fractals_atr_result["fractal_roc_up"][idx] is not None
                        and fractals_atr_result["fractal_roc_up"][idx] > 0
                    ):
                        bull_has_down_fractal = True
                        bull_has_fractal_roc_up = True
                    if (
                        fractals_atr_result["atr_up_breaks"][idx] is not None
                        and fractals_atr_result["atr_up_breaks"][idx] > 0
                    ):
                        bull_has_atr_up_break = True
                
                if last_bearish_signal_idx >= 0:
                    idx = last_bearish_signal_idx
                    if (
                        fractals_atr_result["up_fractals"][idx]
                        and fractals_atr_result["fractal_roc_down"][idx] is not None
                        and fractals_atr_result["fractal_roc_down"][idx] > 0
                    ):
                        bear_has_up_fractal = True
                        bear_has_fractal_roc_down = True
                    if (
                        fractals_atr_result["atr_down_breaks"][idx] is not None
                        and fractals_atr_result["atr_down_breaks"][idx] > 0
                    ):
                        bear_has_atr_down_break = True
                
                logger.debug(
                    "FractalsATRFilter: Last-signal flags -> bull(fractal=%s, atr=%s, roc=%s) "
                    "bear(fractal=%s, atr=%s, roc=%s)",
                    bull_has_down_fractal,
                    bull_has_atr_up_break,
                    bull_has_fractal_roc_up,
                    bear_has_up_fractal,
                    bear_has_atr_down_break,
                    bear_has_fractal_roc_down,
                )

            # Get timestamps for the signal bars for easy TradingView comparison
            bullish_signal_timestamp = -1.0
            bearish_signal_timestamp = -1.0
            if last_bullish_signal_idx >= 0 and last_bullish_signal_idx < len(ohlcv_data):
                bullish_signal_timestamp = float(ohlcv_data[last_bullish_signal_idx]["timestamp"])
            if last_bearish_signal_idx >= 0 and last_bearish_signal_idx < len(ohlcv_data):
                bearish_signal_timestamp = float(ohlcv_data[last_bearish_signal_idx]["timestamp"])
            
            # Store signals in lines dict (IndicatorValue supports lines dict)
            # Note: Bullish signals come from DOWN fractals (marks a low), Bearish from UP fractals (marks a high)
            signals_dict = {
                "bullish_down_fractal": 1.0 if bull_has_down_fractal else 0.0,
                "bullish_atr_up_break": 1.0 if bull_has_atr_up_break else 0.0,
                "bullish_fractal_roc_up": 1.0 if bull_has_fractal_roc_up else 0.0,
                "bearish_up_fractal": 1.0 if bear_has_up_fractal else 0.0,
                "bearish_atr_down_break": 1.0 if bear_has_atr_down_break else 0.0,
                "bearish_fractal_roc_down": 1.0 if bear_has_fractal_roc_down else 0.0,
                # Debug/transparency fields: signal indices and timestamps
                # These help you match signals with TradingView charts
                "last_bullish_signal_idx": float(last_bullish_signal_idx) if last_bullish_signal_idx >= 0 else -1.0,
                "last_bearish_signal_idx": float(last_bearish_signal_idx) if last_bearish_signal_idx >= 0 else -1.0,
                "last_bullish_signal_timestamp": bullish_signal_timestamp,
                "last_bearish_signal_timestamp": bearish_signal_timestamp,
                "most_recent_signal_type": float(1.0) if last_signal_type == "bullish" else (float(2.0) if last_signal_type == "bearish" else (float(3.0) if last_signal_type == "both" else 0.0)),  # 1=bullish, 2=bearish, 3=both, 0=none
                "most_recent_signal_idx": float(last_signal_idx) if last_signal_idx is not None and last_signal_idx >= 0 else -1.0,
            }
            
            logger.info(
                f"FractalsATRFilter [{self.filter_type}] signals detected: "
                f"bullish_idx={last_bullish_signal_idx} (ts={bullish_signal_timestamp}), "
                f"bearish_idx={last_bearish_signal_idx} (ts={bearish_signal_timestamp}), "
                f"most_recent={last_signal_type}@{last_signal_idx}, "
                f"signals={signals_dict}"
            )

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
            logger.debug(f"FractalsATRFilter: Indicator error: {indicator_result.error}")
            return False

        if not hasattr(indicator_result.values, "lines"):
            logger.debug("FractalsATRFilter: No lines in indicator result")
            return False

        signals = indicator_result.values.lines
        if not isinstance(signals, dict):
            logger.debug("FractalsATRFilter: Signals is not a dict")
            return False

        # Get signal indices for logging
        last_bullish_idx = signals.get("last_bullish_signal_idx", -1.0)
        last_bearish_idx = signals.get("last_bearish_signal_idx", -1.0)
        bullish_ts = signals.get("last_bullish_signal_timestamp", -1.0)
        bearish_ts = signals.get("last_bearish_signal_timestamp", -1.0)
        
        if self.filter_type == "bullish":
            # Bullish signals: downFractal + ROC up OR ATR up break
            # Per Pine Script: downFractal and rocup > roclevel OR atrup > atrlevel
            has_fractal = signals.get("bullish_down_fractal", 0.0) > 0.0  # Down fractal marks a low (bullish)
            has_atr_break = signals.get("bullish_atr_up_break", 0.0) > 0.0
            has_roc = signals.get("bullish_fractal_roc_up", 0.0) > 0.0

            logger.info(
                f"FractalsATRFilter [BULLISH] check: "
                f"signal_idx={last_bullish_idx}, signal_ts={bullish_ts}, "
                f"fractal={has_fractal}, atr={has_atr_break}, roc={has_roc}, "
                f"require_fractals={self.require_fractals}, require_atr={self.require_atr_breaks}, require_roc={self.require_roc}"
            )

            # Check if we have a valid bullish signal
            # Signal can be: (fractal AND roc) OR (atr_break)
            has_fractal_roc_signal = has_fractal and has_roc
            has_atr_signal = has_atr_break
            
            # Ensure the bullish signal is more recent than the bearish signal (if last-bar-only mode)
            if self.check_last_bar_only:
                if last_bullish_idx < 0:
                    logger.info("FractalsATRFilter [BULLISH]: No recent bullish signal found; failing filter.")
                    return False
                if last_bearish_idx >= 0 and last_bearish_idx > last_bullish_idx:
                    logger.info(
                        "FractalsATRFilter [BULLISH]: More recent bearish signal (idx=%.0f, ts=%.0f) than bullish signal (idx=%.0f, ts=%.0f); failing filter.",
                        last_bearish_idx,
                        bearish_ts,
                        last_bullish_idx,
                        bullish_ts,
                    )
                    return False
            
            # If specific requirements are set, the signal must match those requirements
            # Note: A signal is EITHER (fractal+ROC) OR (ATR break), not both
            # So if all three are required, it's impossible - log warning and use OR logic
            if self.require_fractals and self.require_roc and self.require_atr_breaks:
                logger.warning("FractalsATRFilter: All three require flags are True, but signals are either "
                              "(fractal+ROC) OR (ATR break), not both. Using OR logic - will pass if EITHER signal type exists.")
                # If all three are required, pass if EITHER (fractal+ROC) OR (ATR break) exists
                result = has_fractal_roc_signal or has_atr_signal
            elif self.require_fractals and self.require_roc:
                # Must have both fractal and ROC (fractal+ROC signal)
                if not has_fractal:
                    logger.debug("FractalsATRFilter: Require fractals but no fractal found")
                    return False
                if not has_roc:
                    logger.debug("FractalsATRFilter: Require ROC but no ROC found")
                    return False
                result = has_fractal_roc_signal
            elif self.require_atr_breaks:
                # Must have ATR break
                if not has_atr_break:
                    logger.debug("FractalsATRFilter: Require ATR breaks but no ATR break found")
                    return False
                result = has_atr_signal
            elif self.require_fractals:
                # Only require fractals (can be part of fractal+ROC or standalone)
                if not has_fractal:
                    logger.debug("FractalsATRFilter: Require fractals but no fractal found")
                    return False
                result = has_fractal_roc_signal or has_atr_signal  # Pass if any signal with fractal
            elif self.require_roc:
                # Only require ROC (must be part of fractal+ROC signal)
                if not has_roc:
                    logger.debug("FractalsATRFilter: Require ROC but no ROC found")
                    return False
                result = has_fractal_roc_signal  # Only fractal+ROC signals have ROC
            else:
                # No specific requirements, pass if any bullish signal
                result = has_fractal_roc_signal or has_atr_signal
            
            if result:
                logger.info(
                    f"FractalsATRFilter [BULLISH] PASSED: signal_idx={last_bullish_idx}, signal_ts={bullish_ts}, "
                    f"signal_type={'fractal+ROC' if has_fractal_roc_signal else 'ATR_break' if has_atr_signal else 'unknown'}"
                )
            else:
                logger.debug(f"FractalsATRFilter [BULLISH] FAILED: no valid signal")
            return result

        else:  # bearish
            # Bearish signals: upFractal + ROC down OR ATR down break
            # Per Pine Script: upFractal and rocdn > roclevel OR atrdn > atrlevel
            has_fractal = signals.get("bearish_up_fractal", 0.0) > 0.0  # Up fractal marks a high (bearish)
            has_atr_break = signals.get("bearish_atr_down_break", 0.0) > 0.0
            has_roc = signals.get("bearish_fractal_roc_down", 0.0) > 0.0

            logger.info(
                f"FractalsATRFilter [BEARISH] check: "
                f"signal_idx={last_bearish_idx}, signal_ts={bearish_ts}, "
                f"fractal={has_fractal}, atr={has_atr_break}, roc={has_roc}, "
                f"require_fractals={self.require_fractals}, require_atr={self.require_atr_breaks}, require_roc={self.require_roc}"
            )

            # Check if we have a valid bearish signal
            # Signal can be: (fractal AND roc) OR (atr_break)
            has_fractal_roc_signal = has_fractal and has_roc
            has_atr_signal = has_atr_break
            
            # Ensure the bearish signal is more recent than the bullish signal (if last-bar-only mode)
            if self.check_last_bar_only:
                if last_bearish_idx < 0:
                    logger.info("FractalsATRFilter [BEARISH]: No recent bearish signal found; failing filter.")
                    return False
                if last_bullish_idx >= 0 and last_bullish_idx > last_bearish_idx:
                    logger.info(
                        "FractalsATRFilter [BEARISH]: More recent bullish signal (idx=%.0f, ts=%.0f) than bearish signal (idx=%.0f, ts=%.0f); failing filter.",
                        last_bullish_idx,
                        bullish_ts,
                        last_bearish_idx,
                        bearish_ts,
                    )
                    return False
            
            # If specific requirements are set, the signal must match those requirements
            # Note: A signal is EITHER (fractal+ROC) OR (ATR break), not both
            # So if all three are required, it's impossible - log warning and use OR logic
            if self.require_fractals and self.require_roc and self.require_atr_breaks:
                logger.warning("FractalsATRFilter: All three require flags are True, but signals are either "
                              "(fractal+ROC) OR (ATR break), not both. Using OR logic - will pass if EITHER signal type exists.")
                # If all three are required, pass if EITHER (fractal+ROC) OR (ATR break) exists
                result = has_fractal_roc_signal or has_atr_signal
            elif self.require_fractals and self.require_roc:
                # Must have both fractal and ROC (fractal+ROC signal)
                if not has_fractal:
                    logger.debug("FractalsATRFilter: Require fractals but no fractal found")
                    return False
                if not has_roc:
                    logger.debug("FractalsATRFilter: Require ROC but no ROC found")
                    return False
                result = has_fractal_roc_signal
            elif self.require_atr_breaks:
                # Must have ATR break
                if not has_atr_break:
                    logger.debug("FractalsATRFilter: Require ATR breaks but no ATR break found")
                    return False
                result = has_atr_signal
            elif self.require_fractals:
                # Only require fractals (can be part of fractal+ROC or standalone)
                if not has_fractal:
                    logger.debug("FractalsATRFilter: Require fractals but no fractal found")
                    return False
                result = has_fractal_roc_signal or has_atr_signal  # Pass if any signal with fractal
            elif self.require_roc:
                # Only require ROC (must be part of fractal+ROC signal)
                if not has_roc:
                    logger.debug("FractalsATRFilter: Require ROC but no ROC found")
                    return False
                result = has_fractal_roc_signal  # Only fractal+ROC signals have ROC
            else:
                # No specific requirements, pass if any bearish signal
                result = has_fractal_roc_signal or has_atr_signal
            
            if result:
                logger.info(
                    f"FractalsATRFilter [BEARISH] PASSED: signal_idx={last_bearish_idx}, signal_ts={bearish_ts}, "
                    f"signal_type={'fractal+ROC' if has_fractal_roc_signal else 'ATR_break' if has_atr_signal else 'unknown'}"
                )
            else:
                logger.debug(f"FractalsATRFilter [BEARISH] FAILED: no valid signal")
            return result
    
    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Override to collect signal metadata for debugging."""
        from core.types_registry import AssetSymbol
        
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {
                "filtered_ohlcv_bundle": {},
                "signal_metadata": {},
            }

        filtered_bundle = {}
        signal_metadata = {}  # Collect signal info for each symbol
        total_symbols = len(ohlcv_bundle)
        processed_symbols = 0

        # Initial progress signal
        try:
            self.report_progress(0.0, f"0/{total_symbols}")
        except Exception:
            pass

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            try:
                indicator_result = self._calculate_indicator(ohlcv_data)
                
                # Extract signal metadata from indicator result
                signal_info = {}
                if hasattr(indicator_result.values, "lines") and isinstance(indicator_result.values.lines, dict):
                    signals = indicator_result.values.lines
                    
                    # Count historical signals before the most recent one
                    # We need to recalculate to count all signals (not just the last one)
                    fractals_atr_result = calculate_fractals_atr(
                        highs=[bar["high"] for bar in ohlcv_data],
                        lows=[bar["low"] for bar in ohlcv_data],
                        opens=[bar["open"] for bar in ohlcv_data],
                        closes=[bar["close"] for bar in ohlcv_data],
                        atr_period=self.atr_period,
                        fractals_periods=self.fractals_periods,
                        roc_break_level=self.roc_break_level,
                        atr_break_level=self.atr_break_level,
                    )
                    
                    # Count all signals in history
                    total_bullish_signals = 0
                    total_bearish_signals = 0
                    bullish_signal_indices = []
                    bearish_signal_indices = []
                    
                    for idx in range(len(ohlcv_data)):
                        # Check for bullish signals
                        has_bullish = False
                        if fractals_atr_result["atr_up_breaks"][idx] is not None and fractals_atr_result["atr_up_breaks"][idx] > 0:
                            has_bullish = True
                        if (
                            fractals_atr_result["down_fractals"][idx]
                            and fractals_atr_result["fractal_roc_up"][idx] is not None
                            and fractals_atr_result["fractal_roc_up"][idx] > 0
                        ):
                            has_bullish = True
                        
                        # Check for bearish signals
                        has_bearish = False
                        if fractals_atr_result["atr_down_breaks"][idx] is not None and fractals_atr_result["atr_down_breaks"][idx] > 0:
                            has_bearish = True
                        if (
                            fractals_atr_result["up_fractals"][idx]
                            and fractals_atr_result["fractal_roc_down"][idx] is not None
                            and fractals_atr_result["fractal_roc_down"][idx] > 0
                        ):
                            has_bearish = True
                        
                        if has_bullish:
                            total_bullish_signals += 1
                            bullish_signal_indices.append(idx)
                        if has_bearish:
                            total_bearish_signals += 1
                            bearish_signal_indices.append(idx)
                    
                    # Calculate signal frequency (signals per 100 bars)
                    total_bars = len(ohlcv_data)
                    bullish_frequency = (total_bullish_signals / total_bars * 100) if total_bars > 0 else 0.0
                    bearish_frequency = (total_bearish_signals / total_bars * 100) if total_bars > 0 else 0.0
                    
                    # Calculate bars between signals (average spacing)
                    avg_bullish_spacing = 0.0
                    avg_bearish_spacing = 0.0
                    if len(bullish_signal_indices) > 1:
                        spacings = [bullish_signal_indices[i] - bullish_signal_indices[i-1] for i in range(1, len(bullish_signal_indices))]
                        avg_bullish_spacing = sum(spacings) / len(spacings) if spacings else 0.0
                    if len(bearish_signal_indices) > 1:
                        spacings = [bearish_signal_indices[i] - bearish_signal_indices[i-1] for i in range(1, len(bearish_signal_indices))]
                        avg_bearish_spacing = sum(spacings) / len(spacings) if spacings else 0.0
                    
                    # Get most recent signal indices
                    last_bullish_idx = signals.get("last_bullish_signal_idx", -1.0)
                    last_bearish_idx = signals.get("last_bearish_signal_idx", -1.0)
                    
                    # Count signals before the most recent one
                    bullish_signals_before_last = sum(1 for idx in bullish_signal_indices if idx < last_bullish_idx) if last_bullish_idx >= 0 else total_bullish_signals
                    bearish_signals_before_last = sum(1 for idx in bearish_signal_indices if idx < last_bearish_idx) if last_bearish_idx >= 0 else total_bearish_signals
                    
                    signal_info = {
                        "last_bullish_signal_idx": last_bullish_idx,
                        "last_bearish_signal_idx": last_bearish_idx,
                        "last_bullish_signal_timestamp": signals.get("last_bullish_signal_timestamp", -1.0),
                        "last_bearish_signal_timestamp": signals.get("last_bearish_signal_timestamp", -1.0),
                        "most_recent_signal_type": signals.get("most_recent_signal_type", 0.0),
                        "most_recent_signal_idx": signals.get("most_recent_signal_idx", -1.0),
                        "bullish_down_fractal": signals.get("bullish_down_fractal", 0.0),
                        "bullish_atr_up_break": signals.get("bullish_atr_up_break", 0.0),
                        "bullish_fractal_roc_up": signals.get("bullish_fractal_roc_up", 0.0),
                        "bearish_up_fractal": signals.get("bearish_up_fractal", 0.0),
                        "bearish_atr_down_break": signals.get("bearish_atr_down_break", 0.0),
                        "bearish_fractal_roc_down": signals.get("bearish_fractal_roc_down", 0.0),
                        # Signal frequency statistics
                        "total_bullish_signals": float(total_bullish_signals),
                        "total_bearish_signals": float(total_bearish_signals),
                        "bullish_signals_before_last": float(bullish_signals_before_last),
                        "bearish_signals_before_last": float(bearish_signals_before_last),
                        "bullish_frequency_per_100_bars": round(bullish_frequency, 2),
                        "bearish_frequency_per_100_bars": round(bearish_frequency, 2),
                        "avg_bullish_signal_spacing_bars": round(avg_bullish_spacing, 1),
                        "avg_bearish_signal_spacing_bars": round(avg_bearish_spacing, 1),
                        "total_bars": float(total_bars),
                        "filter_type": self.filter_type,
                        "passed_filter": False,
                    }
                
                if self._should_pass_filter(indicator_result):
                    filtered_bundle[symbol] = ohlcv_data
                    signal_info["passed_filter"] = True
                
                # Store metadata for all symbols (both passed and failed)
                signal_metadata[str(symbol)] = signal_info

            except Exception as e:
                logger.warning(f"Failed to process indicator for {symbol}: {e}")
                signal_metadata[str(symbol)] = {
                    "error": str(e),
                    "passed_filter": False,
                }
                # Progress should still advance even on failure
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            # Advance progress after successful processing
            processed_symbols += 1
            try:
                progress = (processed_symbols / max(1, total_symbols)) * 100.0
                self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
            except Exception:
                pass

        return {
            "filtered_ohlcv_bundle": filtered_bundle,
            "signal_metadata": signal_metadata,
        }

