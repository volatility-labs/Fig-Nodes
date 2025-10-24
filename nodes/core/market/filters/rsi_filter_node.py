import numpy as np
import pandas as pd

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.rsi_calculator import calculate_rsi


class RSIFilter(BaseIndicatorFilter):
    """
    Filters assets based on RSI (Relative Strength Index) values.
    """

    default_params = {
        "min_rsi": 30.0,
        "max_rsi": 70.0,
        "timeperiod": 14,
    }

    params_meta = [
        {
            "name": "min_rsi",
            "type": "number",
            "default": 30.0,
            "min": 0.0,
            "max": 100.0,
            "step": 1.0,
        },
        {
            "name": "max_rsi",
            "type": "number",
            "default": 70.0,
            "min": 0.0,
            "max": 100.0,
            "step": 1.0,
        },
        {"name": "timeperiod", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        min_rsi = float(self.params.get("min_rsi", 30.0))
        max_rsi = float(self.params.get("max_rsi", 70.0))
        if min_rsi >= max_rsi:
            raise ValueError("Minimum RSI must be less than maximum RSI")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate RSI and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.RSI,
                timestamp=0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="No data",
            )

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["timeperiod"]:
            return IndicatorResult(
                indicator_type=IndicatorType.RSI,
                timestamp=int(df["timestamp"].iloc[-1]),
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="Insufficient data",
            )

        # Prepare dataframe with lowercase column names for the calculator
        df_rsi = df[["close"]].copy()
        df_rsi.columns = [col.lower() for col in df_rsi.columns]

        # Convert to numeric and drop NaN rows
        for col in df_rsi.columns:
            df_rsi[col] = pd.to_numeric(df_rsi[col], errors="coerce")
        df_rsi = df_rsi.dropna()

        if len(df_rsi) < self.params["timeperiod"]:
            return IndicatorResult(
                indicator_type=IndicatorType.RSI,
                timestamp=int(df["timestamp"].iloc[-1]),
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="Insufficient data",
            )

        # Use the calculator - returns full time series
        result = calculate_rsi(df_rsi, length=int(self.params["timeperiod"]), source="close")
        rsi_series = result.get("rsi", [])

        # Return the last value from the series (or NaN if empty)
        if rsi_series and len(rsi_series) > 0:
            latest_rsi = rsi_series[-1]
            latest_rsi = latest_rsi if latest_rsi is not None else np.nan
        else:
            latest_rsi = np.nan

        values = (
            IndicatorValue(single=latest_rsi)
            if not pd.isna(latest_rsi)
            else IndicatorValue(single=np.nan)
        )

        return IndicatorResult(
            indicator_type=IndicatorType.RSI,
            timestamp=int(df["timestamp"].iloc[-1]),
            values=values,
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if RSI is within the specified range."""
        if indicator_result.error or not hasattr(indicator_result.values, "single"):
            return False

        latest_rsi = indicator_result.values.single
        if pd.isna(latest_rsi):
            return False

        min_rsi = self.params["min_rsi"]
        max_rsi = self.params["max_rsi"]

        return min_rsi <= latest_rsi <= max_rsi
