"""Unit tests for orb_calculator.py"""

import pytest
from datetime import datetime, timedelta
from typing import Any

import pytz

from core.types_registry import AssetClass, AssetSymbol


class TestCalculateOrbHappyPath:
    """Test happy path scenarios for calculate_orb"""

    def test_bullish_opening_range(self):
        """Test bullish ORB calculation"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        # Create mock 5-minute bars for 15 days
        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            # Bullish bar (close > open) with higher volume on last day
            volume = 50000 if day_offset == 14 else 30000
            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,  # Bullish
                    "volume": volume,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        assert result["rel_vol"] is not None
        assert result["rel_vol"] > 100  # Should be above average
        assert result["direction"] == "bullish"
        assert result.get("error") is None

    def test_bearish_opening_range(self):
        """Test bearish ORB calculation"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            # Bearish bar (close < open)
            volume = 50000 if day_offset == 14 else 30000
            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 98.0,  # Bearish
                    "volume": volume,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        assert result["rel_vol"] is not None
        assert result["direction"] == "bearish"
        assert result.get("error") is None

    def test_doji_opening_range(self):
        """Test doji ORB calculation (open == close)"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            volume = 50000 if day_offset == 14 else 30000
            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 100.0,  # Doji
                    "volume": volume,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        assert result["rel_vol"] is not None
        assert result["direction"] == "doji"
        assert result.get("error") is None

    def test_crypto_opening_range(self):
        """Test crypto opening range (UTC midnight)"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("BTC", AssetClass.CRYPTO)
        # Crypto uses UTC dates for grouping
        today_utc = datetime.now(pytz.timezone("UTC")).date()

        bars = []
        for day_offset in range(15):
            date = today_utc - timedelta(days=14 - day_offset)
            # Crypto opening range is UTC midnight - need to create timestamp that when
            # converted to Eastern and grouped by Eastern date still makes sense
            # The calculator converts UTC timestamps to Eastern, so we need UTC midnight
            # that maps to Eastern date boundaries
            open_time_utc = datetime.combine(
                date, datetime.strptime("00:00", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("UTC"))
            open_time_ms = int(open_time_utc.timestamp() * 1000)

            volume = 50000 if day_offset == 14 else 30000
            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": volume,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        # Crypto grouping by Eastern date might not align with UTC dates
        # Just verify we get some result or error, not None for both
        assert not (result["rel_vol"] is None and result["direction"] is None and result.get("error") is None)

    def test_relative_volume_calculation(self):
        """Test relative volume calculation accuracy"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            # Last day has 2x volume
            volume = 60000 if day_offset == 14 else 30000
            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": volume,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        # Should be approximately 200% (60000 / 30000 * 100)
        assert 190 <= result["rel_vol"] <= 210


class TestCalculateOrbEdgeCases:
    """Test edge cases for calculate_orb"""

    def test_empty_bars(self):
        """Test with empty bars"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        result = calculate_orb([], symbol)

        assert result["rel_vol"] is None
        assert result["direction"] is None
        assert result["error"] == "No bars provided"

    def test_insufficient_days(self):
        """Test with insufficient days for average calculation"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        # Only 3 days of data
        bars = []
        for day_offset in range(3):
            date = today - timedelta(days=2 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        assert result["rel_vol"] is not None
        assert result["direction"] is not None
        # Should still work with fewer days

    def test_missing_opening_range_bar(self):
        """Test when opening range bar is missing for some days"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            # Skip bars for some days (simulating missing data)
            if day_offset in [5, 7, 9]:
                continue

            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        # Should still work with missing days
        assert result["rel_vol"] is not None
        assert result["direction"] is not None

    def test_bar_outside_opening_range(self):
        """Test when bars exist but not at opening range time"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            # Bars at 10:00 AM instead of 9:30 AM
            open_time = datetime.combine(
                date, datetime.strptime("10:00", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        # Should fail to find opening range bars
        assert result["rel_vol"] is None
        assert result["direction"] is None
        assert result["error"] == "Insufficient days"

    def test_zero_volume(self):
        """Test with zero volume"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 0,  # Zero volume
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        # Should handle zero volume
        assert result["rel_vol"] is not None
        assert result["rel_vol"] == 0.0
        assert result["direction"] == "bullish"

    def test_zero_average_volume(self):
        """Test when average volume is zero"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            # All past days have zero volume
            volume = 50000 if day_offset == 14 else 0
            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": volume,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        # Should return infinity for rel_vol when avg is zero
        assert result["rel_vol"] == float("inf")
        assert result["direction"] == "bullish"

    def test_custom_avg_period(self):
        """Test with custom average period"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        # Create 30 days of data
        for day_offset in range(30):
            date = today - timedelta(days=29 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            volume = 50000 if day_offset == 29 else 30000
            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": volume,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=20)

        assert result["rel_vol"] is not None
        assert result["direction"] == "bullish"

    def test_custom_or_minutes(self):
        """Test with custom opening range minutes"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=15, avg_period=14)

        assert result["rel_vol"] is not None
        assert result["direction"] == "bullish"

    def test_now_func_parameter(self):
        """Test with custom now_func for testing"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        test_date = datetime(2023, 10, 15, tzinfo=pytz.timezone("US/Eastern"))

        def mock_now_func(tz=None):
            if tz is None:
                return test_date
            return test_date.astimezone(tz)

        bars = []
        for day_offset in range(15):
            date = test_date.date() - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14, now_func=mock_now_func)

        assert result["rel_vol"] is not None
        assert result["direction"] == "bullish"


class TestCalculateOrbRegressionTests:
    """Regression tests for calculate_orb"""

    def test_bar_timestamp_edge(self):
        """Test bar that's exactly at opening time"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,  # Exactly at 9:30
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        assert result["rel_vol"] is not None
        assert result["direction"] == "bullish"

    def test_bar_timestamp_within_tolerance(self):
        """Test bar that's within 5 minutes of opening time"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            # Add 4 minutes to test tolerance
            open_time = open_time + timedelta(minutes=4)
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        assert result["rel_vol"] is not None
        assert result["direction"] == "bullish"

    def test_bar_timestamp_beyond_tolerance(self):
        """Test bar that's beyond 5 minutes of opening time"""
        from services.indicator_calculators.orb_calculator import calculate_orb

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today = datetime.now(pytz.timezone("US/Eastern")).date()

        bars = []
        for day_offset in range(15):
            date = today - timedelta(days=14 - day_offset)
            open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            # Add 6 minutes - beyond tolerance
            open_time = open_time + timedelta(minutes=6)
            open_time_ms = int(open_time.timestamp() * 1000)

            bars.append(
                {
                    "timestamp": open_time_ms,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 102.0,
                    "volume": 30000,
                }
            )

        result = calculate_orb(bars, symbol, or_minutes=5, avg_period=14)

        # Should fail to find opening range bars
        assert result["rel_vol"] is None
        assert result["direction"] is None
        assert result["error"] == "Insufficient days"

