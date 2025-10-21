import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar, AssetSymbol
logger = logging.getLogger(__name__)

class SMAFilter(BaseIndicatorFilter):
    """
    Filters assets based on Simple Moving Average (SMA) slope and price position.

    This filter ALWAYS requires current price to be above the SMA, and optionally
    checks if the SMA is trending upward by comparing the current SMA with the SMA
    from N days ago.

    Examples:
    - prior_days = 0: Price above SMA only (no slope requirement)
    - prior_days = 1: Price above SMA AND current SMA > SMA from 1 day ago
    - prior_days = 5: Price above SMA AND current SMA > SMA from 5 days ago

    Parameters:
    - period: SMA calculation period (default: 200)
    - prior_days: Days to look back for slope comparison (default: 1, 0 = price above SMA only)
    """
    default_params = {"period": 200, "prior_days": 1}
    params_meta = [
        {"name": "period", "type": "number", "default": 200, "min": 2, "step": 1},
        {"name": "prior_days", "type": "number", "default": 1, "min": 0, "step": 1, "description": "Days to look back for slope comparison (0 = price above SMA only)"},
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
        current_price = ohlcv_data[-1]['close']

        current_sma = self.indicators_service.calculate_sma(df, self.period)
        if np.isnan(current_sma):
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=last_ts,
                values=IndicatorValue(lines={}),
                error="Unable to compute current SMA"
            )

        # Always include current price for price above SMA check
        if self.prior_days == 0:
            values = IndicatorValue(lines={
                "current": current_sma, 
                "previous": current_sma,  # Set previous = current to pass slope check
                "current_price": current_price
            })
        else:
            cutoff_ts = last_ts - (self.prior_days * 86400000)  # prior_days in ms
            cutoff = pd.to_datetime(cutoff_ts, unit='ms')
            previous_df = df[df.index < cutoff]

            if len(previous_df) < self.period:
                return IndicatorResult(
                    indicator_type=IndicatorType.SMA,
                    timestamp=last_ts,
                    values=IndicatorValue(lines={"current": current_sma, "previous": np.nan, "current_price": current_price}),
                    error="Insufficient data for previous SMA"
                )

            previous_sma = self.indicators_service.calculate_sma(previous_df, self.period)
            if np.isnan(previous_sma):
                return IndicatorResult(
                    indicator_type=IndicatorType.SMA,
                    timestamp=last_ts,
                    values=IndicatorValue(lines={"current": current_sma, "previous": np.nan, "current_price": current_price}),
                    error="Unable to compute previous SMA"
                )

            values = IndicatorValue(lines={"current": current_sma, "previous": previous_sma, "current_price": current_price})

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
        if np.isnan(current):
            return False

        # Always check if price is above SMA
        current_price = lines.get("current_price", np.nan)
        if np.isnan(current_price):
            return False
        
        if current_price <= current:  # Price must be above SMA
            return False

        # If prior_days is 0, only check price above SMA (already done above)
        if self.prior_days == 0:
            return True

        # For prior_days > 0, also check slope (current SMA > previous SMA)
        previous = lines.get("previous", np.nan)
        if np.isnan(previous):
            return False
        return current > previous
