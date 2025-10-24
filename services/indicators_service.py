import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import linregress

from services.indicator_calculators.adx_calculator import calculate_adx
from services.indicator_calculators.atr_calculator import calculate_atr

logger = logging.getLogger(__name__)


class IndicatorsService:
    def __init__(self):
        pass

    def compute_indicators(self, df: pd.DataFrame, timeframe: str) -> dict[str, Any]:
        if df.empty or len(df) < 14:
            logger.warning(f"Insufficient data for indicators on {timeframe}.")
            return {}
        # EVWMA
        evwma = self.calculate_evwma(df["Close"], df["Volume"], length=325)
        # EIS
        eis_bullish = self.is_impulse_bullish(df)
        eis_bearish = self.is_impulse_bearish(df)
        # ADX
        adx = self._calculate_adx_direct(df)
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

    def calculate_evwma(self, price: pd.Series, volume: pd.Series, length: int) -> float:
        if price.empty or volume.empty:
            return np.nan
        nbfs = self.calculate_nbfs(volume, length)
        evwma_values = self.calc_evwma(price.values, volume.values, nbfs)
        if len(evwma_values) == 0:
            return np.nan
        return evwma_values[-1]

    def calculate_nbfs(self, volume: pd.Series, length: int, use_cum: bool = False) -> np.ndarray:
        if volume.empty:
            return np.array([])
        if use_cum:
            return volume.cumsum().values
        roll = volume.rolling(window=min(length, len(volume)), min_periods=1).sum()
        return roll.fillna(0).values

    @staticmethod
    def calc_evwma(price, volume, nbfs):
        if price.size == 0 or volume.size == 0:
            return np.array([])
        ev = np.zeros_like(price, dtype=float)
        ev[0] = price[0]
        for i in range(1, len(price)):
            if nbfs[i] != 0:
                ev[i] = ev[i - 1] * ((nbfs[i] - volume[i]) / nbfs[i]) + price[i] * (
                    volume[i] / nbfs[i]
                )
            else:
                ev[i] = price[i]
        return ev

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

    def calculate_heiken_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        ha_df = pd.DataFrame(index=df.index)
        ha_df["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
        ha_df["HA_Open"] = df["Open"].copy()
        for i in range(1, len(df)):
            ha_df.loc[ha_df.index[i], "HA_Open"] = (
                ha_df.loc[ha_df.index[i - 1], "HA_Open"] + ha_df.loc[ha_df.index[i - 1], "HA_Close"]
            ) / 2
        ha_df["HA_High"] = df[["High", "Open", "Close"]].max(axis=1)
        ha_df["HA_Low"] = df[["Low", "Open", "Close"]].min(axis=1)
        ha_df["Volume"] = df["Volume"]
        return ha_df

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
        close = df["Close"]
        ema_13 = close.ewm(span=13, adjust=False).mean()
        macd_fast = close.ewm(span=12, adjust=False).mean()
        macd_slow = close.ewm(span=26, adjust=False).mean()
        macd_line = macd_fast - macd_slow
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal
        elder_bulls = (ema_13 > ema_13.shift(1)) & (macd_hist > macd_hist.shift(1))
        return bool(elder_bulls.iloc[-1])

    def is_impulse_bearish(self, df: pd.DataFrame) -> bool:
        if df.empty or len(df) < 27:
            return False
        close = df["Close"]
        ema_13 = close.ewm(span=13, adjust=False).mean()
        macd_fast = close.ewm(span=12, adjust=False).mean()
        macd_slow = close.ewm(span=26, adjust=False).mean()
        macd_line = macd_fast - macd_slow
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal
        elder_bears = (ema_13 < ema_13.shift(1)) & (macd_hist < macd_hist.shift(1))
        return bool(elder_bears.iloc[-1])

    def _calculate_adx_direct(self, df: pd.DataFrame, di_len: int = 14) -> float:
        """Helper method to calculate ADX using the calculator directly."""
        if df.empty or len(df) < di_len:
            return np.nan
        required_columns = ["High", "Low", "Close"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return np.nan

        # Prepare dataframe with lowercase column names for the calculator
        df_adx = df[required_columns].copy()
        df_adx.columns = [col.lower() for col in df_adx.columns]

        # Convert to numeric and drop NaN rows
        for col in df_adx.columns:
            df_adx[col] = pd.to_numeric(df_adx[col], errors="coerce")
        df_adx = df_adx.dropna()

        if len(df_adx) < di_len:
            return np.nan

        # Use the calculator - returns full time series
        result = calculate_adx(df_adx, period=di_len)
        adx_series = result.get("adx", [])

        # Return the last value from the series (or NaN if empty)
        if adx_series and len(adx_series) > 0:
            last_value = adx_series[-1]
            return last_value if last_value is not None else np.nan
        return np.nan

    def calculate_three_line_break(self, df: pd.DataFrame, num_lines: int = 3) -> pd.DataFrame:
        tlb_lines = []
        prices = df["Close"].values
        dates = df.index
        if len(prices) < 2:
            return pd.DataFrame()
        direction = "up" if prices[1] > prices[0] else "down"
        current_line = {
            "start_date": dates[0],
            "end_date": dates[1],
            "open": prices[0],
            "close": prices[1],
            "direction": direction,
        }
        tlb_lines.append(current_line)
        lines_close = [prices[1]]
        lines_open = [prices[0]]
        for i in range(2, len(prices)):
            current_price = prices[i]
            current_date = dates[i]
            last_line = tlb_lines[-1]
            last_line["end_date"] = current_date
            if len(tlb_lines) >= num_lines:
                last_n_lines = tlb_lines[-num_lines:]
                max_value = max(
                    max([line["close"] for line in last_n_lines]),
                    max([line["open"] for line in last_n_lines]),
                )
                min_value = min(
                    min([line["close"] for line in last_n_lines]),
                    min([line["open"] for line in last_n_lines]),
                )
            else:
                max_value = max(max(lines_close), max(lines_open))
                min_value = min(min(lines_close), min(lines_open))
            if last_line["direction"] == "up":
                if current_price > max_value:
                    new_open = (
                        last_line["close"]
                        if last_line["close"] > last_line["open"]
                        else last_line["open"]
                    )
                    new_line = {
                        "start_date": current_date,
                        "end_date": current_date,
                        "open": new_open,
                        "close": current_price,
                        "direction": "up",
                    }
                    tlb_lines.append(new_line)
                    lines_close.append(current_price)
                    lines_open.append(new_open)
                    if len(lines_close) > num_lines:
                        lines_close.pop(0)
                        lines_open.pop(0)
                elif current_price < min_value and len(tlb_lines) >= num_lines:
                    new_open = (
                        last_line["open"]
                        if last_line["close"] > last_line["open"]
                        else last_line["close"]
                    )
                    new_line = {
                        "start_date": current_date,
                        "end_date": current_date,
                        "open": new_open,
                        "close": current_price,
                        "direction": "down",
                    }
                    tlb_lines.append(new_line)
                    lines_close.append(current_price)
                    lines_open.append(new_open)
                    if len(lines_close) > num_lines:
                        lines_close.pop(0)
                        lines_open.pop(0)
            else:
                if current_price < min_value:
                    new_open = (
                        last_line["close"]
                        if last_line["close"] < last_line["open"]
                        else last_line["open"]
                    )
                    new_line = {
                        "start_date": current_date,
                        "end_date": current_date,
                        "open": new_open,
                        "close": current_price,
                        "direction": "down",
                    }
                    tlb_lines.append(new_line)
                    lines_close.append(current_price)
                    lines_open.append(new_open)
                    if len(lines_close) > num_lines:
                        lines_close.pop(0)
                        lines_open.pop(0)
                elif current_price > max_value and len(tlb_lines) >= num_lines:
                    new_open = (
                        last_line["open"]
                        if last_line["close"] < last_line["open"]
                        else last_line["close"]
                    )
                    new_line = {
                        "start_date": current_date,
                        "end_date": current_date,
                        "open": new_open,
                        "close": current_price,
                        "direction": "up",
                    }
                    tlb_lines.append(new_line)
                    lines_close.append(current_price)
                    lines_open.append(new_open)
                    if len(lines_close) > num_lines:
                        lines_close.pop(0)
                        lines_open.pop(0)
        return pd.DataFrame(tlb_lines)

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

    def calculate_atrx(
        self,
        df: pd.DataFrame,
        length: int = 14,
        ma_length: int = 50,
        smoothing: str = "RMA",
        price: str = "Close",
    ) -> float:
        """
        Calculate ATRX indicator following TradingView methodology:
        A = ATR% = ATR / Last Done Price
        B = % Gain From 50-MA = (Price - SMA50) / SMA50 * 100
        ATRX = B / A = (% Gain From 50-MA) / ATR%

        Reference:
        https://www.tradingview.com/script/oimVgV7e-ATR-multiple-from-50-MA/
        """
        if df.empty or len(df) < max(length, ma_length):
            return np.nan

        # Validate smoothing parameter (only RMA supported by calculator)
        if smoothing != "RMA":
            raise ValueError(
                f"Invalid smoothing method '{smoothing}'. Only 'RMA' (Wilder's smoothing) is supported."
            )

        # Validate price parameter
        if price not in df.columns:
            return np.nan

        # Calculate ATR using the calculator
        # Prepare dataframe with lowercase column names for the calculator
        df_atr = df[["High", "Low", "Close"]].copy()
        df_atr.columns = [col.lower() for col in df_atr.columns]

        # Convert to numeric and drop NaN rows
        for col in df_atr.columns:
            df_atr[col] = pd.to_numeric(df_atr[col], errors="coerce")
        df_atr = df_atr.dropna()

        if len(df_atr) < length:
            return np.nan

        # Extract lists for the calculator
        highs = df_atr["high"].tolist()
        lows = df_atr["low"].tolist()
        closes = df_atr["close"].tolist()

        # Use the calculator for ATR (only supports RMA/Wilder's smoothing)
        atr_result = calculate_atr(highs, lows, closes, length)
        atr_list = atr_result.get("atr", [])

        if not atr_list or len(atr_list) == 0:
            return np.nan

        # Convert to pandas Series for compatibility
        atr = pd.Series(
            atr_list, index=df_atr.index if len(df_atr) == len(atr_list) else range(len(atr_list))
        )

        # Calculate 50-day SMA of price (not EMA of daily average)
        sma_50 = df[price].rolling(window=ma_length, min_periods=1).mean()

        # Get current values
        current_price = df[price].iloc[-1]
        current_sma_50 = sma_50.iloc[-1]
        current_atr = atr.iloc[-1]

        # Check for invalid values
        if (
            current_atr == 0
            or current_sma_50 == 0
            or np.isnan(current_sma_50)
            or np.isnan(current_atr)
        ):
            return np.nan

        # Calculate ATR% = ATR / Last Done Price
        atr_percent = current_atr / current_price

        # Calculate % Gain From 50-MA = (Price - SMA50) / SMA50
        percent_gain_from_50ma = (current_price - current_sma_50) / current_sma_50

        # Calculate ATRX = (% Gain From 50-MA) / ATR%
        if atr_percent == 0:
            return np.nan

        atrx = percent_gain_from_50ma / atr_percent
        return atrx

    def calculate_sma(self, df: pd.DataFrame, period: int, price: str = "Close") -> float:
        if df.empty or len(df) < period:
            return np.nan
        if price not in df.columns:
            return np.nan
        return df[price].rolling(window=period).mean().iloc[-1]
