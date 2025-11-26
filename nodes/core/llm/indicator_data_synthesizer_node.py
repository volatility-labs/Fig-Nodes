"""
Indicator Data Synthesizer Node

Generic node that accepts any indicator data and/or OHLCV bars from various nodes,
formats and cleans the data, and prepares it for LLM analysis via OpenRouterChat.

This node is designed to be flexible and work with any indicator type:
- Images from chart nodes
- Indicator data in various formats (IndicatorResult, ConfigDict, etc.)
- OHLCV bars for additional context

The node auto-detects data structures and formats them appropriately.
"""

import json
import logging
from datetime import datetime
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class IndicatorDataSynthesizer(Base):
    """
    Generic synthesizer that formats any indicator data and images for LLM analysis.

    Inputs:
    - images: ConfigDict (optional) - Chart images from any chart node
    - indicator_data: Any (optional) - Primary indicator data input
    - indicator_data_1 through indicator_data_5: Any (optional) - Additional explicit indicator inputs
      You can connect multiple indicators to these separate inputs for better organization
    - ohlcv_bundle: OHLCVBundle (optional) - OHLCV bars for additional context

    Outputs:
    - images: ConfigDict - Chart images ready for OpenRouterChat (passes through)
    - formatted_text: str - Formatted indicator data as readable text for prompt
    - combined_data: ConfigDict - All data combined in structured format

    Usage:
    - Connect one indicator to 'indicator_data' (primary input)
    - Connect additional indicators to 'indicator_data_1' through 'indicator_data_5' (up to 5 additional)
    - All connected indicators will be formatted and combined in the output
    """

    inputs = {
        "images": get_type("ConfigDict") | None,
        "indicator_data": Any | None,  # Primary indicator data input
        **{
            f"indicator_data_{i}": Any | None for i in range(1, 6)
        },  # Additional explicit indicator inputs (1-5)
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
    }

    outputs = {
        "images": get_type("ConfigDict"),
        "formatted_text": str,
        "combined_data": get_type("ConfigDict"),
    }

    CATEGORY = NodeCategory.LLM

    default_params = {
        "include_ohlcv": False,  # Disable OHLCV by default (was causing token explosion) - enable only if needed
        "include_indicators": True,
        "ohlcv_max_bars": 3,  # Very aggressive limit for token efficiency
        "format_style": "readable",  # "readable" (svens-branch style), "json", "compact", "summary"
        "include_recent_only": True,  # Only include recent indicator values
        "recent_bars_count": 10,  # Reduced from 20 to 10 for token efficiency
        "bandpass_recent_count": 5,  # Reduced from 10 to 5 for token efficiency
        "summary_only": True,  # Show only stats (not individual values) to reduce tokens
        "max_symbols": 3,  # Reduced from 5 to 3 for token efficiency
        "enable_summarization": False,  # Enable AI summarization before sending to OpenRouter
        "summarization_mode": "ollama",  # "ollama" (local, free) or "openrouter" (cheaper model)
        "summarization_model": "gemma2:2b",  # Ollama model name (e.g., "gemma2:2b", "llama3.2:1b") or OpenRouter model
        "ollama_host": "http://localhost:11434",  # Ollama server URL
    }

    params_meta = [
        {
            "name": "include_ohlcv",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Include OHLCV Data",
            "description": "Include OHLCV bars in formatted output (disabled by default - images already show price data, reduces token usage)",
        },
        {
            "name": "include_indicators",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Include Indicator Data",
            "description": "Include indicator data in formatted output",
        },
        {
            "name": "ohlcv_max_bars",
            "type": "number",
            "default": 3,
            "min": 1,
            "max": 1000,
            "step": 1,
            "label": "Max OHLCV Bars",
            "description": "Number of OHLCV bars to show (very aggressive limit for token efficiency)",
        },
        {
            "name": "format_style",
            "type": "combo",
            "default": "readable",
            "options": ["readable", "summary", "json", "compact"],
            "label": "Format Style",
            "description": "How to format the indicator data: readable (svens-branch style: last 10-20 values + stats), summary (stats only), json (structured), compact (minimal JSON)",
        },
        {
            "name": "summary_only",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Summary Only",
            "description": "Only show summary statistics (no individual values). If false, shows last N values + stats (like svens-branch).",
        },
        {
            "name": "include_recent_only",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Recent Values Only",
            "description": "Only include recent indicator values (last N bars) to reduce token usage",
        },
        {
            "name": "recent_bars_count",
            "type": "number",
            "default": 10,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "Recent Bars Count",
            "description": "Number of recent values to show for composite/MESA/CCO (reduced from 20 to 10 for token efficiency)",
        },
        {
            "name": "bandpass_recent_count",
            "type": "number",
            "default": 5,
            "min": 1,
            "max": 50,
            "step": 1,
            "label": "Bandpass Recent Count",
            "description": "Number of recent values to show for bandpasses (default: 10, matches svens-branch)",
        },
        {
            "name": "max_symbols",
            "type": "number",
            "default": 3,
            "min": 1,
            "max": 50,
            "step": 1,
            "label": "Max Symbols",
            "description": "Maximum number of symbols to process per indicator (default: 3, prevents token explosion with many symbols)",
        },
        {
            "name": "enable_summarization",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Enable AI Summarization",
            "description": "Use AI (Ollama or cheaper OpenRouter model) to summarize indicator data before sending to final analysis. Reduces token usage and improves quality.",
        },
        {
            "name": "summarization_mode",
            "type": "combo",
            "default": "ollama",
            "options": ["ollama", "openrouter"],
            "label": "Summarization Mode",
            "description": "Use Ollama (local, free) or OpenRouter (cheaper model) for summarization",
        },
        {
            "name": "summarization_model",
            "type": "text",
            "default": "gemma2:2b",
            "label": "Summarization Model",
            "description": "Model name: for Ollama use 'gemma2:2b' or 'llama3.2:1b', for OpenRouter use 'google/gemma-2-2b-it' or similar",
        },
        {
            "name": "ollama_host",
            "type": "text",
            "default": "http://localhost:11434",
            "label": "Ollama Host",
            "description": "Ollama server URL (default: http://localhost:11434)",
        },
    ]

    def _format_timestamp(self, timestamp: int | float) -> str:
        """Format timestamp to readable date/time."""
        if timestamp > 1e10:
            dt = datetime.fromtimestamp(timestamp / 1000)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(timestamp)

    def _format_ohlcv_bar(self, bar: dict[str, Any]) -> str:
        """Format a single OHLCV bar."""
        timestamp = self._format_timestamp(bar.get("timestamp", 0))
        return (
            f"{timestamp} | O:{bar.get('open', 'N/A')} "
            f"H:{bar.get('high', 'N/A')} L:{bar.get('low', 'N/A')} "
            f"C:{bar.get('close', 'N/A')} V:{bar.get('volume', 'N/A')}"
        )

    def _is_indicator_result(self, data: Any) -> bool:
        """Check if data is an IndicatorResult structure."""
        return isinstance(data, dict) and "indicator_type" in data and "values" in data

    def _is_series_data(self, data: Any) -> bool:
        """Check if data is a series/list of values."""
        return isinstance(data, list) and len(data) > 0

    def _is_dict_of_series(self, data: Any) -> bool:
        """Check if data is a dict where values are lists/series."""
        if not isinstance(data, dict):
            return False
        return any(isinstance(v, list) and len(v) > 0 for v in data.values() if v is not None)

    def _format_indicator_result(
        self, result: dict[str, Any], recent_only: bool, recent_count: int
    ) -> str:
        """Format a standard IndicatorResult structure."""
        indicator_type = result.get("indicator_type", "unknown")
        values = result.get("values", {})
        timestamp = result.get("timestamp")
        params = result.get("params", {})
        error = result.get("error")

        lines = [f"=== INDICATOR: {indicator_type} ==="]

        if timestamp:
            lines.append(f"Timestamp: {self._format_timestamp(timestamp)}")

        if params:
            lines.append(f"Parameters: {params}")

        if error:
            lines.append(f"Error: {error}")
            lines.append("")
            return "\n".join(lines)

        # Format values
        if isinstance(values, dict):
            # Single value
            if "single" in values and values["single"] is not None:
                lines.append(f"Value: {values['single']}")

            # Lines (dict of named values)
            if "lines" in values and isinstance(values["lines"], dict):
                lines.append("Values:")
                for key, val in values["lines"].items():
                    if val is not None:
                        lines.append(f"  {key}: {val}")

            # Series (list of dicts or values)
            if "series" in values and isinstance(values["series"], list):
                series = values["series"]
                if recent_only and len(series) > recent_count:
                    series = series[-recent_count:]

                lines.append(f"Series ({len(series)} values):")
                if len(series) <= 10:
                    for i, item in enumerate(series):
                        if isinstance(item, dict):
                            lines.append(f"  [{i + 1}] {item}")
                        else:
                            lines.append(f"  [{i + 1}] {item}")
                else:
                    for i, item in enumerate(series[:3]):
                        if isinstance(item, dict):
                            lines.append(f"  [{i + 1}] {item}")
                        else:
                            lines.append(f"  [{i + 1}] {item}")
                    lines.append(f"  ... ({len(series) - 6} more) ...")
                    for i, item in enumerate(series[-3:], start=len(series) - 2):
                        if isinstance(item, dict):
                            lines.append(f"  [{i + 1}] {item}")
                        else:
                            lines.append(f"  [{i + 1}] {item}")

        lines.append("")
        return "\n".join(lines)

    def _format_dict_of_series(
        self,
        data: dict[str, Any],
        label: str,
        recent_only: bool,
        recent_count: int,
        summary_only: bool = False,
        bandpass_count: int = 10,
        max_symbols: int = 10,
    ) -> str:
        """Format a dict where values are series/lists (like hurst_data, mesa_data, cco_data)."""
        lines = [f"=== {label.upper()} ==="]

        # Check if data is per-symbol (dict of dicts) or single symbol (dict of lists)
        is_per_symbol = False
        symbol_count = 0
        if data and isinstance(data, dict):
            # Check if first value is a dict (indicating per-symbol structure)
            # Also check if we have many keys (likely per-symbol structure)
            first_value = next(iter(data.values())) if data.values() else None
            symbol_count = len([k for k in data.keys() if k != "metadata"])

            # Detect per-symbol: either first value is dict, OR we have many keys (likely symbols)
            if isinstance(first_value, dict) or (symbol_count > 5 and first_value is not None):
                # Double-check: if we have many keys and values are complex, it's likely per-symbol
                if symbol_count > 3:  # If more than 3 keys, likely per-symbol structure
                    is_per_symbol = True

        # ALWAYS limit if we have many items (safety measure)
        if isinstance(data, dict) and symbol_count > max_symbols:
            logger.warning(
                f"IndicatorDataSynthesizer: Limiting {label} from {symbol_count} to {max_symbols} items to reduce token usage"
            )
            lines.append(
                f"⚠️ Limiting to first {max_symbols} of {symbol_count} items to reduce token usage"
            )
            # Limit to first max_symbols items (excluding metadata)
            metadata_backup = data.get("metadata")
            limited_items = []
            for key, value in data.items():
                if key == "metadata":
                    continue
                if len(limited_items) >= max_symbols:
                    break
                limited_items.append((key, value))
            data = dict(limited_items)
            # Re-add metadata if it exists
            if metadata_backup:
                data["metadata"] = metadata_backup
            symbol_count = len(data) - (
                1 if "metadata" in data else 0
            )  # Update count after limiting

        # Check for metadata (at top level, not per-symbol)
        metadata = data.get("metadata", {})
        if metadata:
            lines.append("Metadata:")
            for key, value in metadata.items():
                if value is not None:
                    lines.append(f"  {key}: {value}")
            lines.append("")

        # Format series data
        symbol_idx = 0
        for key, value in data.items():
            if key == "metadata":
                continue

            # If per-symbol structure, format this symbol's data inline
            if is_per_symbol and isinstance(value, dict):
                symbol_idx += 1
                lines.append(f"\n--- {key} (Symbol {symbol_idx}/{min(len(data), max_symbols)}) ---")

                # Format this symbol's indicator data (value is a dict of series)
                symbol_metadata = value.get("metadata", {})
                if symbol_metadata:
                    lines.append("Metadata:")
                    for meta_key, meta_val in symbol_metadata.items():
                        if meta_val is not None:
                            lines.append(f"  {meta_key}: {meta_val}")
                    lines.append("")

                # Format each series in this symbol
                for series_key, series_value in value.items():
                    if series_key == "metadata":
                        continue
                    if isinstance(series_value, list):
                        # Format this series (reuse existing logic)
                        non_none_vals = [v for v in series_value if v is not None]
                        if not non_none_vals:
                            continue

                        if summary_only:
                            recent_val = next(
                                (v for v in reversed(series_value) if v is not None), None
                            )
                            if len(non_none_vals) > 1:
                                min_val = min(non_none_vals)
                                max_val = max(non_none_vals)
                                lines.append(
                                    f"{series_key}: Recent={recent_val}, Min={min_val}, Max={max_val}, Count={len(non_none_vals)}/{len(series_value)}"
                                )
                            else:
                                lines.append(f"{series_key}: {recent_val} (1 value)")
                        else:
                            use_count = (
                                bandpass_count if "bandpass" in series_key.lower() else recent_count
                            )
                            if recent_only and len(series_value) > use_count:
                                display_vals = series_value[-use_count:]
                                lines.append(
                                    f"{series_key} (last {len(display_vals)} of {len(series_value)} values):"
                                )
                            else:
                                display_vals = series_value
                                lines.append(f"{series_key} ({len(series_value)} values):")

                            valid_display = [v for v in display_vals if v is not None]
                            if valid_display:
                                start_idx = len(non_none_vals) - len(valid_display)
                                for i, val in enumerate(valid_display):
                                    if isinstance(val, (int, float)):
                                        lines.append(f"  [{start_idx + i}]: {val:.6f}")
                                    else:
                                        lines.append(f"  [{start_idx + i}]: {val}")

                                if len(non_none_vals) > len(valid_display):
                                    lines.append(
                                        f"  ... ({len(non_none_vals) - len(valid_display)} more values)"
                                    )

                                current_val = valid_display[-1]
                                if isinstance(current_val, (int, float)):
                                    lines.append(f"  Current: {current_val:.6f}")
                                    if len(non_none_vals) > 1:
                                        lines.append(
                                            f"  Min: {min(non_none_vals):.6f}, Max: {max(non_none_vals):.6f}"
                                        )
                                        if len(non_none_vals) > 0:
                                            mean_val = sum(non_none_vals) / len(non_none_vals)
                                            lines.append(f"  Mean: {mean_val:.6f}")
                                else:
                                    lines.append(f"  Current: {current_val}")
                                    if len(non_none_vals) > 1:
                                        lines.append(
                                            f"  Min: {min(non_none_vals)}, Max: {max(non_none_vals)}"
                                        )

                lines.append("")  # Blank line between symbols
                continue

            if isinstance(value, list):
                # Series data
                non_none_values = [v for v in value if v is not None]
                if not non_none_values:
                    continue

                if summary_only:
                    # Summary mode: Only show statistics, no individual values
                    recent_val = next((v for v in reversed(value) if v is not None), None)
                    if len(non_none_values) > 1:
                        min_val = min(non_none_values)
                        max_val = max(non_none_values)
                        lines.append(
                            f"{key}: Recent={recent_val}, Min={min_val}, Max={max_val}, Count={len(non_none_values)}/{len(value)}"
                        )
                    else:
                        lines.append(f"{key}: {recent_val} (1 value)")
                else:
                    # Full mode: Show last N values + stats (svens-branch style)
                    # Determine count based on key name (bandpasses get fewer)
                    use_count = bandpass_count if "bandpass" in key.lower() else recent_count

                    if recent_only and len(value) > use_count:
                        display_values = value[-use_count:]
                        lines.append(f"{key} (last {len(display_values)} of {len(value)} values):")
                    else:
                        display_values = value
                        lines.append(f"{key} ({len(value)} values):")

                    # Show individual values (svens-branch style)
                    valid_display = [v for v in display_values if v is not None]
                    if valid_display:
                        start_idx = len(non_none_values) - len(valid_display)
                        for i, val in enumerate(valid_display):
                            if isinstance(val, (int, float)):
                                lines.append(f"  [{start_idx + i}]: {val:.6f}")
                            else:
                                lines.append(f"  [{start_idx + i}]: {val}")

                        # Show summary stats (svens-branch style)
                        if len(non_none_values) > len(valid_display):
                            lines.append(
                                f"  ... ({len(non_none_values) - len(valid_display)} more values)"
                            )

                        current_val = valid_display[-1]
                        if isinstance(current_val, (int, float)):
                            lines.append(f"  Current: {current_val:.6f}")
                            if len(non_none_values) > 1:
                                lines.append(
                                    f"  Min: {min(non_none_values):.6f}, Max: {max(non_none_values):.6f}"
                                )
                                if len(non_none_values) > 0:
                                    mean_val = sum(non_none_values) / len(non_none_values)
                                    lines.append(f"  Mean: {mean_val:.6f}")
                        else:
                            lines.append(f"  Current: {current_val}")
                            if len(non_none_values) > 1:
                                lines.append(
                                    f"  Min: {min(non_none_values)}, Max: {max(non_none_values)}"
                                )

            elif isinstance(value, dict):
                # Nested dict
                if summary_only:
                    # Summary: Just show key counts
                    lines.append(f"{key}: {len(value)} items")
                else:
                    lines.append(f"{key}:")
                    for sub_key, sub_val in list(value.items())[:10]:  # Limit nested items
                        if isinstance(sub_val, list) and len(sub_val) > 0:
                            non_none = [v for v in sub_val if v is not None]
                            if non_none:
                                recent = next((v for v in reversed(sub_val) if v is not None), None)
                                lines.append(f"  {sub_key}: Recent={recent}, Count={len(non_none)}")
                        else:
                            lines.append(f"  {sub_key}: {sub_val}")
                    if len(value) > 10:
                        lines.append(f"  ... ({len(value) - 10} more items)")

            elif value is not None:
                # Simple value
                lines.append(f"{key}: {value}")

        lines.append("")
        return "\n".join(lines)

    def _detect_indicator_name(self, data: Any, input_name: str | None = None) -> str:
        """Detect the indicator name/type from the data structure."""
        if data is None:
            return "Unknown Indicator"

        # Check if it's an IndicatorResult with indicator_type field
        if self._is_indicator_result(data):
            indicator_type = data.get("indicator_type", "")
            if indicator_type:
                # Map common indicator types to readable names
                type_map = {
                    "HURST": "Hurst Spectral Analysis Oscillator",
                    "MESA": "MESA Stochastic Multi Length",
                    "CCO": "Cycle Channel Oscillator (CCO)",
                    "EMA": "Exponential Moving Average (EMA)",
                    "SMA": "Simple Moving Average (SMA)",
                    "RSI": "Relative Strength Index (RSI)",
                    "MACD": "Moving Average Convergence Divergence (MACD)",
                    "ADX": "Average Directional Index (ADX)",
                    "ATR": "Average True Range (ATR)",
                    "VBP": "Volume-by-Price (VBP)",
                    "ORB": "Opening Range Breakout (ORB)",
                }
                return type_map.get(indicator_type.upper(), indicator_type)

        # Check for common data structure patterns
        if isinstance(data, dict):
            # Check for Hurst-specific keys
            if any(
                key in data
                for key in [
                    "composite",
                    "bandpass_5",
                    "bandpass_10",
                    "bandpass_20",
                    "bandpass_40",
                    "bandpass_80",
                ]
            ):
                return "Hurst Spectral Analysis Oscillator"

            # Check for MESA-specific keys
            if any(
                key in data
                for key in [
                    "mesa1",
                    "mesa2",
                    "mesa3",
                    "mesa4",
                    "trigger1",
                    "trigger2",
                    "trigger3",
                    "trigger4",
                ]
            ):
                return "MESA Stochastic Multi Length"

            # Check for CCO-specific keys
            if any(
                key in data
                for key in ["fast_osc", "slow_osc", "fast_oscillator", "slow_oscillator"]
            ):
                return "Cycle Channel Oscillator (CCO)"

            # Check for VBP-specific keys
            if any(key in data for key in ["vbp_levels", "price_levels", "volume_profile"]):
                return "Volume-by-Price (VBP)"

            # Check metadata for indicator hints
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                indicator_name = (
                    metadata.get("indicator_name")
                    or metadata.get("indicator_type")
                    or metadata.get("name")
                )
                if indicator_name:
                    return str(indicator_name)

        # Use input name as hint (e.g., "hurst_data" -> "Hurst Data")
        if input_name:
            # Remove common prefixes/suffixes
            name = input_name.replace("_data", "").replace("_", " ").title()
            # Map common names
            name_map = {
                "Hurst": "Hurst Spectral Analysis Oscillator",
                "Mesa": "MESA Stochastic Multi Length",
                "Cco": "Cycle Channel Oscillator (CCO)",
            }
            return name_map.get(name, name)

        return "Indicator Data"

    def _format_generic_indicator(
        self,
        data: Any,
        label: str | None = None,
        recent_only: bool = True,
        recent_count: int = 20,
        input_name: str | None = None,
        summary_only: bool = False,
        bandpass_count: int = 10,
        max_symbols: int = 10,
    ) -> str:
        """Format generic indicator data, auto-detecting structure."""
        if data is None:
            return ""

        # Auto-detect indicator name if label not provided
        if not label:
            label = self._detect_indicator_name(data, input_name)

        # Auto-detect structure and format accordingly
        if self._is_indicator_result(data):
            return self._format_indicator_result(data, recent_only, recent_count)

        if isinstance(data, dict):
            # Check if it's a dict of series (like hurst_data format)
            if self._is_dict_of_series(data):
                label_str = label or "INDICATOR DATA"
                return self._format_dict_of_series(
                    data,
                    label_str,
                    recent_only,
                    recent_count,
                    summary_only,
                    bandpass_count,
                    max_symbols,
                )

            # Generic dict - format as key-value pairs
            lines = [f"=== {label.upper() if label else 'INDICATOR DATA'} ==="]
            for key, value in list(data.items())[:20]:  # Limit to first 20 items
                if isinstance(value, list):
                    if recent_only and len(value) > recent_count:
                        value = value[-recent_count:]
                    lines.append(f"{key}: {len(value)} values")
                    if len(value) <= 5:
                        for v in value:
                            if v is not None:
                                lines.append(f"  {v}")
                    else:
                        for v in value[:2]:
                            if v is not None:
                                lines.append(f"  {v}")
                        lines.append(f"  ... ({len(value) - 4} more) ...")
                        for v in value[-2:]:
                            if v is not None:
                                lines.append(f"  {v}")
                else:
                    lines.append(f"{key}: {value}")
            if len(data) > 20:
                lines.append(f"... ({len(data) - 20} more items)")
            lines.append("")
            return "\n".join(lines)

        if isinstance(data, list):
            # List of indicators or values
            if len(data) == 0:
                return ""

            lines = [f"=== {label.upper() if label else 'INDICATOR DATA'} ==="]
            lines.append(f"Count: {len(data)}")

            # Check if list contains IndicatorResult structures
            if all(self._is_indicator_result(item) for item in data[:5]):
                # List of IndicatorResult
                for i, item in enumerate(data[:10]):  # Limit to first 10
                    lines.append("")
                    lines.append(self._format_indicator_result(item, recent_only, recent_count))
                if len(data) > 10:
                    lines.append(f"... ({len(data) - 10} more indicators)")
            else:
                # Generic list
                display_items = (
                    data[-recent_count:] if recent_only and len(data) > recent_count else data
                )
                for i, item in enumerate(display_items[:20]):
                    if isinstance(item, dict):
                        lines.append(f"  [{i + 1}] {json.dumps(item, default=str)[:100]}")
                    else:
                        lines.append(f"  [{i + 1}] {item}")
                if len(display_items) > 20:
                    lines.append(f"  ... ({len(display_items) - 20} more)")

            lines.append("")
            return "\n".join(lines)

        # Fallback: convert to string
        return f"=== {label.upper() if label else 'INDICATOR DATA'} ===\n{str(data)}\n\n"

    def _format_ohlcv_bundle(
        self,
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]],
        max_bars: int,
        summary_only: bool = False,
        max_symbols: int = 5,
    ) -> str:
        """Format OHLCV bundle data."""
        if not ohlcv_bundle:
            return ""

        lines = ["=== OHLCV PRICE DATA ==="]
        lines.append("")

        # Apply max_symbols limit (svens-branch had no limit, but we cap for safety)
        original_symbol_count = len(ohlcv_bundle)
        if original_symbol_count > max_symbols:
            logger.warning(
                f"IndicatorDataSynthesizer: Limiting OHLCV bundle from {original_symbol_count} to {max_symbols} symbols to reduce token usage."
            )
            ohlcv_bundle = dict(list(ohlcv_bundle.items())[:max_symbols])

        for symbol, bars in ohlcv_bundle.items():
            symbol_str = str(symbol)
            lines.append(f"Symbol: {symbol_str}")
            lines.append(f"Total Bars: {len(bars)}")

            if summary_only:
                # Summary mode: Only show recent price info
                if bars:
                    recent_bar = dict(bars[-1])
                    lines.append(f"Recent: {self._format_ohlcv_bar(recent_bar)}")
                    if len(bars) > 1:
                        first_bar = dict(bars[0])
                        price_range = (
                            f"O:{first_bar.get('open', 'N/A')}-{recent_bar.get('close', 'N/A')}"
                        )
                        lines.append(f"Price Range: {price_range}")
            else:
                # Full mode: Show first 5 + last 5 bars (matches svens-branch exactly)
                preview_count = min(5, len(bars))
                lines.append(f"\nFirst {preview_count} bars:")
                for i, bar in enumerate(bars[:preview_count]):
                    lines.append(f"  [{i}] {self._format_ohlcv_bar(dict(bar))}")

                if len(bars) > preview_count * 2:
                    lines.append(f"\n... ({len(bars) - preview_count * 2} bars) ...\n")

                # Show last few bars (matches svens-branch: last 5)
                if len(bars) > preview_count:
                    last_count = min(preview_count, len(bars) - preview_count)
                    lines.append(f"Last {last_count} bars:")
                    for i, bar in enumerate(bars[-last_count:], start=len(bars) - last_count):
                        lines.append(f"  [{i}] {self._format_ohlcv_bar(dict(bar))}")

                # Summary stats (matches svens-branch)
                if bars:
                    closes = [float(bar.get("close", 0)) for bar in bars if "close" in bar]
                    if closes:
                        lines.append("\nPrice Summary:")
                        lines.append(f"  First Close: ${closes[0]:.4f}")
                        lines.append(f"  Last Close: ${closes[-1]:.4f}")
                        lines.append(f"  Min: ${min(closes):.4f}, Max: ${max(closes):.4f}")
                        if len(closes) > 1:
                            change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100
                            lines.append(f"  Change: {change_pct:+.2f}%")

            lines.append("")

        if original_symbol_count > max_symbols:
            lines.append(f"... and {original_symbol_count - max_symbols} more symbols")
            lines.append("")

        return "\n".join(lines)

    def _format_as_json(self, data: Any, indent: int = 2) -> str:
        """Format data as JSON."""
        try:
            return json.dumps(data, default=str, indent=indent)
        except Exception as e:
            logger.warning(f"Error formatting as JSON: {e}")
            return str(data)

    def _format_as_compact(self, data: Any) -> str:
        """Format data as compact JSON."""
        try:
            return json.dumps(data, default=str, separators=(",", ":"))
        except Exception as e:
            logger.warning(f"Error formatting as compact JSON: {e}")
            return str(data)

    async def _summarize_text(self, text: str) -> str | None:
        """Summarize text using Ollama or OpenRouter."""
        summarization_mode = str(self.params.get("summarization_mode", "ollama")).lower()
        model = str(self.params.get("summarization_model", "gemma2:2b"))

        summarization_prompt = """You are a financial data analyst. Summarize the following indicator data, focusing on:
- Key trends and patterns
- Recent signal changes
- Critical values and crossovers
- Overall market direction

Keep the summary concise but comprehensive. Preserve important numerical values and signal states.
"""

        if summarization_mode == "ollama":
            # Use Ollama (local, free)
            ollama_host = str(self.params.get("ollama_host", "http://localhost:11434"))
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{ollama_host}/api/chat",
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": summarization_prompt},
                                {
                                    "role": "user",
                                    "content": f"Summarize this indicator data:\n\n{text}",
                                },
                            ],
                            "stream": False,
                        },
                    )
                    response.raise_for_status()
                    result = response.json()
                    if "message" in result and "content" in result["message"]:
                        return result["message"]["content"]
                    logger.warning(f"Ollama summarization returned unexpected format: {result}")
                    return None
            except Exception as e:
                logger.error(f"Ollama summarization failed: {e}")
                return None

        elif summarization_mode == "openrouter":
            # Use OpenRouter (cheaper model)
            api_key = APIKeyVault().get("OPENROUTER_API_KEY")
            if not api_key:
                logger.warning("OpenRouter API key not found. Skipping summarization.")
                return None

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "HTTP-Referer": "https://github.com/volatility-labs/Fig-Nodes",
                            "X-Title": "Fig-Nodes Indicator Synthesizer",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": summarization_prompt},
                                {
                                    "role": "user",
                                    "content": f"Summarize this indicator data:\n\n{text}",
                                },
                            ],
                        },
                    )
                    response.raise_for_status()
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        message = result["choices"][0].get("message", {})
                        if "content" in message:
                            return message["content"]
                    logger.warning(f"OpenRouter summarization returned unexpected format: {result}")
                    return None
            except Exception as e:
                logger.error(f"OpenRouter summarization failed: {e}")
                return None

        return None

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the synthesizer node."""
        # Get inputs
        images = inputs.get("images") or {}
        ohlcv_bundle = inputs.get("ohlcv_bundle") or {}

        # Collect all indicator data - both primary and explicit named inputs
        indicator_data_list: list[Any] = []

        # Add primary indicator_data if present
        if inputs.get("indicator_data") is not None:
            indicator_data_list.append(inputs["indicator_data"])

        # Add explicit named inputs (indicator_data_1 through indicator_data_5)
        for i in range(1, 6):
            key = f"indicator_data_{i}"
            if inputs.get(key) is not None:
                indicator_data_list.append(inputs[key])

        # Get parameters
        include_ohlcv = self.params.get("include_ohlcv", False)  # Default False to reduce tokens
        include_indicators = self.params.get("include_indicators", True)
        ohlcv_max_bars = int(
            self.params.get("ohlcv_max_bars", 3)
        )  # Default 3 (reduced for token efficiency)
        format_style = str(self.params.get("format_style", "readable")).lower()
        include_recent_only = self.params.get("include_recent_only", True)
        recent_bars_count = int(
            self.params.get("recent_bars_count", 5)
        )  # Default 5 (reduced for token efficiency)
        bandpass_recent_count = int(
            self.params.get("bandpass_recent_count", 3)
        )  # Default 3 (reduced for token efficiency)
        max_symbols = int(
            self.params.get("max_symbols", 3)
        )  # Default 3 (reduced for token efficiency)
        summary_only = (
            self.params.get("summary_only", True) or format_style == "summary"
        )  # Default True for token efficiency

        # Log current settings for debugging
        logger.info(
            f"IndicatorDataSynthesizer: max_symbols={max_symbols}, recent_bars_count={recent_bars_count}, bandpass_recent_count={bandpass_recent_count}, include_ohlcv={include_ohlcv}, ohlcv_max_bars={ohlcv_max_bars}"
        )

        # Build formatted text based on format style
        formatted_sections: list[str] = []

        # Detect indicator names for combined_data metadata
        indicator_names: list[str] = []
        input_names = []
        if inputs.get("indicator_data") is not None:
            input_names.append("indicator_data")
        for i in range(1, 6):
            key = f"indicator_data_{i}"
            if inputs.get(key) is not None:
                input_names.append(key)

        for i, indicator_data in enumerate(indicator_data_list):
            if indicator_data is not None:
                input_name = input_names[i] if i < len(input_names) else None
                indicator_name = self._detect_indicator_name(indicator_data, input_name)
                indicator_names.append(indicator_name)

        combined_data: dict[str, Any] = {
            "images_count": len(images),
            "indicators_count": len(indicator_data_list),
            "indicator_names": indicator_names,  # List of detected indicator names
            "ohlcv_symbols_count": len(ohlcv_bundle),
        }

        if format_style in ("readable", "summary"):
            # Human-readable format (summary mode is a subset of readable)
            if include_indicators and indicator_data_list:
                # Track which input each indicator came from for better labeling
                input_names = []
                if inputs.get("indicator_data") is not None:
                    input_names.append("indicator_data")
                for i in range(1, 6):
                    key = f"indicator_data_{i}"
                    if inputs.get(key) is not None:
                        input_names.append(key)

                for i, indicator_data in enumerate(indicator_data_list):
                    if indicator_data is None:
                        continue

                    # Auto-detect indicator name from data structure
                    input_name = input_names[i] if i < len(input_names) else None
                    indicator_name = self._detect_indicator_name(indicator_data, input_name)

                    formatted_text = self._format_generic_indicator(
                        indicator_data,
                        indicator_name,
                        include_recent_only,
                        recent_bars_count,
                        input_name,
                        summary_only,
                        bandpass_recent_count,
                        max_symbols,
                    )
                    if formatted_text:
                        formatted_sections.append(formatted_text)

                    # Store in combined_data with meaningful key
                    # Use detected name or fallback to numbered key
                    if indicator_name and indicator_name != "Indicator Data":
                        # Create a safe key from indicator name
                        safe_key = (
                            indicator_name.lower()
                            .replace(" ", "_")
                            .replace("(", "")
                            .replace(")", "")
                            .replace("-", "_")
                        )
                        combined_data[safe_key] = indicator_data
                        combined_data[f"indicator_{i + 1}"] = (
                            indicator_data  # Also keep numbered key for compatibility
                        )
                    else:
                        combined_data[f"indicator_{i + 1}"] = indicator_data

            if include_ohlcv and ohlcv_bundle:
                formatted_sections.append(
                    self._format_ohlcv_bundle(
                        ohlcv_bundle, ohlcv_max_bars, summary_only, max_symbols
                    )
                )
                combined_data["ohlcv_bundle"] = {
                    str(symbol): bars for symbol, bars in ohlcv_bundle.items()
                }

        elif format_style == "json":
            # JSON format
            json_data: dict[str, Any] = {}
            if include_indicators and indicator_data_list:
                # Track which input each indicator came from for better labeling
                input_names = []
                if inputs.get("indicator_data") is not None:
                    input_names.append("indicator_data")
                for i in range(1, 6):
                    key = f"indicator_data_{i}"
                    if inputs.get(key) is not None:
                        input_names.append(key)

                # Create labeled indicators dict
                labeled_indicators: dict[str, Any] = {}
                for i, indicator_data in enumerate(indicator_data_list):
                    if indicator_data is None:
                        continue
                    input_name = input_names[i] if i < len(input_names) else None
                    indicator_name = self._detect_indicator_name(indicator_data, input_name)
                    if indicator_name and indicator_name != "Indicator Data":
                        safe_key = (
                            indicator_name.lower()
                            .replace(" ", "_")
                            .replace("(", "")
                            .replace(")", "")
                            .replace("-", "_")
                        )
                        labeled_indicators[safe_key] = indicator_data
                    else:
                        labeled_indicators[f"indicator_{i + 1}"] = indicator_data

                json_data["indicators"] = labeled_indicators
                combined_data["indicators"] = labeled_indicators

            if include_ohlcv and ohlcv_bundle:
                json_data["ohlcv_bundle"] = {
                    str(symbol): bars for symbol, bars in ohlcv_bundle.items()
                }
                combined_data["ohlcv_bundle"] = json_data["ohlcv_bundle"]

            formatted_sections.append(self._format_as_json(json_data))

        elif format_style == "compact":
            # Compact JSON format
            compact_data: dict[str, Any] = {}
            if include_indicators and indicator_data_list:
                # Track which input each indicator came from for better labeling
                input_names = []
                if inputs.get("indicator_data") is not None:
                    input_names.append("indicator_data")
                for i in range(1, 6):
                    key = f"indicator_data_{i}"
                    if inputs.get(key) is not None:
                        input_names.append(key)

                # Create labeled indicators dict
                labeled_indicators: dict[str, Any] = {}
                for i, indicator_data in enumerate(indicator_data_list):
                    if indicator_data is None:
                        continue
                    input_name = input_names[i] if i < len(input_names) else None
                    indicator_name = self._detect_indicator_name(indicator_data, input_name)
                    if indicator_name and indicator_name != "Indicator Data":
                        safe_key = (
                            indicator_name.lower()
                            .replace(" ", "_")
                            .replace("(", "")
                            .replace(")", "")
                            .replace("-", "_")
                        )
                        labeled_indicators[safe_key] = indicator_data
                    else:
                        labeled_indicators[f"indicator_{i + 1}"] = indicator_data

                compact_data["indicators"] = labeled_indicators
                combined_data["indicators"] = labeled_indicators

            if include_ohlcv and ohlcv_bundle:
                compact_data["ohlcv_bundle"] = {
                    str(symbol): bars for symbol, bars in ohlcv_bundle.items()
                }
                combined_data["ohlcv_bundle"] = compact_data["ohlcv_bundle"]

            formatted_sections.append(self._format_as_compact(compact_data))

        formatted_text = "\n\n".join(filter(None, formatted_sections))

        # Images pass through (already in correct format for OpenRouterChat)
        output_images = images if images else {}

        # Estimate token count (rough approximation: 1 token ≈ 4 characters)
        formatted_text_size = len(formatted_text)
        estimated_tokens = formatted_text_size // 4

        # Hard cap: If we're generating too much, truncate aggressively
        # Hard cap: With max_tokens=900000 for output, OpenRouter only allows ~100k tokens for input
        # Set cap to 50k to leave room for safety margin
        MAX_TOKENS = 50000  # Hard cap at 50k tokens (~200KB text) - OpenRouter allows ~100k input with 900k output
        if estimated_tokens > MAX_TOKENS:
            logger.error(
                f"⚠️ IndicatorDataSynthesizer: Formatted text exceeds hard cap ({estimated_tokens:,} tokens > {MAX_TOKENS:,}). "
                f"Truncating to prevent API errors. Current settings: max_symbols={max_symbols}, recent_bars_count={recent_bars_count}, "
                f"bandpass_recent_count={bandpass_recent_count}, include_ohlcv={include_ohlcv}"
            )
            # Truncate to ~50k tokens worth of text
            max_chars = MAX_TOKENS * 4
            formatted_text = (
                formatted_text[:max_chars]
                + "\n\n[TRUNCATED - Text exceeded token limit. Reduce max_symbols, recent_bars_count, or disable OHLCV.]"
            )
            estimated_tokens = MAX_TOKENS

        logger.info(
            f"IndicatorDataSynthesizer: Processed {len(output_images)} images, "
            f"{len(indicator_data_list)} indicator inputs, {len(ohlcv_bundle)} OHLCV symbols. "
            f"Formatted text: ~{formatted_text_size:,} chars (~{estimated_tokens:,} tokens). "
            f"Settings: max_symbols={max_symbols}, recent_bars_count={recent_bars_count}, bandpass_recent_count={bandpass_recent_count}"
        )

        # Warn if text is very large
        if estimated_tokens > 30_000:
            logger.warning(
                f"IndicatorDataSynthesizer: Large formatted text detected (~{estimated_tokens:,} tokens). "
                f"Consider disabling OHLCV (images already show price data), reducing max_symbols, or enabling summarization."
            )

        # Optional AI summarization step
        enable_summarization = self.params.get("enable_summarization", False)
        if enable_summarization and formatted_text:
            try:
                summarized_text = await self._summarize_text(formatted_text)
                if summarized_text:
                    logger.info(
                        f"IndicatorDataSynthesizer: Summarized text from ~{estimated_tokens:,} tokens to ~{len(summarized_text) // 4:,} tokens"
                    )
                    formatted_text = summarized_text
            except Exception as e:
                logger.warning(
                    f"IndicatorDataSynthesizer: Summarization failed: {e}. Using original text."
                )
                # Continue with original text if summarization fails

        return {
            "images": output_images,
            "formatted_text": formatted_text,
            "combined_data": combined_data,
        }
