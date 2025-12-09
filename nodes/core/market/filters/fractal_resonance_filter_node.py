"""
Fractal Resonance Filter Node

Filters assets based on Fractal Resonance indicator signals.
Requires ALL timeframe lines (1x, 2x, 4x, 8x, 16x, 32x, 64x, 128x) to be green
at the same vertical position (same bar index) to pass the filter.
"""

import json
import logging
from typing import Any

import numpy as np

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar, get_type
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.fractal_resonance_calculator import calculate_fractal_resonance

logger = logging.getLogger(__name__)


class FractalResonanceFilter(BaseIndicatorFilter):
    """
    Filters assets based on Fractal Resonance indicator signals.
    
    Requires ALL 8 timeframe lines (1x, 2x, 4x, 8x, 16x, 32x, 64x, 128x) to be green
    (bullish, wtA > wtB) at the same vertical position (same bar index) to pass the filter.
    """
    
    default_params = {
        "n1": 10,  # Channel Length
        "n2": 21,  # Stochastic Ratio Length
        "crossover_sma_len": 3,  # Crossover Lag
        "ob_level": 75.0,  # Overbought level
        "ob_embed_level": 88.0,  # Embedded overbought level
        "ob_extreme_level": 100.0,  # Extreme overbought level
        "cross_separation": 3.0,  # Embed separation
        "check_last_bar_only": True,  # If True, only check the last bar; if False, check last N bars
        "lookback_bars": 5,  # Number of bars to check if check_last_bar_only is False
        "min_green_timeframes": 8,  # Minimum number of timeframes that must be green (1-8). 8 = all must be green
    }

    params_meta = [
        {
            "name": "n1",
            "type": "number",
            "default": 10,
            "min": 1,
            "step": 1,
            "description": "Channel Length (>1)",
        },
        {
            "name": "n2",
            "type": "number",
            "default": 21,
            "min": 1,
            "step": 1,
            "description": "Stochastic Ratio Length (>1)",
        },
        {
            "name": "crossover_sma_len",
            "type": "number",
            "default": 3,
            "min": 1,
            "step": 1,
            "description": "Crossover Lag (>1)",
        },
        {
            "name": "ob_level",
            "type": "number",
            "default": 75.0,
            "min": 0.0,
            "step": 1.0,
            "description": "Overbought level",
        },
        {
            "name": "ob_embed_level",
            "type": "number",
            "default": 88.0,
            "min": 0.0,
            "step": 1.0,
            "description": "Embedded overbought level",
        },
        {
            "name": "ob_extreme_level",
            "type": "number",
            "default": 100.0,
            "min": 0.0,
            "step": 1.0,
            "description": "Extreme overbought level",
        },
        {
            "name": "cross_separation",
            "type": "number",
            "default": 3.0,
            "min": 0.0,
            "step": 0.1,
            "description": "Embed separation",
        },
        {
            "name": "check_last_bar_only",
            "type": "boolean",
            "default": True,
            "description": "If True, only check the last bar for all-green condition; if False, check last N bars",
        },
        {
            "name": "lookback_bars",
            "type": "number",
            "default": 5,
            "min": 1,
            "step": 1,
            "description": "Number of bars to check if check_last_bar_only is False",
        },
        {
            "name": "min_green_timeframes",
            "type": "number",
            "default": 8,
            "min": 1,
            "max": 8,
            "step": 1,
            "description": "Ideal number of timeframes to check (8 = all timeframes). Filter will accept symbols with 3-4+ timeframes if all are green. For daily data: 3 months = 4 TFs, 2 years = 6 TFs, 7+ years = 8 TFs",
        },
    ]

    def _validate_indicator_params(self):
        self.n1 = int(self.params.get("n1", 10))
        self.n2 = int(self.params.get("n2", 21))
        self.crossover_sma_len = int(self.params.get("crossover_sma_len", 3))
        self.ob_level = float(self.params.get("ob_level", 75.0))
        self.ob_embed_level = float(self.params.get("ob_embed_level", 88.0))
        self.ob_extreme_level = float(self.params.get("ob_extreme_level", 100.0))
        self.cross_separation = float(self.params.get("cross_separation", 3.0))
        self.check_last_bar_only = bool(self.params.get("check_last_bar_only", True))
        self.lookback_bars = int(self.params.get("lookback_bars", 5))
        self.min_green_timeframes = int(self.params.get("min_green_timeframes", 8))
        # Clamp to valid range
        if self.min_green_timeframes < 1:
            self.min_green_timeframes = 1
        elif self.min_green_timeframes > 8:
            self.min_green_timeframes = 8

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate Fractal Resonance and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="No data",
            )

        # Extract closes
        closes = [bar["close"] for bar in ohlcv_data]
        
        # Validate we have data
        valid_closes = [c for c in closes if c is not None and c != 0]
        if len(valid_closes) < 100:  # Need at least some data for calculation
            logger.debug(
                f"FractalResonanceFilter: Insufficient data - only {len(valid_closes)}/{len(closes)} valid closes"
            )
            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=ohlcv_data[-1]["timestamp"] if ohlcv_data else 0,
                values=IndicatorValue(lines={}),
                params=self.params,
                error=f"Insufficient data: {len(valid_closes)} valid closes",
            )
        
        # Forward-fill any None/zero closes to avoid breaking calculations
        for i in range(len(closes)):
            if closes[i] is None or closes[i] == 0:
                # Find the last valid close
                for j in range(i - 1, -1, -1):
                    if closes[j] is not None and closes[j] != 0:
                        closes[i] = closes[j]
                        break
                # If no previous valid close found, use the next valid one
                if closes[i] is None or closes[i] == 0:
                    for j in range(i + 1, len(closes)):
                        if closes[j] is not None and closes[j] != 0:
                            closes[i] = closes[j]
                            break

        # Calculate Fractal Resonance
        try:
            logger.debug(
                f"FractalResonanceFilter: Starting calculation for symbol with {len(closes)} closes "
                f"({len(valid_closes)} initially valid)"
            )
            fr_result = calculate_fractal_resonance(
                closes=closes,
                n1=self.n1,
                n2=self.n2,
                crossover_sma_len=self.crossover_sma_len,
                ob_level=self.ob_level,
                ob_embed_level=self.ob_embed_level,
                ob_extreme_level=self.ob_extreme_level,
                cross_separation=self.cross_separation,
            )

            # Get wt_a and wt_b for all timeframes
            wt_a_dict = fr_result.get("wt_a", {})
            wt_b_dict = fr_result.get("wt_b", {})
            block_colors_dict = fr_result.get("block_colors", {})
            
            # Debug: Log what we got from the calculation
            logger.debug(
                f"FractalResonanceFilter: Calculation result - wt_a_dict keys: {list(wt_a_dict.keys())}, "
                f"wt_b_dict keys: {list(wt_b_dict.keys())}, "
                f"block_colors keys: {list(block_colors_dict.keys())}, "
                f"data length: {len(ohlcv_data)}"
            )
            
            # Warn if block_colors is missing (critical for 16-row check)
            if not block_colors_dict:
                logger.warning(
                    f"⚠️ FractalResonanceFilter: block_colors_dict is EMPTY! "
                    f"Cannot check block rows. Symbol will FAIL."
                )
                return IndicatorResult(
                    indicator_type=IndicatorType.CUSTOM,
                    timestamp=ohlcv_data[-1]["timestamp"] if ohlcv_data else 0,
                    values=IndicatorValue(lines={}),
                    params=self.params,
                    error="block_colors_dict is empty - cannot verify all 16 rows",
                )
            # Debug logging for QXO (check in _should_pass_filter where symbol is available)
            if wt_a_dict:
                sample_tm = list(wt_a_dict.keys())[0]
                logger.debug(
                    f"FractalResonanceFilter: Sample timeframe {sample_tm} - "
                    f"wt_a length: {len(wt_a_dict[sample_tm])}, "
                    f"wt_b length: {len(wt_b_dict.get(sample_tm, []))}, "
                    f"block_colors length: {len(block_colors_dict.get(sample_tm, []))}"
                )
            
            # Time multipliers: 1, 2, 4, 8, 16, 32, 64, 128
            time_multipliers = [1, 2, 4, 8, 16, 32, 64, 128]
            
            # Find bars where ALL 16 visual rows are green (8 color rows + 8 block rows)
            # This means: wtA > wtB for all timeframes AND block_color is NOT white (not embedded)
            all_green_bars = []
            
            # Determine which bars to check
            if self.check_last_bar_only:
                check_indices = [len(ohlcv_data) - 1]
            else:
                lookback = min(self.lookback_bars, len(ohlcv_data))
                start_idx = max(0, len(ohlcv_data) - lookback)
                check_indices = list(range(start_idx, len(ohlcv_data)))
            
            for bar_idx in check_indices:
                if bar_idx < 0 or bar_idx >= len(ohlcv_data):
                    continue
                
                # Count how many timeframes have ALL 16 rows green (color + block)
                green_count = 0
                valid_timeframes_count = 0  # Count only timeframes with valid data
                failed_timeframes = []
                
                for tm in time_multipliers:
                    # Convert integer key to string (calculator returns string keys)
                    tm_key = str(tm)
                    wt_a_list = wt_a_dict.get(tm_key, [])
                    wt_b_list = wt_b_dict.get(tm_key, [])
                    block_colors_list = block_colors_dict.get(tm_key, [])
                    
                    if bar_idx >= len(wt_a_list) or bar_idx >= len(wt_b_list):
                        failed_timeframes.append(f"WT{tm}(missing)")
                        continue
                    
                    a_val = wt_a_list[bar_idx]
                    b_val = wt_b_list[bar_idx]
                    
                    # Green means bullish: wtA > wtB (and both must be valid)
                    if a_val is None or b_val is None:
                        failed_timeframes.append(f"WT{tm}(None)")
                        continue
                    
                    # This timeframe has valid data
                    valid_timeframes_count += 1
                    
                    # Check both conditions:
                    # 1. Color row must be green (wtA > wtB)
                    # 2. Block row must NOT be white (not embedded)
                    is_color_green = a_val > b_val
                    
                    # Get block color - handle missing data
                    if bar_idx >= len(block_colors_list):
                        # Block colors missing - treat as not green to be safe
                        block_color = None
                        is_block_green = False
                    else:
                        block_color = block_colors_list[bar_idx]
                        # Block is green if it's NOT white (white = embedded)
                        is_block_green = block_color not in [None, "#ffffff", "#FFFFFF", "white"]
                    
                    if is_color_green and is_block_green:
                        green_count += 1
                    else:
                        if not is_color_green:
                            failed_timeframes.append(f"WT{tm}(a={a_val:.2f}<=b={b_val:.2f})")
                        elif not is_block_green:
                            failed_timeframes.append(f"WT{tm}(embedded:{block_color})")
                
                # Check if we have enough green timeframes
                # STRICT MODE: Require ALL valid timeframes to be green (or at least min_green_timeframes, whichever is stricter)
                # This ensures symbols with full data (8 timeframes) must have all 8 green
                if valid_timeframes_count == 0:
                    # No valid timeframes at all - fail
                    if len(all_green_bars) == 0:
                        logger.debug(
                            f"❌ FractalResonanceFilter: FAIL - No valid timeframes at bar {bar_idx}"
                        )
                    continue
                
                # Require: ALL valid timeframes must be green
                # For symbols with full data (8 timeframes), require all 8 to be green (all 16 visual rows)
                # For symbols with partial data (6-7 timeframes), require ALL of them to be green
                # This ensures we get the maximum possible green rows for each symbol
                required_count = valid_timeframes_count  # Require ALL valid timeframes to be green
                
                # Minimum threshold: Require at least 6 valid timeframes to avoid false positives from limited data
                # Many symbols don't have enough historical data for 64x/128x timeframes, so we allow 6-7 timeframes
                # But we still require ALL of them to be green
                min_required_valid = max(6, self.min_green_timeframes - 2)  # At least 6 valid timeframes (prefer 8)
                
                # Skip if we have too few valid timeframes (less than minimum threshold)
                if valid_timeframes_count < min_required_valid:
                    if len(all_green_bars) == 0:
                        logger.debug(
                            f"❌ FractalResonanceFilter: FAIL - Only {valid_timeframes_count} valid timeframes "
                            f"(need at least {min_required_valid} valid timeframes, ideal: {self.min_green_timeframes})"
                        )
                    continue
                
                if green_count >= required_count:
                    all_green_bars.append(bar_idx)
                    visual_rows = green_count * 2  # Each timeframe has 2 visual rows (color + block)
                    logger.debug(
                        f"✅ FractalResonanceFilter: PASS - Symbol has ALL {visual_rows} visual rows green "
                        f"({green_count}/{valid_timeframes_count} timeframes, {green_count*2} visual rows) "
                        f"at bar {bar_idx} (color rows green AND block rows NOT white/embedded)"
                    )
                else:
                    # Only log first few failures to avoid spam, but make them visible
                    if len(all_green_bars) == 0:  # Only log if this is the first check and it failed
                        logger.debug(
                            f"❌ FractalResonanceFilter: FAIL - Symbol has only {green_count}/{valid_timeframes_count} green timeframes "
                            f"at bar {bar_idx} (required: {required_count} = ALL valid TFs). "
                            f"Failed: {', '.join(failed_timeframes[:5])}"
                        )
            
            # Store results in IndicatorResult
            has_signal = len(all_green_bars) > 0
            last_green_bar_idx = all_green_bars[-1] if all_green_bars else -1
            last_green_bar_timestamp = (
                ohlcv_data[last_green_bar_idx]["timestamp"] if last_green_bar_idx >= 0 else -1.0
            )
            
            # Calculate max green count and valid timeframes for the last bar (for debugging)
            # IMPORTANT: Must check BOTH color row (wtA > wtB) AND block row (not white) to match filter logic
            max_green_count = 0
            valid_timeframes_at_last_bar = 0
            failed_timeframes_at_last_bar = []
            timeframe_details_at_last_bar = []  # Store detailed info for each timeframe
            if check_indices:
                last_idx = check_indices[-1]
                green_count = 0
                valid_count = 0
                for tm in time_multipliers:
                    # Convert integer key to string (calculator returns string keys)
                    tm_key = str(tm)
                    wt_a_list = wt_a_dict.get(tm_key, [])
                    wt_b_list = wt_b_dict.get(tm_key, [])
                    block_colors_list = block_colors_dict.get(tm_key, [])
                    
                    if last_idx < len(wt_a_list) and last_idx < len(wt_b_list):
                        a_val = wt_a_list[last_idx]
                        b_val = wt_b_list[last_idx]
                        if a_val is not None and b_val is not None:
                            valid_count += 1
                            
                            # Check BOTH conditions (same as filter logic):
                            # 1. Color row must be green (wtA > wtB)
                            # 2. Block row must NOT be white (not embedded)
                            is_color_green = a_val > b_val
                            
                            # Get block color - handle missing data
                            if last_idx >= len(block_colors_list):
                                is_block_green = False
                                block_color = None
                            else:
                                block_color = block_colors_list[last_idx]
                                # Block is green if it's NOT white (white = embedded)
                                is_block_green = block_color not in [None, "#ffffff", "#FFFFFF", "white"]
                            
                            # Store detailed info for debugging
                            timeframe_details_at_last_bar.append({
                                "timeframe": tm,
                                "a_val": a_val,
                                "b_val": b_val,
                                "is_color_green": is_color_green,
                                "block_color": block_color,
                                "is_block_green": is_block_green,
                                "is_both_green": is_color_green and is_block_green,
                            })
                            
                            if is_color_green and is_block_green:
                                green_count += 1
                            else:
                                # Track which timeframes failed and why
                                if not is_color_green:
                                    failed_timeframes_at_last_bar.append(f"WT{tm}(a={a_val:.2f}<=b={b_val:.2f})")
                                elif not is_block_green:
                                    failed_timeframes_at_last_bar.append(f"WT{tm}(embedded:{block_color})")
                max_green_count = green_count
                valid_timeframes_at_last_bar = valid_count
            
            # Store timeframe details as JSON string for debugging (QXO/MRNA)
            timeframe_details_json = json.dumps(timeframe_details_at_last_bar, default=str)
            
            result_dict = {
                "has_all_green_signal": 1.0 if has_signal else 0.0,
                "total_all_green_bars": float(len(all_green_bars)),
                "last_all_green_bar_idx": float(last_green_bar_idx),
                "last_all_green_bar_timestamp": float(last_green_bar_timestamp),
                "checked_bars": float(len(check_indices)),
                "max_green_count_at_last_bar": float(max_green_count),
                "valid_timeframes_at_last_bar": float(valid_timeframes_at_last_bar),
                "min_required_green": float(self.min_green_timeframes),
                "failed_timeframes_at_last_bar": ",".join(failed_timeframes_at_last_bar[:10]),  # Limit to first 10
                "timeframe_details_at_last_bar": timeframe_details_json,  # JSON string for debugging
            }
            
            required_at_last_bar = max(self.min_green_timeframes, valid_timeframes_at_last_bar) if valid_timeframes_at_last_bar > 0 else self.min_green_timeframes
            logger.debug(
                f"FractalResonanceFilter: Symbol result - {len(all_green_bars)} qualifying bars "
                f"(checked {len(check_indices)} bars, required: {required_at_last_bar} = ALL valid TFs must be green, "
                f"last bar has {max_green_count}/{valid_timeframes_at_last_bar} green timeframes, {valid_timeframes_at_last_bar} valid TFs)"
            )

            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines=result_dict),
                params=self.params,
            )

        except Exception as e:
            import traceback
            logger.error(
                f"❌ FractalResonanceFilter: Failed to calculate Fractal Resonance: {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            return IndicatorResult(
                indicator_type=IndicatorType.CUSTOM,
                timestamp=ohlcv_data[-1]["timestamp"] if ohlcv_data else 0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error=str(e),
            )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if there's at least one bar where all timeframes are green."""
        if indicator_result.error:
            logger.debug(f"FractalResonanceFilter: Indicator error: {indicator_result.error}")
            return False

        if not hasattr(indicator_result.values, "lines"):
            logger.debug("FractalResonanceFilter: No lines in indicator result")
            return False

        result_dict = indicator_result.values.lines
        if not isinstance(result_dict, dict):
            logger.debug("FractalResonanceFilter: Result dict is not a dict")
            return False

        has_signal = result_dict.get("has_all_green_signal", 0.0) > 0.0
        total_green_bars = result_dict.get("total_all_green_bars", 0.0)
        last_green_idx = result_dict.get("last_all_green_bar_idx", -1.0)
        
        max_green = result_dict.get("max_green_count_at_last_bar", 0.0)
        min_required = result_dict.get("min_required_green", 8.0)
        
        if has_signal:
            logger.debug(
                f"✅ FractalResonanceFilter: PASSED - Found {total_green_bars} qualifying bar(s), "
                f"last at index {last_green_idx}, max green: {max_green:.0f}/{min_required:.0f}"
            )
        else:
            logger.debug(
                f"❌ FractalResonanceFilter: FAILED - No qualifying bars found. "
                f"Last bar has {max_green:.0f}/{min_required:.0f} green timeframes (need {min_required:.0f})"
            )
        
        return has_signal
    
    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Override to add summary logging."""
        from core.types_registry import AssetSymbol, OHLCVBar
        
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}
        total_symbols = len(ohlcv_bundle)
        processed_symbols = 0
        passed_count = 0
        failed_count = 0
        qxo_status = None  # Track QXO's status: "passed", "failed", "not_found", or "error"
        mrna_status = None  # Track MRNA's status: "passed", "failed", "not_found", or "error"

        # Initial progress signal
        try:
            self.report_progress(0.0, f"0/{total_symbols}")
        except Exception:
            pass

        logger.info(f"🔵 FractalResonanceFilter: Starting filter on {total_symbols} symbols (STRICT MODE: ALL 16 rows must be green - color rows AND block rows not white/embedded, min TFs: {self.min_green_timeframes})")
        
        # Check if QXO is in the bundle (keys are AssetSymbol objects, not strings)
        qxo_symbol = None
        for sym in ohlcv_bundle.keys():
            if str(sym).upper() == "QXO" or (hasattr(sym, 'ticker') and sym.ticker.upper() == "QXO"):
                qxo_symbol = sym
                break
        
        if qxo_symbol:
            qxo_status = "found"
            logger.warning(f"🔍 QXO: Found in input bundle! Data length: {len(ohlcv_bundle[qxo_symbol]) if ohlcv_bundle[qxo_symbol] else 0}")
            print(f"🔍 QXO: Found in input bundle! Data length: {len(ohlcv_bundle[qxo_symbol]) if ohlcv_bundle[qxo_symbol] else 0}")
        else:
            qxo_status = "not_found"
            sample_symbols = [str(sym) for sym in list(ohlcv_bundle.keys())[:10]]
            logger.warning(f"🔍 QXO: NOT FOUND in input bundle! Available symbols: {sample_symbols}...")
            print(f"🔍 QXO: NOT FOUND in input bundle!")
        
        # Check if MRNA is in the bundle (keys are AssetSymbol objects, not strings)
        mrna_symbol = None
        for sym in ohlcv_bundle.keys():
            if str(sym).upper() == "MRNA" or (hasattr(sym, 'ticker') and sym.ticker.upper() == "MRNA"):
                mrna_symbol = sym
                break
        
        if mrna_symbol:
            mrna_status = "found"
            logger.warning(f"🔍 MRNA: Found in input bundle! Data length: {len(ohlcv_bundle[mrna_symbol]) if ohlcv_bundle[mrna_symbol] else 0}")
            print(f"🔍 MRNA: Found in input bundle! Data length: {len(ohlcv_bundle[mrna_symbol]) if ohlcv_bundle[mrna_symbol] else 0}")
        else:
            mrna_status = "not_found"
            sample_symbols = [str(sym) for sym in list(ohlcv_bundle.keys())[:10]]
            logger.warning(f"🔍 MRNA: NOT FOUND in input bundle! Available symbols: {sample_symbols}...")
            print(f"🔍 MRNA: NOT FOUND in input bundle!")

        for symbol, ohlcv_data in ohlcv_bundle.items():
            is_qxo = (qxo_symbol is not None and symbol == qxo_symbol) or (str(symbol).upper() == "QXO")
            is_mrna = (mrna_symbol is not None and symbol == mrna_symbol) or (str(symbol).upper() == "MRNA")
            
            # QXO debug: Log when we start processing QXO
            if is_qxo:
                logger.warning(f"🔍 QXO: Starting filter processing - data length: {len(ohlcv_data) if ohlcv_data else 0}")
                print(f"🔍 QXO: Starting filter processing - data length: {len(ohlcv_data) if ohlcv_data else 0}")  # Print as fallback
            
            # MRNA debug: Log when we start processing MRNA
            if is_mrna:
                logger.warning(f"🔍 MRNA: Starting filter processing - data length: {len(ohlcv_data) if ohlcv_data else 0}")
                print(f"🔍 MRNA: Starting filter processing - data length: {len(ohlcv_data) if ohlcv_data else 0}")  # Print as fallback
            
            if not ohlcv_data:
                processed_symbols += 1
                failed_count += 1
                if is_qxo:
                    qxo_status = "failed"
                    logger.warning(f"🔍 QXO: FAILED - No OHLCV data")
                    print(f"🔍 QXO: FAILED - No OHLCV data")
                if is_mrna:
                    mrna_status = "failed"
                    logger.warning(f"🔍 MRNA: FAILED - No OHLCV data")
                    print(f"🔍 MRNA: FAILED - No OHLCV data")
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            try:
                if is_qxo:
                    logger.warning(f"🔍 QXO: Calling _calculate_indicator...")
                    print(f"🔍 QXO: Calling _calculate_indicator...")
                if is_mrna:
                    logger.warning(f"🔍 MRNA: Calling _calculate_indicator...")
                    print(f"🔍 MRNA: Calling _calculate_indicator...")
                indicator_result = self._calculate_indicator(ohlcv_data)
                
                # Debug logging for QXO
                if is_qxo:
                    logger.warning(f"🔍 QXO: IndicatorResult error: {indicator_result.error}")
                    print(f"🔍 QXO: IndicatorResult error: {indicator_result.error}")  # Print as fallback
                    if hasattr(indicator_result.values, "lines"):
                        result_dict = indicator_result.values.lines
                        log_msg = (
                            f"🔍 QXO: has_signal={result_dict.get('has_all_green_signal', 0.0)}, "
                            f"total_green_bars={result_dict.get('total_all_green_bars', 0.0)}, "
                            f"max_green={result_dict.get('max_green_count_at_last_bar', 0.0)}/{result_dict.get('valid_timeframes_at_last_bar', 0.0)} "
                            f"(required: ALL {result_dict.get('valid_timeframes_at_last_bar', 0.0)} must be green)"
                        )
                        logger.warning(log_msg)
                        print(log_msg)  # Print as fallback
                        
                        # Detailed timeframe breakdown for QXO
                        timeframe_details_json = result_dict.get('timeframe_details_at_last_bar', '[]')
                        try:
                            timeframe_details = json.loads(timeframe_details_json) if timeframe_details_json else []
                            logger.warning("🔍 QXO: Detailed timeframe breakdown at last bar:")
                            print("🔍 QXO: Detailed timeframe breakdown at last bar:")
                            for tf_detail in timeframe_details:
                                tf = tf_detail.get('timeframe', '?')
                                a_val = tf_detail.get('a_val', 0)
                                b_val = tf_detail.get('b_val', 0)
                                color_green = tf_detail.get('is_color_green', False)
                                block_color = tf_detail.get('block_color', 'N/A')
                                block_green = tf_detail.get('is_block_green', False)
                                both_green = tf_detail.get('is_both_green', False)
                                
                                status_icon = "✅" if both_green else "❌"
                                color_status = "GREEN" if color_green else f"RED (a={a_val:.2f} <= b={b_val:.2f})"
                                block_status = f"GREEN ({block_color})" if block_green else f"WHITE/EMBEDDED ({block_color})"
                                
                                detail_msg = (
                                    f"  {status_icon} WT{tf}: Color={color_status}, Block={block_status}"
                                )
                                logger.warning(detail_msg)
                                print(detail_msg)
                        except Exception as e:
                            logger.warning(f"🔍 QXO: Could not parse timeframe details: {e}")
                            print(f"🔍 QXO: Could not parse timeframe details: {e}")
                
                # Debug logging for MRNA
                if is_mrna:
                    logger.warning(f"🔍 MRNA: IndicatorResult error: {indicator_result.error}")
                    print(f"🔍 MRNA: IndicatorResult error: {indicator_result.error}")  # Print as fallback
                    if hasattr(indicator_result.values, "lines"):
                        result_dict = indicator_result.values.lines
                        failed_tfs = result_dict.get('failed_timeframes_at_last_bar', 'N/A')
                        log_msg = (
                            f"🔍 MRNA: has_signal={result_dict.get('has_all_green_signal', 0.0)}, "
                            f"total_green_bars={result_dict.get('total_all_green_bars', 0.0)}, "
                            f"max_green={result_dict.get('max_green_count_at_last_bar', 0.0)}/{result_dict.get('valid_timeframes_at_last_bar', 0.0)} "
                            f"(required: ALL {result_dict.get('valid_timeframes_at_last_bar', 0.0)} must be green), "
                            f"failed_timeframes: {failed_tfs}"
                        )
                        logger.warning(log_msg)
                        print(log_msg)  # Print as fallback

                if self._should_pass_filter(indicator_result):
                    filtered_bundle[symbol] = ohlcv_data
                    passed_count += 1
                    if is_qxo:
                        qxo_status = "passed"
                        logger.warning(f"🔍 QXO: PASSED the filter!")
                        print(f"🔍 QXO: PASSED the filter!")  # Print as fallback
                    if is_mrna:
                        mrna_status = "passed"
                        logger.warning(f"🔍 MRNA: PASSED the filter!")
                        print(f"🔍 MRNA: PASSED the filter!")  # Print as fallback
                else:
                    failed_count += 1
                    if is_qxo:
                        qxo_status = "failed"
                        logger.warning(f"🔍 QXO: FAILED the filter")
                        print(f"🔍 QXO: FAILED the filter")  # Print as fallback
                    if is_mrna:
                        mrna_status = "failed"
                        logger.warning(f"🔍 MRNA: FAILED the filter")
                        print(f"🔍 MRNA: FAILED the filter")  # Print as fallback

            except Exception as e:
                logger.error(f"❌ FractalResonanceFilter: Failed to process {symbol}: {e}")
                if is_qxo:
                    qxo_status = "error"
                    logger.warning(f"🔍 QXO: ERROR during processing: {e}")
                    print(f"🔍 QXO: ERROR during processing: {e}")
                if is_mrna:
                    mrna_status = "error"
                    logger.warning(f"🔍 MRNA: ERROR during processing: {e}")
                    print(f"🔍 MRNA: ERROR during processing: {e}")
                failed_count += 1
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

        logger.info(
            f"🔵 FractalResonanceFilter: COMPLETE - {passed_count} passed, {failed_count} failed "
            f"(out of {total_symbols} total symbols, STRICT MODE: ALL valid timeframes must be green)"
        )
        
        # Prominent QXO status summary
        if qxo_status == "passed":
            logger.warning("=" * 80)
            logger.warning("⚠️  QXO STATUS: PASSED THE FILTER (but may not have all 16 rows green!)")
            logger.warning("=" * 80)
            print("=" * 80)
            print("⚠️  QXO STATUS: PASSED THE FILTER (but may not have all 16 rows green!)")
            print("=" * 80)
        elif qxo_status == "failed":
            logger.warning("=" * 80)
            logger.warning("✅ QXO STATUS: FAILED THE FILTER (correctly filtered out)")
            logger.warning("=" * 80)
            print("=" * 80)
            print("✅ QXO STATUS: FAILED THE FILTER (correctly filtered out)")
            print("=" * 80)
        elif qxo_status == "not_found":
            logger.warning("=" * 80)
            logger.warning("❓ QXO STATUS: NOT FOUND IN INPUT BUNDLE")
            logger.warning("=" * 80)
            print("=" * 80)
            print("❓ QXO STATUS: NOT FOUND IN INPUT BUNDLE")
            print("=" * 80)
        elif qxo_status == "error":
            logger.warning("=" * 80)
            logger.warning("❌ QXO STATUS: ERROR DURING PROCESSING")
            logger.warning("=" * 80)
            print("=" * 80)
            print("❌ QXO STATUS: ERROR DURING PROCESSING")
            print("=" * 80)
        
        # Prominent MRNA status summary
        if mrna_status == "passed":
            logger.warning("=" * 80)
            logger.warning("✅ MRNA STATUS: PASSED THE FILTER")
            logger.warning("=" * 80)
            print("=" * 80)
            print("✅ MRNA STATUS: PASSED THE FILTER")
            print("=" * 80)
        elif mrna_status == "failed":
            logger.warning("=" * 80)
            logger.warning("❌ MRNA STATUS: FAILED THE FILTER (investigate why - should have all 16 rows green)")
            logger.warning("=" * 80)
            print("=" * 80)
            print("❌ MRNA STATUS: FAILED THE FILTER (investigate why - should have all 16 rows green)")
            print("=" * 80)
        elif mrna_status == "not_found":
            logger.warning("=" * 80)
            logger.warning("❓ MRNA STATUS: NOT FOUND IN INPUT BUNDLE")
            logger.warning("=" * 80)
            print("=" * 80)
            print("❓ MRNA STATUS: NOT FOUND IN INPUT BUNDLE")
            print("=" * 80)
        elif mrna_status == "error":
            logger.warning("=" * 80)
            logger.warning("🔥 MRNA STATUS: ERROR DURING PROCESSING")
            logger.warning("=" * 80)
            print("=" * 80)
            print("🔥 MRNA STATUS: ERROR DURING PROCESSING")
            print("=" * 80)

        return {
            "filtered_ohlcv_bundle": filtered_bundle,
        }

