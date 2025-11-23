"""
Hurst Spectral Analysis Oscillator Calculator

Implements bandpass filters and cycle analysis based on J.M. Hurst's spectral analysis.
Adapted from PineScript indicator by BarefootJoey.

Reference: J.M. Hurst's "Profit Magic" - Spectral Analysis chapter
"""

import math
from collections.abc import Sequence
from typing import Any


def calculate_bandpass_filter(
    series: Sequence[float | None],
    period: float,
    bandwidth: float = 0.025,
) -> list[float | None]:
    """
    Calculate bandpass filter using the HPotter/Ehlers formula.

    This is a recursive filter that isolates specific frequency components.

    Args:
        series: Input price series (e.g., HL2, close, etc.)
        period: Period in bars (can be float/decimal)
        bandwidth: Bandwidth parameter (default 0.025)

    Returns:
        List of filtered values (same length as input)
    """
    if period < 2.0 or bandwidth <= 0.0:
        return [None] * len(series)

    # Convert to list for easier indexing
    series_list = list(series)
    result: list[float | None] = [None] * len(series_list)

    # Pre-calculate constants
    # IMPORTANT: Pinescript uses 3.14 as approximation of pi, not math.pi!
    # To match TradingView exactly, we must use the same approximation
    pi_approx = 3.14  # Pinescript approximation (not math.pi!)
    beta = math.cos(pi_approx * (360.0 / period) / 180.0)
    gamma = 1.0 / math.cos(pi_approx * (720.0 * bandwidth / period) / 180.0)
    alpha = gamma - math.sqrt(gamma * gamma - 1.0)

    # Initialize state variables for filtered values (not raw prices)
    # These store the previous filtered bandpass values (tmpbpf[1] and tmpbpf[2] in Pinescript)
    # In Pinescript: nz(tmpbpf[1]) returns 0 if tmpbpf[1] is na, so we start at 0.0
    prev_bpf1: float = 0.0  # tmpbpf[1] - previous filtered value
    prev_bpf2: float = 0.0  # tmpbpf[2] - two bars ago filtered value

    for i in range(len(series_list)):
        current = series_list[i]

        if current is None:
            result[i] = None
            # Don't update prev values when current is None (keep previous filtered values)
            continue

        # Need at least 2 previous bars for the filter
        if i < 2:
            result[i] = None
            # Keep prev values at 0.0 for initial bars (matches Pinescript nz() behavior)
            continue

        # Get current and 2-bars-ago raw price values
        current_val: float = current
        two_bars_ago_raw = series_list[i - 2]
        two_bars_ago_val: float = two_bars_ago_raw if two_bars_ago_raw is not None else current_val

        # Bandpass filter formula (matching Pinescript exactly)
        # tmpbpf := 0.5 * (1 - alpha) * (Series - Series[2]) + beta * (1 + alpha) * nz(tmpbpf[1]) - alpha * nz(tmpbpf[2])
        bpf: float = (
            0.5 * (1.0 - alpha) * (current_val - two_bars_ago_val)
            + beta * (1.0 + alpha) * prev_bpf1
            - alpha * prev_bpf2
        )

        result[i] = bpf

        # Update state for next iteration (shift filtered values)
        prev_bpf2 = prev_bpf1
        prev_bpf1 = bpf

    return result


def detect_peaks_troughs(
    series: Sequence[float | None],
) -> tuple[list[int], list[int]]:
    """
    Detect peaks and troughs in a series.

    Peak: value is higher than both previous and next values
    Trough: value is lower than both previous and next values

    Args:
        series: Input series

    Returns:
        Tuple of (peak_indices, trough_indices)
    """
    peaks: list[int] = []
    troughs: list[int] = []

    for i in range(1, len(series) - 1):
        if series[i] is None or series[i - 1] is None or series[i + 1] is None:
            continue

        val = series[i]
        prev_val = series[i - 1]
        next_val = series[i + 1]

        if val is not None and prev_val is not None and next_val is not None:
            if val > prev_val and val > next_val:
                peaks.append(i)
            elif val < prev_val and val < next_val:
                troughs.append(i)

    return peaks, troughs


