import logging
from typing import Any

import pandas as pd

from core.types_registry import (
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    OHLCVBar,
    get_type,
)
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter

logger = logging.getLogger(__name__)


class AtrXFilter(BaseIndicatorFilter):
    """
    Filters OHLCV bundle based on ATRX indicator thresholds.
    """

    outputs = {
        "filtered_ohlcv_bundle": get_type("OHLCVBundle")  # Inherit or specify if needed
    }
    default_params = {
        "length": 14,
        "smoothing": "RMA",
        "price": "Close",
        "ma_length": 50,
        "upper_threshold": 6.0,
        "lower_threshold": -4.0,
        "filter_condition": "outside",  # "outside" or "inside"
    }
    params_meta = [
        {"name": "length", "type": "integer", "default": 14},
        {"name": "smoothing", "type": "combo", "default": "RMA", "options": ["RMA", "EMA", "SMA"]},
        {"name": "price", "type": "string", "default": "Close"},
        {"name": "ma_length", "type": "integer", "default": 50},
        {"name": "upper_threshold", "type": "float", "default": 6.0},
        {"name": "lower_threshold", "type": "float", "default": -4.0},
        {
            "name": "filter_condition",
            "type": "combo",
            "default": "outside",
            "options": ["outside", "inside"],
        },
    ]

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="No data",
            )
        df_data = [
            {
                "timestamp": pd.to_datetime(bar["timestamp"], unit="ms"),
                "Open": bar["open"],
                "High": bar["high"],
                "Low": bar["low"],
                "Close": bar["close"],
                "Volume": bar["volume"],
            }
            for bar in ohlcv_data
        ]
        df = pd.DataFrame(df_data).set_index("timestamp")

        # Check for minimum data requirements
        min_required = max(self.params.get("length", 14), self.params.get("ma_length", 50))
        if len(df) < min_required:
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="Insufficient data",
            )

        atrx_value = self.indicators_service.calculate_atrx(
            df,
            length=self.params.get("length", 14),
            ma_length=self.params.get("ma_length", 50),
            smoothing=self.params.get("smoothing", "RMA"),
            price=self.params.get("price", "Close"),
        )

        # Handle NaN results (e.g., zero volatility cases)
        if pd.isna(atrx_value):
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="ATRX calculation resulted in NaN",
            )

        return IndicatorResult(
            indicator_type=IndicatorType.ATRX,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(single=atrx_value),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            return False
        value = indicator_result.values.single
        upper = self.params.get("upper_threshold", 6.0)
        lower = self.params.get("lower_threshold", -4.0)
        condition = self.params.get("filter_condition", "outside")
        if condition == "outside":
            return value >= upper or value <= lower
        else:  # "inside"
            return lower <= value <= upper

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        # Delegate to BaseIndicatorFilterNode to leverage per-symbol error handling and progress reporting
        return await super()._execute_impl(inputs)
