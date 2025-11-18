from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.sma_calculator import calculate_sma


class SMACrossoverFilter(BaseIndicatorFilter):
    """
    Filters assets where short-term SMA crosses above long-term SMA (bullish crossover).
    """

    default_params = {
        "short_period": 20,
        "long_period": 50,
    }

    params_meta = [
        {"name": "short_period", "type": "number", "default": 20, "min": 1, "step": 1},
        {"name": "long_period", "type": "number", "default": 50, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        short_period_value = self.params.get("short_period", 20)
        long_period_value = self.params.get("long_period", 50)

        if not isinstance(short_period_value, int):
            raise ValueError("short_period must be an integer")
        if not isinstance(long_period_value, int):
            raise ValueError("long_period must be an integer")

        short_period: int = short_period_value
        long_period: int = long_period_value

        if short_period >= long_period:
            raise ValueError("Short period must be less than long period")

        self.short_period = short_period
        self.long_period = long_period

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate SMA crossover signal and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=0,
                values=IndicatorValue(single=False),
                params=self.params,
                error="No data",
            )

        data_length: int = len(ohlcv_data)
        if data_length < self.long_period:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=False),
                params=self.params,
                error="Insufficient data",
            )

        # Calculate SMAs using the calculator
        close_prices: list[float] = [bar["close"] for bar in ohlcv_data]

        short_sma_result: dict[str, list[float | None]] = calculate_sma(
            close_prices, period=self.short_period
        )
        long_sma_result: dict[str, list[float | None]] = calculate_sma(
            close_prices, period=self.long_period
        )

        short_sma_values: list[float | None] = short_sma_result.get("sma", [])
        long_sma_values: list[float | None] = long_sma_result.get("sma", [])

        # Check for crossover by comparing last 2 values of each SMA
        # Bullish crossover: short SMA crosses above long SMA
        latest_crossover: bool = False

        if len(short_sma_values) >= 2 and len(long_sma_values) >= 2:
            prev_short: float | None = short_sma_values[-2]
            curr_short: float | None = short_sma_values[-1]
            prev_long: float | None = long_sma_values[-2]
            curr_long: float | None = long_sma_values[-1]

            # Only proceed if all values are valid (not None)
            if (
                prev_short is not None
                and curr_short is not None
                and prev_long is not None
                and curr_long is not None
            ):
                # Crossover occurs when previous period: short <= long, current period: short > long
                if prev_short <= prev_long and curr_short > curr_long:
                    latest_crossover = True

        return IndicatorResult(
            indicator_type=IndicatorType.SMA,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(single=latest_crossover),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if there's a recent bullish crossover."""
        if indicator_result.error or not hasattr(indicator_result.values, "single"):
            return False

        latest_crossover = indicator_result.values.single
        return bool(latest_crossover)
