import logging
from typing import Any

from core.types_registry import (
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    OHLCVBar,
    get_type,
)
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.atrx_calculator import calculate_atrx

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
        {"name": "price", "type": "text", "default": "Close"},
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

        # Check minimum data requirements first
        length_param = self.params.get("length", 14)
        ma_length_param = self.params.get("ma_length", 50)

        length_value = int(length_param) if isinstance(length_param, int | float) else 14
        ma_length_value = int(ma_length_param) if isinstance(ma_length_param, int | float) else 50

        min_required = max(length_value, ma_length_value)
        if len(ohlcv_data) < min_required:
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="Insufficient data",
            )

        # Get smoothing parameter
        smoothing = self.params.get("smoothing", "RMA")
        if smoothing not in ["RMA", "SMA", "EMA"]:
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error=f"Invalid smoothing method '{smoothing}'. Must be 'RMA', 'SMA', or 'EMA'.",
            )

        # Extract lists directly from OHLCV data
        high_prices = [bar["high"] for bar in ohlcv_data]
        low_prices = [bar["low"] for bar in ohlcv_data]
        close_prices = [bar["close"] for bar in ohlcv_data]

        # Map price column name
        price_col: str = str(self.params.get("price", "Close"))
        price_map = {
            "Open": [bar["open"] for bar in ohlcv_data],
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
        }

        if price_col not in price_map:
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error=f"Invalid price column '{price_col}'",
            )

        source_prices = price_map[price_col]

        # Call calculator with lists and smoothing parameter
        smoothing_str = str(smoothing) if isinstance(smoothing, str) else "RMA"
        atrx_result = calculate_atrx(
            highs=high_prices,
            lows=low_prices,
            closes=close_prices,
            prices=source_prices,
            length=length_value,
            ma_length=ma_length_value,
            smoothing=smoothing_str,
        )
        atrx_values = atrx_result.get("atrx", [])

        if not atrx_values:
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="ATRX calculation returned empty results",
            )

        # Get last value
        atrx_value = atrx_values[-1]

        # Handle None
        if atrx_value is None:
            return IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="ATRX calculation resulted in None",
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
        value = float(indicator_result.values.single)

        upper_threshold = self.params.get("upper_threshold", 6.0)
        if not isinstance(upper_threshold, int | float):
            upper_threshold = 6.0
        upper = float(upper_threshold)

        lower_threshold = self.params.get("lower_threshold", -4.0)
        if not isinstance(lower_threshold, int | float):
            lower_threshold = -4.0
        lower = float(lower_threshold)

        filter_condition = self.params.get("filter_condition", "outside")
        if not isinstance(filter_condition, str):
            filter_condition = "outside"
        condition = str(filter_condition)

        if condition == "outside":
            return value >= upper or value <= lower
        else:  # "inside"
            return lower <= value <= upper

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        # Delegate to BaseIndicatorFilterNode to leverage per-symbol error handling and progress reporting
        return await super()._execute_impl(inputs)
