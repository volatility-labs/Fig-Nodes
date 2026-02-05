from typing import Any

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.adx_calculator import calculate_adx


class WildersADXFilter(BaseIndicatorFilter):
    """
    Wilder's ADX-based filter with optional +DI/-DI direction and crossover requirements.

    Parameters:
    - min_adx: Minimum ADX threshold to qualify as trending (default: 25.0)
    - timeperiod: ADX period (default: 14)
    - direction: 'any' | 'bullish' | 'bearish' (default: 'any')
    - require_crossover: Require recent +DI/-DI crossover consistent with direction (default: False)
    - di_lookback_bars: Lookback bars to detect crossover (default: 3)
    - require_adx_rising: Require ADX rising vs previous bar (default: False)
    """

    default_params = {
        "min_adx": 25.0,
        "timeperiod": 14,
        "direction": "any",  # any | bullish | bearish
        "require_crossover": False,
        "di_lookback_bars": 3,
        "require_adx_rising": False,
    }

    params_meta = [
        {
            "name": "min_adx",
            "type": "number",
            "default": 25.0,
            "min": 0.0,
            "max": 100.0,
            "step": 0.1,
        },
        {"name": "timeperiod", "type": "number", "default": 14, "min": 1, "step": 1},
        {
            "name": "direction",
            "type": "combo",
            "default": "any",
            "options": ["any", "bullish", "bearish"],
        },
        {"name": "require_crossover", "type": "combo", "default": False, "options": [True, False]},
        {"name": "di_lookback_bars", "type": "number", "default": 3, "min": 1, "step": 1},
        {"name": "require_adx_rising", "type": "combo", "default": False, "options": [True, False]},
    ]

    def _validate_indicator_params(self):
        min_adx = self.params.get("min_adx", 25.0)
        timeperiod = self.params.get("timeperiod", 14)
        lookback = self.params.get("di_lookback_bars", 3)
        direction = self.params.get("direction", "any")

        if not isinstance(min_adx, int | float) or min_adx < 0:
            raise ValueError("Minimum ADX cannot be negative")
        if not isinstance(timeperiod, int | float) or timeperiod <= 0:
            raise ValueError("Time period must be positive")
        if not isinstance(lookback, int | float) or lookback <= 0:
            raise ValueError("di_lookback_bars must be positive")
        if direction not in ("any", "bullish", "bearish"):
            raise ValueError("direction must be one of: any, bullish, bearish")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.ADX,
                timestamp=0,
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="No data",
            )

        timeperiod_value = self.params.get("timeperiod", 14)
        if not isinstance(timeperiod_value, int | float):
            timeperiod_value = 14
        timeperiod = int(timeperiod_value)
        if len(ohlcv_data) < timeperiod:
            return IndicatorResult(
                indicator_type=IndicatorType.ADX,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="Insufficient data",
            )

        highs = [bar["high"] for bar in ohlcv_data]
        lows = [bar["low"] for bar in ohlcv_data]
        closes = [bar["close"] for bar in ohlcv_data]

        result = calculate_adx(highs, lows, closes, period=timeperiod)
        adx_series = result.get("adx", [])
        pdi_series = result.get("pdi", [])
        ndi_series = result.get("ndi", [])

        latest_adx = adx_series[-1] if adx_series else None
        latest_pdi = pdi_series[-1] if pdi_series else None
        latest_ndi = ndi_series[-1] if ndi_series else None

        # Build a small tail series for downstream logic (last N bars)
        lookback = self.params.get("di_lookback_bars", 3)
        if not isinstance(lookback, int | float):
            lookback = 3
        lb = max(1, int(lookback))

        tail_start = max(0, len(adx_series) - lb - 1)  # include one extra for comparisons
        tail: list[dict[str, Any]] = []
        for i in range(tail_start, len(adx_series)):
            adx_val = adx_series[i] if i < len(adx_series) else None
            pdi_val = pdi_series[i] if i < len(pdi_series) else None
            ndi_val = ndi_series[i] if i < len(ndi_series) else None
            tail.append({"adx": adx_val, "+di": pdi_val, "-di": ndi_val})

        values = IndicatorValue(
            single=float(latest_adx or 0.0),
            lines={"pdi": float(latest_pdi or 0.0), "ndi": float(latest_ndi or 0.0)},
            series=tail,
        )

        return IndicatorResult(
            indicator_type=IndicatorType.ADX,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=values,
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            return False

        params: dict[str, Any] = self.params
        min_adx = params.get("min_adx", 25.0)
        direction = params.get("direction", "any")
        require_crossover = params.get("require_crossover", False)
        require_adx_rising = params.get("require_adx_rising", False)

        latest_adx = indicator_result.values.single
        lines = indicator_result.values.lines
        series = indicator_result.values.series

        if latest_adx < float(min_adx):
            return False

        pdi = float(lines.get("pdi", 0.0))
        ndi = float(lines.get("ndi", 0.0))

        # Direction filter
        if direction == "bullish" and not (pdi > ndi):
            return False
        if direction == "bearish" and not (ndi > pdi):
            return False

        # ADX rising requirement
        if require_adx_rising and len(series) >= 2:
            prev_adx = series[-2].get("adx")
            if isinstance(prev_adx, int | float) and not (latest_adx > prev_adx):
                return False

        # Crossover requirement within tail series
        if require_crossover and len(series) >= 2:
            crossed = False
            for i in range(1, len(series)):
                prev = series[i - 1]
                curr = series[i]
                p_prev = prev.get("+di")
                n_prev = prev.get("-di")
                p_curr = curr.get("+di")
                n_curr = curr.get("-di")
                if not all(isinstance(v, int | float) for v in [p_prev, n_prev, p_curr, n_curr]):
                    continue
                # Type narrowing: we know these are int/float after isinstance check
                assert isinstance(p_prev, int | float)
                assert isinstance(n_prev, int | float)
                assert isinstance(p_curr, int | float)
                assert isinstance(n_curr, int | float)
                prev_sign = (p_prev > n_prev) - (p_prev < n_prev)  # 1 bullish, -1 bearish, 0 equal
                curr_sign = (p_curr > n_curr) - (p_curr < n_curr)
                if prev_sign != curr_sign and curr_sign != 0:
                    # A crossover occurred at step i
                    if direction == "any":
                        crossed = True
                        break
                    if direction == "bullish" and curr_sign == 1:
                        crossed = True
                        break
                    if direction == "bearish" and curr_sign == -1:
                        crossed = True
                        break
            if not crossed:
                return False

        return True
