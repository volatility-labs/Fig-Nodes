
import pandas as pd
import numpy as np
from typing import List
from ta.trend import EMAIndicator
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from core.types_registry import IndicatorResult, IndicatorType, OHLCVBar, IndicatorValue

class EmaRangeFilter(BaseIndicatorFilter):
    """
    Filters assets where EMA(10, high-low range) > close / 100
    """

    default_params = {
        "timeperiod": 10,
        "divisor": 100.0,
    }

    params_meta = [
        {"name": "timeperiod", "type": "number", "default": 10, "min": 1, "step": 1},
        {"name": "divisor", "type": "number", "default": 100.0, "min": 1.0, "step": 1.0},
    ]

    def _validate_indicator_params(self):
        if self.params["timeperiod"] < 1:
            raise ValueError("Time period must be at least 1")
        if self.params["divisor"] <= 0:
            raise ValueError("Divisor must be positive")

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA_RANGE,
                values=IndicatorValue(lines={"ema_range": np.nan, "close": np.nan}),
                params=self.params,
                error="No data"
            )

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["timeperiod"]:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA_RANGE,
                timestamp=int(df['timestamp'].iloc[-1]) if 'timestamp' in df else 0,
                values=IndicatorValue(lines={"ema_range": np.nan, "close": df['close'].iloc[-1]}),
                params=self.params,
                error="Insufficient data"
            )

        price_range = df['high'] - df['low']
        ema_indicator = EMAIndicator(price_range, window=self.params["timeperiod"])
        ema_series = ema_indicator.ema_indicator()
        latest_ema = ema_series.iloc[-1] if not ema_series.empty else np.nan
        latest_close = df['close'].iloc[-1]

        values = IndicatorValue(lines={
            "ema_range": latest_ema if not pd.isna(latest_ema) else np.nan,
            "close": latest_close
        })

        return IndicatorResult(
            indicator_type=IndicatorType.EMA_RANGE,
            timestamp=int(df['timestamp'].iloc[-1]) if 'timestamp' in df else 0,
            values=values,
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error or not hasattr(indicator_result.values, 'lines'):
            return False

        values = indicator_result.values.lines
        if "ema_range" not in values or "close" not in values:
            return False

        ema_range = values["ema_range"]
        close = values["close"]
        if pd.isna(ema_range) or pd.isna(close):
            return False

        return ema_range > close / self.params["divisor"]
