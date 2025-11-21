import logging
from typing import Any

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    get_type,
)
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicator
from services.indicator_calculators.orb_calculator import calculate_orb
from services.polygon_service import fetch_bars

logger = logging.getLogger(__name__)


class OrbIndicator(BaseIndicator):
    """
    Computes the ORB (Opening Range Breakout) indicator for a single asset.
    Outputs relative volume (RVOL) and direction (bullish/bearish/doji).
    """

    inputs = {"symbol": get_type("AssetSymbol")}
    outputs = {"results": list[IndicatorResult]}
    default_params = {
        "or_minutes": 5,
        "avg_period": 14,
    }
    params_meta = [
        {"name": "or_minutes", "type": "number", "default": 5, "min": 1, "step": 1},
        {"name": "avg_period", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _map_to_indicator_value(
        self, ind_type: IndicatorType, raw: dict[str, Any]
    ) -> IndicatorValue:
        """
        Satisfy BaseIndicator's abstract contract. ORB node uses its own
        _execute_impl path and does not rely on base mapping.
        """
        return IndicatorValue(single=float("nan"))

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        print("=" * 80)
        print("ORB INDICATOR: Starting execution")
        print("=" * 80)
        logger.info("=" * 80)
        logger.info("ORB INDICATOR: Starting execution")
        logger.info("=" * 80)

        symbol_raw = inputs.get("symbol")
        if not symbol_raw or not isinstance(symbol_raw, AssetSymbol):
            logger.warning("No symbol provided to ORB indicator")
            return {"results": []}
        symbol: AssetSymbol = symbol_raw

        print(f"ORB INDICATOR: Processing symbol {symbol.ticker}")
        logger.info(f"ORB INDICATOR: Processing symbol {symbol.ticker}")

        # Get API key
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key or not api_key.strip():
            logger.error("Polygon API key not found in vault")
            return {"results": []}

        # Get parameters
        avg_period_raw = self.params.get("avg_period", 14)
        or_minutes_raw = self.params.get("or_minutes", 5)

        # Type guards
        if not isinstance(avg_period_raw, int | float):
            logger.error(f"avg_period must be a number, got {type(avg_period_raw)}")
            return {"results": []}

        if not isinstance(or_minutes_raw, int | float):
            logger.error(f"or_minutes must be a number, got {type(or_minutes_raw)}")
            return {"results": []}

        avg_period = int(avg_period_raw)
        or_minutes = int(or_minutes_raw)

        # Fetch 5-min bars for enough days to guarantee avg_period trading days
        # avg_period is in trading days, so we need to fetch more calendar days (weekends/holidays)
        # A safe multiplier is 2x + buffer to ensure we get full 14 trading days
        lookback_days = int(avg_period * 2) + 5
        
        fetch_params = {
            "multiplier": 5,
            "timespan": "minute",
            "lookback_period": f"{lookback_days} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }

        try:
            print(f"ORB INDICATOR: Fetching bars with params: {fetch_params}")
            logger.info(f"ORB INDICATOR: Fetching bars with params: {fetch_params}")

            bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)

            if not bars:
                print(f"ORB INDICATOR: No bars fetched for {symbol.ticker}")
                logger.warning(f"No bars fetched for {symbol}")
                return {"results": []}

            print(f"ORB INDICATOR: Fetched {len(bars)} bars for {symbol.ticker}")
            print(
                f"ORB INDICATOR: First bar timestamp: {bars[0]['timestamp']}, last bar timestamp: {bars[-1]['timestamp']}"
            )
            print(f"ORB INDICATOR: First bar: {bars[0]}")
            print(f"ORB INDICATOR: Last bar: {bars[-1]}")

            logger.info(f"ORB Indicator: Fetched {len(bars)} bars for {symbol}")
            logger.info(
                f"ORB Indicator: First bar timestamp: {bars[0]['timestamp']}, last bar timestamp: {bars[-1]['timestamp']}"
            )
            logger.info(f"ORB Indicator: First bar: {bars[0]}")
            logger.info(f"ORB Indicator: Last bar: {bars[-1]}")

            # Use the calculator to calculate ORB indicators
            print("ORB INDICATOR: Calling calculate_orb...")
            logger.info("ORB INDICATOR: Calling calculate_orb...")
            result = calculate_orb(bars, symbol, or_minutes, avg_period)
            print(f"ORB INDICATOR: Got result: {result}")
            logger.info(f"ORB INDICATOR: Got result: {result}")

            if result.get("error"):
                logger.warning(f"ORB calculation error for {symbol}: {result['error']}")
                return {"results": []}

            rel_vol_raw = result.get("rel_vol")
            direction = result.get("direction", "doji")
            or_high = result.get("or_high")
            or_low = result.get("or_low")

            # Type guard for rel_vol
            if not isinstance(rel_vol_raw, int | float):
                logger.error(f"rel_vol must be a number, got {type(rel_vol_raw)}")
                return {"results": []}

            rel_vol = round(float(rel_vol_raw), 2)  # Round to 2 decimal places for readability

            # Get the latest timestamp from bars for the result
            latest_timestamp = bars[-1]["timestamp"] if bars else 0
            
            # Get current price from the latest bar
            current_price_raw = bars[-1]["close"] if bars else None
            current_price = round(current_price_raw, 2) if current_price_raw is not None else None
            
            # Round ORH/ORL to 2 decimal places for readability
            or_high = round(or_high, 2) if or_high is not None else None
            or_low = round(or_low, 2) if or_low is not None else None

            # Special logging for PDD
            is_pdd = symbol.ticker.upper() == "PDD"
            if is_pdd:
                print("=" * 80, flush=True)
                print(f"🔵 PDD ORB INDICATOR RESULTS:", flush=True)
                print(f"   Relative Volume: {rel_vol:.2f}%", flush=True)
                print(f"   Direction: {direction}", flush=True)
                if or_high is not None:
                    print(f"   OR High: ${or_high:.2f}", flush=True)
                else:
                    print("   OR High: N/A", flush=True)
                if or_low is not None:
                    print(f"   OR Low: ${or_low:.2f}", flush=True)
                else:
                    print("   OR Low: N/A", flush=True)
                if current_price is not None:
                    print(f"   Current Price: ${current_price:.2f}", flush=True)
                else:
                    print("   Current Price: N/A", flush=True)
                if current_price and or_high:
                    print(f"   Price vs ORH: ${current_price:.2f} vs ${or_high:.2f} (diff: ${current_price - or_high:.2f})", flush=True)
                if current_price and or_low:
                    print(f"   Price vs ORL: ${current_price:.2f} vs ${or_low:.2f} (diff: ${current_price - or_low:.2f})", flush=True)
                print("=" * 80, flush=True)

            # Return values in lines (for RVOL, ORH, ORL, current_price) and series (for direction)
            values = IndicatorValue(
                lines={
                    "rel_vol": rel_vol,
                    "or_high": or_high,
                    "or_low": or_low,
                    "current_price": current_price
                },
                series=[{"direction": direction}]
            )

            indicator_result = IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=latest_timestamp,
                values=values,
                params=self.params,
            )

            return {"results": [indicator_result.to_dict()]}

        except Exception as e:
            logger.error(f"Error calculating ORB for {symbol}: {e}", exc_info=True)
            return {"results": []}
