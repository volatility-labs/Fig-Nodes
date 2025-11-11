import logging
from datetime import datetime, timedelta

import numpy as np
import pytz

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.sma_calculator import calculate_sma

logger = logging.getLogger(__name__)


class MovingAverageFilter(BaseIndicatorFilter):
    default_params = {"period": 200, "prior_days": 1, "ma_type": "SMA"}
    params_meta = [
        {"name": "period", "type": "number", "default": 200, "min": 2, "step": 1},
        {"name": "prior_days", "type": "number", "default": 1, "min": 0, "step": 1},
        {"name": "ma_type", "type": "combo", "default": "SMA", "options": ["SMA", "EMA"]},
    ]

    def _validate_indicator_params(self):
        period_value = self.params.get("period", 200)
        prior_days_value = self.params.get("prior_days", 1)
        ma_type_value = self.params.get("ma_type", "SMA")

        if not isinstance(period_value, int):
            raise ValueError("period must be an integer")
        if not isinstance(prior_days_value, int):
            raise ValueError("prior_days must be an integer")
        if ma_type_value not in ["SMA", "EMA"]:
            raise ValueError("ma_type must be 'SMA' or 'EMA'")

        self.period = period_value
        self.prior_days = prior_days_value
        self.ma_type = ma_type_value

    def _get_indicator_type(self) -> IndicatorType:
        return IndicatorType.SMA if self.ma_type == "SMA" else IndicatorType.EMA

    def _calculate_ma(
        self, close_prices: list[float], period: int
    ) -> dict[str, list[float | None]]:
        if self.ma_type == "SMA":
            return calculate_sma(close_prices, period=period)
        else:
            return calculate_ema(close_prices, period=period)

    def _get_ma_key(self) -> str:
        return "sma" if self.ma_type == "SMA" else "ema"

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        indicator_type = self._get_indicator_type()
        ma_key = self._get_ma_key()

        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error="No OHLCV data",
            )

        data_length: int = len(ohlcv_data)
        if data_length < self.period:
            error_msg = f"Insufficient data: {data_length} bars < {self.period}"
            logger.warning(error_msg)
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error=error_msg,
            )

        last_ts: int = ohlcv_data[-1]["timestamp"]

        # Calculate current MA using the calculator
        current_close_prices: list[float] = [bar["close"] for bar in ohlcv_data]
        current_ma_result: dict[str, list[float | None]] = self._calculate_ma(
            current_close_prices, period=self.period
        )
        current_ma_values: list[float | None] = current_ma_result.get(ma_key, [])
        current_ma_raw: float | None = current_ma_values[-1] if current_ma_values else None
        current_ma: float = current_ma_raw if current_ma_raw is not None else np.nan

        if np.isnan(current_ma):
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=IndicatorValue(lines={}),
                error=f"Unable to compute current {self.ma_type}",
            )

        # Handle prior_days = 0 case (no slope requirement)
        if self.prior_days == 0:
            current_price = ohlcv_data[-1]["close"]
            values = IndicatorValue(
                lines={"current": current_ma, "previous": np.nan, "price": current_price}
            )
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=values,
                params={"period": self.period, "ma_type": self.ma_type},
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
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=IndicatorValue(
                    lines={"current": np.nan, "previous": np.nan, "price": current_price}
                ),
                error=f"Insufficient data for previous {self.ma_type}",
            )

        # Calculate previous MA using the calculator
        previous_close_prices: list[float] = [bar["close"] for bar in previous_data]
        previous_ma_result: dict[str, list[float | None]] = self._calculate_ma(
            previous_close_prices, period=self.period
        )
        previous_ma_values: list[float | None] = previous_ma_result.get(ma_key, [])
        previous_ma_raw: float | None = previous_ma_values[-1] if previous_ma_values else None
        previous_ma: float = previous_ma_raw if previous_ma_raw is not None else np.nan

        if np.isnan(previous_ma):
            current_price = ohlcv_data[-1]["close"]
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=IndicatorValue(
                    lines={"current": current_ma, "previous": np.nan, "price": current_price}
                ),
                error=f"Unable to compute previous {self.ma_type}",
            )

        current_price = ohlcv_data[-1]["close"]
        values = IndicatorValue(
            lines={"current": current_ma, "previous": previous_ma, "price": current_price}
        )
        return IndicatorResult(
            indicator_type=indicator_type,
            timestamp=last_ts,
            values=values,
            params={"period": self.period, "ma_type": self.ma_type},
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            return False
        lines: dict[str, float] = indicator_result.values.lines
        current_ma: float = lines.get("current", np.nan)
        current_price: float = lines.get("price", np.nan)

        # Always require price > current MA
        if np.isnan(current_price) or np.isnan(current_ma):
            return False
        if not (current_price > current_ma):
            return False

        # If prior_days is 0, no slope requirement beyond price > MA
        if self.prior_days == 0:
            return True

        # For prior_days > 0, also check that current MA > previous MA (upward slope)
        previous: float = lines.get("previous", np.nan)
        if np.isnan(previous):
            return False
        return current_ma > previous
