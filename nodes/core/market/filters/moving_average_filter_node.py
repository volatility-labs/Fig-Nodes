import logging
from datetime import datetime
from typing import Any

import numpy as np

from core.types_registry import AssetSymbol, IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.sma_calculator import calculate_sma

logger = logging.getLogger(__name__)


class MovingAverageFilter(BaseIndicatorFilter):
    default_params = {"period": 200, "prior_bars": 1, "ma_type": "SMA", "require_price_above_ma": "true"}
    params_meta = [
        {"name": "period", "type": "number", "default": 200, "min": 2, "step": 1},
        {"name": "prior_bars", "type": "number", "default": 1, "min": 0, "step": 1, "description": "Number of bars to look back for slope calculation (works with any interval: 15min, 1hr, daily, etc.)"},
        {"name": "ma_type", "type": "combo", "default": "SMA", "options": ["SMA", "EMA"]},
        {"name": "require_price_above_ma", "type": "combo", "default": "true", "options": ["true", "false"], "description": "If true, requires price > MA. If false, only checks for rising MA slope."},
    ]

    def _validate_indicator_params(self):
        period_value = self.params.get("period", 200)
        prior_bars_value = self.params.get("prior_bars", 1)
        ma_type_value = self.params.get("ma_type", "SMA")
        require_price_above_ma_value = self.params.get("require_price_above_ma", "true")

        # Convert period to integer if it's a string or float
        try:
            if isinstance(period_value, str):
                period_value = int(float(period_value))
            elif isinstance(period_value, float):
                period_value = int(period_value)
            elif not isinstance(period_value, int):
                raise ValueError("period must be an integer")
        except (ValueError, TypeError):
            raise ValueError("period must be an integer")
        
        # Convert prior_bars to integer if it's a string or float
        try:
            if isinstance(prior_bars_value, str):
                prior_bars_value = int(float(prior_bars_value))
            elif isinstance(prior_bars_value, float):
                prior_bars_value = int(prior_bars_value)
            elif not isinstance(prior_bars_value, int):
                raise ValueError("prior_bars must be an integer")
        except (ValueError, TypeError):
            raise ValueError("prior_bars must be an integer")
        
        if ma_type_value not in ["SMA", "EMA"]:
            raise ValueError("ma_type must be 'SMA' or 'EMA'")
        
        # Convert string "true"/"false" to boolean
        if isinstance(require_price_above_ma_value, str):
            require_price_above_ma_value = require_price_above_ma_value.lower() == "true"
        elif isinstance(require_price_above_ma_value, bool):
            pass  # Already a boolean
        else:
            raise ValueError("require_price_above_ma must be 'true' or 'false'")

        self.period = period_value
        self.prior_bars = prior_bars_value
        self.ma_type = ma_type_value
        self.require_price_above_ma = require_price_above_ma_value

    def _get_indicator_type(self) -> IndicatorType:
        return IndicatorType.SMA if self.ma_type == "SMA" else IndicatorType.EMA

    def _calculate_ma(
        self, close_prices: list[float], period: int
    ) -> dict[str, list[float | None]]:
        if self.ma_type == "SMA":
            return calculate_sma(close_prices, period=period)
        else:
            return calculate_ema(close_prices, period=period)

    def _get_ma_key(self) -> str:
        return "sma" if self.ma_type == "SMA" else "ema"

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        indicator_type = self._get_indicator_type()
        ma_key = self._get_ma_key()

        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error="No OHLCV data",
            )

        data_length: int = len(ohlcv_data)
        if data_length < self.period:
            error_msg = f"Insufficient data: {data_length} bars < {self.period}"
            logger.warning(error_msg)
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=0,
                values=IndicatorValue(lines={}),
                error=error_msg,
            )

        last_ts: int = ohlcv_data[-1]["timestamp"]

        # Calculate current MA using the calculator
        current_close_prices: list[float] = [bar["close"] for bar in ohlcv_data]
        current_ma_result: dict[str, list[float | None]] = self._calculate_ma(
            current_close_prices, period=self.period
        )
        current_ma_values: list[float | None] = current_ma_result.get(ma_key, [])
        current_ma_raw: float | None = current_ma_values[-1] if current_ma_values else None
        current_ma: float = current_ma_raw if current_ma_raw is not None else np.nan

        if np.isnan(current_ma):
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=IndicatorValue(lines={}),
                error=f"Unable to compute current {self.ma_type}",
            )

        # Handle prior_bars = 0 case (no slope requirement)
        if self.prior_bars == 0:
            current_price = ohlcv_data[-1]["close"]
            values = IndicatorValue(
                lines={"current": current_ma, "previous": np.nan, "price": current_price}
            )
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=values,
                params={"period": self.period, "ma_type": self.ma_type},
            )

        # Use bar-based lookback instead of calendar days
        # This works correctly with any interval: 15min, 1hr, daily, etc.
        # prior_bars=2 means compare current MA (at last bar) to MA from 2 bars ago
        # If we have bars [0, 1, 2, ..., N-1], and prior_bars=2:
        #   - Current MA is at bar N-1 (last bar)
        #   - Previous MA should be at bar N-3 (2 bars before last)
        #   - So we need data up to and including bar N-3
        lookback_index = len(ohlcv_data) - self.prior_bars
        
        # Ensure we have enough data for the lookback
        if lookback_index < self.period:
            current_price = ohlcv_data[-1]["close"]
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=IndicatorValue(
                    lines={"current": np.nan, "previous": np.nan, "price": current_price}
                ),
                error=f"Insufficient data for {self.prior_bars} bar lookback with {self.period} period MA",
            )

        # Get previous data up to (and including) the lookback point
        # This gives us bars [0, 1, ..., lookback_index-1] which is exactly prior_bars bars before the end
        previous_data: list[OHLCVBar] = ohlcv_data[:lookback_index]

        if len(previous_data) < self.period:
            current_price = ohlcv_data[-1]["close"]
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=IndicatorValue(
                    lines={"current": np.nan, "previous": np.nan, "price": current_price}
                ),
                error=f"Insufficient data for previous {self.ma_type}",
            )

        # Calculate previous MA using the calculator
        previous_close_prices: list[float] = [bar["close"] for bar in previous_data]
        previous_ma_result: dict[str, list[float | None]] = self._calculate_ma(
            previous_close_prices, period=self.period
        )
        previous_ma_values: list[float | None] = previous_ma_result.get(ma_key, [])
        previous_ma_raw: float | None = previous_ma_values[-1] if previous_ma_values else None
        previous_ma: float = previous_ma_raw if previous_ma_raw is not None else np.nan

        if np.isnan(previous_ma):
            current_price = ohlcv_data[-1]["close"]
            return IndicatorResult(
                indicator_type=indicator_type,
                timestamp=last_ts,
                values=IndicatorValue(
                    lines={"current": current_ma, "previous": np.nan, "price": current_price}
                ),
                error=f"Unable to compute previous {self.ma_type}",
            )

        current_price = ohlcv_data[-1]["close"]
        
        # Debug logging to verify calculation
        current_bar_index = len(ohlcv_data) - 1
        previous_bar_index = lookback_index - 1
        
        # Get timestamps for better debugging
        current_ts = ohlcv_data[current_bar_index]["timestamp"]
        previous_ts = ohlcv_data[previous_bar_index]["timestamp"] if previous_bar_index >= 0 else 0
        current_dt = datetime.fromtimestamp(current_ts / 1000) if current_ts else "N/A"
        previous_dt = datetime.fromtimestamp(previous_ts / 1000) if previous_ts else "N/A"
        
        # Calculate bars difference for clarity
        bars_difference = current_bar_index - previous_bar_index
        
        # Get symbol from context if available (set by _execute_impl override)
        symbol_str = getattr(self, '_current_symbol', 'UNKNOWN')
        
        logger.warning(
            f"📊 MA Filter [{symbol_str}]: period={self.period}, prior_bars={self.prior_bars}, "
            f"current_MA@{current_bar_index}({current_dt})={current_ma:.4f}, "
            f"previous_MA@{previous_bar_index}({previous_dt})={previous_ma:.4f}, "
            f"bars_diff={bars_difference}, "
            f"slope={'POSITIVE' if current_ma > previous_ma else 'NEGATIVE'}, "
            f"price={current_price:.4f}, diff={current_ma - previous_ma:.6f}"
        )
        
        values = IndicatorValue(
            lines={"current": current_ma, "previous": previous_ma, "price": current_price}
        )
        return IndicatorResult(
            indicator_type=indicator_type,
            timestamp=last_ts,
            values=values,
            params={"period": self.period, "ma_type": self.ma_type},
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        # Get symbol from context if available (set by _execute_impl override)
        symbol_str = getattr(self, '_current_symbol', 'UNKNOWN')
        
        if indicator_result.error:
            logger.warning(f"❌ MA Filter [{symbol_str}]: Failed due to error: {indicator_result.error}")
            return False
        lines: dict[str, float] = indicator_result.values.lines
        current_ma: float = lines.get("current", np.nan)
        current_price: float = lines.get("price", np.nan)

        # Check for NaN values
        if np.isnan(current_price) or np.isnan(current_ma):
            logger.warning(f"❌ MA Filter [{symbol_str}]: Failed - NaN values (price={current_price}, MA={current_ma})")
            return False

        # If require_price_above_ma is True, check price > MA
        if self.require_price_above_ma:
            if not (current_price > current_ma):
                logger.warning(f"❌ MA Filter [{symbol_str}]: Failed - price {current_price:.4f} <= MA {current_ma:.4f}")
                return False

        # If prior_bars is 0, only check price > MA (if required) or just pass if only slope is needed
        if self.prior_bars == 0:
            if self.require_price_above_ma:
                logger.warning(f"✅ MA Filter [{symbol_str}]: Passed - price {current_price:.4f} > MA {current_ma:.4f} (no slope check)")
            else:
                logger.warning(f"✅ MA Filter [{symbol_str}]: Passed - no price/MA requirement and no slope check (prior_bars=0)")
            return True

        # For prior_bars > 0, check that current MA > previous MA (upward slope)
        previous: float = lines.get("previous", np.nan)
        if np.isnan(previous):
            logger.warning(f"❌ MA Filter [{symbol_str}]: Failed - previous MA is NaN")
            return False
        
        slope_positive = current_ma > previous
        slope_diff = current_ma - previous
        
        if slope_positive:
            if self.require_price_above_ma:
                logger.warning(f"✅ MA Filter [{symbol_str}]: Passed - price {current_price:.4f} > MA {current_ma:.4f}, slope POSITIVE ({current_ma:.4f} > {previous:.4f}, diff={slope_diff:.6f})")
            else:
                logger.warning(f"✅ MA Filter [{symbol_str}]: Passed - slope POSITIVE ({current_ma:.4f} > {previous:.4f}, diff={slope_diff:.6f}), price={current_price:.4f}, MA={current_ma:.4f}")
        else:
            if self.require_price_above_ma:
                logger.warning(f"❌ MA Filter [{symbol_str}]: Failed - price {current_price:.4f} > MA {current_ma:.4f}, but slope NEGATIVE ({current_ma:.4f} <= {previous:.4f}, diff={slope_diff:.6f})")
            else:
                logger.warning(f"❌ MA Filter [{symbol_str}]: Failed - slope NEGATIVE ({current_ma:.4f} <= {previous:.4f}, diff={slope_diff:.6f}), price={current_price:.4f}, MA={current_ma:.4f}")
        
        return slope_positive
    
    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Override to set current symbol context for logging."""
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}
        total_symbols = len(ohlcv_bundle)
        processed_symbols = 0

        # Initial progress signal
        try:
            self.report_progress(0.0, f"0/{total_symbols}")
        except Exception:
            pass

        for symbol, ohlcv_data in ohlcv_bundle.items():
            # Set current symbol for logging context
            self._current_symbol = str(symbol)
            
            if not ohlcv_data:
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            try:
                indicator_result = self._calculate_indicator(ohlcv_data)

                if self._should_pass_filter(indicator_result):
                    filtered_bundle[symbol] = ohlcv_data

            except Exception as e:
                logger.warning(f"Failed to process indicator for {symbol}: {e}")
                # Progress should still advance even on failure
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            # Advance progress after successful processing
            processed_symbols += 1
            try:
                progress = (processed_symbols / max(1, total_symbols)) * 100.0
                self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
            except Exception:
                pass
        
        # Clear symbol context
        if hasattr(self, '_current_symbol'):
            delattr(self, '_current_symbol')

        return {
            "filtered_ohlcv_bundle": filtered_bundle,
        }
