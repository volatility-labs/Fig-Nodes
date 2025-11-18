import logging
from typing import Any

import numpy as np
import pandas as pd

from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter

logger = logging.getLogger(__name__)


class EVWMAFilter(BaseFilter):
    """
    EVWMA (Exponential Volume Weighted Moving Average) Filter

    Filters symbols based on EVWMA alignment and correlation across multiple timeframes.
    Requires warm-up period for accurate calculations.

    Note: Higher timeframes (4hr, 1day, weekly) are less accurate than shorter ones (1min, 5min, 15min).
    """

    CATEGORY = NodeCategory.MARKET

    default_params = {
        "evwma1_timeframe": "1min",
        "evwma2_timeframe": "5min",
        "evwma3_timeframe": "15min",
        "length": 325,
        "use_cum_volume": False,
        "roll_window": 325,
        "corr_smooth_window": 1,
        "correlation_threshold": 0.6,
        "require_alignment": True,
        "require_price_above_evwma": True,
    }

    params_meta = [
        {
            "name": "evwma1_timeframe",
            "type": "combo",
            "default": "1min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 1 Timeframe",
            "description": "First EVWMA timeframe (leave blank to skip). Shorter timeframes (1min, 5min, 15min) are more accurate.",
        },
        {
            "name": "evwma2_timeframe",
            "type": "combo",
            "default": "5min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 2 Timeframe",
            "description": "Second EVWMA timeframe (leave blank to skip). Shorter timeframes (1min, 5min, 15min) are more accurate.",
        },
        {
            "name": "evwma3_timeframe",
            "type": "combo",
            "default": "15min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 3 Timeframe",
            "description": "Third EVWMA timeframe (leave blank to skip). Shorter timeframes (1min, 5min, 15min) are more accurate.",
        },
        {
            "name": "length",
            "type": "number",
            "default": 325,
            "min": 1,
            "step": 1,
            "label": "EVWMA Length",
            "description": "Period for EVWMA calculation",
        },
        {
            "name": "use_cum_volume",
            "type": "boolean",
            "default": False,
            "label": "Use Cumulative Volume",
            "description": "Use cumulative volume instead of rolling window volume",
        },
        {
            "name": "roll_window",
            "type": "number",
            "default": 325,
            "min": 1,
            "step": 1,
            "label": "Rolling Window",
            "description": "Window size for rolling correlation calculation",
        },
        {
            "name": "corr_smooth_window",
            "type": "number",
            "default": 1,
            "min": 1,
            "step": 1,
            "label": "Correlation Smoothing Window",
            "description": "Window size for smoothing correlation values",
        },
        {
            "name": "correlation_threshold",
            "type": "number",
            "default": 0.6,
            "min": 0.0,
            "max": 1.0,
            "step": 0.01,
            "label": "Correlation Threshold",
            "description": "Minimum correlation between EVWMAs to pass filter",
        },
        {
            "name": "require_alignment",
            "type": "boolean",
            "default": True,
            "label": "Require Alignment",
            "description": "Require EVWMAs to be in descending order (shorter > longer timeframe)",
        },
        {
            "name": "require_price_above_evwma",
            "type": "boolean",
            "default": True,
            "label": "Require Price Above EVWMA",
            "description": "Require current price to be above all EVWMAs",
        },
    ]

    def __init__(
        self,
        id: int,
        params: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ):
        super().__init__(id, params, graph_context)
        self._validate_params()

    def _validate_params(self):
        """Validate filter parameters."""
        length = self.params.get("length", 325)
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")

        roll_window = self.params.get("roll_window", 325)
        if not isinstance(roll_window, (int, float)) or roll_window <= 0:
            raise ValueError("roll_window must be a positive number")

        corr_smooth_window = self.params.get("corr_smooth_window", 1)
        if not isinstance(corr_smooth_window, (int, float)) or corr_smooth_window <= 0:
            raise ValueError("corr_smooth_window must be a positive number")

        correlation_threshold = self.params.get("correlation_threshold", 0.6)
        if not isinstance(correlation_threshold, (int, float)) or correlation_threshold < 0 or correlation_threshold > 1:
            raise ValueError("correlation_threshold must be between 0 and 1")

    def _timeframe_to_multiplier_timespan(self, timeframe: str) -> tuple[int, str]:
        """Convert timeframe string to multiplier and timespan for Polygon API."""
        timeframe_map = {
            "1min": (1, "minute"),
            "5min": (5, "minute"),
            "15min": (15, "minute"),
            "30min": (30, "minute"),
            "1hr": (1, "hour"),
            "4hr": (4, "hour"),
            "1day": (1, "day"),
            "weekly": (1, "week"),
        }
        return timeframe_map.get(timeframe, (1, "minute"))

    def _calculate_evwma(
        self, df: pd.DataFrame, length: int, use_cum_volume: bool, roll_window: int
    ) -> pd.Series:
        """Calculate EVWMA (Exponential Volume Weighted Moving Average)."""
        if df.empty or len(df) < length:
            return pd.Series(dtype=float)

        # Calculate typical price (HLC/3)
        typical_price = (df["high"] + df["low"] + df["close"]) / 3

        # Calculate volume-weighted price
        vwp = typical_price * df["volume"]

        if use_cum_volume:
            # Use cumulative volume
            cum_volume = df["volume"].cumsum()
            cum_vwp = vwp.cumsum()
            evwma = cum_vwp / cum_volume
        else:
            # Use rolling window volume
            roll_vwp = vwp.rolling(window=roll_window, min_periods=1).sum()
            roll_volume = df["volume"].rolling(window=roll_window, min_periods=1).sum()
            evwma = roll_vwp / roll_volume

        # Apply exponential smoothing with alpha = 2 / (length + 1)
        alpha = 2.0 / (length + 1)
        evwma_smoothed = evwma.ewm(alpha=alpha, adjust=False).mean()

        return evwma_smoothed

    def _rolling_corr(self, x: pd.Series, y: pd.Series, window: int) -> pd.Series:
        """Calculate rolling correlation between two series."""
        if len(x) < window or len(y) < window:
            return pd.Series(dtype=float)

        return x.rolling(window=window, min_periods=1).corr(y)

    async def _filter_condition_async(
        self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]
    ) -> bool:
        """Async filter condition for EVWMA filter."""
        try:
            # Get parameters
            evwma1_tf = self.params.get("evwma1_timeframe", "1min")
            evwma2_tf = self.params.get("evwma2_timeframe", "5min")
            evwma3_tf = self.params.get("evwma3_timeframe", "15min")
            length = int(self.params.get("length", 325))
            use_cum_volume = self.params.get("use_cum_volume", False)
            roll_window = int(self.params.get("roll_window", 325))
            corr_smooth_window = int(self.params.get("corr_smooth_window", 1))
            threshold = float(self.params.get("correlation_threshold", 0.6))
            require_alignment = self.params.get("require_alignment", True)
            require_price_above_evwma = self.params.get("require_price_above_evwma", True)

            # Get selected timeframes (non-empty)
            selected_timeframes = [tf for tf in [evwma1_tf, evwma2_tf, evwma3_tf] if tf]

            if not selected_timeframes:
                logger.warning("No EVWMA timeframes selected")
                return False

            # Get current price from 1min data (most recent bar)
            if not ohlcv_data:
                return False
            current_price = ohlcv_data[-1]["close"]

            # Fetch data for each timeframe and calculate EVWMA
            from core.api_key_vault import APIKeyVault
            from services.polygon_service import fetch_bars

            vault = APIKeyVault()
            api_key = vault.get("POLYGON_API_KEY")
            if not api_key:
                logger.warning("POLYGON_API_KEY not found in vault")
                return False

            evwma_series = {}
            evwma_dataframes = {}

            for i, timeframe in enumerate(selected_timeframes):
                multiplier, timespan = self._timeframe_to_multiplier_timespan(timeframe)

                # Calculate lookback period based on length and timeframe
                # For 1min: need length bars
                # For other timeframes: need more bars to cover the same time period
                if timeframe == "1min":
                    lookback_days = max(1, int(length / (390 * 60))) + 1  # 390 minutes per trading day
                elif timeframe.endswith("min"):
                    mins = int(timeframe.replace("min", ""))
                    lookback_days = max(1, int(length * mins / (390 * 60))) + 1
                elif timeframe == "1hr":
                    lookback_days = max(1, int(length / 390)) + 1
                elif timeframe == "4hr":
                    lookback_days = max(1, int(length * 4 / 390)) + 1
                elif timeframe == "1day":
                    lookback_days = max(1, length) + 1
                elif timeframe == "weekly":
                    lookback_days = max(7, length * 7) + 1
                else:
                    lookback_days = 30

                fetch_params = {
                    "multiplier": multiplier,
                    "timespan": timespan,
                    "lookback_period": f"{lookback_days} days",
                    "adjusted": True,
                    "sort": "asc",
                    "limit": 50000,
                }

                bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)

                if not bars or len(bars) < length:
                    logger.warning(f"Insufficient data for {timeframe} EVWMA: {len(bars) if bars else 0} bars")
                    return False

                # Convert to DataFrame
                df = pd.DataFrame(bars)
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)

                # Calculate EVWMA
                evwma = self._calculate_evwma(df, length, use_cum_volume, roll_window)

                if evwma.empty or len(evwma) < length:
                    logger.warning(f"Insufficient EVWMA data for {timeframe}")
                    return False

                evwma_name = f"evwma{i+1}"
                evwma_series[evwma_name] = evwma
                evwma_dataframes[evwma_name] = df

            # Check price above EVWMA if required
            if require_price_above_evwma:
                for evwma_name, evwma_series_data in evwma_series.items():
                    latest_evwma = evwma_series_data.iloc[-1]
                    if pd.isna(latest_evwma):
                        return False

                    # For non-1min timeframes, we need to compare with the resampled price
                    # For 1min, compare directly with current price
                    if evwma_name == "evwma1" and selected_timeframes[0] == "1min":
                        if current_price <= latest_evwma:
                            return False
                    else:
                        # For other timeframes, get the latest close from the resampled dataframe
                        df_tf = evwma_dataframes[evwma_name]
                        latest_close_tf = df_tf["close"].iloc[-1]
                        if latest_close_tf <= latest_evwma:
                            return False

            # If only one EVWMA selected, check if we have enough data
            if len(evwma_series) == 1:
                ev1 = list(evwma_series.values())[0]
                return len(ev1) >= length

            # Align all EVWMAs to the shortest timeframe (most granular)
            # Find the most granular timeframe
            base_series = None
            base_name = None
            for name, series in evwma_series.items():
                if base_series is None or len(series) > len(base_series):
                    base_series = series
                    base_name = name

            # Align all series to base index
            df_evw = pd.DataFrame(
                {name: series.reindex(base_series.index, method="ffill") for name, series in evwma_series.items()}
            ).dropna()

            if df_evw.empty:
                return False

            # Check alignment if required and we have multiple EVWMAs
            if require_alignment and len(evwma_series) >= 2:
                latest = df_evw.iloc[-1]
                values = latest.values
                # Check that values are in descending order (shorter timeframe > longer timeframe)
                for i in range(len(values) - 1):
                    if values[i] <= values[i + 1]:
                        return False

            # Calculate correlations if we have at least 2 EVWMAs
            if len(evwma_series) >= 2:
                corr_series_list = []
                evwma_names = list(df_evw.columns)

                # Calculate correlation between all pairs
                for i in range(len(evwma_names)):
                    for j in range(i + 1, len(evwma_names)):
                        corr = self._rolling_corr(df_evw[evwma_names[i]], df_evw[evwma_names[j]], roll_window)
                        if not corr.empty:
                            corr_series_list.append(corr)

                if not corr_series_list:
                    return False

                # Combine all correlations
                df_corr = pd.DataFrame({f"corr_{i}": corr for i, corr in enumerate(corr_series_list)}).dropna()

                if df_corr.empty:
                    return False

                df_corr["avg_corr"] = df_corr.mean(axis=1)
                df_corr["avg_corr_smooth"] = df_corr["avg_corr"].rolling(
                    corr_smooth_window, min_periods=1
                ).mean()

                final_corr = df_corr["avg_corr"].iloc[-1]
                if pd.isna(final_corr) or final_corr < threshold:
                    return False

            return True

        except Exception as e:
            logger.warning(f"EVWMA filter error for {symbol}: {e}")
            return False

