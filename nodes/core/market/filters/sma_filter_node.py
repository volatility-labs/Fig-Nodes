import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar, AssetSymbol
logger = logging.getLogger(__name__)

class SMAFilterNode(BaseIndicatorFilterNode):
    default_params = {"period": 200, "prior_days": 1}
    params_meta = [
        {"name": "period", "type": "number", "default": 200, "min": 2, "step": 1},
        {"name": "prior_days", "type": "number", "default": 1, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        self.period = int(self.params.get("period", 200))
        self.prior_days = int(self.params.get("prior_days", 1))

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error="No OHLCV data"
            )

        df_data = [{
            'timestamp': pd.to_datetime(bar['timestamp'], unit='ms'),
            'Open': bar['open'],
            'High': bar['high'],
            'Low': bar['low'],
            'Close': bar['close'],
            'Volume': bar['volume']
        } for bar in ohlcv_data]
        df = pd.DataFrame(df_data).set_index('timestamp').sort_index()

        if len(df) < self.period:
            error_msg = f"Insufficient data: {len(df)} bars < {self.period}"
            logger.warning(error_msg)
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error=error_msg
            )

        last_ts = ohlcv_data[-1]['timestamp']
        cutoff_ts = last_ts - (self.prior_days * 86400000)  # prior_days in ms
        cutoff = pd.to_datetime(cutoff_ts, unit='ms')
        previous_df = df[df.index < cutoff]

        current_sma = self.indicators_service.calculate_sma(df, self.period)
        if np.isnan(current_sma):
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={}),
                error="Unable to compute current SMA"
            )

        if len(previous_df) < self.period:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={"current": current_sma, "previous": np.nan}),
                error="Insufficient data for previous SMA"
            )

        previous_sma = self.indicators_service.calculate_sma(previous_df, self.period)
        if np.isnan(previous_sma):
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={"current": current_sma, "previous": np.nan}),
                error="Unable to compute previous SMA"
            )

        values = IndicatorValue(lines={"current": current_sma, "previous": previous_sma})
        return IndicatorResult(
            indicator_type=IndicatorType.SMA,
            timestamp=last_ts,
            values=values,
            params={"period": self.period}
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            return False
        lines = indicator_result.values.lines
        current = lines.get("current", np.nan)
        previous = lines.get("previous", np.nan)
        if np.isnan(current) or np.isnan(previous):
            return False
        return current > previous
