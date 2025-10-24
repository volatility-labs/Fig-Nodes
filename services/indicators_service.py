import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import linregress

from services.indicator_calculators.ema_calculator import calculate_ema

logger = logging.getLogger(__name__)


class IndicatorsService:
    def __init__(self):
        pass

    def compute_indicators(self, df: pd.DataFrame, timeframe: str) -> dict[str, Any]:
        if df.empty or len(df) < 14:
            logger.warning(f"Insufficient data for indicators on {timeframe}.")
            return {}

        # EIS
        eis_bullish = self.is_impulse_bullish(df)
        eis_bearish = self.is_impulse_bearish(df)
        # TLB
        tlb = self.calculate_three_line_break(df)
        # VBP
        vbp = self.calculate_volume_profile(df)
        # Hurst
        hurst = self.calculate_hurst_exponent(df["Close"])
        # Acceleration
        acceleration = self.roc_slope(df["Close"])
        # Volume Ratio
        ha_df = self.calculate_heiken_ashi(df)
        volume_ratio = self.calculate_volume_metrics(df, ha_df, 325)
        # Support/Resistance
        current_price = df["Close"].iloc[-1]
        resistance, res_pct, res_tf = self.get_next_significant_level(
            df, current_price, "above", timeframe
        )
        support, sup_pct, sup_tf = self.get_next_significant_level(
            df, current_price, "below", timeframe
        )
        return {
            "evwma": evwma,
            "eis_bullish": eis_bullish,
            "eis_bearish": eis_bearish,
            "adx": adx,
            "tlb": tlb,
            "vbp": vbp,
            "hurst": hurst,
            "acceleration": acceleration,
            "volume_ratio": volume_ratio,
            "resistance": resistance,
            "res_pct": res_pct,
            "res_tf": res_tf,
            "support": support,
            "sup_pct": sup_pct,
            "sup_tf": sup_tf,
        }

    def calculate_hurst_exponent(self, price_series: pd.Series, lags_range=None) -> float:
        if price_series is None or price_series.empty:
            return np.nan

        # Adapt lags_range to available data - use min of 10 data points or available data
        min_data_points = 10
        if len(price_series) < min_data_points:
            return np.nan

        if lags_range is None:
            max_lag = min(50, len(price_series) // 2)  # Use up to half the data points, max 50
            lags_range = range(2, max_lag + 1)

        if len(price_series) < max(lags_range) + 1:
            return np.nan
        log_prices = np.log(price_series.values.astype(float))
        tau = []
        for lag in lags_range:
            diff = log_prices[lag:] - log_prices[:-lag]
            tau.append(np.sqrt(np.std(diff)))
        tau = np.array(tau)
        if np.any(tau <= 0):
            return np.nan
        poly = np.polyfit(np.log(list(lags_range)), np.log(tau), 1)
        hurst = 2 * poly[0]
        return hurst

    def roc_slope(self, series: pd.Series, window: int = 10) -> float:
        roc = series.pct_change().iloc[-window:]
        x = np.arange(len(roc))
        if len(roc.dropna()) < 2:
            return 0
        slope, _, _, _, _ = linregress(x, roc)
        return slope

    def compute_up_down_volume(self, df_ha: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        if df_ha.empty:
            return pd.Series(), pd.Series()
        up_vol = pd.Series(0.0, index=df_ha.index)
        dn_vol = pd.Series(0.0, index=df_ha.index)
        for i in range(len(df_ha)):
            if i == 0:
                if df_ha["HA_Close"].iloc[i] > df_ha["HA_Open"].iloc[i]:
                    up_vol.iloc[i] = df_ha["Volume"].iloc[i]
                elif df_ha["HA_Close"].iloc[i] < df_ha["HA_Open"].iloc[i]:
                    dn_vol.iloc[i] = df_ha["Volume"].iloc[i]
            else:
                if df_ha["HA_Close"].iloc[i] > df_ha["HA_Open"].iloc[i]:
                    up_vol.iloc[i] = df_ha["Volume"].iloc[i]
                    dn_vol.iloc[i] = dn_vol.iloc[i - 1]
                elif df_ha["HA_Close"].iloc[i] < df_ha["HA_Open"].iloc[i]:
                    dn_vol.iloc[i] = df_ha["Volume"].iloc[i]
                    up_vol.iloc[i] = up_vol.iloc[i - 1]
                else:
                    up_vol.iloc[i] = up_vol.iloc[i - 1]
                    dn_vol.iloc[i] = dn_vol.iloc[i - 1]
        return up_vol, dn_vol

    def rolling_sma(self, series: pd.Series, window: int) -> pd.Series:
        if series.empty:
            return pd.Series()
        return series.rolling(window=min(window, len(series)), min_periods=1).mean()

    def calculate_volume_metrics(
        self, df: pd.DataFrame, ha_df: pd.DataFrame, rolling_length: int
    ) -> float:
        if df.empty or ha_df.empty:
            return 1.0
        df_vol = df.copy()
        full_up_vol, full_dn_vol = self.compute_up_down_volume(ha_df)
        df_vol["UpVolume"] = full_up_vol.reindex(df.index, method="ffill")
        df_vol["DownVolume"] = full_dn_vol.reindex(df.index, method="ffill")
        df_vol["UpVolAvg"] = self.rolling_sma(df_vol["UpVolume"], rolling_length)
        df_vol["DownVolAvg"] = self.rolling_sma(df_vol["DownVolume"], rolling_length)
        df_vol["VolumeRatio"] = df_vol["UpVolAvg"] / df_vol["DownVolAvg"].replace(0, np.nan)
        return df_vol["VolumeRatio"].iloc[-1] if not df_vol["VolumeRatio"].isna().all() else 1.0

    def get_next_significant_level(
        self, df: pd.DataFrame, current_price: float, direction: str, timeframe: str
    ) -> tuple[float | None, float | None, str | None]:
        vbp = self.calculate_volume_profile(df)
        if vbp.empty:
            return None, None, None
        significant_levels = vbp.nlargest(5).index.tolist()
        if direction == "above":
            above = [l for l in significant_levels if l > current_price]
            if not above:
                return None, None, None
            level = min(above)
        elif direction == "below":
            below = [l for l in significant_levels if l < current_price]
            if not below:
                return None, None, None
            level = max(below)
        else:
            return None, None, None
        pct = abs((level - current_price) / current_price) * 100
        return level, pct, timeframe

    def is_impulse_bullish(self, df: pd.DataFrame) -> bool:
        if df.empty or len(df) < 27:
            return False
        # Prepare dataframe with lowercase column names for the calculator
        df_ema = df[["Close"]].copy()
        df_ema.columns = [col.lower() for col in df_ema.columns]

        # Convert to numeric and drop NaN rows
        for col in df_ema.columns:
            df_ema[col] = pd.to_numeric(df_ema[col], errors="coerce")
        df_ema = df_ema.dropna()

        if len(df_ema) < 27:
            return False

        # Use calculators for EMA calculations
        ema_13_result = calculate_ema(df_ema, period=13, source="close")
        ema_13_values = ema_13_result.get("ema", [])
        ema_13 = pd.Series(ema_13_values, index=df_ema.index[: len(ema_13_values)])

        macd_fast_result = calculate_ema(df_ema, period=12, source="close")
        macd_fast_values = macd_fast_result.get("ema", [])
        macd_fast = pd.Series(macd_fast_values, index=df_ema.index[: len(macd_fast_values)])

        macd_slow_result = calculate_ema(df_ema, period=26, source="close")
        macd_slow_values = macd_slow_result.get("ema", [])
        macd_slow = pd.Series(macd_slow_values, index=df_ema.index[: len(macd_slow_values)])

        macd_line = macd_fast - macd_slow

        macd_signal_result = calculate_ema(
            pd.DataFrame({"macd": macd_line.values}), period=9, source="macd"
        )
        macd_signal_values = macd_signal_result.get("ema", [])
        macd_signal = pd.Series(
            macd_signal_values, index=macd_line.index[: len(macd_signal_values)]
        )

        macd_hist = macd_line - macd_signal
        elder_bulls = (ema_13 > ema_13.shift(1)) & (macd_hist > macd_hist.shift(1))
        return bool(elder_bulls.iloc[-1])

    def is_impulse_bearish(self, df: pd.DataFrame) -> bool:
        if df.empty or len(df) < 27:
            return False
        # Prepare dataframe with lowercase column names for the calculator
        df_ema = df[["Close"]].copy()
        df_ema.columns = [col.lower() for col in df_ema.columns]

        # Convert to numeric and drop NaN rows
        for col in df_ema.columns:
            df_ema[col] = pd.to_numeric(df_ema[col], errors="coerce")
        df_ema = df_ema.dropna()

        if len(df_ema) < 27:
            return False

        # Use calculators for EMA calculations
        ema_13_result = calculate_ema(df_ema, period=13, source="close")
        ema_13_values = ema_13_result.get("ema", [])
        ema_13 = pd.Series(ema_13_values, index=df_ema.index[: len(ema_13_values)])

        macd_fast_result = calculate_ema(df_ema, period=12, source="close")
        macd_fast_values = macd_fast_result.get("ema", [])
        macd_fast = pd.Series(macd_fast_values, index=df_ema.index[: len(macd_fast_values)])

        macd_slow_result = calculate_ema(df_ema, period=26, source="close")
        macd_slow_values = macd_slow_result.get("ema", [])
        macd_slow = pd.Series(macd_slow_values, index=df_ema.index[: len(macd_slow_values)])

        macd_line = macd_fast - macd_slow

        macd_signal_result = calculate_ema(
            pd.DataFrame({"macd": macd_line.values}), period=9, source="macd"
        )
        macd_signal_values = macd_signal_result.get("ema", [])
        macd_signal = pd.Series(
            macd_signal_values, index=macd_line.index[: len(macd_signal_values)]
        )

        macd_hist = macd_line - macd_signal
        elder_bears = (ema_13 < ema_13.shift(1)) & (macd_hist < macd_hist.shift(1))
        return bool(elder_bears.iloc[-1])

    def calculate_volume_profile(self, df: pd.DataFrame, bins: int = 100) -> pd.Series:
        if df.empty:
            return pd.Series()
        df = df.copy()
        df["volume_usd"] = df["Volume"] * df["Close"]
        price_range = df["High"].max() - df["Low"].min()
        if price_range == 0:
            return pd.Series()
        bin_size = price_range / bins
        df["price_bin"] = ((df["Close"] - df["Low"].min()) / bin_size).astype(int) * bin_size + df[
            "Low"
        ].min()
        volume_profile = df.groupby("price_bin")["volume_usd"].sum().sort_index()
        return volume_profile
