import logging
from datetime import datetime, timedelta

import numpy as np
import pytz

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.ema_calculator import calculate_ema

logger = logging.getLogger(__name__)


class EMAFilter(BaseIndicatorFilter):
    default_params = {"period": 200, "prior_days": 1}
    params_meta = [
        {"name": "period", "type": "number", "default": 200, "min": 2, "step": 1},
        {"name": "prior_days", "type": "number", "default": 1, "min": 0, "step": 1},
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
                indicator_type=IndicatorType.EMA,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error="No OHLCV data",
            )

        data_length: int = len(ohlcv_data)
        if data_length < self.period:
            error_msg = f"Insufficient data: {data_length} bars < {self.period}"
            logger.warning(error_msg)
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error=error_msg,
            )

        last_ts: int = ohlcv_data[-1]["timestamp"]

        # Calculate current EMA using the calculator
        current_close_prices: list[float] = [bar["close"] for bar in ohlcv_data]
        current_ema_result: dict[str, list[float | None]] = calculate_ema(
            current_close_prices, period=self.period
        )
        current_ema_values: list[float | None] = current_ema_result.get("ema", [])
        current_ema_raw: float | None = current_ema_values[-1] if current_ema_values else None
        current_ema: float = current_ema_raw if current_ema_raw is not None else np.nan

        if np.isnan(current_ema):
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={}),
                error="Unable to compute current EMA",
            )

        # Handle prior_days = 0 case (no slope requirement)
        if self.prior_days == 0:
            current_price = ohlcv_data[-1]["close"]
            values = IndicatorValue(lines={"current": current_ema, "previous": np.nan, "price": current_price})
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=last_ts,
                values=values,
                params={"period": self.period},
            )

        # Use calendar-aware date calculation instead of hardcoded milliseconds
        # Convert UTC timestamp to datetime, subtract days, convert back to milliseconds
        last_dt = datetime.fromtimestamp(last_ts / 1000, tz=pytz.UTC)
        cutoff_dt = last_dt - timedelta(days=self.prior_days)
        cutoff_ts: int = int(cutoff_dt.timestamp() * 1000)

        # Filter previous data manually by timestamp
        previous_data: list[OHLCVBar] = [bar for bar in ohlcv_data if bar["timestamp"] < cutoff_ts]

        if len(previous_data) < self.period:
            current_price = ohlcv_data[-1]["close"]
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={"current": np.nan, "previous": np.nan, "price": current_price}),
                error="Insufficient data for previous EMA",
            )

        # Calculate previous EMA using the calculator
        previous_close_prices: list[float] = [bar["close"] for bar in previous_data]
        previous_ema_result: dict[str, list[float | None]] = calculate_ema(
            previous_close_prices, period=self.period
        )
        previous_ema_values: list[float | None] = previous_ema_result.get("ema", [])
        previous_ema_raw: float | None = previous_ema_values[-1] if previous_ema_values else None
        previous_ema: float = previous_ema_raw if previous_ema_raw is not None else np.nan

        if np.isnan(previous_ema):
            current_price = ohlcv_data[-1]["close"]
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={"current": current_ema, "previous": np.nan, "price": current_price}),
                error="Unable to compute previous EMA",
            )

        current_price = ohlcv_data[-1]["close"]
        values = IndicatorValue(lines={"current": current_ema, "previous": previous_ema, "price": current_price})
        return IndicatorResult(
            indicator_type=IndicatorType.EMA,
            timestamp=last_ts,
            values=values,
            params={"period": self.period},
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            return False

        lines: dict[str, float] = indicator_result.values.lines
        current_ema: float = lines.get("current", np.nan)
        current_price: float = lines.get("price", np.nan)

        # Always require price > current EMA
        if np.isnan(current_price) or np.isnan(current_ema):
            return False
        if not (current_price > current_ema):
            return False

        # If prior_days is 0, no slope requirement beyond price > EMA
        if self.prior_days == 0:
            return True

        # For prior_days > 0, also check that current EMA > previous EMA (upward slope)
        previous: float = lines.get("previous", np.nan)
        if np.isnan(previous):
            return False
        return current_ema > previous
