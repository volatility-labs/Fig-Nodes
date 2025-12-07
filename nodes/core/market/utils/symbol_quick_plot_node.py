"""
Symbol Quick Plot Node

Allows entering symbols directly into the node to generate charts on demand.
Similar to OHLCVPlotEnhanced but fetches data internally.
"""

import base64
import io
import logging
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
else:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    AssetClass,
    AssetSymbol,
    NodeCategory,
    OHLCVBar,
    get_type,
)
from nodes.base.base_node import Base
from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.sma_calculator import calculate_sma
from services.polygon_service import fetch_bars, fetch_current_snapshot
from services.time_utils import convert_timestamps_to_datetimes

logger = logging.getLogger(__name__)

# Import plotting functions from enhanced plot node
from nodes.core.market.utils.ohlcv_plot_enhanced_node import (
    _encode_fig_to_data_url,
    _normalize_bars,
    _plot_candles,
    _fetch_weekly_bars_for_vbp,
    _calculate_vbp_levels_from_weekly,
    _find_significant_levels,
)
from services.indicator_calculators.vbp_calculator import calculate_vbp


def _parse_symbols(symbols_str: str) -> list[str]:
    """Parse comma-separated symbol string into list of tickers."""
    if not symbols_str or not isinstance(symbols_str, str):
        return []
    
    # Split by comma and clean up whitespace
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    return symbols


def _is_ratio_symbol(ticker: str) -> bool:
    """Check if a ticker is a ratio symbol (e.g., ETHUSD/BTCUSD)."""
    return "/" in ticker and ticker.count("/") == 1


def _parse_ratio_symbol(ticker: str) -> tuple[str, str]:
    """Parse a ratio symbol into numerator and denominator (e.g., ETHUSD/BTCUSD -> ETHUSD, BTCUSD)."""
    if not _is_ratio_symbol(ticker):
        raise ValueError(f"Not a valid ratio symbol: {ticker}")
    parts = ticker.split("/")
    return parts[0].strip(), parts[1].strip()


def _calculate_ratio_bars(
    numerator_bars: list[OHLCVBar],
    denominator_bars: list[OHLCVBar],
) -> list[OHLCVBar]:
    """
    Calculate ratio bars from two OHLCV datasets.
    
    Creates synthetic OHLCV bars where:
    - Each bar's timestamp matches (intersection of timestamps)
    - OHLC values are numerator / denominator
    - Volume is the minimum of the two volumes (or 0 if one is missing)
    
    Args:
        numerator_bars: OHLCV bars for numerator (e.g., ETHUSD)
        denominator_bars: OHLCV bars for denominator (e.g., BTCUSD)
    
    Returns:
        List of synthetic OHLCV bars representing the ratio
    """
    # Sort bars by timestamp to ensure proper alignment
    sorted_num_bars = sorted(numerator_bars, key=lambda b: b["timestamp"])
    sorted_denom_bars = sorted(denominator_bars, key=lambda b: b["timestamp"])
    
    # Create timestamp -> bar maps for efficient lookup
    num_map: dict[int, OHLCVBar] = {bar["timestamp"]: bar for bar in sorted_num_bars}
    denom_map: dict[int, OHLCVBar] = {bar["timestamp"]: bar for bar in sorted_denom_bars}
    
    # Find common timestamps (intersection)
    common_timestamps = sorted(set(num_map.keys()) & set(denom_map.keys()))
    
    if not common_timestamps:
        logger.warning("No common timestamps found between numerator and denominator bars")
        return []
    
    # Log sample values for debugging
    if len(common_timestamps) > 0:
        sample_ts = common_timestamps[0]
        sample_num = num_map[sample_ts]
        sample_denom = denom_map[sample_ts]
        logger.info(
            f"Sample ratio calculation: {sample_num['close']:.2f} / {sample_denom['close']:.2f} = "
            f"{sample_num['close'] / sample_denom['close']:.6f}"
        )
    
    ratio_bars: list[OHLCVBar] = []
    for ts in common_timestamps:
        num_bar = num_map[ts]
        denom_bar = denom_map[ts]
        
        # Calculate ratio for OHLC
        # Avoid division by zero
        if denom_bar["open"] == 0 or denom_bar["high"] == 0 or denom_bar["low"] == 0 or denom_bar["close"] == 0:
            logger.debug(f"Skipping bar at {ts}: zero denominator value")
            continue
        
        ratio_open = num_bar["open"] / denom_bar["open"]
        ratio_close = num_bar["close"] / denom_bar["close"]
        
        # For high/low, we need to consider all possible combinations
        # High ratio occurs when numerator is high and denominator is low
        # Low ratio occurs when numerator is low and denominator is high
        ratio_high_candidates = [
            num_bar["high"] / denom_bar["low"],  # Highest possible ratio
            num_bar["open"] / denom_bar["open"],
            num_bar["close"] / denom_bar["close"],
        ]
        ratio_low_candidates = [
            num_bar["low"] / denom_bar["high"],  # Lowest possible ratio
            num_bar["open"] / denom_bar["open"],
            num_bar["close"] / denom_bar["close"],
        ]
        
        ratio_high = max(ratio_high_candidates)
        ratio_low = min(ratio_low_candidates)
        
        # Ensure high >= open, close and low <= open, close
        ratio_high = max(ratio_high, ratio_open, ratio_close)
        ratio_low = min(ratio_low, ratio_open, ratio_close)
        
        # Volume is minimum of the two (or 0 if either is missing)
        ratio_volume = min(num_bar["volume"], denom_bar["volume"])
        
        # Get optional fields safely
        num_vwap = num_bar.get("vwap")
        denom_vwap = denom_bar.get("vwap")
        num_transactions = num_bar.get("transactions")
        denom_transactions = denom_bar.get("transactions")
        
        ratio_bar: OHLCVBar = {
            "timestamp": ts,
            "open": ratio_open,
            "high": ratio_high,
            "low": ratio_low,
            "close": ratio_close,
            "volume": ratio_volume,
        }
        
        # Add optional fields if both have them
        if num_vwap and denom_vwap:
            ratio_bar["vwap"] = num_vwap / denom_vwap
        if num_transactions and denom_transactions:
            ratio_bar["transactions"] = min(num_transactions, denom_transactions)
        ratio_bars.append(ratio_bar)
    
    if ratio_bars:
        min_ratio = min(b["close"] for b in ratio_bars)
        max_ratio = max(b["close"] for b in ratio_bars)
        logger.info(
            f"Calculated {len(ratio_bars)} ratio bars from {len(numerator_bars)} numerator and {len(denominator_bars)} denominator bars. "
            f"Ratio range: {min_ratio:.6f} to {max_ratio:.6f}"
        )
    else:
        logger.warning("No ratio bars calculated")
    return ratio_bars


