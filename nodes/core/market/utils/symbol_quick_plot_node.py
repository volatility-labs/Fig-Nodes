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


def _create_asset_symbol(ticker: str, asset_class: AssetClass = AssetClass.CRYPTO) -> AssetSymbol:
    """Create an AssetSymbol from a ticker string."""
    return AssetSymbol(ticker=ticker, asset_class=asset_class)


class SymbolQuickPlot(Base):
    """
    Quick plot node that accepts symbols directly and generates charts.
    
    - Input: symbols as comma-separated text (e.g., "BTCUSD,ETHUSD,SOLUSD")
    - Fetches OHLCV data internally from Polygon API
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
            "description": "Comma-separated symbols (e.g., BTCUSD,ETHUSD,SOLUSD)",
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
            "max": 200,
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
            "max": 200,
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
                # Create AssetSymbol
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
                            if display_unit == "day" or display_unit == "days":
                                display_bars = display_amount * 24  # 24 hours per day
                            elif display_unit == "week" or display_unit == "weeks":
                                display_bars = display_amount * 168  # 7 * 24 = 168 hours per week
                            elif display_unit == "month" or display_unit == "months":
                                display_bars = display_amount * 720  # 30 * 24 = 720 hours per month
                            else:
                                display_bars = None
                        elif timespan == "minute":
                            if display_unit == "day" or display_unit == "days":
                                display_bars = display_amount * 1440  # 24 * 60 = 1440 minutes per day
                            elif display_unit == "hour" or display_unit == "hours":
                                display_bars = display_amount * 60  # 60 minutes per hour
                            else:
                                display_bars = None
                        else:
                            display_bars = None
                        
                        # Only display the requested number of bars (most recent)
                        if display_bars is not None and display_bars > 0:
                            if len(full_norm) > display_bars:
                                norm = full_norm[-display_bars:]
                                logger.debug(
                                    f"Displaying {len(norm)} bars (requested {display_bars}) "
                                    f"from {len(full_norm)} fetched bars (warm-up included) for {ticker}"
                                )
                    except (ValueError, IndexError):
                        # If parsing fails, use all bars
                        pass

                # Calculate overlays using ALL available bars (full_norm) for warm-up
                # This ensures moving averages are properly initialized before the display range
                overlays: list[tuple[list[float | None], str, str]] = []
                
                # Extract close prices from full dataset for calculation
                calc_closes = [bar[4] for bar in full_norm]
                
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
                    logger.debug(
                        f"Computed {overlay1_type}({overlay1_period}) for {ticker}: {len(overlay1_values)} total, "
                        f"{non_none_count} non-None in plot of {len(norm)} bars (calculated on {len(full_norm)} bars)"
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

                # Calculate VBP levels if enabled
                vbp_levels: list[float] | None = None
                if show_vbp:
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