def calculate_hurst_oscillator(
    closes: Sequence[float | None],
    highs: Sequence[float | None] | None = None,
    lows: Sequence[float | None] | None = None,
    source: str = "hl2",
    bandwidth: float = 0.025,
    periods: dict[str, float] | None = None,
    composite_selection: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """
    Calculate Hurst Spectral Analysis Oscillator with multiple bandpass filters.

    Args:
        closes: Close prices
        highs: High prices (optional, for HL2 calculation)
        lows: Low prices (optional, for HL2 calculation)
        source: Source type - "close", "hl2", "open", "high", "low"
        bandwidth: Bandwidth parameter for filters (default 0.025)
        periods: Dict of period names to period values (bars)
        composite_selection: Dict of period names to bool (which to include in composite)

    Returns:
        Dictionary with:
        - 'bandpasses': Dict of period_name -> list of filtered values
        - 'composite': List of composite values
        - 'peaks': List of peak indices
        - 'troughs': List of trough indices
        - 'wavelength': Estimated wavelength
        - 'amplitude': Total amplitude (peak - trough)
    """
    if not closes or len(closes) == 0:
        return {
            "bandpasses": {},
            "composite": [],
            "peaks": [],
            "troughs": [],
            "wavelength": None,
            "amplitude": None,
        }

    # Default periods matching TradingView Hurst Spectral Analysis Oscillator
    # All 11 cycles from 5 Day to 18 Year
    default_periods = {
        "5_day": 4.3,
        "10_day": 8.5,
        "20_day": 17.0,
        "40_day": 34.1,
        "80_day": 68.2,
        "20_week": 136.4,
        "40_week": 272.8,
        "18_month": 545.6,
        "54_month": 1636.8,
        "9_year": 3273.6,
        "18_year": 6547.2,
    }

    if periods is None:
        periods = default_periods

    # Default composite selection (all enabled)
    if composite_selection is None:
        composite_selection = {name: True for name in periods.keys()}

    # Calculate source series
    source_series: list[float | None] = []

    if source == "close":
        source_series = list(closes)
    elif source == "hl2":
        if highs is None or lows is None:
            # Fallback to close if HL2 not available
            source_series = list(closes)
        else:
            source_series = [
                (h + low) / 2.0 if h is not None and low is not None else None
                for h, low in zip(highs, lows)
            ]
    elif source == "open" and len(closes) > 0:
        # Would need opens, but for now use close
        source_series = list(closes)
    else:
        source_series = list(closes)

    # Calculate all bandpass filters
    bandpasses: dict[str, list[float | None]] = {}

    for period_name, period_value in periods.items():
        bpf_values = calculate_bandpass_filter(source_series, period_value, bandwidth)
        bandpasses[period_name] = bpf_values

    # Calculate composite (sum of selected bandpasses)
    composite: list[float | None] = []

    if bandpasses:
        for i in range(len(source_series)):
            comp_value: float = 0.0
            has_value = False

            for period_name, bpf_values in bandpasses.items():
                if composite_selection.get(period_name, False):
                    if i < len(bpf_values):
                        bpf_val = bpf_values[i]
                        if bpf_val is not None:
                            comp_value += bpf_val
                            has_value = True

            composite.append(comp_value if has_value else None)
    else:
        composite = [None] * len(source_series)

    # Detect peaks and troughs in composite
    peaks, troughs = detect_peaks_troughs(composite)

    # Calculate wavelength (average distance between peaks and troughs)
    wavelength: float | None = None
    if len(peaks) > 1:
        peak_distances = [peaks[i] - peaks[i - 1] for i in range(1, len(peaks))]
        if peak_distances:
            wavelength = sum(peak_distances) / len(peak_distances)
    elif len(troughs) > 1:
        trough_distances = [troughs[i] - troughs[i - 1] for i in range(1, len(troughs))]
        if trough_distances:
            wavelength = sum(trough_distances) / len(trough_distances)

    # Calculate amplitude (peak - trough) from composite
    amplitude: float | None = None
    if composite:
        valid_values = [v for v in composite if v is not None]
        if valid_values:
            max_val = max(valid_values)
            min_val = min(valid_values)
            amplitude = max_val - min_val

    return {
        "bandpasses": bandpasses,
        "composite": composite,
        "peaks": peaks,
        "troughs": troughs,
        "wavelength": wavelength,
        "amplitude": amplitude,
    }
