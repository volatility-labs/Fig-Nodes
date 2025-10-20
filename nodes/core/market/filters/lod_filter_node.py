import logging
import math
from typing import List
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from core.types_registry import OHLCVBar, IndicatorResult, IndicatorType, IndicatorValue

logger = logging.getLogger(__name__)

class LodFilter(BaseIndicatorFilter):
    """
    Filters assets based on LoD (Low of Day Distance) values.

    LoD Distance is calculated as the distance of current price from the low of the day
    as a percentage of ATR (Average True Range).

    Formula: LoD Distance % = ((current_price - low_of_day) / ATR) * 100

    Only assets with LoD Distance above the minimum threshold will pass the filter.

    Parameter guidance:
    - min_lod_distance: Enter a percentage of ATR (not price points).
      For example, 3.16 means the current price is 3.16% of one ATR above the
      day's low. Use numeric values like 3, 5.5, 10, etc. The underlying unit is '% of ATR'.

    Reference:
    https://www.tradingview.com/script/uloAa2EI-Swing-Data-ADR-RVol-PVol-Float-Avg-Vol/
    """

    default_params = {
        "min_lod_distance": 3.16,  # Minimum LoD distance percentage threshold
        "atr_window": 14,          # ATR calculation window
    }

    params_meta = [
        {
            "name": "min_lod_distance",
            "type": "number",
            "default": 3.16,
            "min": 0.0,
            "step": 0.1,
            "precision": 2,
            "label": "Min LoD Distance %",
            "unit": "%",
            "description": "Minimum Low of Day distance as percentage of ATR (e.g., 3.16 = 3.16% of ATR)"
        },
        {
            "name": "atr_window",
            "type": "number",
            "default": 14,
            "min": 1,
            "step": 1,
            "label": "ATR Window",
            "description": "Period for ATR calculation"
        },
    ]

    def _validate_indicator_params(self):
        if self.params["min_lod_distance"] < 0:
            raise ValueError("Minimum LoD distance cannot be negative")
        if self.params["atr_window"] <= 0:
            raise ValueError("ATR window must be positive")

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate LoD Distance and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=0,
                values=IndicatorValue(lines={"lod_distance_pct": 0.0}),
                params=self.params,
                error="No data"
            )
        timestamp_value: int = ohlcv_data[-1]['timestamp']
        
        if len(ohlcv_data) < self.params["atr_window"]:
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=timestamp_value,
                values=IndicatorValue(lines={"lod_distance_pct": 0.0}),
                params=self.params,
                error="Insufficient data for ATR calculation"
            )

        # Calculate ATR for the LoD distance calculation using Wilder's smoothing (RMA)
        true_ranges: List[float] = []
        for i in range(len(ohlcv_data)):
            if i == 0:
                # First bar: true range is just high - low
                true_range: float = ohlcv_data[i]['high'] - ohlcv_data[i]['low']
            else:
                # Subsequent bars: max of (high-low, |high-prev_close|, |low-prev_close|)
                high_low: float = ohlcv_data[i]['high'] - ohlcv_data[i]['low']
                high_close: float = abs(ohlcv_data[i]['high'] - ohlcv_data[i-1]['close'])
                low_close: float = abs(ohlcv_data[i]['low'] - ohlcv_data[i-1]['close'])
                true_range: float = max(high_low, high_close, low_close)
            true_ranges.append(true_range)
        
        # Wilder's smoothing (RMA) - matches TradingView implementation
        alpha = 1.0 / self.params["atr_window"]
        atr_values = [true_ranges[0]]  # First ATR value is just the first true range
        
        for i in range(1, len(true_ranges)):
            atr_value = alpha * true_ranges[i] + (1 - alpha) * atr_values[i-1]
            atr_values.append(atr_value)
        
        latest_atr = atr_values[-1] if atr_values else 0.0

        if latest_atr <= 0:
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=ohlcv_data[-1]['timestamp'],
                values=IndicatorValue(lines={"lod_distance_pct": 0.0}),
                params=self.params,
                error="Invalid ATR calculation"
            )

        # Get current (latest) price and low of the day
        latest_bar = ohlcv_data[-1]
        current_price = latest_bar['close']
        low_of_day = latest_bar['low']

        # Calculate LoD Distance as percentage of ATR
        # LoD Distance % = ((current_price - low_of_day) / ATR) * 100
        lod_distance_pct = ((current_price - low_of_day) / latest_atr) * 100

        # Ensure non-negative distance
        lod_distance_pct = max(0.0, lod_distance_pct)

        return IndicatorResult(
            indicator_type=IndicatorType.LOD,
            timestamp=latest_bar['timestamp'],
            values=IndicatorValue(lines={
                "lod_distance_pct": lod_distance_pct,
                "current_price": current_price,
                "low_of_day": low_of_day,
                "atr": latest_atr
            }),
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if LoD Distance is above minimum threshold."""
        if indicator_result.error:
            return False

        lines = indicator_result.values.lines
        if "lod_distance_pct" not in lines:
            return False
        
        lod_distance_pct = lines["lod_distance_pct"]

        if not math.isfinite(lod_distance_pct):
            return False
        
        return lod_distance_pct >= self.params["min_lod_distance"]
