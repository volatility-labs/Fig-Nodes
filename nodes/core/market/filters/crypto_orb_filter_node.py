"""
Crypto ORB Filter Node

Filters crypto assets based on Opening Range Breakout (ORB) criteria using:
- 00:00 UTC as the opening range start time
- 30-minute intervals (instead of 5-minute intervals)
- First 30-minute bar (00:00-00:30 UTC) for ORH/ORL calculation
"""

import asyncio
import logging
import math
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pytz

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    AssetClass,
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    NodeOutputs,
    OHLCVBar,
    get_type,
)
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.crypto_orb_calculator import calculate_crypto_orb
from services.polygon_service import fetch_bars, fetch_current_snapshot
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class CryptoOrbFilter(BaseIndicatorFilter):
    """
    Filters crypto assets based on Opening Range Breakout (ORB) criteria.
    
    Uses 00:00 UTC as opening range start time with 30-minute intervals.
    Calculates ORH/ORL from the first 30-minute bar (00:00-00:30 UTC).
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    default_params = {
        "or_minutes": 30,  # Opening range is 30 minutes (first 30-min bar)
        "rel_vol_threshold": 100.0,
        "direction": "both",  # 'bullish', 'bearish', 'both'
        "avg_period": 14,
        "filter_above_orh": "false",  # Filter for price above Opening Range High
        "filter_below_orl": "false",  # Filter for price below Opening Range Low
        "max_concurrent": 10,  # For concurrency limiting
        "rate_limit_per_second": 95,  # Stay under Polygon's recommended 100/sec
    }

    params_meta = [
        {
            "name": "or_minutes",
            "type": "number",
            "default": 30,
            "min": 30,
            "step": 30,
            "description": "Opening range period in minutes (fixed at 30 for crypto ORB)",
        },
        {
            "name": "rel_vol_threshold",
            "type": "number",
            "default": 100.0,
            "min": 0.0,
            "step": 1.0,
            "description": "Minimum relative volume percentage to pass filter",
        },
        {
            "name": "direction",
            "type": "combo",
            "default": "both",
            "options": ["bullish", "bearish", "both"],
            "description": "Filter direction: bullish, bearish, or both",
        },
        {
            "name": "avg_period",
            "type": "number",
            "default": 14,
            "min": 1,
            "step": 1,
            "description": "Number of days to use for average volume calculation",
        },
        {
            "name": "filter_above_orh",
            "type": "combo",
            "default": "false",
            "options": ["true", "false"],
            "description": "Only pass symbols with price above Opening Range High",
        },
        {
            "name": "filter_below_orl",
            "type": "combo",
            "default": "false",
            "options": ["true", "false"],
            "description": "Only pass symbols with price below Opening Range Low",
        },
    ]

    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):
        super().__init__(id, params, graph_context)
        self.workers: list[asyncio.Task[None]] = []
        self._max_safe_concurrency = 5

    def force_stop(self):
        if self._is_stopped:
            return
        self._is_stopped = True
        for w in self.workers:
            if not w.done():
                w.cancel()
        self.workers.clear()

    def _validate_indicator_params(self):
        or_minutes = self.params.get("or_minutes", 30)
        rel_vol_threshold = self.params.get("rel_vol_threshold", 100.0)
        avg_period = self.params.get("avg_period", 14)
        filter_above_orh = self.params.get("filter_above_orh", "false")
        filter_below_orl = self.params.get("filter_below_orl", "false")

        # Force or_minutes to 30 for crypto ORB
        if or_minutes != 30:
            logger.warning(f"CryptoOrbFilter: or_minutes must be 30 for crypto ORB, forcing to 30 (was {or_minutes})")
            self.params["or_minutes"] = 30

        if not isinstance(rel_vol_threshold, int | float) or rel_vol_threshold < 0:
            raise ValueError("Relative volume threshold cannot be negative")
        if not isinstance(avg_period, int | float) or avg_period <= 0:
            raise ValueError("Average period must be positive")
        if not isinstance(filter_above_orh, str) or filter_above_orh not in ["true", "false"]:
            raise ValueError('filter_above_orh must be "true" or "false"')
        if not isinstance(filter_below_orl, str) or filter_below_orl not in ["true", "false"]:
            raise ValueError('filter_below_orl must be "true" or "false"')

    async def _calculate_orb_indicator(self, symbol: AssetSymbol, api_key: str) -> IndicatorResult:
        # Ensure symbol is crypto
        if symbol.asset_class != AssetClass.CRYPTO:
            logger.warning(
                f"CryptoOrbFilter: Symbol {symbol.ticker} is not crypto ({symbol.asset_class}), skipping"
            )
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error=f"Symbol {symbol.ticker} is not crypto",
            )

        avg_period_raw = self.params.get("avg_period", 14)
        or_minutes_raw = self.params.get("or_minutes", 30)

        # Type guard: ensure avg_period is a number
        if not isinstance(avg_period_raw, int | float):
            raise ValueError(f"avg_period must be a number, got {type(avg_period_raw)}")

        avg_period = int(avg_period_raw)

        # Type guard: ensure or_minutes is a number
        if not isinstance(or_minutes_raw, int | float):
            raise ValueError(f"or_minutes must be a number, got {type(or_minutes_raw)}")

        or_minutes = int(or_minutes_raw)
        # Force to 30 for crypto ORB
        if or_minutes != 30:
            or_minutes = 30
            self.params["or_minutes"] = 30

        # Fetch 5-min bars for last avg_period +1 days
        # We'll aggregate them to create proper 30-minute opening range bars starting at 00:00 UTC
        # Polygon's 30-minute bars don't align with UTC midnight (they start at 00:18, 00:48, etc.)
        fetch_params = {
            "multiplier": 5,  # 5-minute intervals - we'll aggregate to 30-min bars
            "timespan": "minute",
            "lookback_period": f"{avg_period + 1} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }

        logger.info("=" * 80)
        logger.info(f"CRYPTO_ORB_FILTER: Starting bar fetch for {symbol.ticker} ({symbol.asset_class})")
        logger.info(f"CRYPTO_ORB_FILTER: Fetch params: {fetch_params}")
        logger.info(f"CRYPTO_ORB_FILTER: Opening range: 00:00 UTC (30-minute bar)")
        logger.info(f"CRYPTO_ORB_FILTER: Request time: {datetime.now(pytz.timezone('UTC'))}")
        logger.info("=" * 80)

        bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)

        if not bars:
            logger.warning(f"CRYPTO_ORB_FILTER: No bars returned for {symbol.ticker}")
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error="No bars fetched",
            )

        # Log bar details for delay analysis
        if bars:
            from services.time_utils import utc_timestamp_ms_to_et_datetime

            current_time_utc = datetime.now(pytz.timezone("UTC"))
            first_bar_time = utc_timestamp_ms_to_et_datetime(bars[0]["timestamp"])
            last_bar_time = utc_timestamp_ms_to_et_datetime(bars[-1]["timestamp"])
            time_diff = current_time_utc - last_bar_time
            delay_minutes = time_diff.total_seconds() / 60

            logger.info("=" * 80)
            logger.info(f"CRYPTO_ORB_FILTER: Bars received for {symbol.ticker}")
            logger.info(f"CRYPTO_ORB_FILTER: Total bars: {len(bars)}")
            logger.info(f"CRYPTO_ORB_FILTER: First bar timestamp (UTC): {first_bar_time}")
            logger.info(f"CRYPTO_ORB_FILTER: Last bar timestamp (UTC): {last_bar_time}")
            logger.info(f"CRYPTO_ORB_FILTER: Current time (UTC): {current_time_utc}")
            logger.info(f"CRYPTO_ORB_FILTER: Delay from last bar: {delay_minutes:.2f} minutes")

            if delay_minutes < 30:
                logger.info(f"CRYPTO_ORB_FILTER: ✅ Data appears REAL-TIME for {symbol.ticker}")
            elif delay_minutes < 60:
                logger.warning(
                    f"CRYPTO_ORB_FILTER: ⚠️ Data appears SLIGHTLY DELAYED for {symbol.ticker} ({delay_minutes:.2f} min)"
                )
            else:
                logger.warning(
                    f"CRYPTO_ORB_FILTER: ⚠️ Data appears SIGNIFICANTLY DELAYED for {symbol.ticker} ({delay_minutes:.2f} min)"
                )
            logger.info("=" * 80)

        # Use the crypto-specific calculator
        result = calculate_crypto_orb(bars, symbol, or_minutes, avg_period)

        if result.get("error"):
            logger.warning(
                f"CRYPTO_ORB_FILTER: Calculator error for {symbol.ticker}: {result['error']}"
            )
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error=result["error"],
            )
        
        # Validate that we have valid OR data
        if result.get("rel_vol") is None or result.get("direction") is None:
            logger.warning(
                f"CRYPTO_ORB_FILTER: Missing OR data for {symbol.ticker} - rel_vol={result.get('rel_vol')}, "
                f"direction={result.get('direction')}"
            )
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error="Missing opening range data",
            )

        rel_vol_raw = result.get("rel_vol")
        direction = result.get("direction", "doji")
        or_high = result.get("or_high")
        or_low = result.get("or_low")

        # Type guard: ensure rel_vol is a number
        if not isinstance(rel_vol_raw, int | float):
            raise ValueError(f"rel_vol must be a number, got {type(rel_vol_raw)}")

        rel_vol = float(rel_vol_raw)

        # Get the latest timestamp from bars for the result
        latest_timestamp = bars[-1]["timestamp"] if bars else 0

        # For crypto, fetch current snapshot price to ensure we have the most up-to-date price
        # This is critical for filter_above_orh and filter_below_orl checks
        current_price = np.nan
        try:
            snapshot_price, snapshot_metadata = await fetch_current_snapshot(symbol, api_key)
            if snapshot_price is not None and snapshot_price > 0:
                current_price = float(snapshot_price)
                logger.debug(
                    f"CRYPTO_ORB_FILTER: Using snapshot price {current_price} for {symbol.ticker}"
                )
            else:
                # Fallback to last bar's close if snapshot fails
                current_price = bars[-1]["close"] if bars else np.nan
                logger.warning(
                    f"CRYPTO_ORB_FILTER: Snapshot fetch failed for {symbol.ticker}, using last bar close {current_price}"
                )
        except Exception as e:
            # Fallback to last bar's close if snapshot fetch fails
            current_price = bars[-1]["close"] if bars else np.nan
            logger.warning(
                f"CRYPTO_ORB_FILTER: Error fetching snapshot for {symbol.ticker}: {e}, using last bar close {current_price}"
            )

        # Convert None values to np.nan for type compatibility
        or_high_float = or_high if or_high is not None else np.nan
        or_low_float = or_low if or_low is not None else np.nan

        values = IndicatorValue(
            lines={
                "rel_vol": rel_vol,
                "or_high": or_high_float,
                "or_low": or_low_float,
                "current_price": current_price,
                "symbol": str(symbol),  # Add symbol for logging
            },
            series=[{"direction": direction}],
        )

        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=latest_timestamp,
            values=values,
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult, symbol: AssetSymbol | None = None) -> bool:
        # Get symbol name for logging
        symbol_name = str(symbol) if symbol else indicator_result.values.lines.get("symbol", "unknown")
        
        if (
            indicator_result.error
            or not indicator_result.values.lines
            or not indicator_result.values.series
        ):
            logger.debug(
                f"CRYPTO_ORB_FILTER: FAIL - Error or missing data for {symbol_name}. "
                f"error={indicator_result.error}, has_lines={bool(indicator_result.values.lines)}, "
                f"has_series={bool(indicator_result.values.series)}"
            )
            return False

        rel_vol = indicator_result.values.lines.get("rel_vol", 0)
        if math.isnan(rel_vol):
            logger.debug(f"CRYPTO_ORB_FILTER: FAIL - {symbol_name} rel_vol is NaN")
            return False
        directions = [s["direction"] for s in indicator_result.values.series if "direction" in s]
        direction = directions[0] if directions else "doji"

        if direction == "doji":
            logger.debug(f"CRYPTO_ORB_FILTER: FAIL - {symbol_name} direction is doji")
            return False

        rel_vol_threshold = self.params.get("rel_vol_threshold", 0.0)
        if not isinstance(rel_vol_threshold, int | float):
            raise ValueError(f"rel_vol_threshold must be a number, got {type(rel_vol_threshold)}")

        if rel_vol < float(rel_vol_threshold):
            logger.debug(
                f"CRYPTO_ORB_FILTER: FAIL - {symbol_name} rel_vol {rel_vol} < threshold {rel_vol_threshold}"
            )
            return False

        param_dir = self.params.get("direction", "both")
        if param_dir != "both" and direction != param_dir:
            logger.debug(
                f"CRYPTO_ORB_FILTER: FAIL - {symbol_name} direction {direction} != required {param_dir}"
            )
            return False

        # Additional price-based filters
        lines = indicator_result.values.lines
        current_price = lines.get("current_price", np.nan)
        or_high = lines.get("or_high", np.nan)
        or_low = lines.get("or_low", np.nan)

        # Check filter_above_orh (convert string "true"/"false" to boolean)
        filter_above_orh_str = self.params.get("filter_above_orh", "false")
        filter_above_orh = filter_above_orh_str == "true"
        if filter_above_orh:
            if math.isnan(current_price) or math.isnan(or_high):
                logger.warning(
                    f"CRYPTO_ORB_FILTER: FAIL - {symbol_name} filter_above_orh=true but price={current_price} or or_high={or_high} is NaN"
                )
                return False
            price_diff = current_price - or_high
            if not (current_price > or_high):
                logger.info(
                    f"CRYPTO_ORB_FILTER: ❌ FAIL - {symbol_name} current_price {current_price:.6f} <= or_high {or_high:.6f} "
                    f"(diff: {price_diff:.6f}, {price_diff/or_high*100:.2f}% below ORH)"
                )
                return False
            logger.info(
                f"CRYPTO_ORB_FILTER: ✅ PASS - {symbol_name} current_price {current_price:.6f} > or_high {or_high:.6f} "
                f"(diff: {price_diff:.6f}, {price_diff/or_high*100:.2f}% above ORH)"
            )

        # Check filter_below_orl (convert string "true"/"false" to boolean)
        filter_below_orl_str = self.params.get("filter_below_orl", "false")
        filter_below_orl = filter_below_orl_str == "true"
        if filter_below_orl:
            if math.isnan(current_price) or math.isnan(or_low):
                logger.debug(
                    f"CRYPTO_ORB_FILTER: FAIL - filter_below_orl=true but price={current_price} or or_low={or_low} is NaN"
                )
                return False
            if not (current_price < or_low):
                logger.debug(
                    f"CRYPTO_ORB_FILTER: FAIL - filter_below_orl=true but price {current_price} >= or_low {or_low}"
                )
                return False

        logger.debug(
            f"CRYPTO_ORB_FILTER: PASS - rel_vol={rel_vol}, direction={direction}, "
            f"price={current_price}, or_high={or_high}, or_low={or_low}, "
            f"filter_above_orh={filter_above_orh}, filter_below_orl={filter_below_orl}"
        )
        return True

    async def _execute_impl(self, inputs: dict[str, Any]) -> NodeOutputs:
        self.api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Polygon API key not found in vault")

        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        max_concurrent_raw = self.params.get("max_concurrent", 10)
        if not isinstance(max_concurrent_raw, int):
            raise ValueError(f"max_concurrent must be an int, got {type(max_concurrent_raw)}")
        max_concurrent: int = max_concurrent_raw

        rate_limit_raw = self.params.get("rate_limit_per_second", 95)
        if not isinstance(rate_limit_raw, int):
            raise ValueError(f"rate_limit_per_second must be an int, got {type(rate_limit_raw)}")
        rate_limit: int = rate_limit_raw

        filtered_bundle = {}
        indicator_data_output: dict[str, Any] = {}
        rate_limiter = RateLimiter(max_per_second=rate_limit)
        total_symbols = len(ohlcv_bundle)
        completed_count = 0
        
        # Check if we should output indicator data
        output_indicator_data = self.params.get(
            "output_indicator_data", self.default_params.get("output_indicator_data", True)
        )

        # Use a bounded worker pool to avoid creating one task per symbol
        queue: asyncio.Queue[tuple[AssetSymbol, list[OHLCVBar]]] = asyncio.Queue()
        for symbol, ohlcv_data in ohlcv_bundle.items():
            if ohlcv_data:  # Only process symbols with data
                queue.put_nowait((symbol, ohlcv_data))

        async def worker(worker_id: int):
            nonlocal completed_count
            while True:
                # Check for cancellation before processing next symbol
                if self._is_stopped:
                    logger.debug(f"Worker {worker_id} stopped due to _is_stopped flag")
                    break

                try:
                    try:
                        symbol, ohlcv_data = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        logger.debug(f"Worker {worker_id} queue empty, finishing")
                        break

                    try:
                        # Respect Polygon rate limit
                        await rate_limiter.acquire()

                        # Check for cancellation again after rate limiting
                        if self._is_stopped:
                            logger.debug(f"Worker {worker_id} stopped after rate limiting")
                            break

                        # Emit early progress to reflect work starting on this symbol
                        try:
                            progress_pre = (
                                (completed_count / total_symbols) * 100 if total_symbols else 0.0
                            )
                            progress_text_pre = f"{completed_count}/{total_symbols}"
                            self.report_progress(progress_pre, progress_text_pre)
                        except Exception:
                            # Progress reporting should never break execution
                            logger.debug("Progress pre-update failed; continuing")

                        # Calculate ORB indicator with error handling
                        try:
                            indicator_result = await self._calculate_orb_indicator(
                                symbol, self.api_key or ""
                            )
                            if self._should_pass_filter(indicator_result, symbol):
                                filtered_bundle[symbol] = ohlcv_data
                                
                                # Store indicator data if enabled
                                if output_indicator_data:
                                    try:
                                        # Convert IndicatorResult to dict format
                                        symbol_key = str(symbol)
                                        indicator_dict = indicator_result.to_dict()
                                        indicator_data_output[symbol_key] = indicator_dict
                                    except Exception as e:
                                        logger.debug(
                                            f"CryptoOrbFilter: Failed to build indicator_data for {symbol}: {e}"
                                        )

                            # Only increment counter on successful completion
                            completed_count += 1
                            progress = (completed_count / total_symbols) * 100
                            progress_text = f"{completed_count}/{total_symbols}"
                            self.report_progress(progress, progress_text)
                        except asyncio.CancelledError:
                            # Coordinate shutdown across workers
                            self.force_stop()
                            raise  # Propagate cancellation
                        except Exception as e:
                            logger.error(
                                f"Error calculating Crypto ORB for {symbol}: {str(e)}", exc_info=True
                            )
                            # Continue without adding to bundle
                    finally:
                        queue.task_done()
                except asyncio.CancelledError:
                    # Also catch cancellations from rate limiter or queue ops
                    self.force_stop()
                    raise

        # Enforce a conservative upper bound for concurrency to maintain fairness and predictable timing
        effective_concurrency = min(max_concurrent, self._max_safe_concurrency)
        self.workers.clear()
        self.workers.extend(
            asyncio.create_task(worker(i)) for i in range(min(effective_concurrency, total_symbols))
        )

        # Gather workers: swallow regular exceptions to allow partial success, but
        # propagate cancellations to honor caller's intent.
        if self.workers:
            results = await asyncio.gather(*self.workers, return_exceptions=True)
            for res in results:
                if isinstance(res, asyncio.CancelledError):
                    # Re-raise cancellation so upstream can handle it
                    raise res
                if isinstance(res, Exception):
                    logger.error(f"Worker task error: {res}", exc_info=True)

        result: dict[str, Any] = {"filtered_ohlcv_bundle": filtered_bundle}
        
        # Output indicator_data if enabled
        if output_indicator_data:
            result["indicator_data"] = indicator_data_output
            logger.info(
                f"CryptoOrbFilter: Outputting indicator_data for {len(indicator_data_output)} symbols"
            )
        else:
            result["indicator_data"] = {}
            logger.info("CryptoOrbFilter: output_indicator_data is False, not outputting indicator data")

        return result

