import logging
import math

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators import calculate_lod

logger = logging.getLogger(__name__)


class LodFilter(BaseIndicatorFilter):
    """
    Filters assets based on LoD (Low of Day Distance) values.

    LoD Distance is calculated as the distance of current price from the low of the day
    as a percentage of ATR (Average True Range).

    Formula: LoD Distance % = ((current_price - low_of_day) / ATR) * 100

    Filter can be set to pass assets with LoD Distance above a minimum threshold or
    below a maximum threshold.

    Parameter guidance:
    - lod_distance_threshold: Enter a percentage of ATR (not price points).
      For example, 3.16 means the current price is 3.16% of one ATR above the
      day's low. Use numeric values like 3, 5.5, 10, etc. The underlying unit is '% of ATR'.
    - filter_mode: Choose "min" to filter for assets above threshold, or "max" to filter
      for assets below threshold.

    Reference:
    https://www.tradingview.com/script/uloAa2EI-Swing-Data-ADR-RVol-PVol-Float-Avg-Vol/
    """

    default_params = {
        "lod_distance_threshold": 3.16,  # LoD distance percentage threshold
        "atr_window": 14,  # ATR calculation window
        "filter_mode": "min",  # Filter mode: "min" or "max"
    }

    params_meta = [
        {
            "name": "lod_distance_threshold",
            "type": "number",
            "default": 3.16,
            "min": 0.0,
            "step": 0.1,
            "precision": 2,
            "label": "LoD Distance Threshold %",
            "unit": "%",
            "description": "LoD distance threshold as percentage of ATR (e.g., 3.16 = 3.16% of ATR)",
        },
        {
            "name": "atr_window",
            "type": "number",
            "default": 14,
            "min": 1,
            "step": 1,
            "label": "ATR Window",
            "description": "Period for ATR calculation",
        },
        {
            "name": "filter_mode",
            "type": "combo",
            "default": "min",
            "options": ["min", "max"],
            "label": "Filter Mode",
            "description": "Filter for assets above threshold (min) or below threshold (max)",
        },
    ]

    def _validate_indicator_params(self):
        if not isinstance(self.params["lod_distance_threshold"], int | float):
            raise ValueError("LoD distance threshold must be a number")
        if self.params["lod_distance_threshold"] < 0:
            raise ValueError("LoD distance threshold cannot be negative")

        if not isinstance(self.params["atr_window"], int | float):
            raise ValueError("ATR window must be a number")
        if self.params["atr_window"] <= 0:
            raise ValueError("ATR window must be positive")

        if self.params["filter_mode"] not in ["min", "max"]:
            raise ValueError("Filter mode must be either 'min' or 'max'")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate LoD Distance and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=0,
                values=IndicatorValue(lines={"lod_distance_pct": 0.0}),
                params=self.params,
                error="No data",
            )
        timestamp_value: int = ohlcv_data[-1]["timestamp"]

        atr_window_param = self.params["atr_window"]
        if not isinstance(atr_window_param, int | float):
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=timestamp_value,
                values=IndicatorValue(lines={"lod_distance_pct": 0.0}),
                params=self.params,
                error="Invalid ATR window parameter",
            )
        atr_window = int(atr_window_param)

        if len(ohlcv_data) < atr_window:
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=timestamp_value,
                values=IndicatorValue(lines={"lod_distance_pct": 0.0}),
                params=self.params,
                error="Insufficient data for ATR calculation",
            )

        # Extract price data from OHLCV bars
        highs = [bar["high"] for bar in ohlcv_data]
        lows = [bar["low"] for bar in ohlcv_data]
        closes = [bar["close"] for bar in ohlcv_data]

        # Calculate LoD using the calculator
        lod_result = calculate_lod(highs, lows, closes, atr_window)

        # Get the latest values
        lod_distance_pct = lod_result["lod_distance_pct"][-1]
        current_price = lod_result["current_price"][-1]
        low_of_day = lod_result["low_of_day"][-1]
        atr = lod_result["atr"][-1]

        # Check for invalid calculation
        if (
            lod_distance_pct is None
            or atr is None
            or atr <= 0
            or current_price is None
            or low_of_day is None
        ):
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={"lod_distance_pct": 0.0}),
                params=self.params,
                error="Invalid LoD calculation",
            )

        latest_bar = ohlcv_data[-1]

        return IndicatorResult(
            indicator_type=IndicatorType.LOD,
            timestamp=latest_bar["timestamp"],
            values=IndicatorValue(
                lines={
                    "lod_distance_pct": lod_distance_pct,
                    "current_price": current_price,
                    "low_of_day": low_of_day,
                    "atr": atr,
                }
            ),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter based on LoD Distance threshold and filter mode."""
        if indicator_result.error:
            return False

        lines = indicator_result.values.lines
        if "lod_distance_pct" not in lines:
            return False

        lod_distance_pct = lines["lod_distance_pct"]

        if not math.isfinite(lod_distance_pct):
            return False

        lod_distance_threshold_param = self.params["lod_distance_threshold"]
        if not isinstance(lod_distance_threshold_param, int | float):
            return False
        lod_distance_threshold = float(lod_distance_threshold_param)

        filter_mode = self.params["filter_mode"]

        if filter_mode == "min":
            # Filter for assets with LoD Distance ABOVE threshold
            return lod_distance_pct >= lod_distance_threshold
        elif filter_mode == "max":
            # Filter for assets with LoD Distance BELOW threshold
            return lod_distance_pct <= lod_distance_threshold
        else:
            return False
