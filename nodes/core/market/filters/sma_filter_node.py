import logging

import numpy as np

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.sma_calculator import calculate_sma

logger = logging.getLogger(__name__)


class SMAFilter(BaseIndicatorFilter):
    default_params = {"period": 200, "prior_days": 1}
    params_meta = [
        {"name": "period", "type": "number", "default": 200, "min": 2, "step": 1},
        {"name": "prior_days", "type": "number", "default": 1, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        period_value = self.params.get("period", 200)
        prior_days_value = self.params.get("prior_days", 1)

        if not isinstance(period_value, int):
            raise ValueError("period must be an integer")
        if not isinstance(prior_days_value, int):
            raise ValueError("prior_days must be an integer")

        self.period = period_value
        self.prior_days = prior_days_value

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error="No OHLCV data",
            )

        data_length: int = len(ohlcv_data)
        if data_length < self.period:
            error_msg = f"Insufficient data: {data_length} bars < {self.period}"
            logger.warning(error_msg)
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error=error_msg,
            )

        last_ts: int = ohlcv_data[-1]["timestamp"]
        cutoff_ts: int = last_ts - (self.prior_days * 86400000)  # prior_days in ms

        # Filter previous data manually by timestamp
        previous_data: list[OHLCVBar] = [bar for bar in ohlcv_data if bar["timestamp"] < cutoff_ts]

        if len(previous_data) < self.period:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={"current": np.nan, "previous": np.nan}),
                error="Insufficient data for previous SMA",
            )

        # Calculate current SMA using the calculator
        current_close_prices: list[float] = [bar["close"] for bar in ohlcv_data]
        current_sma_result: dict[str, list[float | None]] = calculate_sma(
            current_close_prices, period=self.period
        )
        current_sma_values: list[float | None] = current_sma_result.get("sma", [])
        current_sma_raw: float | None = current_sma_values[-1] if current_sma_values else None
        current_sma: float = current_sma_raw if current_sma_raw is not None else np.nan

        if np.isnan(current_sma):
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={}),
                error="Unable to compute current SMA",
            )

        # Calculate previous SMA using the calculator
        previous_close_prices: list[float] = [bar["close"] for bar in previous_data]
        previous_sma_result: dict[str, list[float | None]] = calculate_sma(
            previous_close_prices, period=self.period
        )
        previous_sma_values: list[float | None] = previous_sma_result.get("sma", [])
        previous_sma_raw: float | None = previous_sma_values[-1] if previous_sma_values else None
        previous_sma: float = previous_sma_raw if previous_sma_raw is not None else np.nan

        if np.isnan(previous_sma):
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={"current": current_sma, "previous": np.nan}),
                error="Unable to compute previous SMA",
            )

        values = IndicatorValue(lines={"current": current_sma, "previous": previous_sma})
        return IndicatorResult(
            indicator_type=IndicatorType.SMA,
            timestamp=last_ts,
            values=values,
            params={"period": self.period},
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            return False
        lines: dict[str, float] = indicator_result.values.lines
        current: float = lines.get("current", np.nan)
        previous: float = lines.get("previous", np.nan)
        if np.isnan(current) or np.isnan(previous):
            return False
        return current > previous
