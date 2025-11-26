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
import httpx
from datetime import datetime
from typing import Any

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, ConfigDict, NodeCategory, OHLCVBar, OHLCVBundle, ProgressState, get_type
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
        **{f"indicator_data_{i}": Any | None for i in range(1, 6)},  # Additional explicit indicator inputs (1-5)
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
        "ohlcv_max_bars": 20,  # Increased from 3 - summarization handles large data efficiently
        "format_style": "readable",  # "readable" (svens-branch style), "json", "compact", "summary"
        "recent_bars_count": 50,  # Number of recent bars to include (always limited to this count)
        "summary_only": False,  # Default False (will be True if summarization disabled). False = show individual values, True = stats only
        "max_symbols": 20,  # Increased from 3 - summarization handles large data efficiently
        "enable_summarization": False,  # Enable AI summarization before sending to OpenRouter
        "summarize_full_dataset": False,  # If True, summarize full dataset (historical) + recent bars (detail). If False, only summarize formatted output.
        "recursive_summarization": False,  # Use recursive summarization (better coherence, sequential processing)
        "summarization_mode": "ollama",  # "ollama" (local, free) or "openrouter" (cheaper model)
        "summarization_model": "qwen2.5:7b",  # Ollama model name - prefer Qwen for large contexts (qwen2.5:7b=128k, qwen2.5-1m=1M tokens)
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
            "default": 20,
            "min": 1,
            "max": 1000,
            "step": 1,
            "label": "Max OHLCV Bars",
            "description": "Number of OHLCV bars to show per symbol (increased default - summarization handles large data efficiently)",
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
            "default": False,
            "options": [True, False],
            "label": "Summary Only",
            "description": "True = Only stats (min/max/recent). False = Shows last N individual values + stats. Defaults to False when summarization enabled (show data, let AI compress). Defaults to True when summarization disabled (save tokens).",
        },
        {
            "name": "recent_bars_count",
            "type": "number",
            "default": 50,
            "min": 1,
            "max": 500,
            "step": 1,
            "label": "Recent Bars Count",
            "description": "Number of recent bars/values to include for all indicators (always limited to this count - no option to show all values)",
        },
        {
            "name": "max_symbols",
            "type": "number",
            "default": 20,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "Max Symbols",
            "description": "Maximum number of symbols to process per indicator (increased default - summarization handles large data efficiently)",
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
            "name": "summarize_full_dataset",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Summarize Full Dataset",
            "description": "If True: Summarize full dataset (historical context) + format recent bars (detail). If False: Only summarize formatted output. Requires summarization enabled.",
        },
        {
            "name": "recursive_summarization",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Recursive Summarization",
            "description": "Use recursive summarization (each chunk incorporates previous summary). Better coherence but sequential (slower). Only works when summarization is enabled.",
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
            "type": "string",
            "default": "qwen2.5:7b",
            "label": "Summarization Model",
            "description": "Ollama model: 'qwen2.5:7b' (128k context, recommended), 'qwen2.5-1m' (1M context if available), or 'gemma2:2b' (8k, slow). OpenRouter: 'google/gemma-2-2b-it'",
        },
        {
            "name": "ollama_host",
            "type": "string",
            "default": "http://localhost:11434",
            "label": "Ollama Host",
            "description": "Ollama server URL (default: http://localhost:11434)",
        },
    ]

    def _format_timestamp(self, timestamp: int | float) -> str:
        """Format timestamp to readable date/time."""
        if isinstance(timestamp, (int, float)) and timestamp > 1e10:
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
        return (
            isinstance(data, dict)
            and "indicator_type" in data
            and "values" in data
        )

    def _is_series_data(self, data: Any) -> bool:
        """Check if data is a series/list of values."""
        return isinstance(data, list) and len(data) > 0

    def _is_dict_of_series(self, data: Any) -> bool:
        """Check if data is a dict where values are lists/series."""
        if not isinstance(data, dict):
            return False
        return any(isinstance(v, list) and len(v) > 0 for v in data.values() if v is not None)

    def _format_indicator_result(self, result: dict[str, Any], recent_only: bool, recent_count: int) -> str:
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
                            lines.append(f"  [{i+1}] {item}")
                        else:
                            lines.append(f"  [{i+1}] {item}")
                else:
                    for i, item in enumerate(series[:3]):
                        if isinstance(item, dict):
                            lines.append(f"  [{i+1}] {item}")
                        else:
                            lines.append(f"  [{i+1}] {item}")
                    lines.append(f"  ... ({len(series) - 6} more) ...")
                    for i, item in enumerate(series[-3:], start=len(series) - 2):
                        if isinstance(item, dict):
                            lines.append(f"  [{i+1}] {item}")
                        else:
                            lines.append(f"  [{i+1}] {item}")

        lines.append("")
        return "\n".join(lines)

    def _format_dict_of_series(self, data: dict[str, Any], label: str, recent_count: int, summary_only: bool = False, max_symbols: int = 10) -> str:
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
            if isinstance(first_value, dict) or (symbol_count > 5 and isinstance(first_value, (dict, list))):
                # Double-check: if we have many keys and values are complex, it's likely per-symbol
                if symbol_count > 3:  # If more than 3 keys, likely per-symbol structure
                    is_per_symbol = True
        
        # ALWAYS limit if we have many items (safety measure)
        if isinstance(data, dict) and symbol_count > max_symbols:
            logger.warning(f"IndicatorDataSynthesizer: Limiting {label} from {symbol_count} to {max_symbols} items to reduce token usage")
            lines.append(f"⚠️ Limiting to first {max_symbols} of {symbol_count} items to reduce token usage")
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
            symbol_count = len(data) - (1 if "metadata" in data else 0)  # Update count after limiting
        
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
                            recent_val = next((v for v in reversed(series_value) if v is not None), None)
                            if len(non_none_vals) > 1:
                                min_val = min(non_none_vals)
                                max_val = max(non_none_vals)
                                lines.append(f"{series_key}: Recent={recent_val}, Min={min_val}, Max={max_val}, Count={len(non_none_vals)}/{len(series_value)}")
                            else:
                                lines.append(f"{series_key}: {recent_val} (1 value)")
                        else:
                            # Always limit to recent_count (no option to show all values)
                            if len(series_value) > recent_count:
                                display_vals = series_value[-recent_count:]
                                lines.append(f"{series_key} (last {len(display_vals)} of {len(series_value)} values):")
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
                                    lines.append(f"  ... ({len(non_none_vals) - len(valid_display)} more values)")
                                
                                current_val = valid_display[-1]
                                if isinstance(current_val, (int, float)):
                                    lines.append(f"  Current: {current_val:.6f}")
                                    if len(non_none_vals) > 1:
                                        lines.append(f"  Min: {min(non_none_vals):.6f}, Max: {max(non_none_vals):.6f}")
                                        if len(non_none_vals) > 0:
                                            mean_val = sum(non_none_vals) / len(non_none_vals)
                                            lines.append(f"  Mean: {mean_val:.6f}")
                                else:
                                    lines.append(f"  Current: {current_val}")
                                    if len(non_none_vals) > 1:
                                        lines.append(f"  Min: {min(non_none_vals)}, Max: {max(non_none_vals)}")
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
                        lines.append(f"{key}: Recent={recent_val}, Min={min_val}, Max={max_val}, Count={len(non_none_values)}/{len(value)}")
                    else:
                        lines.append(f"{key}: {recent_val} (1 value)")
                else:
                    # Full mode: Show last N values + stats (svens-branch style)
                    if recent_only and len(value) > recent_count:
                        display_values = value[-recent_count:]
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
                            lines.append(f"  ... ({len(non_none_values) - len(valid_display)} more values)")
                        
                        current_val = valid_display[-1]
                        if isinstance(current_val, (int, float)):
                            lines.append(f"  Current: {current_val:.6f}")
                            if len(non_none_values) > 1:
                                lines.append(f"  Min: {min(non_none_values):.6f}, Max: {max(non_none_values):.6f}")
                                if len(non_none_values) > 0:
                                    mean_val = sum(non_none_values) / len(non_none_values)
                                    lines.append(f"  Mean: {mean_val:.6f}")
                        else:
                            lines.append(f"  Current: {current_val}")
                            if len(non_none_values) > 1:
                                lines.append(f"  Min: {min(non_none_values)}, Max: {max(non_none_values)}")
            
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
            if any(key in data for key in ["composite", "bandpass_5", "bandpass_10", "bandpass_20", "bandpass_40", "bandpass_80"]):
                return "Hurst Spectral Analysis Oscillator"
            
            # Check for MESA-specific keys
            if any(key in data for key in ["mesa1", "mesa2", "mesa3", "mesa4", "trigger1", "trigger2", "trigger3", "trigger4"]):
                return "MESA Stochastic Multi Length"
            
            # Check for CCO-specific keys
            if any(key in data for key in ["fast_osc", "slow_osc", "fast_oscillator", "slow_oscillator"]):
                return "Cycle Channel Oscillator (CCO)"
            
            # Check for VBP-specific keys
            if any(key in data for key in ["vbp_levels", "price_levels", "volume_profile"]):
                return "Volume-by-Price (VBP)"
            
            # Check metadata for indicator hints
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                indicator_name = metadata.get("indicator_name") or metadata.get("indicator_type") or metadata.get("name")
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

    def _format_generic_indicator(self, data: Any, label: str | None = None, recent_count: int = 20, input_name: str | None = None, summary_only: bool = False, max_symbols: int = 10) -> str:
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
                return self._format_dict_of_series(data, label_str, recent_count, summary_only, max_symbols)
            
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
                display_items = data[-recent_count:] if recent_only and len(data) > recent_count else data
                for i, item in enumerate(display_items[:20]):
                    if isinstance(item, dict):
                        lines.append(f"  [{i+1}] {json.dumps(item, default=str)[:100]}")
                    else:
                        lines.append(f"  [{i+1}] {item}")
                if len(display_items) > 20:
                    lines.append(f"  ... ({len(display_items) - 20} more)")
            
            lines.append("")
            return "\n".join(lines)
        
        # Fallback: convert to string
        return f"=== {label.upper() if label else 'INDICATOR DATA'} ===\n{str(data)}\n\n"

    def _format_ohlcv_bundle(self, ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]], max_bars: int, summary_only: bool = False, max_symbols: int = 5) -> str:
        """Format OHLCV bundle data."""
        if not ohlcv_bundle:
            return ""

        lines = ["=== OHLCV PRICE DATA ==="]
        lines.append("")
        
        # Apply max_symbols limit (svens-branch had no limit, but we cap for safety)
        original_symbol_count = len(ohlcv_bundle)
        if original_symbol_count > max_symbols:
            logger.warning(f"IndicatorDataSynthesizer: Limiting OHLCV bundle from {original_symbol_count} to {max_symbols} symbols to reduce token usage.")
            ohlcv_bundle = dict(list(ohlcv_bundle.items())[:max_symbols])

        for symbol, bars in ohlcv_bundle.items():
            symbol_str = str(symbol)
            lines.append(f"Symbol: {symbol_str}")
            lines.append(f"Total Bars: {len(bars)}")
            
            if summary_only:
                # Summary mode: Only show recent price info
                if bars:
                    recent_bar = bars[-1]
                    lines.append(f"Recent: {self._format_ohlcv_bar(recent_bar)}")
                    if len(bars) > 1:
                        first_bar = bars[0]
                        price_range = f"O:{first_bar.get('open', 'N/A')}-{recent_bar.get('close', 'N/A')}"
                        lines.append(f"Price Range: {price_range}")
            else:
                # Full mode: Show first 5 + last 5 bars (matches svens-branch exactly)
                preview_count = min(5, len(bars))
                lines.append(f"\nFirst {preview_count} bars:")
                for i, bar in enumerate(bars[:preview_count]):
                    lines.append(f"  [{i}] {self._format_ohlcv_bar(bar)}")
                
                if len(bars) > preview_count * 2:
                    lines.append(f"\n... ({len(bars) - preview_count * 2} bars) ...\n")
                
                # Show last few bars (matches svens-branch: last 5)
                if len(bars) > preview_count:
                    last_count = min(preview_count, len(bars) - preview_count)
                    lines.append(f"Last {last_count} bars:")
                    for i, bar in enumerate(bars[-last_count:], start=len(bars) - last_count):
                        lines.append(f"  [{i}] {self._format_ohlcv_bar(bar)}")
                
                # Summary stats (matches svens-branch)
                if bars:
                    closes = [float(bar.get("close", 0)) for bar in bars if isinstance(bar, dict) and "close" in bar]
                    if closes:
                        lines.append(f"\nPrice Summary:")
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
        """Summarize text using Ollama or OpenRouter. Handles large text by chunking if needed."""
        summarization_mode = str(self.params.get("summarization_mode", "ollama")).lower()
        model = str(self.params.get("summarization_model", "qwen2.5:7b"))  # Default model (updated to match default_params)
        
        summarization_prompt = """You are a financial data analyst. Summarize the following indicator data, focusing on:
- Key trends and patterns
- Recent signal changes
- Critical values and crossovers
- Overall market direction

Keep the summary concise but comprehensive. Preserve important numerical values and signal states.
"""
        
        # Estimate text size - adjust chunk size based on model context window
        text_tokens = len(text) // 4
        
        # Detect model context window and adjust chunk size accordingly
        model_name = model.lower()  # Use the model we already retrieved above
        original_model = model  # Store original for warning logic
        
        if "qwen2.5" in model_name and ("1m" in model_name or "1-m" in model_name):
            MAX_CHUNK_TOKENS = 800000  # Qwen 2.5-1M has 1M context window
            logger.info("Using Qwen 2.5-1M model with 1M token context window")
        elif "qwen2.5" in model_name or "qwen3" in model_name:
            MAX_CHUNK_TOKENS = 100000  # Qwen 2.5/3 standard models have 128k context
            logger.info("Using Qwen model with 128k token context window")
        elif "qwen2" in model_name:
            MAX_CHUNK_TOKENS = 30000  # Qwen 2 has 32k context
            logger.info("Using Qwen 2 model with 32k token context window")
        elif "llama3.2" in model_name:
            MAX_CHUNK_TOKENS = 100000  # Llama 3.2 has 128k context
            logger.info("Using Llama 3.2 model with 128k token context window")
        else:
            MAX_CHUNK_TOKENS = 4000  # Conservative limit for Gemma 2's 8k context
            # Don't warn yet - wait until after fallback logic to see final model
        
        if summarization_mode == "ollama":
            # Use Ollama (local, free)
            ollama_host = str(self.params.get("ollama_host", "http://localhost:11434"))
            
            # Check if Ollama is reachable first and verify model exists
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Check if Ollama is running
                    health_check = await client.get(f"{ollama_host}/api/tags")
                    health_check.raise_for_status()
                    
                    # Get list of available models
                    tags_response = await client.get(f"{ollama_host}/api/tags")
                    tags_data = tags_response.json()
                    available_models = [m.get("name", "") for m in tags_data.get("models", [])]
                    
                    # Check if requested model exists, try alternatives
                    # Prefer models with larger context windows for large data
                    model_variants = [
                        model,  # User's requested model
                        f"{model}-it",
                        model.replace(":", ":latest"),
                        "qwen2.5:7b",  # 128k context - BEST for large data (already installed!)
                        "qwen3:8b",  # 128k+ context
                        "qwen2.5:3b",  # 128k context (smaller model)
                        "qwen2:7b",  # 32k context
                        "llama3.2:1b",  # 128k context
                        "gemma2:2b",  # 8k context - fallback (too small!)
                        "gemma:2b"
                    ]
                    found_model = None
                    for variant in model_variants:
                        if variant in available_models:
                            found_model = variant
                            break
                    
                    if not found_model:
                        logger.error(
                            f"❌ Model '{model}' not found in Ollama. Available models: {', '.join(available_models[:5])}... "
                            f"Install with: 'ollama pull gemma2:2b' or 'ollama pull llama3.2:1b'"
                        )
                        return None
                    
                    if found_model != model:
                        logger.info(f"Using model '{found_model}' instead of '{model}'")
                        model = found_model
                        # Update model_name after fallback so warning logic uses correct model
                        model_name = model.lower()
                        # Re-check context window after fallback
                        if "qwen2.5" in model_name and ("1m" in model_name or "1-m" in model_name):
                            MAX_CHUNK_TOKENS = 800000
                        elif "qwen2.5" in model_name or "qwen3" in model_name:
                            MAX_CHUNK_TOKENS = 100000
                        elif "qwen2" in model_name:
                            MAX_CHUNK_TOKENS = 30000
                        elif "llama3.2" in model_name:
                            MAX_CHUNK_TOKENS = 100000
                        else:
                            MAX_CHUNK_TOKENS = 4000
                            # Only warn if user explicitly chose a small context model (not if we fell back to it)
                            if original_model.lower() == model_name:
                                logger.warning(f"Using small context model ({model_name}). Consider switching to qwen2.5:7b for better performance with large data.")
                        
            except Exception as e:
                logger.error(f"❌ Ollama not reachable at {ollama_host}: {e}. Make sure Ollama is running: 'ollama serve'")
                return None
            
            # Store the model name to use (might have been updated to an alternative)
            effective_model = model
            
            # Check if recursive summarization is enabled
            recursive_summarization = self.params.get("recursive_summarization", False)
            
            # Chunk large text if needed
            if text_tokens > MAX_CHUNK_TOKENS:
                chunks = self._chunk_text(text, MAX_CHUNK_TOKENS * 4)
                num_chunks = len(chunks)
                logger.info(f"IndicatorDataSynthesizer: Text is large ({text_tokens:,} tokens), chunking into {num_chunks} chunks for summarization...")
                
                # Warn if too many chunks (will take very long)
                if num_chunks > 100:
                    logger.warning(
                        f"⚠️ Warning: {num_chunks} chunks will take a very long time to summarize with Gemma 2:2b (8k context). "
                        f"Consider using OpenRouter summarization with a larger model (e.g., 'google/gemma-2-9b-it' with 8k context) "
                        f"or install a model with larger context: 'ollama pull qwen2.5:7b' (32k context) or 'ollama pull llama3.2:3b' (128k context)"
                    )
                
                if recursive_summarization:
                    # Recursive summarization: each chunk incorporates previous summary
                    # M_i = summarize(M_{i-1} + Chunk_i)
                    logger.info("Using recursive summarization mode (better coherence, sequential processing)")
                    previous_memory = None
                    
                    for i, chunk in enumerate(chunks):
                        # Update progress for each chunk (50-85% range for chunking)
                        chunk_progress = 50.0 + (i / num_chunks) * 35.0
                        chunk_tokens = len(chunk) // 4
                        
                        if previous_memory:
                            # Incorporate previous memory into current chunk
                            memory_tokens = len(previous_memory) // 4
                            combined_input = f"[Previous Summary]\n{previous_memory}\n\n[New Data]\n{chunk}"
                            self._emit_progress(
                                ProgressState.UPDATE, 
                                chunk_progress, 
                                f"Recursively summarizing chunk {i+1}/{num_chunks} (~{chunk_tokens:,} tokens + {memory_tokens:,} from previous)..."
                            )
                            logger.info(f"Recursively summarizing chunk {i+1}/{num_chunks} (chunk: {chunk_tokens:,} tokens, memory: {memory_tokens:,} tokens)...")
                        else:
                            # First chunk - no previous memory
                            self._emit_progress(
                                ProgressState.UPDATE, 
                                chunk_progress, 
                                f"Summarizing chunk {i+1}/{num_chunks} (~{chunk_tokens:,} tokens)..."
                            )
                            logger.info(f"Summarizing chunk {i+1}/{num_chunks} ({chunk_tokens:,} tokens)...")
                            combined_input = chunk
                        
                        try:
                            if previous_memory:
                                # Recursive: summarize previous memory + new chunk
                                chunk_summary = await self._summarize_chunk(
                                    combined_input, 
                                    summarization_prompt, 
                                    ollama_host, 
                                    effective_model
                                )
                            else:
                                # First chunk: summarize normally
                                chunk_summary = await self._summarize_chunk(
                                    chunk, 
                                    summarization_prompt, 
                                    ollama_host, 
                                    effective_model
                                )
                            
                            if chunk_summary:
                                previous_memory = chunk_summary  # Update memory for next iteration
                            else:
                                logger.warning(f"Failed to summarize chunk {i+1}, continuing with previous memory...")
                        except Exception as e:
                            logger.warning(f"Failed to summarize chunk {i+1}: {e}. Continuing with previous memory...")
                    
                    # Return the final recursive memory
                    if previous_memory:
                        logger.info(f"Recursive summarization complete. Final summary: {len(previous_memory) // 4:,} tokens")
                        return previous_memory
                    return None
                else:
                    # Standard parallel summarization: summarize chunks independently, then combine
                    summaries = []
                    
                    for i, chunk in enumerate(chunks):
                        # Update progress for each chunk (50-85% range for chunking)
                        chunk_progress = 50.0 + (i / num_chunks) * 35.0
                        chunk_tokens = len(chunk) // 4
                        self._emit_progress(
                            ProgressState.UPDATE, 
                            chunk_progress, 
                            f"Summarizing chunk {i+1}/{num_chunks} (~{chunk_tokens:,} tokens)..."
                        )
                        
                        if (i + 1) % 10 == 0 or i == 0:  # Log every 10th chunk to reduce spam
                            logger.info(f"Summarizing chunk {i+1}/{num_chunks} ({chunk_tokens:,} tokens)...")
                        try:
                            chunk_summary = await self._summarize_chunk(chunk, summarization_prompt, ollama_host, effective_model)
                            if chunk_summary:
                                summaries.append(chunk_summary)
                        except Exception as e:
                            logger.warning(f"Failed to summarize chunk {i+1}: {e}")
                    
                    if summaries:
                        # Summarize the summaries if we have multiple chunks
                        if len(summaries) > 1:
                            self._emit_progress(ProgressState.UPDATE, 85.0, "Combining chunk summaries...")
                            logger.info(f"Combining {len(summaries)} chunk summaries...")
                            combined = "\n\n".join(summaries)
                            return await self._summarize_chunk(combined, summarization_prompt, ollama_host, effective_model)
                        return summaries[0]
                    return None
            else:
                # Single chunk - summarize directly
                self._emit_progress(ProgressState.UPDATE, 60.0, f"Summarizing single chunk (~{text_tokens:,} tokens)...")
                return await self._summarize_chunk(text, summarization_prompt, ollama_host, effective_model)
        
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
                                {"role": "user", "content": f"Summarize this indicator data:\n\n{text}"}
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
    
    async def _summarize_chunk(self, text: str, prompt: str, ollama_host: str, model: str) -> str | None:
        """Summarize a single chunk of text using Ollama."""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:  # Longer timeout for large chunks
                response = await client.post(
                    f"{ollama_host}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": f"Summarize this indicator data:\n\n{text}"}
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
        except httpx.TimeoutException:
            logger.error(f"❌ Ollama summarization timed out. The text might be too large or Ollama is slow.")
            return None
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if hasattr(e.response, 'text') else str(e)
            if e.response.status_code == 404 and "not found" in error_text.lower():
                logger.error(
                    f"❌ Ollama model '{model}' not found. "
                    f"Install with: 'ollama pull gemma2:2b' or 'ollama pull llama3.2:1b'. "
                    f"Or switch to OpenRouter summarization mode."
                )
            else:
                logger.error(f"❌ Ollama HTTP error: {e.response.status_code}: {error_text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ollama summarization failed: {e}")
            import traceback
            logger.debug(f"Full error: {traceback.format_exc()}")
            return None
    
    def _chunk_text(self, text: str, max_chunk_size: int) -> list[str]:
        """Split text into chunks that fit within token limits, trying to break at logical boundaries."""
        chunks = []
        current_chunk = ""
        
        # Split by sections (=== headers) first
        sections = text.split("\n===")
        
        for i, section in enumerate(sections):
            # Add back the === if not first section
            if i > 0:
                section = "===" + section
            
            # If section fits, add it
            if len(current_chunk) + len(section) < max_chunk_size:
                current_chunk += section + "\n"
            else:
                # Save current chunk if it has content
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                # If section itself is too large, split by lines
                if len(section) > max_chunk_size:
                    lines = section.split("\n")
                    temp_chunk = ""
                    for line in lines:
                        if len(temp_chunk) + len(line) < max_chunk_size:
                            temp_chunk += line + "\n"
                        else:
                            if temp_chunk.strip():
                                chunks.append(temp_chunk.strip())
                            temp_chunk = line + "\n"
                    current_chunk = temp_chunk
                else:
                    current_chunk = section + "\n"
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the synthesizer node."""
        # Start execution
        self._emit_progress(ProgressState.START, 0.0, "Starting data synthesis...")
        
        # Get inputs
        images = inputs.get("images") or {}
        ohlcv_bundle = inputs.get("ohlcv_bundle") or {}

        # Collect all indicator data - both primary and explicit named inputs
        self._emit_progress(ProgressState.UPDATE, 5.0, "Collecting indicator data...")
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
        ohlcv_max_bars = int(self.params.get("ohlcv_max_bars", 20))  # Default 20 (increased - summarization handles large data)
        format_style = str(self.params.get("format_style", "readable")).lower()
        recent_bars_count = int(self.params.get("recent_bars_count", 50))  # Default 50 (increased - summarization handles large data)
        max_symbols = int(self.params.get("max_symbols", 20))  # Default 20 (increased - summarization handles large data)
        # Smart default: if summarization is enabled, show full data (False). Otherwise, save tokens (True).
        enable_summarization = self.params.get("enable_summarization", False)
        summarize_full_dataset_param = self.params.get("summarize_full_dataset", False)
        summarize_full_dataset = summarize_full_dataset_param and enable_summarization
        summary_only_default = False if enable_summarization else True  # Show data if summarization will compress it
        summary_only = self.params.get("summary_only", summary_only_default) or format_style == "summary"
        
        # Log current settings for debugging - CRITICAL DEBUG
        logger.warning(
            f"🔍 IndicatorDataSynthesizer DEBUG: enable_summarization={enable_summarization}, "
            f"summarize_full_dataset_param={summarize_full_dataset_param}, "
            f"summarize_full_dataset={summarize_full_dataset}, summary_only={summary_only}"
        )
        logger.info(
            f"IndicatorDataSynthesizer: max_symbols={max_symbols}, recent_bars_count={recent_bars_count}, "
            f"include_ohlcv={include_ohlcv}, ohlcv_max_bars={ohlcv_max_bars}, "
            f"summarize_full_dataset={summarize_full_dataset}"
        )

        # Build formatted text based on format style
        self._emit_progress(ProgressState.UPDATE, 15.0, "Formatting data...")
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
        
        # SMART AUTO-REDUCTION: When dealing with many symbols, automatically reduce bars to prevent token explosion
        # This applies regardless of summarization settings
        effective_recent_bars = recent_bars_count
        effective_ohlcv_bars = ohlcv_max_bars
        total_symbols = len(ohlcv_bundle) if ohlcv_bundle else 0
        
        if total_symbols > 20:  # Many symbols detected
            # With 20+ symbols, cap at 20 bars max to prevent millions of tokens
            max_bars_for_many_symbols = 20
            if recent_bars_count > max_bars_for_many_symbols:
                effective_recent_bars = max_bars_for_many_symbols
                logger.warning(
                    f"🔄 IndicatorDataSynthesizer: Auto-reducing bars from {recent_bars_count} to {effective_recent_bars} "
                    f"due to {total_symbols} symbols (>20 symbols triggers auto-reduction to prevent token explosion)"
                )
            if ohlcv_max_bars > max_bars_for_many_symbols:
                effective_ohlcv_bars = max_bars_for_many_symbols
        elif total_symbols > 10:  # Moderate number of symbols
            # With 10-20 symbols, cap at 30 bars max
            max_bars_for_moderate_symbols = 30
            if recent_bars_count > max_bars_for_moderate_symbols:
                effective_recent_bars = max_bars_for_moderate_symbols
                logger.info(
                    f"🔄 IndicatorDataSynthesizer: Auto-reducing bars from {recent_bars_count} to {effective_recent_bars} "
                    f"due to {total_symbols} symbols (10-20 symbols triggers moderate reduction)"
                )
            if ohlcv_max_bars > max_bars_for_moderate_symbols:
                effective_ohlcv_bars = max_bars_for_moderate_symbols

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
                
                total_indicators = len([d for d in indicator_data_list if d is not None])
                for i, indicator_data in enumerate(indicator_data_list):
                    if indicator_data is None:
                        continue
                    
                    # Auto-detect indicator name from data structure
                    input_name = input_names[i] if i < len(input_names) else None
                    indicator_name = self._detect_indicator_name(indicator_data, input_name)
                    
                    # Update progress during formatting
                    if total_indicators > 0:
                        progress = 20.0 + (i / total_indicators) * 20.0  # 20-40% for indicators
                        self._emit_progress(ProgressState.UPDATE, progress, f"Formatting {indicator_name or f'indicator {i+1}'}...")
                    
                    formatted_text = self._format_generic_indicator(
                        indicator_data, indicator_name, effective_recent_bars, input_name, summary_only, max_symbols
                    )
                    if formatted_text:
                        formatted_sections.append(formatted_text)
                    
                    # Store in combined_data with meaningful key
                    # Use detected name or fallback to numbered key
                    if indicator_name and indicator_name != "Indicator Data":
                        # Create a safe key from indicator name
                        safe_key = indicator_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
                        combined_data[safe_key] = indicator_data
                        combined_data[f"indicator_{i+1}"] = indicator_data  # Also keep numbered key for compatibility
                    else:
                        combined_data[f"indicator_{i+1}"] = indicator_data

            if include_ohlcv and ohlcv_bundle:
                self._emit_progress(ProgressState.UPDATE, 45.0, f"Formatting OHLCV data ({len(ohlcv_bundle)} symbols)...")
                formatted_sections.append(
                    self._format_ohlcv_bundle(ohlcv_bundle, effective_ohlcv_bars, summary_only, max_symbols)
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
                        safe_key = indicator_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
                        labeled_indicators[safe_key] = indicator_data
                    else:
                        labeled_indicators[f"indicator_{i+1}"] = indicator_data
                
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
                        safe_key = indicator_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
                        labeled_indicators[safe_key] = indicator_data
                    else:
                        labeled_indicators[f"indicator_{i+1}"] = indicator_data
                
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
        
        logger.info(
            f"IndicatorDataSynthesizer: Processed {len(output_images)} images, "
            f"{len(indicator_data_list)} indicator inputs, {len(ohlcv_bundle)} OHLCV symbols. "
            f"Formatted text (recent bars): ~{formatted_text_size:,} chars (~{estimated_tokens:,} tokens). "
            f"Settings: max_symbols={max_symbols}, recent_bars_count={effective_recent_bars} (requested: {recent_bars_count})"
        )
        
        # Log preview of formatted text to verify data is included
        if formatted_text:
            preview_lines = formatted_text.split('\n')[:20]  # First 20 lines
            preview = '\n'.join(preview_lines)
            logger.info(f"📊 IndicatorDataSynthesizer: Recent bars preview (first 20 lines):\n{preview}")
            if len(formatted_text.split('\n')) > 20:
                logger.info(f"   ... ({len(formatted_text.split('\n')) - 20} more lines)")
        
        # Store recent detail (already formatted with summary_only=False and recent_bars_count limit)
        recent_detail = formatted_text
        
        # Optional AI summarization step - DO THIS BEFORE TRUNCATION
        # This allows summarization to work on the full dataset, reducing token count significantly
        logger.warning(f"🔍 DEBUG: About to check hybrid approach. summarize_full_dataset={summarize_full_dataset}")
        if summarize_full_dataset:
            # HYBRID APPROACH: Summarize full dataset (historical) + format recent bars (detail)
            logger.info("🔄 IndicatorDataSynthesizer: Using hybrid approach - summarizing full dataset + formatting recent bars")
            self._emit_progress(ProgressState.UPDATE, 40.0, "Preparing hybrid summarization (full dataset + recent detail)...")
            
            # CRITICAL: When using hybrid approach, reduce recent detail bars to prevent token explosion
            # The historical summary already provides full context, so we only need a small recent sample
            # With many symbols (40+), even 30 bars generates millions of tokens, so cap at 10 bars
            # Note: effective_recent_bars may already be reduced by auto-reduction logic above
            recent_detail_bars = min(effective_recent_bars, 10)  # Cap at 10 bars for detail when using hybrid (was 30, but still too large)
            
            # ALWAYS re-format recent detail when using hybrid mode (don't check if it's less)
            # This ensures we use the reduced bar count even if user already reduced recent_bars_count
            logger.info(f"📉 IndicatorDataSynthesizer: Using {recent_detail_bars} bars for recent detail in hybrid mode (reduced from {effective_recent_bars} to prevent token explosion)")
            
            # Re-format recent detail with smaller bar count
            recent_detail_sections: list[str] = []
            if include_indicators and indicator_data_list:
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
                    input_name = input_names[i] if i < len(input_names) else None
                    indicator_name = self._detect_indicator_name(indicator_data, input_name)
                    detail_text = self._format_generic_indicator(
                        indicator_data, indicator_name, recent_detail_bars, input_name, False, max_symbols  # summary_only=False, but fewer bars
                    )
                    if detail_text:
                        recent_detail_sections.append(detail_text)
            
            if include_ohlcv and ohlcv_bundle:
                recent_detail_sections.append(
                    self._format_ohlcv_bundle(ohlcv_bundle, min(ohlcv_max_bars, recent_detail_bars), False, max_symbols)
                )
            
            recent_detail = "\n\n".join(filter(None, recent_detail_sections))
            
            # Step 1: Format FULL dataset with summary_only=True (stats only, no bar limit)
            # Use a very high limit to get all bars, but summary_only=True means we only get stats
            self._emit_progress(ProgressState.UPDATE, 40.0, "Formatting full dataset for historical summary...")
            full_dataset_sections: list[str] = []
            
            if include_indicators and indicator_data_list:
                input_names = []
                if inputs.get("indicator_data") is not None:
                    input_names.append("indicator_data")
                for i in range(1, 6):
                    key = f"indicator_data_{i}"
                    if inputs.get(key) is not None:
                        input_names.append(key)
                
                total_indicators = len([d for d in indicator_data_list if d is not None])
                for i, indicator_data in enumerate(indicator_data_list):
                    if indicator_data is None:
                        continue
                    
                    input_name = input_names[i] if i < len(input_names) else None
                    indicator_name = self._detect_indicator_name(indicator_data, input_name)
                    
                    # Update progress
                    if total_indicators > 0:
                        progress = 40.0 + (i / total_indicators) * 5.0  # 40-45% for full dataset formatting
                        self._emit_progress(ProgressState.UPDATE, progress, f"Formatting full dataset: {indicator_name or f'indicator {i+1}'}...")
                    
                    # Format with summary_only=True and very high limit (effectively no limit for stats)
                    # summary_only=True means we only get stats, not individual values
                    full_text = self._format_generic_indicator(
                        indicator_data, indicator_name, 999999, input_name, True, max_symbols  # summary_only=True, high limit
                    )
                    if full_text:
                        full_dataset_sections.append(full_text)
            
            if include_ohlcv and ohlcv_bundle:
                self._emit_progress(ProgressState.UPDATE, 45.0, f"Formatting full OHLCV dataset ({len(ohlcv_bundle)} symbols)...")
                full_dataset_sections.append(
                    self._format_ohlcv_bundle(ohlcv_bundle, 999999, True, max_symbols)  # summary_only=True, high limit
                )
            
            full_dataset_text = "\n\n".join(filter(None, full_dataset_sections))
            
            # Step 2: Summarize full dataset → historical summary
            if full_dataset_text:
                full_tokens = len(full_dataset_text) // 4
                self._emit_progress(ProgressState.UPDATE, 46.0, f"Summarizing full dataset (~{full_tokens:,} tokens)...")
                logger.info(f"IndicatorDataSynthesizer: Summarizing full dataset (~{full_tokens:,} tokens) for historical context...")
                
                try:
                    historical_summary = await self._summarize_text(full_dataset_text)
                    if historical_summary and len(historical_summary.strip()) > 0:
                        hist_tokens = len(historical_summary) // 4
                        reduction_pct = 100 * (1 - hist_tokens/full_tokens) if full_tokens > 0 else 0
                        logger.info(
                            f"✅ IndicatorDataSynthesizer: Full dataset summarized! "
                            f"Reduced from ~{full_tokens:,} to ~{hist_tokens:,} tokens ({reduction_pct:.1f}% reduction) - historical context"
                        )
                    else:
                        logger.warning("IndicatorDataSynthesizer: Full dataset summarization returned empty. Using formatted stats instead.")
                        historical_summary = full_dataset_text  # Fallback to formatted stats
                except Exception as e:
                    logger.error(f"❌ IndicatorDataSynthesizer: Full dataset summarization failed: {e}. Using formatted stats instead.")
                    historical_summary = full_dataset_text  # Fallback to formatted stats
            else:
                historical_summary = ""
            
            # Step 3: Recent detail is already formatted (summary_only=False, recent_bars_count limit)
            # This was done above as `formatted_text` (now stored as `recent_detail`)
            
            # Step 4: Combine both
            if historical_summary and recent_detail:
                # Use recent_detail_bars (which is already capped at 10 for hybrid mode) or recent_bars_count
                actual_recent_bars = recent_detail_bars if summarize_full_dataset else recent_bars_count
                formatted_text = f"=== HISTORICAL SUMMARY (Full Dataset) ===\n\n{historical_summary}\n\n=== RECENT DETAIL (Last {actual_recent_bars} bars) ===\n\n{recent_detail}"
                estimated_tokens = len(formatted_text) // 4
                formatted_text_size = len(formatted_text)
                logger.info(
                    f"✅ IndicatorDataSynthesizer: Hybrid approach complete! "
                    f"Historical summary: ~{len(historical_summary) // 4:,} tokens, "
                    f"Recent detail: ~{len(recent_detail) // 4:,} tokens, "
                    f"Total: ~{estimated_tokens:,} tokens"
                )
            elif historical_summary:
                formatted_text = f"=== HISTORICAL SUMMARY (Full Dataset) ===\n\n{historical_summary}"
                estimated_tokens = len(formatted_text) // 4
                formatted_text_size = len(formatted_text)
            elif recent_detail:
                formatted_text = recent_detail
                estimated_tokens = len(formatted_text) // 4
                formatted_text_size = len(formatted_text)
        
        elif enable_summarization and formatted_text:
            self._emit_progress(ProgressState.UPDATE, 50.0, f"Starting summarization (~{estimated_tokens:,} tokens)...")
            logger.info(f"IndicatorDataSynthesizer: Starting summarization of ~{estimated_tokens:,} tokens...")
            try:
                summarized_text = await self._summarize_text(formatted_text)
                if summarized_text and len(summarized_text.strip()) > 0:
                    summarized_tokens = len(summarized_text) // 4
                    reduction_pct = 100 * (1 - summarized_tokens/estimated_tokens) if estimated_tokens > 0 else 0
                    logger.info(f"✅ IndicatorDataSynthesizer: Summarization successful! Reduced from ~{estimated_tokens:,} tokens to ~{summarized_tokens:,} tokens ({reduction_pct:.1f}% reduction)")
                    
                    # Log preview of summarized text to verify data detail is preserved
                    preview_lines = summarized_text.split('\n')[:20]  # First 20 lines
                    preview = '\n'.join(preview_lines)
                    logger.info(f"📊 IndicatorDataSynthesizer: Summarized text preview (first 20 lines):\n{preview}")
                    if len(summarized_text.split('\n')) > 20:
                        logger.info(f"   ... ({len(summarized_text.split('\n')) - 20} more lines)")
                    
                    self._emit_progress(ProgressState.UPDATE, 90.0, f"Summarization complete ({reduction_pct:.1f}% reduction)")
                    formatted_text = summarized_text
                    estimated_tokens = summarized_tokens
                    formatted_text_size = len(formatted_text)
                else:
                    logger.warning(
                        "IndicatorDataSynthesizer: Summarization returned empty result. Using original text. "
                        "If using Ollama, make sure the model is installed: 'ollama pull gemma2:2b' or switch to OpenRouter summarization."
                    )
            except Exception as e:
                logger.error(
                    f"❌ IndicatorDataSynthesizer: Summarization failed: {e}. Using original text. "
                    f"If using Ollama, check: 'ollama list' or switch summarization_mode to 'openrouter'."
                )
                import traceback
                logger.debug(f"Summarization error traceback: {traceback.format_exc()}")
        
        # Hard cap: If we're still generating too much after summarization, truncate
        # Many modern models (Gemini 2.5 Pro, Claude 3.5 Sonnet, etc.) support 1M+ token context windows
        # Set cap to 500k to allow substantial data while leaving room for output and safety margin
        MAX_TOKENS = 900000  # Hard cap at 900k tokens (~3.6MB text) - Increased to allow more data with summarization
        if estimated_tokens > MAX_TOKENS:
            logger.error(
                f"⚠️ IndicatorDataSynthesizer: Formatted text still exceeds hard cap ({estimated_tokens:,} tokens > {MAX_TOKENS:,}) after summarization. "
                f"Truncating to prevent API errors. Current settings: max_symbols={max_symbols}, recent_bars_count={recent_bars_count}, "
                f"include_ohlcv={include_ohlcv}"
            )
            # Truncate to ~500k tokens worth of text
            max_chars = MAX_TOKENS * 4
            formatted_text = formatted_text[:max_chars] + "\n\n[TRUNCATED - Text exceeded token limit even after summarization. Consider reducing max_symbols or recent_bars_count.]"
            estimated_tokens = MAX_TOKENS
        
        # Warn if text is very large (but still under the cap)
        if estimated_tokens > 600_000:
            logger.warning(
                f"IndicatorDataSynthesizer: Large formatted text detected (~{estimated_tokens:,} tokens). "
                f"Consider enabling summarization to reduce token usage, or reduce max_symbols/recent_bars_count."
            )

        # Finalize
        self._emit_progress(ProgressState.DONE, 100.0, f"Complete (~{estimated_tokens:,} tokens)")

        # Final logging: Show what's being sent to OpenRouter
        final_tokens = len(formatted_text) // 4 if formatted_text else 0
        logger.info(
            f"📤 IndicatorDataSynthesizer: Final output ready - "
            f"~{final_tokens:,} tokens of text data, {len(output_images)} images. "
            f"This will be sent to OpenRouter for analysis."
        )
        
        return {
            "images": output_images,
            "formatted_text": formatted_text,
            "combined_data": combined_data,
        }
