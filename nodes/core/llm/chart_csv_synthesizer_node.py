"""
Chart CSV Synthesizer Node

Simple, fast CSV synthesizer optimized for Qwen3-VL and other vision-language models.
Outputs clean CSV format that aligns perfectly with chart images.

This node is designed for the exact use case:
- 10 charts + exact OHLCV + a few indicators → Qwen3-VL-7B/72B
- No summarization, no verbose formatting, just clean CSV

Inputs:
- images: ConfigDict (optional) - Chart images from any source
- ohlcv_bundle: OHLCVBundle - OHLCV price/volume data
- indicator_data: Any (optional) - Indicator data (dict of series or IndicatorResult)
- indicator_data_1 through indicator_data_5: Any (optional) - Additional indicator inputs

Outputs:
- images: ConfigDict - Images ready for LLM analysis
- csv_text: str - Clean CSV format aligned with charts
- csv_per_chart: ConfigDict - Optional: one CSV per chart
"""

import logging
from datetime import datetime
from typing import Any

from core.types_registry import AssetSymbol, ConfigDict, NodeCategory, OHLCVBar, OHLCVBundle, ProgressState, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class ChartCSVSynthesizer(Base):
    """
    Simple CSV synthesizer that outputs clean CSV format for vision-language models.
    
    Optimized for Qwen3-VL and similar models that parse CSV data reliably.
    No summarization, no verbose formatting - just clean CSV aligned with chart images.
    """

    inputs = {
        "images": get_type("ConfigDict") | None,
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
        "indicator_data": Any | None,
        **{f"indicator_data_{i}": Any | None for i in range(1, 6)},
    }

    outputs = {
        "images": get_type("ConfigDict"),
        "csv_text": str,
        "csv_per_chart": get_type("ConfigDict"),
    }

    CATEGORY = NodeCategory.LLM

    default_params = {
        "max_bars": 200,  # Maximum bars per symbol
    }

    params_meta = [
        {
            "name": "max_bars",
            "type": "number",
            "default": 200,
            "min": 10,
            "max": 1000,
            "step": 10,
            "label": "Max Bars",
            "description": "Maximum bars to include per symbol",
        },
    ]

    def _format_timestamp(self, timestamp: int | float) -> str:
        """Format timestamp to date string (YYYY-MM-DD).
        
        Handles both millisecond and second timestamps.
        """
        if isinstance(timestamp, (int, float)):
            # Assume milliseconds if > 1e10, otherwise seconds
            if timestamp > 1e10:
                dt = datetime.fromtimestamp(timestamp / 1000)
            else:
                dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d")
        return str(timestamp)

    def _extract_indicator_series(self, indicator_data: Any, symbol: AssetSymbol) -> dict[str, list[float]]:
        """Extract indicator series values from various data formats.
        
        Returns dict mapping indicator name -> list of values aligned with OHLCV bars.
        Handles multiple formats:
        - IndicatorResult with series/lines
        - Dict of series (per-symbol or single symbol)
        - List of IndicatorResult
        """
        indicator_series: dict[str, list[float]] = {}
        
        if indicator_data is None:
            return indicator_series
        
        # Handle list of IndicatorResult
        if isinstance(indicator_data, list):
            for item in indicator_data:
                if isinstance(item, dict) and "indicator_type" in item:
                    item_series = self._extract_indicator_series(item, symbol)
                    indicator_series.update(item_series)
            return indicator_series
        
        # Handle IndicatorResult format
        if isinstance(indicator_data, dict) and "indicator_type" in indicator_data:
            values = indicator_data.get("values", {})
            indicator_type = str(indicator_data.get("indicator_type", "")).lower()
            
            if isinstance(values, dict):
                # Check for series data
                if "series" in values and isinstance(values["series"], list):
                    series = values["series"]
                    if series:
                        # If series contains dicts with multiple values, extract them
                        if isinstance(series[0], dict):
                            for key in series[0].keys():
                                if key not in ["timestamp", "date"]:
                                    indicator_name = f"{indicator_type}_{key}" if indicator_type else key
                                    indicator_series[indicator_name] = [
                                        float(item.get(key, 0)) if isinstance(item, dict) else float(item) 
                                        for item in series if item is not None
                                    ]
                        else:
                            # Single value series - use indicator type as name
                            indicator_series[indicator_type] = [
                                float(v) if v is not None else 0.0 for v in series
                            ]
                # Check for lines (dict of named values) - convert to series
                elif "lines" in values and isinstance(values["lines"], dict):
                    for key, val in values["lines"].items():
                        if val is not None:
                            indicator_name = f"{indicator_type}_{key}" if indicator_type else key
                            indicator_series[indicator_name] = [float(val)]
                # Check for single value
                elif "single" in values and values["single"] is not None:
                    indicator_series[indicator_type] = [float(values["single"])]
        
        # Handle dict of series format (common for multi-indicator outputs)
        elif isinstance(indicator_data, dict):
            # Check if it's per-symbol structure (dict of dicts)
            first_value = next(iter(indicator_data.values())) if indicator_data.values() else None
            
            if isinstance(first_value, dict) and not isinstance(first_value, list):
                # Per-symbol structure - get data for this symbol
                # Try multiple key formats
                symbol_keys = [symbol, str(symbol), symbol.ticker if hasattr(symbol, 'ticker') else None]
                symbol_data = None
                for key in symbol_keys:
                    if key and key in indicator_data:
                        symbol_data = indicator_data[key]
                        break
                
                # If not found, try first non-metadata entry
                if symbol_data is None:
                    for key, value in indicator_data.items():
                        if key != "metadata" and isinstance(value, dict):
                            symbol_data = value
                            break
                
                if isinstance(symbol_data, dict):
                    for key, value in symbol_data.items():
                        if key == "metadata":
                            continue
                        if isinstance(value, list):
                            # Extract numeric values
                            numeric_values = []
                            for v in value:
                                if isinstance(v, (int, float)):
                                    numeric_values.append(float(v))
                                elif isinstance(v, dict):
                                    # Try to extract a single value from dict
                                    for k in ["value", "close", "val", "atr", "rsi", "macd"]:
                                        if k in v and isinstance(v[k], (int, float)):
                                            numeric_values.append(float(v[k]))
                                            break
                            if numeric_values:
                                indicator_series[key] = numeric_values
            else:
                # Single symbol structure - values are lists
                for key, value in indicator_data.items():
                    if key == "metadata":
                        continue
                    if isinstance(value, list):
                        numeric_values = []
                        for v in value:
                            if isinstance(v, (int, float)):
                                numeric_values.append(float(v))
                            elif isinstance(v, dict):
                                # Try to extract a single value from dict
                                for k in ["value", "close", "val", "atr", "rsi", "macd", "signal", "histogram"]:
                                    if k in v and isinstance(v[k], (int, float)):
                                        numeric_values.append(float(v[k]))
                                        break
                        if numeric_values:
                            indicator_series[key] = numeric_values
        
        return indicator_series

    def _create_csv_for_symbol(
        self, 
        symbol: AssetSymbol, 
        bars: list[OHLCVBar], 
        all_indicators: dict[str, list[float]],
        max_bars: int
    ) -> str:
        """Create CSV string for a single symbol."""
        if not bars:
            return ""
        
        # Limit to max_bars
        bars = bars[-max_bars:] if len(bars) > max_bars else bars
        
        # Build CSV rows
        rows = []
        
        # Determine all indicator columns
        indicator_cols = sorted(all_indicators.keys())
        
        # Build header
        header = ["date", "open", "high", "low", "close", "volume"] + indicator_cols
        rows.append(",".join(header))
        
        # Build data rows - align indicators with bars by index
        # Note: Indicators may have fewer values than bars (warmup period)
        max_indicator_len = max((len(v) for v in all_indicators.values()), default=0)
        
        for i, bar in enumerate(bars):
            date_str = self._format_timestamp(bar.get("timestamp", 0))
            open_val = bar.get("open", 0.0)
            high_val = bar.get("high", 0.0)
            low_val = bar.get("low", 0.0)
            close_val = bar.get("close", 0.0)
            volume_val = bar.get("volume", 0.0)
            
            # Build row with OHLCV
            row = [
                date_str,
                f"{open_val:.6f}",
                f"{high_val:.6f}",
                f"{low_val:.6f}",
                f"{close_val:.6f}",
                f"{volume_val:.0f}",
            ]
            
            # Add indicator values (aligned by index from end of series)
            # If indicator has fewer values, align from the end (most recent values)
            for col in indicator_cols:
                indicator_values = all_indicators[col]
                if indicator_values:
                    # Align from end: if indicator has 100 values and bars have 200,
                    # use indicator[0] with bar[100], indicator[1] with bar[101], etc.
                    offset = len(bars) - len(indicator_values)
                    if i >= offset:
                        idx = i - offset
                        if 0 <= idx < len(indicator_values):
                            row.append(f"{indicator_values[idx]:.6f}")
                        else:
                            row.append("")
                    else:
                        row.append("")  # Before indicator data starts
                else:
                    row.append("")  # No indicator data
            
            rows.append(",".join(row))
        
        return "\n".join(rows)

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the CSV synthesizer node."""
        self._emit_progress(ProgressState.START, 0.0, "Starting CSV synthesis...")
        
        # Get inputs
        images = inputs.get("images") or {}
        ohlcv_bundle = inputs.get("ohlcv_bundle") or {}
        max_bars = int(self.params.get("max_bars", 200))
        
        # Collect all indicator data
        self._emit_progress(ProgressState.UPDATE, 10.0, "Collecting indicator data...")
        indicator_data_list: list[Any] = []
        
        if inputs.get("indicator_data") is not None:
            indicator_data_list.append(inputs["indicator_data"])
        
        for i in range(1, 6):
            key = f"indicator_data_{i}"
            if inputs.get(key) is not None:
                indicator_data_list.append(inputs[key])
        
        if not ohlcv_bundle:
            logger.warning("ChartCSVSynthesizer: No OHLCV bundle provided")
            return {
                "images": images,
                "csv_text": "",
                "csv_per_chart": {},
            }
        
        # Process each symbol
        self._emit_progress(ProgressState.UPDATE, 20.0, f"Processing {len(ohlcv_bundle)} symbols...")
        csv_per_chart: dict[str, str] = {}
        all_csv_sections: list[str] = []
        
        symbol_list = list(ohlcv_bundle.items())
        for idx, (symbol, bars) in enumerate(symbol_list):
            if not bars:
                continue
            
            # Update progress
            progress = 20.0 + (idx / len(symbol_list)) * 70.0
            self._emit_progress(ProgressState.UPDATE, progress, f"Processing {symbol}...")
            
            # Extract all indicator series for this symbol
            all_indicators: dict[str, list[float]] = {}
            
            for indicator_data in indicator_data_list:
                if indicator_data is None:
                    continue
                
                # Extract indicator series for this symbol
                symbol_indicators = self._extract_indicator_series(indicator_data, symbol)
                
                # Merge into all_indicators (handle name conflicts by appending index)
                for key, values in symbol_indicators.items():
                    if key in all_indicators:
                        # Name conflict - try to find unique name
                        base_key = key
                        counter = 1
                        while key in all_indicators:
                            key = f"{base_key}_{counter}"
                            counter += 1
                    all_indicators[key] = values
            
            # Create CSV for this symbol
            csv_str = self._create_csv_for_symbol(symbol, bars, all_indicators, max_bars)
            
            if csv_str:
                chart_key = f"chart_{idx + 1}"
                csv_per_chart[chart_key] = csv_str
                
                # Add to combined CSV with header
                symbol_str = str(symbol)
                all_csv_sections.append(f"=== CHART {idx + 1} - {symbol_str} ===\n{csv_str}")
        
        # Combine all CSV sections
        csv_text = "\n\n".join(all_csv_sections)
        
        self._emit_progress(ProgressState.DONE, 100.0, f"Complete - {len(csv_per_chart)} charts processed")
        
        logger.info(
            f"ChartCSVSynthesizer: Processed {len(csv_per_chart)} charts, "
            f"{len(indicator_data_list)} indicator inputs, "
            f"CSV text length: {len(csv_text)} chars"
        )
        
        return {
            "images": images,
            "csv_text": csv_text,
            "csv_per_chart": csv_per_chart,
        }

