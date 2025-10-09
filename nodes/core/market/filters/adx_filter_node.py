import pandas as pd
from typing import Dict, Any, List
from ta.trend import ADXIndicator
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import OHLCVBar, IndicatorResult, IndicatorType, IndicatorValue


class ADXFilterNode(BaseIndicatorFilterNode):
    """
    Filters assets based on ADX (Average Directional Index) values.
    """

    default_params = {
        "min_adx": 25.0,
        "timeperiod": 14,
        "timeframe": "1d"  # Added for consistency
    }

    params_meta = [
        {"name": "min_adx", "type": "number", "default": 25.0, "min": 0.0, "max": 100.0, "step": 0.1},
        {"name": "timeperiod", "type": "number", "default": 14, "min": 1, "step": 1},
        {"name": "timeframe", "type": "combo", "default": "1d", "options": ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]},
    ]

    def _validate_indicator_params(self):
        if self.params["min_adx"] < 0:
            raise ValueError("Minimum ADX cannot be negative")
        if self.params["timeperiod"] <= 0:
            raise ValueError("Time period must be positive")
        valid_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
        if self.params["timeframe"] not in valid_timeframes:
            raise ValueError("Invalid timeframe")

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate ADX and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.ADX,
                timestamp=0,
                values={"single": 0.0},
                params=self.params,
                error="No data"
            )

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["timeperiod"]:
            return IndicatorResult(
                indicator_type=IndicatorType.ADX,
                timestamp=int(df['timestamp'].iloc[-1]),
                values={"single": 0.0},
                params=self.params,
                error="Insufficient data"
            )

        adx_indicator = ADXIndicator(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=self.params["timeperiod"]
        )
        adx_series = adx_indicator.adx()
        latest_adx = adx_series.iloc[-1] if not adx_series.empty else 0.0

        values: IndicatorValue = {"single": latest_adx} if not pd.isna(latest_adx) else {"single": 0.0}

        return IndicatorResult(
            indicator_type=IndicatorType.ADX,
            timestamp=int(df['timestamp'].iloc[-1]),
            values=values,
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if ADX is above minimum threshold."""
        if "error" in indicator_result or "single" not in indicator_result["values"]:
            return False

        latest_adx = indicator_result["values"]["single"]
        if pd.isna(latest_adx):
            return False

        return latest_adx >= self.params["min_adx"]