def _aggregate_bars(bars: list[OHLCVBar], group_size: int) -> list[OHLCVBar]:
    """
    Aggregate consecutive bars into larger bars of size `group_size`.
    Example: aggregate 1h bars into 4h bars when group_size=4.
    """
    if group_size <= 1 or len(bars) <= 1:
        return bars

    aggregated: list[OHLCVBar] = []
    for i in range(0, len(bars), group_size):
        chunk = bars[i : i + group_size]
        if not chunk:
            continue
        open_price = chunk[0]["open"]
        close_price = chunk[-1]["close"]
        high_price = max(b["high"] for b in chunk)
        low_price = min(b["low"] for b in chunk)
        volume_sum = sum(b.get("volume", 0.0) for b in chunk)
        timestamp = chunk[-1]["timestamp"]
        agg_bar: OHLCVBar = {
            "timestamp": timestamp,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume_sum,
        }
        if chunk[-1].get("vwap") is not None:
            agg_bar["vwap"] = chunk[-1]["vwap"]
        if chunk[-1].get("transactions") is not None:
            agg_bar["transactions"] = chunk[-1]["transactions"]
        aggregated.append(agg_bar)
    return aggregated


def _estimate_required_bars(lookback_period: str, multiplier: int, timespan: str) -> int | None:
    """
    Rough estimate of bars needed based on lookback, multiplier, and timespan.
    Currently only tailored for hour-based timespans.
    """
    parts = lookback_period.split()
    if len(parts) != 2:
        return None
    try:
        amount = int(parts[0])
    except ValueError:
        return None
    unit = parts[1].lower()

    if timespan == "hour":
        hours_per_unit = {
            "day": 24,
            "days": 24,
            "week": 24 * 7,
            "weeks": 24 * 7,
            "month": 24 * 30,
            "months": 24 * 30,
            "year": 24 * 365,
            "years": 24 * 365,
        }.get(unit)
        if hours_per_unit is None:
            return None
        total_hours = hours_per_unit * amount
        hours_per_bar = max(1, multiplier)
        return max(1, total_hours // hours_per_bar)
    return None


def _create_asset_symbol(ticker: str, asset_class: AssetClass = AssetClass.CRYPTO) -> AssetSymbol:
    """Create an AssetSymbol from a ticker string."""
    return AssetSymbol(ticker=ticker, asset_class=asset_class)


class SymbolQuickPlot(Base):
    """
    Quick plot node that accepts symbols directly and generates charts.
    
    - Input: symbols as comma-separated text (e.g., "BTCUSD,ETHUSD,SOLUSD")
    - Supports ratio symbols like "ETHUSD/BTCUSD" to plot ETH priced in BTC
    - Fetches OHLCV data internally from Polygon API
    - For ratio symbols, fetches both numerator and denominator, calculates ratio bars
    - Generates charts similar to OHLCVPlotEnhanced
    - Output: 'images' -> Dict[str, str] mapping symbol to data URL
    """

    inputs = {}  # No inputs required - symbols come from params
    outputs = {
        "images": get_type("ConfigDict"),
    }

    CATEGORY = NodeCategory.MARKET
    
    default_params = {
        "symbols": "",  # Comma-separated symbols (e.g., "BTCUSD,ETHUSD")
        "asset_class": "crypto",  # "crypto" or "stocks"
        "interval": None,  # If set, overrides multiplier and timespan
        "multiplier": 1,
        "timespan": "day",
        "lookback_period": "3 months",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
        "max_symbols": 10,
        "overlay1_period": 20,
        "overlay1_type": "SMA",
        "overlay2_period": 50,
        "overlay2_type": "SMA",
        "show_vbp_levels": False,
        "vbp_bins": 50,
        "vbp_num_levels": 5,
        "vbp_lookback_years": 2,
        "vbp_lookback_years_2": None,
        "vbp_use_dollar_weighted": False,
        "vbp_use_close_only": False,
        "vbp_style": "dashed",
        "dpi": 150,
    }

    params_meta = [
        {
            "name": "symbols",
            "type": "text",
            "default": "",
            "description": "Comma-separated symbols (e.g., BTCUSD,ETHUSD,SOLUSD). Supports ratio symbols like ETHUSD/BTCUSD to plot ETH priced in BTC.",
        },
        {
            "name": "asset_class",
            "type": "combo",
            "default": "crypto",
            "options": ["crypto", "stocks"],
            "description": "Asset class for symbols",
        },
        {
            "name": "interval",
            "type": "combo",
            "default": None,
            "options": [None, "1min", "5min", "15min", "30min", "1hr", "4hr", "day", "week", "month"],
            "description": "Bar interval (overrides multiplier/timespan if set)",
        },
        {
            "name": "multiplier",
            "type": "number",
            "default": 1,
            "min": 1,
            "max": 100,
            "step": 1,
            "description": "Bar multiplier (ignored if interval is set)",
        },
        {
            "name": "timespan",
            "type": "combo",
            "default": "day",
            "options": ["minute", "hour", "day", "week", "month", "quarter", "year"],
            "description": "Bar timespan (ignored if interval is set)",
        },
        {
            "name": "lookback_period",
            "type": "combo",
            "default": "3 months",
            "options": [
                "1 day",
                "3 days",
                "1 week",
                "2 weeks",
                "1 month",
                "2 months",
                "3 months",
                "4 months",
                "6 months",
                "9 months",
                "1 year",
                "18 months",
                "2 years",
                "3 years",
                "5 years",
                "10 years",
            ],
            "description": "Lookback period for fetching bars",
        },
        {
            "name": "adjusted",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "description": "Use adjusted prices",
        },
        {
            "name": "sort",
            "type": "combo",
            "default": "asc",
            "options": ["asc", "desc"],
            "description": "Sort order",
        },
        {
            "name": "limit",
            "type": "number",
            "default": 5000,
            "min": 1,
            "max": 50000,
            "step": 1,
            "description": "Maximum number of bars to fetch",
        },
        {
            "name": "max_symbols",
            "type": "number",
            "default": 10,
            "min": 1,
            "max": 50,
            "step": 1,
            "description": "Maximum number of symbols to plot",
        },
        {
            "name": "overlay1_type",
            "type": "combo",
            "default": "SMA",
            "options": ["SMA", "EMA"],
            "description": "First overlay type",
        },
        {
            "name": "overlay1_period",
            "type": "number",
            "default": 20,
            "min": 2,
            "max": 999,
            "step": 1,
            "description": "First overlay period",
        },
        {
            "name": "overlay2_type",
            "type": "combo",
            "default": "SMA",
            "options": ["SMA", "EMA"],
            "description": "Second overlay type",
        },
        {
            "name": "overlay2_period",
            "type": "number",
            "default": 50,
            "min": 2,
            "max": 999,
            "step": 1,
            "description": "Second overlay period",
        },
        {
            "name": "show_vbp_levels",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show Volume-by-Price levels",
        },
        {
            "name": "vbp_bins",
            "type": "number",
            "default": 50,
            "min": 10,
            "max": 200,
            "step": 5,
            "description": "Number of VBP bins",
        },
        {
            "name": "vbp_num_levels",
            "type": "number",
            "default": 5,
            "min": 1,
            "max": 20,
            "step": 1,
            "description": "Number of VBP levels to display",
        },
        {
            "name": "vbp_lookback_years",
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 10,
            "step": 1,
            "description": "VBP lookback period (years)",
        },
        {
            "name": "vbp_lookback_years_2",
            "type": "number",
            "default": None,
            "min": 1,
            "max": 10,
            "step": 1,
            "description": "Optional second VBP lookback period (years)",
        },
        {
            "name": "vbp_use_dollar_weighted",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Use dollar-weighted VBP",
        },
        {
            "name": "vbp_use_close_only",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Use close prices only for VBP",
        },
        {
            "name": "vbp_style",
            "type": "combo",
            "default": "dashed",
            "options": ["solid", "dashed", "dotted"],
            "description": "VBP level line style",
        },
        {
            "name": "dpi",
            "type": "number",
            "default": 150,
            "min": 100,
            "max": 300,
            "step": 50,
            "description": "Image DPI (dots per inch)",
        },
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the quick plot node."""
        # Get symbols from params
        symbols_str = str(self.params.get("symbols", "")).strip()
        logger.info(f"SymbolQuickPlot node {self.id}: symbols_str='{symbols_str}', params={self.params}")
        if not symbols_str:
            logger.warning(f"SymbolQuickPlot node {self.id}: No symbols provided")
            return {"images": {}}

        # Parse symbols
        tickers = _parse_symbols(symbols_str)
        logger.info(f"SymbolQuickPlot node {self.id}: Parsed tickers={tickers}")
        if not tickers:
            logger.warning(f"SymbolQuickPlot node {self.id}: No valid symbols found")
            return {"images": {}}

        # Limit to max_symbols
        max_syms = int(self.params.get("max_symbols", 10))
        tickers = tickers[:max_syms]

        # Get asset class
        asset_class_str = str(self.params.get("asset_class", "crypto")).lower()
        asset_class = AssetClass.CRYPTO if asset_class_str == "crypto" else AssetClass.STOCKS

        # Get API key
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("POLYGON_API_KEY is required but not set in vault")

        # Handle interval parameter (like PolygonBatchCustomBars)
        interval = self.params.get("interval")
        if interval:
            # Convert interval to multiplier/timespan
            interval_lower = str(interval).lower()
            if interval_lower == "1min":
                multiplier, timespan = 1, "minute"
            elif interval_lower == "5min":
                multiplier, timespan = 5, "minute"
            elif interval_lower == "15min":
                multiplier, timespan = 15, "minute"
            elif interval_lower == "30min":
                multiplier, timespan = 30, "minute"
            elif interval_lower == "1hr":
                multiplier, timespan = 1, "hour"
            elif interval_lower == "4hr":
                multiplier, timespan = 4, "hour"
            elif interval_lower == "day":
                multiplier, timespan = 1, "day"
            elif interval_lower == "week":
                multiplier, timespan = 1, "week"
            elif interval_lower == "month":
                multiplier, timespan = 1, "month"
            else:
                multiplier, timespan = 1, "day"
        else:
            multiplier = int(self.params.get("multiplier", 1))
            timespan = str(self.params.get("timespan", "day"))

        # Get fetch parameters
        fetch_params = {
            "multiplier": multiplier,
            "timespan": timespan,
            "lookback_period": str(self.params.get("lookback_period", "3 months")),
            "adjusted": bool(self.params.get("adjusted", True)),
            "sort": str(self.params.get("sort", "asc")),
            "limit": int(self.params.get("limit", 5000)),
        }

        # Get plot parameters
        overlay1_type = str(self.params.get("overlay1_type", "SMA"))
        overlay1_period = int(self.params.get("overlay1_period", 20))
        overlay2_type = str(self.params.get("overlay2_type", "SMA"))
        overlay2_period = int(self.params.get("overlay2_period", 50))
        show_vbp = bool(self.params.get("show_vbp_levels", False))
        vbp_bins = int(self.params.get("vbp_bins", 50))
        vbp_num_levels = int(self.params.get("vbp_num_levels", 5))
        vbp_lookback_years = int(self.params.get("vbp_lookback_years", 2))
        vbp_lookback_years_2_raw = self.params.get("vbp_lookback_years_2")
        vbp_lookback_years_2: int | None = None
        if vbp_lookback_years_2_raw is not None:
            if isinstance(vbp_lookback_years_2_raw, int | float):
                vbp_lookback_years_2 = int(vbp_lookback_years_2_raw)
        vbp_use_dollar_weighted = bool(self.params.get("vbp_use_dollar_weighted", False))
        vbp_use_close_only = bool(self.params.get("vbp_use_close_only", False))
        vbp_style = str(self.params.get("vbp_style", "dashed"))
        dpi = int(self.params.get("dpi", 150))

        # Determine maximum overlay period for warm-up calculation
        max_overlay_period = max(overlay1_period if overlay1_period > 0 else 0, overlay2_period if overlay2_period > 0 else 0)
        
        # Extend lookback_period to ensure we have enough data for moving average warm-up
        # We need at least max_overlay_period extra bars beyond the display period
        original_lookback = str(self.params.get("lookback_period", "3 months"))
        
        # Parse the original lookback period
        lookback_parts = original_lookback.split()
        if len(lookback_parts) == 2:
            try:
                amount = int(lookback_parts[0])
                unit = lookback_parts[1].lower()
                
                # Estimate bars needed for warm-up based on timespan
                # For daily bars, we need max_overlay_period extra days
                # For hourly bars, we need max_overlay_period extra hours, etc.
                if max_overlay_period > 0:
                    if timespan == "day":
                        # Add extra days for warm-up (round up to nearest month for simplicity)
                        warmup_days = max_overlay_period
                        if unit == "day" or unit == "days":
                            amount += warmup_days
                        elif unit == "week" or unit == "weeks":
                            # Convert warmup days to weeks (round up)
                            warmup_weeks = (warmup_days + 6) // 7
                            amount += warmup_weeks
                        elif unit == "month" or unit == "months":
                            # Convert warmup days to months (round up, ~30 days per month)
                            warmup_months = (warmup_days + 29) // 30
                            amount += warmup_months
                        elif unit == "year" or unit == "years":
                            # Convert warmup days to years (round up, ~365 days per year)
                            warmup_years = (warmup_days + 364) // 365
                            amount += warmup_years
                    elif timespan == "week":
                        # Add extra weeks for warm-up
                        warmup_weeks = max_overlay_period
                        if unit == "week" or unit == "weeks":
                            amount += warmup_weeks
                        elif unit == "month" or unit == "months":
                            # Convert warmup weeks to months (round up, ~4.33 weeks per month)
                            warmup_months = (warmup_weeks + 3) // 4
                            amount += warmup_months
                        elif unit == "year" or unit == "years":
                            # Convert warmup weeks to years (round up, ~52 weeks per year)
                            warmup_years = (warmup_weeks + 51) // 52
                            amount += warmup_years
                    elif timespan == "month":
                        # Add extra months for warm-up
                        warmup_months = max_overlay_period
                        if unit == "month" or unit == "months":
                            amount += warmup_months
                        elif unit == "year" or unit == "years":
                            # Convert warmup months to years (round up, 12 months per year)
                            warmup_years = (warmup_months + 11) // 12
                            amount += warmup_years
                    elif timespan == "hour":
                        # Add extra hours for warm-up
                        warmup_hours = max_overlay_period
                        if unit == "day" or unit == "days":
                            # Convert warmup hours to days (round up, ~24 hours per day)
                            warmup_days = (warmup_hours + 23) // 24
                            amount += warmup_days
                        elif unit == "week" or unit == "weeks":
                            warmup_weeks = (warmup_hours + 167) // 168  # 7 * 24 = 168 hours per week
                            amount += warmup_weeks
                        elif unit == "month" or unit == "months":
                            warmup_months = (warmup_hours + 719) // 720  # 30 * 24 = 720 hours per month
                            amount += warmup_months
                    elif timespan == "minute":
                        # Add extra minutes for warm-up
                        warmup_minutes = max_overlay_period
                        if unit == "day" or unit == "days":
                            warmup_days = (warmup_minutes + 1439) // 1440  # 24 * 60 = 1440 minutes per day
                            amount += warmup_days
                        elif unit == "hour" or unit == "hours":
                            warmup_hours = (warmup_minutes + 59) // 60
                            amount += warmup_hours
                    
                    # Update fetch_params with extended lookback
                    fetch_params["lookback_period"] = f"{amount} {unit}"
                    logger.debug(
                        f"Extended lookback_period from '{original_lookback}' to '{fetch_params['lookback_period']}' "
                        f"to ensure warm-up data for {max_overlay_period}-period moving averages"
                    )
            except (ValueError, IndexError):
                # If parsing fails, use original lookback
                logger.warning(f"Could not parse lookback_period '{original_lookback}', using as-is")

        images: dict[str, str] = {}

        # Fetch and plot each symbol
        for ticker in tickers:
            try:
                bars: list[OHLCVBar] | None = None
                metadata: dict[str, Any] | None = None
                symbol: AssetSymbol | None = None
                is_ratio = _is_ratio_symbol(ticker)
                
                # Check if this is a ratio symbol (e.g., ETHUSD/BTCUSD)
                if is_ratio:
                    # Parse ratio symbol
                    num_ticker, denom_ticker = _parse_ratio_symbol(ticker)
                    logger.info(f"Processing ratio symbol {ticker} = {num_ticker}/{denom_ticker}")
                    
                    # Fetch numerator and denominator data
                    num_symbol = _create_asset_symbol(num_ticker, asset_class)
                    denom_symbol = _create_asset_symbol(denom_ticker, asset_class)
                    
                    logger.info(f"Fetching numerator data for {num_ticker}...")
                    num_bars, num_metadata = await fetch_bars(num_symbol, api_key, fetch_params)
                    
                    logger.info(f"Fetching denominator data for {denom_ticker}...")
                    denom_bars, denom_metadata = await fetch_bars(denom_symbol, api_key, fetch_params)
                    
                    # If we didn't get enough bars for the requested lookback, try a 1h fallback and aggregate
                    estimated_needed = _estimate_required_bars(str(self.params.get("lookback_period", "3 months")), multiplier, timespan)
                    shortfall = estimated_needed is not None and (len(num_bars or []) < max(10, int(0.8 * estimated_needed)) or len(denom_bars or []) < max(10, int(0.8 * estimated_needed)))
                    can_fallback = multiplier > 1  # allow fallback for multi-hour by using minute->hour
                    if can_fallback and shortfall:
                        # Expand lookback to ensure enough bars for display + MA warmup
                        total_needed_bars = (estimated_needed or 0) + max_overlay_period
                        hours_needed = max(1, total_needed_bars * multiplier)
                        days_needed = (hours_needed + 23) // 24
                        # Add a little buffer
                        days_needed += 14
                        fallback_lookback = f"{days_needed} days"
                        # Use minute data with 60-min bars to ensure we can aggregate reliably
                        fallback_base_minutes = 60  # 1h bars
                        target_minutes = multiplier * 60
                        group_size = max(1, target_minutes // fallback_base_minutes)
                        logger.warning(
                            f"Retrying with 1h-minute data for {ticker} because only {len(num_bars)} / {len(denom_bars)} bars received; "
                            f"needed ~{estimated_needed} for lookback {self.params.get('lookback_period')}, "
                            f"requesting expanded lookback {fallback_lookback}"
                        )
                        fallback_params = {
                            **fetch_params,
                            "multiplier": fallback_base_minutes,  # 60-minute bars via minute timespan
                            "timespan": "minute",
                            "sort": "asc",
                            "lookback_period": fallback_lookback,
                        }
                        num_bars, num_metadata = await fetch_bars(num_symbol, api_key, fallback_params)
                        denom_bars, denom_metadata = await fetch_bars(denom_symbol, api_key, fallback_params)
                        # Aggregate back to original multiplier (e.g., 60-min -> 4h)
                        num_bars = _aggregate_bars(num_bars, group_size) if num_bars else num_bars
                        denom_bars = _aggregate_bars(denom_bars, group_size) if denom_bars else denom_bars
                        logger.info(
                            f"Fallback fetched {len(num_bars) if num_bars else 0} numerator bars and {len(denom_bars) if denom_bars else 0} denominator bars after aggregation"
                        )
                    
                    if not num_bars or len(num_bars) < 10:
                        logger.warning(f"Insufficient numerator data for {num_ticker}: {len(num_bars) if num_bars else 0} bars")
                        continue
                    
                    if not denom_bars or len(denom_bars) < 10:
                        logger.warning(f"Insufficient denominator data for {denom_ticker}: {len(denom_bars) if denom_bars else 0} bars")
                        continue
                    
                    # Calculate ratio bars
                    bars = _calculate_ratio_bars(num_bars, denom_bars)
                    metadata = num_metadata  # Use numerator metadata
                    symbol = num_symbol  # Use numerator symbol for VBP (will skip VBP for ratios)
                    
                    if not bars or len(bars) < 10:
                        logger.warning(f"Insufficient ratio data for {ticker}: {len(bars) if bars else 0} bars")
                        continue
                else:
                    # Regular symbol - fetch normally
                    symbol = _create_asset_symbol(ticker, asset_class)
                    
                    # Fetch OHLCV data
                    logger.info(f"Fetching data for {ticker}...")
                    bars, metadata = await fetch_bars(symbol, api_key, fetch_params)
                    
                    if not bars or len(bars) < 10:
                        logger.warning(f"Insufficient data for {ticker}: {len(bars) if bars else 0} bars")
                        continue

                # Normalize bars - keep full set for warm-up calculation
                full_norm = _normalize_bars(bars)
                if not full_norm:
                    logger.warning(f"No valid bars after normalization for {ticker}")
                    continue
                
                logger.info(
                    f"Normalized {len(full_norm)} bars for {ticker} "
                    f"(ratio symbol: {is_ratio}, interval: {interval or f'{multiplier}{timespan}'})"
                )

                # Determine how many bars to display based on original lookback_period
                # We fetched more data for warm-up, but only display the requested period
                norm = full_norm
                original_lookback_str = str(self.params.get("lookback_period", "3 months"))
                lookback_parts = original_lookback_str.split()
                if len(lookback_parts) == 2:
                    try:
                        display_amount = int(lookback_parts[0])
                        display_unit = lookback_parts[1].lower()
                        
                        # Estimate number of bars to display based on timespan
                        if timespan == "day":
                            if display_unit == "day" or display_unit == "days":
                                display_bars = display_amount
                            elif display_unit == "week" or display_unit == "weeks":
                                display_bars = display_amount * 7  # ~7 trading days per week
                            elif display_unit == "month" or display_unit == "months":
                                display_bars = display_amount * 30  # ~30 trading days per month
                            elif display_unit == "year" or display_unit == "years":
                                display_bars = display_amount * 365  # ~365 trading days per year
                            else:
                                display_bars = None
                        elif timespan == "week":
                            if display_unit == "week" or display_unit == "weeks":
                                display_bars = display_amount
                            elif display_unit == "month" or display_unit == "months":
                                display_bars = display_amount * 4  # ~4 weeks per month
                            elif display_unit == "year" or display_unit == "years":
                                display_bars = display_amount * 52  # ~52 weeks per year
                            else:
                                display_bars = None
                        elif timespan == "month":
                            if display_unit == "month" or display_unit == "months":
                                display_bars = display_amount
                            elif display_unit == "year" or display_unit == "years":
                                display_bars = display_amount * 12  # 12 months per year
                            else:
                                display_bars = None
                        elif timespan == "hour":
                            # Account for multiplier (e.g., 4hr bars means multiplier=4)
                            if display_unit == "day" or display_unit == "days":
                                display_bars = (display_amount * 24) // multiplier  # 24 hours per day / multiplier
                            elif display_unit == "week" or display_unit == "weeks":
                                display_bars = (display_amount * 168) // multiplier  # 7 * 24 = 168 hours per week / multiplier
                            elif display_unit == "month" or display_unit == "months":
                                display_bars = (display_amount * 720) // multiplier  # 30 * 24 = 720 hours per month / multiplier
                            else:
                                display_bars = None
                        elif timespan == "minute":
                            # Account for multiplier (e.g., 15min bars means multiplier=15)
                            if display_unit == "day" or display_unit == "days":
                                display_bars = (display_amount * 1440) // multiplier  # 24 * 60 = 1440 minutes per day / multiplier
                            elif display_unit == "hour" or display_unit == "hours":
                                display_bars = (display_amount * 60) // multiplier  # 60 minutes per hour / multiplier
                            else:
                                display_bars = None
                        else:
                            display_bars = None
                        
                        # Only display the requested number of bars (most recent)
                        if display_bars is not None and display_bars > 0:
                            if len(full_norm) > display_bars:
                                norm = full_norm[-display_bars:]
                                logger.info(
                                    f"Displaying {len(norm)} bars (requested {display_bars} for {original_lookback_str}) "
                                    f"from {len(full_norm)} fetched bars for {ticker}"
                                )
                            else:
                                logger.warning(
                                    f"Only have {len(full_norm)} bars but requested {display_bars} for {original_lookback_str} "
                                    f"(interval: {interval or f'{multiplier}{timespan}'}) for {ticker}"
                                )
                    except (ValueError, IndexError):
                        # If parsing fails, use all bars
                        pass

                # Calculate overlays using ALL available bars (full_norm) for warm-up
                # This ensures moving averages are properly initialized before the display range
                overlays: list[tuple[list[float | None], str, str]] = []
                
                # Extract close prices from full dataset for calculation
                calc_closes = [bar[4] for bar in full_norm]
                
                # Log sample values for ratio symbols to verify calculation
                if is_ratio and len(calc_closes) > 0:
                    logger.info(
                        f"EMA calculation for {ticker}: Using {len(calc_closes)} close prices. "
                        f"Sample closes: first={calc_closes[0]:.6f}, last={calc_closes[-1]:.6f}, "
                        f"min={min(calc_closes):.6f}, max={max(calc_closes):.6f}"
                    )
                
                if overlay1_period > 0:
                    # Calculate overlay on full dataset (warm-up)
                    if overlay1_type == "SMA":
                        sma1_result = calculate_sma(calc_closes, period=overlay1_period)
                        calc_overlay1_values = sma1_result.get("sma", [])
                    else:  # EMA
                        ema1_result = calculate_ema(calc_closes, period=overlay1_period)
                        calc_overlay1_values = ema1_result.get("ema", [])
                    
                    # Slice to match display range (take last len(norm) values)
                    if len(calc_overlay1_values) >= len(norm):
                        overlay1_values = calc_overlay1_values[-len(norm):]
                    else:
                        # If not enough values, pad with None at the beginning
                        overlay1_values = [None] * (len(norm) - len(calc_overlay1_values)) + calc_overlay1_values
                    
                    non_none_count = sum(1 for v in overlay1_values if v is not None)
                    logger.info(
                        f"Computed {overlay1_type}({overlay1_period}) for {ticker}: {len(overlay1_values)} total, "
                        f"{non_none_count} non-None in plot of {len(norm)} bars (calculated on {len(full_norm)} bars)"
                    )
                    # Log last few values for ratio symbols to verify alignment
                    if is_ratio and len(overlay1_values) > 0 and len(norm) > 0:
                        last_price = norm[-1][4]  # Close price of last bar
                        last_ema = overlay1_values[-1]
                        ema_str = f"{last_ema:.6f}" if last_ema is not None else "None"
                        comparison = ">" if (last_ema is not None and last_price > last_ema) else ("<=" if last_ema is not None else "N/A")
                        logger.info(
                            f"Last bar for {ticker}: price={last_price:.6f}, {overlay1_type}({overlay1_period})={ema_str}, "
                            f"price {comparison} EMA"
                        )
                    overlays.append((overlay1_values, f"{overlay1_type}({overlay1_period})", "#FF6B35"))

                if overlay2_period > 0:
                    # Calculate overlay on full dataset (warm-up)
                    if overlay2_type == "SMA":
                        sma2_result = calculate_sma(calc_closes, period=overlay2_period)
                        calc_overlay2_values = sma2_result.get("sma", [])
                    else:  # EMA
                        ema2_result = calculate_ema(calc_closes, period=overlay2_period)
                        calc_overlay2_values = ema2_result.get("ema", [])
                    
                    # Slice to match display range (take last len(norm) values)
                    if len(calc_overlay2_values) >= len(norm):
                        overlay2_values = calc_overlay2_values[-len(norm):]
                    else:
                        # If not enough values, pad with None at the beginning
                        overlay2_values = [None] * (len(norm) - len(calc_overlay2_values)) + calc_overlay2_values
                    
                    non_none_count = sum(1 for v in overlay2_values if v is not None)
                    logger.debug(
                        f"Computed {overlay2_type}({overlay2_period}) for {ticker}: {len(overlay2_values)} total, "
                        f"{non_none_count} non-None in plot of {len(norm)} bars (calculated on {len(full_norm)} bars)"
                    )
                    overlays.append((overlay2_values, f"{overlay2_type}({overlay2_period})", "#4ECDC4"))

                # Calculate VBP levels if enabled (skip for ratio symbols)
                vbp_levels: list[float] | None = None
                if show_vbp and not is_ratio:
                    try:
                        logger.debug(f"Fetching weekly bars for VBP calculation ({vbp_lookback_years} years) for {ticker}")
                        weekly_bars_1 = await _fetch_weekly_bars_for_vbp(
                            symbol, api_key, vbp_lookback_years
                        )
                        logger.debug(f"Fetched {len(weekly_bars_1) if weekly_bars_1 else 0} weekly bars for period 1 for {ticker}")
                        
                        all_vbp_levels: list[float] = []
                        if weekly_bars_1:
                            levels_1 = _calculate_vbp_levels_from_weekly(
                                weekly_bars_1,
                                vbp_bins,
                                vbp_num_levels,
                                vbp_use_dollar_weighted,
                                vbp_use_close_only,
                            )
                            if levels_1:
                                all_vbp_levels.extend(levels_1)
                                logger.debug(f"Calculated {len(levels_1)} VBP levels for period 1 for {ticker}")
                        
                        # Calculate levels for second period if specified
                        if vbp_lookback_years_2 is not None:
                            logger.debug(f"Fetching weekly bars for VBP calculation (period 2: {vbp_lookback_years_2} years) for {ticker}")
                            weekly_bars_2 = await _fetch_weekly_bars_for_vbp(
                                symbol, api_key, vbp_lookback_years_2
                            )
                            logger.debug(f"Fetched {len(weekly_bars_2) if weekly_bars_2 else 0} weekly bars for period 2 for {ticker}")
                            if weekly_bars_2:
                                levels_2 = _calculate_vbp_levels_from_weekly(
                                    weekly_bars_2,
                                    vbp_bins,
                                    vbp_num_levels,
                                    vbp_use_dollar_weighted,
                                    vbp_use_close_only,
                                )
                                if levels_2:
                                    all_vbp_levels.extend(levels_2)
                                    logger.debug(f"Calculated {len(levels_2)} VBP levels for period 2 for {ticker}")
                        
                        # Deduplicate levels (keep unique price levels)
                        if all_vbp_levels:
                            all_vbp_levels.sort()
                            deduplicated: list[float] = []
                            for level in all_vbp_levels:
                                if not deduplicated:
                                    deduplicated.append(level)
                                else:
                                    # Check if level is too close to previous level (within 0.01%)
                                    last_level = deduplicated[-1]
                                    tolerance = last_level * 0.0001  # 0.01%
                                    if abs(level - last_level) > tolerance:
                                        deduplicated.append(level)
                            vbp_levels = deduplicated[:vbp_num_levels]  # Limit to requested number
                            logger.debug(f"Final VBP levels for {ticker}: {len(vbp_levels)} levels")
                    except Exception as e:
                        logger.warning(f"Failed to calculate VBP levels for {ticker}: {e}")
                        vbp_levels = None

                # Fetch current price for annotation
                fresh_price: float | None = None
                if is_ratio:
                    # For ratio symbols, use the latest close price from the ratio bars
                    if bars and len(bars) > 0:
                        fresh_price = bars[-1]["close"]
                else:
                    try:
                        fresh_price, _ = await fetch_current_snapshot(symbol, api_key)
                    except Exception as e:
                        logger.debug(f"Could not fetch snapshot for {ticker}: {e}")

                # Create figure
                plt.close('all')  # Clean state
                fig, ax = plt.subplots(figsize=(3.2, 2.2))
                fig.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.15)

                # Plot chart
                _plot_candles(
                    ax=ax,
                    series=norm,
                    overlays=overlays if overlays else None,
                    vbp_levels=vbp_levels,
                    vbp_color="#FF6B35",
                    vbp_style=vbp_style,
                    asset_class=asset_class,
                )

                ax.set_title(f"{ticker}", fontsize=10, fontweight='bold', pad=5)
                ax.set_ylabel("Price", fontsize=8)
                ax.tick_params(labelsize=7)

                # Encode to data URL
                image_data = _encode_fig_to_data_url(fig)
                images[ticker] = image_data

                # Emit partial result
                self.emit_partial_result({"images": {ticker: image_data}})

                logger.info(f"✅ Generated chart for {ticker}")

            except Exception as e:
                logger.error(f"Failed to plot {ticker}: {e}", exc_info=True)
                continue

        logger.info(
            "SymbolQuickPlot node %s: Generated %s images (%s)",
            self.id,
            len(images),
            list(images.keys()),
        )
        return {"images": images}

