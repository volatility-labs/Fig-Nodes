import logging
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime, timedelta
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorResult, IndicatorType
from services.polygon_service import fetch_bars
import pytz

logger = logging.getLogger(__name__)

class OrbFilterNode(BaseIndicatorFilterNode):
    """
    Filters assets based on Opening Range Breakout (ORB) criteria including relative volume and direction.
    """

    ui_module = "market/OrbFilterNodeUI"

    inputs = {
        "ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]],
        "api_key": str,
    }

    default_params = {
        "or_minutes": 5,
        "rel_vol_threshold": 100.0,
        "direction": "both",  # 'bullish', 'bearish', 'both'
        "avg_period": 14,
    }

    params_meta = [
        {"name": "or_minutes", "type": "number", "default": 5, "min": 1, "step": 1},
        {"name": "rel_vol_threshold", "type": "number", "default": 100.0, "min": 0.0, "step": 1.0},
        {"name": "direction", "type": "combo", "default": "both", "options": ["bullish", "bearish", "both"]},
        {"name": "avg_period", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        if self.params["or_minutes"] <= 0:
            raise ValueError("Opening range minutes must be positive")
        if self.params["rel_vol_threshold"] < 0:
            raise ValueError("Relative volume threshold cannot be negative")
        if self.params["avg_period"] <= 0:
            raise ValueError("Average period must be positive")

    async def _calculate_orb_indicator(self, symbol: AssetSymbol, api_key: str) -> IndicatorResult:

        avg_period = self.params["avg_period"]
        or_minutes = self.params["or_minutes"]

        # Fetch 1-min bars for last avg_period +1 days
        fetch_params = {
            "multiplier": 1,
            "timespan": "minute",
            "lookback_period": f"{avg_period + 1} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }

        bars = await fetch_bars(symbol, api_key, fetch_params)

        if not bars:
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values={},
                params=self.params,
                error="No bars fetched"
            )

        # Convert to df
        df = pd.DataFrame(bars)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')

        # Group by date
        df['date'] = df['timestamp'].dt.date
        daily_groups = df.groupby('date')

        or_volumes = {}
        today_direction = None
        today_date = datetime.now(pytz.timezone('US/Eastern')).date()

        for date, group in daily_groups:
            # Find bars from 9:30 to 9:30 + or_minutes
            open_time = datetime.combine(date, datetime.strptime('09:30', '%H:%M').time()).replace(tzinfo=pytz.timezone('US/Eastern'))
            close_time = open_time + timedelta(minutes=or_minutes)

            or_bars = group[(group['timestamp'] >= open_time) & (group['timestamp'] < close_time)]

            if or_bars.empty:
                continue

            or_high = or_bars['high'].max()
            or_low = or_bars['low'].min()
            or_volume = or_bars['volume'].sum()
            or_open = or_bars.iloc[0]['open']
            or_close = or_bars.iloc[-1]['close']

            direction = 'bullish' if or_close > or_open else 'bearish' if or_close < or_open else 'doji'

            or_volumes[date] = or_volume

            # Save direction for today
            if date == today_date:
                today_direction = direction

        # Get sorted dates
        sorted_dates = sorted(or_volumes.keys())
        if len(sorted_dates) < 2:
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values={},
                params=self.params,
                error="Insufficient days"
            )

        today = sorted_dates[-1]
        past_volumes = [or_volumes[d] for d in sorted_dates[-avg_period-1:-1]] if len(sorted_dates) > avg_period else [or_volumes[d] for d in sorted_dates[:-1]]

        if not past_volumes:
            avg_vol = 0
        else:
            avg_vol = sum(past_volumes) / len(past_volumes)

        current_vol = or_volumes[today]
        rel_vol = (current_vol / avg_vol * 100) if avg_vol > 0 else 0

        if today_direction is None:
            today_direction = 'doji'  # Default if no data for today

        values = {
            "rel_vol": rel_vol,
            "direction": today_direction,
        }

        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=int(df['timestamp'].iloc[-1].timestamp() * 1000),
            values=values,
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if "error" in indicator_result or "rel_vol" not in indicator_result["values"] or "direction" not in indicator_result["values"]:
            return False

        rel_vol = indicator_result["values"]["rel_vol"]
        direction = indicator_result["values"]["direction"]

        if direction == "doji":
            return False

        if rel_vol < self.params["rel_vol_threshold"]:
            return False

        param_dir = self.params["direction"]
        if param_dir == "both":
            return True
        return direction == param_dir

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.api_key = inputs.get("api_key")
        if not self.api_key:
            raise ValueError("API key is required")

        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}
        total_symbols = len(ohlcv_bundle)
        processed_symbols = 0
        try:
            self.report_progress(0.0, f"0/{total_symbols}")
        except Exception:
            pass

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                continue

            try:
                indicator_result = await self._calculate_orb_indicator(symbol, self.api_key)
                if self._should_pass_filter(indicator_result):
                    filtered_bundle[symbol] = ohlcv_data
            except Exception as e:
                logger.warning(f"Failed to process for {symbol}: {e}")
                # still advance progress on failure
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            processed_symbols += 1
            try:
                progress = (processed_symbols / max(1, total_symbols)) * 100.0
                self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
            except Exception:
                pass

        return {"filtered_ohlcv_bundle": filtered_bundle}
