import logging
from datetime import datetime, timedelta
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
            "description": "First EVWMA timeframe (leave blank to skip). Shorter timeframes (1min, 5min, 15min) are more accurate."
        },
        {
            "name": "evwma2_timeframe",
            "type": "combo",
            "default": "5min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 2 Timeframe",
            "description": "Second EVWMA timeframe (leave blank to skip). Required for correlation calculation."
        },
        {
            "name": "evwma3_timeframe",
            "type": "combo",
            "default": "15min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 3 Timeframe",
            "description": "Third EVWMA timeframe (leave blank to skip). Optional for additional correlation pairs."
        },
        {
            "name": "require_alignment",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Require EVWMA Alignment",
            "description": "Require EVWMA1 > EVWMA2 > EVWMA3 (only applies if multiple EVWMAs are selected)"
        },
        {
            "name": "require_price_above_evwma",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Require Price Above EVWMA",
            "description": "Require current price to be above the EVWMA level (applies to all selected EVWMAs)"
        },
        {
            "name": "length",
            "type": "number",
            "default": 325,
            "min": 1,
            "step": 1,
            "label": "EVWMA Length",
            "description": "Length parameter for EVWMA calculation (default: 325)"
        },
        {
            "name": "use_cum_volume",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Use Cumulative Volume",
            "description": "Whether to use cumulative volume for NBF calculation"
        },
        {
            "name": "roll_window",
            "type": "number",
            "default": 325,
            "min": 1,
            "step": 1,
            "label": "Correlation Window",
            "description": "Rolling window for correlation calculation (default: 325)"
        },
        {
            "name": "corr_smooth_window",
            "type": "number",
            "default": 1,
            "min": 1,
            "step": 1,
            "label": "Correlation Smooth Window",
            "description": "Smoothing window for correlation (default: 1 = no smoothing)"
        },
        {
            "name": "correlation_threshold",
            "type": "number",
            "default": 0.6,
            "min": 0.0,
            "max": 1.0,
            "step": 0.01,
            "label": "Correlation Threshold",
            "description": "Minimum average correlation required to pass filter (0.0-1.0)"
        },
    ]

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate timestamps, keeping first occurrence."""
        if df.empty:
            return df
        return df[~df.index.duplicated(keep='first')]

    def _resample_and_fill(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample DataFrame to target timeframe and fill missing values."""
        df = self._remove_duplicates(df)
        if df.empty:
            return df

        # Convert timeframe to pandas frequency
        tf_map = {
            "1min": "1min",
            "5min": "5min",
            "15min": "15min",
            "30min": "30min",
            "1hr": "1H",
            "4hr": "4H",
            "1day": "1D",
            "weekly": "W",
        }
        freq = tf_map.get(timeframe, "1min")

        last_ts = df.index[-1]
        rng = pd.date_range(start=df.index[0], end=last_ts, freq=freq)

        df_res = df.resample(freq, closed='left', label='left').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })

        # Handle partial bar at end
        if last_ts > rng[-1] if len(rng) > 0 else True:
            sub = df[df.index > (rng[-1] if len(rng) > 0 else df.index[0])]
            if not sub.empty:
                partial_agg = pd.DataFrame({
                    'open': [sub['open'].iloc[0]],
                    'high': [sub['high'].max()],
                    'low': [sub['low'].min()],
                    'close': [sub['close'].iloc[-1]],
                    'volume': [sub['volume'].sum()]
                }, index=[last_ts])
                df_res = pd.concat([df_res, partial_agg])

        df_res = df_res.ffill()
        df_res = self._remove_duplicates(df_res)
        return df_res

    def _calculate_nbfs(self, volume: pd.Series, length: int, use_cum: bool) -> np.ndarray:
        """Calculate NBF (Normalized Bar Frequency Sum) for EVWMA."""
        if volume.empty:
            return np.array([])
        
        if use_cum:
            return volume.cumsum().values
        
        roll = volume.rolling(window=length, min_periods=length).sum()
        fv = roll.first_valid_index()
        if fv:
            roll.loc[:fv] = roll.loc[fv]
        return roll.values

    def _calc_evwma(self, price: np.ndarray, volume: np.ndarray, nbfs: np.ndarray) -> np.ndarray:
        """Calculate EVWMA (Exponential Volume Weighted Moving Average)."""
        if price.size == 0:
            return np.array([])
        
        ev = np.zeros_like(price)
        ev[0] = price[0]
        
        for i in range(1, len(price)):
            if nbfs[i] != 0:
                ev[i] = ev[i-1] * ((nbfs[i] - volume[i]) / nbfs[i]) + price[i] * (volume[i] / nbfs[i])
            else:
                ev[i] = ev[i-1]
        
        return ev

    def _rolling_corr(self, sA: pd.Series, sB: pd.Series, window: int) -> pd.Series:
        """Calculate rolling correlation between two series."""
        sA = self._remove_duplicates(sA.to_frame()).iloc[:, 0]
        sB = self._remove_duplicates(sB.to_frame()).iloc[:, 0]
        
        if sA.empty or sB.empty:
            return pd.Series(dtype=float)
        
        b_aligned = sB.reindex(sA.index, method='ffill')
        dfC = pd.DataFrame({"A": sA, "B": b_aligned})
        return dfC["A"].rolling(window).corr(dfC["B"])

    def _ohlcv_bars_to_dataframe(self, ohlcv_data: list[OHLCVBar]) -> pd.DataFrame:
        """Convert list of OHLCVBar dicts to pandas DataFrame."""
        if not ohlcv_data:
            return pd.DataFrame()
        
        data = []
        for bar in ohlcv_data:
            data.append({
                'timestamp': pd.to_datetime(bar['timestamp'], unit='ms'),
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar['volume']
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df

    async def _filter_condition_async(
        self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]
    ) -> bool:
        """Check if symbol passes EVWMA filter conditions."""
        try:
            if not ohlcv_data or len(ohlcv_data) < 500:  # Need sufficient data for warm-up
                return False

            # Get parameters
            evwma1_tf = self.params.get("evwma1_timeframe", "1min") or ""
            evwma2_tf = self.params.get("evwma2_timeframe", "5min") or ""
            evwma3_tf = self.params.get("evwma3_timeframe", "15min") or ""
            length = int(self.params.get("length", 325))
            use_cum_volume = self.params.get("use_cum_volume", False)
            roll_window = int(self.params.get("roll_window", 325))
            corr_smooth_window = int(self.params.get("corr_smooth_window", 1))
            threshold = float(self.params.get("correlation_threshold", 0.6))
            require_alignment = self.params.get("require_alignment", True)
            require_price_above = self.params.get("require_price_above_evwma", True)

            # Collect selected timeframes (non-empty)
            selected_timeframes = [tf for tf in [evwma1_tf, evwma2_tf, evwma3_tf] if tf]
            
            if not selected_timeframes:
                logger.warning(f"EVWMA filter: No timeframes selected for {symbol}")
                return False

            # Convert OHLCV bars to DataFrame
            df_1m = self._ohlcv_bars_to_dataframe(ohlcv_data)
            if df_1m.empty:
                return False

            df_1m = self._remove_duplicates(df_1m)
            if df_1m.empty:
                return False

            # Get current price (latest close)
            current_price = df_1m['close'].iloc[-1]

            # Resample to each selected timeframe and calculate EVWMAs
            evwma_series = {}
            evwma_dataframes = {}  # Store dataframes for price comparison
            for i, tf in enumerate(selected_timeframes, 1):
                if tf == "1min":
                    df_tf = df_1m
                else:
                    df_tf = self._resample_and_fill(df_1m, tf)
                
                if df_tf.empty:
                    continue
                
                nbfs = self._calculate_nbfs(df_tf['volume'], length, use_cum_volume)
                evwma = self._calc_evwma(df_tf['close'].values, df_tf['volume'].values, nbfs)
                evwma_series[f"evwma{i}"] = pd.Series(evwma, index=df_tf.index)
                evwma_dataframes[f"evwma{i}"] = df_tf  # Store for price comparison

            if not evwma_series:
                return False

            # Check price above EVWMA if required
            if require_price_above:
                for evwma_name, evwma_s in evwma_series.items():
                    # Get the latest EVWMA value
                    latest_evwma = evwma_s.iloc[-1]
                    
                    # For non-1min timeframes, we need to compare with the resampled price
                    # For 1min, compare directly with current price
                    if evwma_name == "evwma1" and selected_timeframes[0] == "1min":
                        if current_price <= latest_evwma:
                            return False
                    else:
                        # For other timeframes, get the latest close from the resampled dataframe
                        df_tf = evwma_dataframes[evwma_name]
                        latest_close_tf = df_tf['close'].iloc[-1]
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
            df_evw = pd.DataFrame({name: series.reindex(base_series.index, method='ffill') 
                                  for name, series in evwma_series.items()}).dropna()

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

