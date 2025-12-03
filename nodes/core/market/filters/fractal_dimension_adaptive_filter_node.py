"""
Fractal Dimension Adaptive Filter Node

Filters assets based on Fractal Dimension Adaptive (DSSAKAMA) indicator signals.
Can filter for bullish (Outer > Signal, green) or bearish (Outer <= Signal, red) signals.
"""

import logging
from typing import Any

import numpy as np

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.fractal_dimension_adaptive_calculator import (
    calculate_fractal_dimension_adaptive,
)

logger = logging.getLogger(__name__)


class FractalDimensionAdaptiveFilter(BaseIndicatorFilter):
    """
    Filters assets based on Fractal Dimension Adaptive (DSSAKAMA) indicator signals.
    
    Can filter for:
    - Bullish: Outer > Signal (green line)
    - Bearish: Outer <= Signal (red line)
    """

    default_params = {
        "filter_type": "bullish",  # "bullish" or "bearish"
        "period": 10,
        "kama_fastend": 2.0,
        "kama_slowend": 30.0,
        "efratiocalc": "Fractal Dimension Adaptive",
        "jcount": 2,
        "smooth_power": 2,
        "stoch_len": 30,
        "sm_ema": 9,
        "sig_ema": 5,
        "lookback_bars": 1,  # Check last N bars for signal consistency
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
            "name": "period",
            "type": "number",
            "default": 10,
            "min": 1,
            "step": 1,
            "description": "KAMA period",
        },
        {
            "name": "kama_fastend",
            "type": "number",
            "default": 2.0,
            "min": 0.1,
            "step": 0.1,
            "description": "Kaufman AMA fast-end period",
        },
        {
            "name": "kama_slowend",
            "type": "number",
            "default": 30.0,
            "min": 0.1,
            "step": 0.1,
            "description": "Kaufman AMA slow-end period",
        },
        {
            "name": "efratiocalc",
            "type": "string",
            "default": "Fractal Dimension Adaptive",
            "options": ["Regular", "Fractal Dimension Adaptive"],
            "description": "Efficiency ratio calculation type",
        },
        {
            "name": "jcount",
            "type": "number",
            "default": 2,
            "min": 1,
            "step": 1,
            "description": "Fractal dimension count",
        },
        {
            "name": "smooth_power",
            "type": "number",
            "default": 2,
            "min": 1,
            "step": 1,
            "description": "Kaufman power smoothing",
        },
        {
            "name": "stoch_len",
            "type": "number",
            "default": 30,
            "min": 1,
            "step": 1,
            "description": "Stochastic smoothing period",
        },
        {
            "name": "sm_ema",
            "type": "number",
            "default": 9,
            "min": 1,
            "step": 1,
            "description": "Intermediate EMA smoothing period",
        },
        {
            "name": "sig_ema",
            "type": "number",
            "default": 5,
            "min": 1,
            "step": 1,
            "description": "Signal EMA smoothing period",
        },
        {
            "name": "lookback_bars",
            "type": "number",
            "default": 1,
            "min": 1,
            "step": 1,
            "description": "Check last N bars for signal consistency",
        },
    ]

    def _validate_indicator_params(self):
        filter_type_value = self.params.get("filter_type", "bullish")
        if filter_type_value not in ["bullish", "bearish"]:
            raise ValueError("filter_type must be 'bullish' or 'bearish'")

        self.filter_type = str(filter_type_value)
        self.period = int(self.params.get("period", 10))
        self.kama_fastend = float(self.params.get("kama_fastend", 2.0))
        self.kama_slowend = float(self.params.get("kama_slowend", 30.0))
        self.efratiocalc = str(self.params.get("efratiocalc", "Fractal Dimension Adaptive"))
        self.jcount = int(self.params.get("jcount", 2))
        self.smooth_power = int(self.params.get("smooth_power", 2))
        self.stoch_len = int(self.params.get("stoch_len", 30))
        self.sm_ema = int(self.params.get("sm_ema", 9))
        self.sig_ema = int(self.params.get("sig_ema", 5))
        self.lookback_bars = int(self.params.get("lookback_bars", 1))

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate Fractal Dimension Adaptive and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="No data",
            )

        # Extract OHLC data
        closes = [bar["close"] for bar in ohlcv_data]
        highs = [bar["high"] for bar in ohlcv_data]
        lows = [bar["low"] for bar in ohlcv_data]

        # Calculate Fractal Dimension Adaptive
        try:
            fractal_dim_result = calculate_fractal_dimension_adaptive(
                closes=closes,
                highs=highs,
                lows=lows,
                period=self.period,
                kama_fastend=self.kama_fastend,
                kama_slowend=self.kama_slowend,
                efratiocalc=self.efratiocalc,
                jcount=self.jcount,
                smooth_power=self.smooth_power,
                stoch_len=self.stoch_len,
                sm_ema=self.sm_ema,
                sig_ema=self.sig_ema,
            )

            signal = fractal_dim_result.get("signal", [])
            outer = fractal_dim_result.get("outer", [])

            if not signal or not outer:
                return IndicatorResult(
                    indicator_type=IndicatorType.CUSTOM,
                    timestamp=ohlcv_data[-1]["timestamp"],
                    values=IndicatorValue(single=np.nan),
                    params=self.params,
                    error="Insufficient data",
                )

            # Check last N bars for signal consistency
            lookback = min(self.lookback_bars, len(signal), len(outer))
            start_idx = max(0, len(signal) - lookback)

            # Count bullish and bearish signals in lookback period
            bullish_count = 0
            bearish_count = 0

            for i in range(start_idx, len(signal)):
                if signal[i] is not None and outer[i] is not None:
                    if outer[i] > signal[i]:
                        bullish_count += 1
                    else:
                        bearish_count += 1

            # Get latest values
            latest_signal = signal[-1] if signal else None
            latest_outer = outer[-1] if outer else None

            is_bullish = False
            is_bearish = False

            if latest_signal is not None and latest_outer is not None:
                is_bullish = latest_outer > latest_signal
                is_bearish = latest_outer <= latest_signal

            # Store signals in lines dict (IndicatorValue supports lines dict)
            signals_dict = {
                "is_bullish": 1.0 if is_bullish else 0.0,
                "is_bearish": 1.0 if is_bearish else 0.0,
                "bullish_count": float(bullish_count),
                "bearish_count": float(bearish_count),
                "latest_signal": latest_signal if latest_signal is not None else 0.0,
                "latest_outer": latest_outer if latest_outer is not None else 0.0,
            }

            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines=signals_dict),
                params=self.params,
            )

        except Exception as e:
            logger.warning(f"Failed to calculate Fractal Dimension Adaptive: {e}")
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
            return signals.get("is_bullish", 0.0) > 0.0
        else:  # bearish
            return signals.get("is_bearish", 0.0) > 0.0

