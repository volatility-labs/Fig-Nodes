import logging
import pandas as pd
from typing import Dict, Any, List
from ta.volatility import AverageTrueRange
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import OHLCVBar, IndicatorResult, IndicatorType

logger = logging.getLogger(__name__)

class LodFilterNode(BaseIndicatorFilterNode):
    """
    Filters assets based on LoD (Low of Day Distance) values.

    LoD Distance is calculated as the distance of current price from the low of the day
    as a percentage of ATR (Average True Range).

    Formula: LoD Distance % = ((current_price - low_of_day) / ATR) * 100

    Only assets with LoD Distance above the minimum threshold will pass the filter.
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
            "label": "Min LoD Distance %",
            "description": "Minimum Low of Day distance as percentage of ATR"
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
                values={"lod_distance_pct": 0.0},
                params=self.params,
                error="No data"
            )

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["atr_window"]:
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=int(df['timestamp'].iloc[-1]),
                values={"lod_distance_pct": 0.0},
                params=self.params,
                error="Insufficient data for ATR calculation"
            )

        # Calculate ATR for the LoD distance calculation
        atr_indicator = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=self.params["atr_window"]
        )
        atr_series = atr_indicator.average_true_range()
        latest_atr = atr_series.iloc[-1] if not atr_series.empty else 0.0

        if pd.isna(latest_atr) or latest_atr <= 0:
            return IndicatorResult(
                indicator_type=IndicatorType.LOD,
                timestamp=int(df['timestamp'].iloc[-1]),
                values={"lod_distance_pct": 0.0},
                params=self.params,
                error="Invalid ATR calculation"
            )

        # Get current (latest) price and low of the day
        latest_bar = df.iloc[-1]
        current_price = latest_bar['close']
        low_of_day = latest_bar['low']

        # Calculate LoD Distance as percentage of ATR
        # LoD Distance % = ((current_price - low_of_day) / ATR) * 100
        lod_distance_pct = ((current_price - low_of_day) / latest_atr) * 100

        # Ensure non-negative distance
        lod_distance_pct = max(0.0, lod_distance_pct)

        return IndicatorResult(
            indicator_type=IndicatorType.LOD,
            timestamp=int(latest_bar['timestamp']),
            values={
                "lod_distance_pct": lod_distance_pct,
                "current_price": current_price,
                "low_of_day": low_of_day,
                "atr": latest_atr
            },
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if LoD Distance is above minimum threshold."""
        if "error" in indicator_result:
            return False

        values = indicator_result.get("values", {})
        if "lod_distance_pct" not in values:
            return False

        lod_distance_pct = values["lod_distance_pct"]
        if pd.isna(lod_distance_pct):
            return False

        # Only pass stocks with LoD distance above the threshold
        return lod_distance_pct >= self.params["min_lod_distance"]
