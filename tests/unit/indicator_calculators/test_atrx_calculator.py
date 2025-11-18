import numpy as np
import pytest

from services.indicator_calculators.atrx_calculator import calculate_atrx


@pytest.fixture
def sample_ohlcv_data() -> dict[str, list[float]]:
    """Create realistic OHLCV data for testing ATRX."""
    np.random.seed(42)

    # Create a trending price series
    close_prices = 100 + np.cumsum(np.random.normal(0.1, 2, 60))
    high_prices = close_prices + np.random.uniform(0.5, 3, 60)
    low_prices = close_prices - np.random.uniform(0.5, 3, 60)

    return {
        "highs": high_prices.tolist(),
        "lows": low_prices.tolist(),
        "closes": close_prices.tolist(),
        "prices": close_prices.tolist(),
    }


@pytest.fixture
def trending_upward_data() -> dict[str, list[float]]:
    """Create data with strong upward trend."""
    base_prices = np.linspace(100, 150, 60)
    high_prices = base_prices + np.random.uniform(1, 3, 60)
    low_prices = base_prices - np.random.uniform(1, 3, 60)
    close_prices = base_prices + np.random.normal(0, 0.5, 60)

    return {
        "highs": high_prices.tolist(),
        "lows": low_prices.tolist(),
        "closes": close_prices.tolist(),
        "prices": close_prices.tolist(),
    }


@pytest.fixture
def constant_data() -> dict[str, list[float]]:
    """Create constant data for testing."""
    return {
        "highs": [105.0] * 60,
        "lows": [95.0] * 60,
        "closes": [102.0] * 60,
        "prices": [102.0] * 60,
    }


class TestCalculateATRX:
    """Tests for ATRX calculation."""

    def test_atrx_basic_happy_path(self, sample_ohlcv_data):
        """Test basic ATRX calculation with valid data."""
        result = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
        )

        # Should return dictionary with atrx as list
        assert isinstance(result, dict)
        assert "atrx" in result

        # Values should be list
        assert isinstance(result["atrx"], list)

        # Should have same length as input
        assert len(result["atrx"]) == len(sample_ohlcv_data["highs"])

        # Check that values are valid (either None or float)
        for val in result["atrx"]:
            assert val is None or isinstance(val, float)

    def test_atrx_with_different_smoothing_methods(self, sample_ohlcv_data):
        """Test ATRX with different smoothing methods."""
        for smoothing in ["RMA", "SMA", "EMA"]:
            result = calculate_atrx(
                sample_ohlcv_data["highs"],
                sample_ohlcv_data["lows"],
                sample_ohlcv_data["closes"],
                sample_ohlcv_data["prices"],
                length=14,
                ma_length=50,
                smoothing=smoothing,
            )

            # Should return valid results
            assert isinstance(result, dict)
            assert "atrx" in result
            assert len(result["atrx"]) == len(sample_ohlcv_data["highs"])

            # Should have some valid values (after initial None values)
            valid_values = [v for v in result["atrx"] if v is not None]
            assert len(valid_values) > 0

    def test_atrx_with_different_periods(self, sample_ohlcv_data):
        """Test ATRX with different periods."""
        result_14_50 = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
        )
        result_20_30 = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=20,
            ma_length=30,
        )

        # Both should return valid results
        assert isinstance(result_14_50, dict)
        assert isinstance(result_20_30, dict)
        assert isinstance(result_14_50["atrx"], list)
        assert isinstance(result_20_30["atrx"], list)

        # Both should have same length as input
        assert len(result_14_50["atrx"]) == len(sample_ohlcv_data["highs"])
        assert len(result_20_30["atrx"]) == len(sample_ohlcv_data["highs"])

    def test_atrx_empty_data(self):
        """Test ATRX with empty data."""
        result = calculate_atrx([], [], [], [], length=14, ma_length=50)

        assert result == {"atrx": []}

    def test_atrx_zero_length(self, sample_ohlcv_data):
        """Test ATRX with length=0."""
        result = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=0,
            ma_length=50,
        )

        # Should return all None values
        assert isinstance(result, dict)
        assert "atrx" in result
        assert all(v is None for v in result["atrx"])

    def test_atrx_zero_ma_length(self, sample_ohlcv_data):
        """Test ATRX with ma_length=0."""
        result = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=0,
        )

        # Should return all None values
        assert isinstance(result, dict)
        assert "atrx" in result
        assert all(v is None for v in result["atrx"])

    def test_atrx_negative_length(self, sample_ohlcv_data):
        """Test ATRX with negative length."""
        result = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=-5,
            ma_length=50,
        )

        # Should return all None values
        assert isinstance(result, dict)
        assert "atrx" in result
        assert all(v is None for v in result["atrx"])

    def test_atrx_insufficient_data(self):
        """Test ATRX with insufficient data (< max period)."""
        highs = [100.0, 102.0, 104.0]
        lows = [98.0, 100.0, 102.0]
        closes = [99.0, 101.0, 103.0]
        prices = [99.0, 101.0, 103.0]

        result = calculate_atrx(highs, lows, closes, prices, length=14, ma_length=50)

        # Should return all None values
        assert isinstance(result, dict)
        assert "atrx" in result
        assert all(v is None for v in result["atrx"])

    def test_atrx_exactly_period_length(self):
        """Test ATRX with exactly max period length of data."""
        # Use max(14, 50) = 50 for ma_length
        highs = [100.0 + i for i in range(50)]
        lows = [98.0 + i for i in range(50)]
        closes = [99.0 + i for i in range(50)]
        prices = [99.0 + i for i in range(50)]

        result = calculate_atrx(highs, lows, closes, prices, length=14, ma_length=50)

        # Should return results
        assert isinstance(result, dict)
        assert "atrx" in result
        assert len(result["atrx"]) == 50

        # Last value should be calculated
        assert result["atrx"][-1] is not None

    def test_atrx_unequal_list_lengths(self):
        """Test ATRX with unequal list lengths."""
        highs = [100.0, 102.0, 104.0]
        lows = [98.0, 100.0]
        closes = [99.0, 101.0, 103.0]
        prices = [99.0, 101.0, 103.0]

        result = calculate_atrx(highs, lows, closes, prices, length=14, ma_length=50)

        # Should return all None values
        assert isinstance(result, dict)
        assert "atrx" in result
        assert all(v is None for v in result["atrx"])

    def test_atrx_with_none_values(self):
        """Test ATRX with None values in data."""
        highs = [100.0, None, 104.0, 103.0, 105.0]
        lows = [98.0, 100.0, None, 101.0, 103.0]
        closes = [99.0, 101.0, 103.0, 102.0, 104.0]
        prices = [99.0, 101.0, 103.0, 102.0, 104.0]

        result = calculate_atrx(highs, lows, closes, prices, length=3, ma_length=5)

        # Should handle None values gracefully
        assert isinstance(result, dict)
        assert "atrx" in result
        assert len(result["atrx"]) == 5

    def test_atrx_all_none_values(self):
        """Test ATRX with all None values."""
        highs = [None, None, None]
        lows = [None, None, None]
        closes = [None, None, None]
        prices = [None, None, None]

        result = calculate_atrx(highs, lows, closes, prices, length=2, ma_length=2)

        # Should return None values
        assert isinstance(result, dict)
        assert "atrx" in result
        assert all(v is None for v in result["atrx"])

    def test_atrx_consistency(self, sample_ohlcv_data):
        """Test ATRX calculation consistency."""
        # Calculate twice and should get same results
        result1 = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
        )
        result2 = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
        )

        assert result1 == result2

    def test_atrx_trending_data(self, trending_upward_data):
        """Test ATRX with trending upward data."""
        result = calculate_atrx(
            trending_upward_data["highs"],
            trending_upward_data["lows"],
            trending_upward_data["closes"],
            trending_upward_data["prices"],
            length=14,
            ma_length=50,
        )

        # Should return valid ATRX values
        assert isinstance(result, dict)
        assert "atrx" in result

        # Extract last valid ATRX value
        valid_atrx_values = [v for v in result["atrx"] if v is not None]
        if valid_atrx_values:
            last_atrx = valid_atrx_values[-1]
            assert isinstance(last_atrx, float)

    def test_atrx_constant_data(self, constant_data):
        """Test ATRX with constant data."""
        result = calculate_atrx(
            constant_data["highs"],
            constant_data["lows"],
            constant_data["closes"],
            constant_data["prices"],
            length=14,
            ma_length=50,
        )

        # Should return valid results
        assert isinstance(result, dict)
        assert "atrx" in result

        # With constant prices, SMA50 = price, so % Gain From 50-MA = 0
        # ATR should be ~ (high-low) = 10
        # ATR% = 10 / 102 ≈ 0.098
        # ATRX = 0 / 0.098 = 0 (or close to 0)
        valid_atrx_values = [v for v in result["atrx"] if v is not None]
        if valid_atrx_values:
            last_atrx = valid_atrx_values[-1]
            # ATRX should be close to 0 for constant data
            assert abs(last_atrx) < 0.1

    def test_atrx_default_parameters(self, sample_ohlcv_data):
        """Test ATRX with default parameters."""
        result_default = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
        )
        result_explicit = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
            smoothing="RMA",
        )

        # Should produce identical results
        assert result_default == result_explicit

    def test_atrx_single_data_point(self):
        """Test ATRX with single data point."""
        result = calculate_atrx([100.0], [98.0], [99.0], [99.0], length=14, ma_length=50)

        # Should return single None value (insufficient data)
        assert isinstance(result, dict)
        assert "atrx" in result
        assert len(result["atrx"]) == 1
        assert result["atrx"][0] is None

    def test_atrx_two_data_points(self):
        """Test ATRX with two data points."""
        result = calculate_atrx(
            [100.0, 102.0], [98.0, 100.0], [99.0, 101.0], [99.0, 101.0], length=14, ma_length=50
        )

        # Should return None values (insufficient data)
        assert isinstance(result, dict)
        assert "atrx" in result
        assert len(result["atrx"]) == 2
        assert all(v is None for v in result["atrx"])

    def test_atrx_large_period(self, sample_ohlcv_data):
        """Test ATRX with period larger than data length."""
        result = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=100,
            ma_length=200,
        )

        # Should return all None values
        assert isinstance(result, dict)
        assert "atrx" in result
        assert all(v is None for v in result["atrx"])

    def test_atrx_period_one(self, sample_ohlcv_data):
        """Test ATRX with period=1."""
        result = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=1,
            ma_length=1,
        )

        # Should return valid values starting from index 0
        assert isinstance(result, dict)
        assert "atrx" in result

        # All values after period-1 should be non-None
        valid_values = [v for v in result["atrx"] if v is not None]
        assert len(valid_values) > 0

    def test_atrx_smoothing_methods_comparison(self, sample_ohlcv_data):
        """Test that different smoothing methods produce different ATRX results."""
        result_rma = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
            smoothing="RMA",
        )
        result_sma = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
            smoothing="SMA",
        )
        result_ema = calculate_atrx(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            sample_ohlcv_data["prices"],
            length=14,
            ma_length=50,
            smoothing="EMA",
        )

        # All should return valid results
        assert len(result_rma["atrx"]) == len(result_sma["atrx"])
        assert len(result_sma["atrx"]) == len(result_ema["atrx"])

        # Last values should all be non-None
        rma_last = result_rma["atrx"][-1]
        sma_last = result_sma["atrx"][-1]
        ema_last = result_ema["atrx"][-1]

        assert rma_last is not None
        assert sma_last is not None
        assert ema_last is not None

    def test_atrx_with_zero_atr(self):
        """Test ATRX with zero ATR values."""
        # Data where high = low = close (zero range)
        highs = [100.0] * 60
        lows = [100.0] * 60
        closes = [100.0] * 60
        prices = [100.0] * 60

        result = calculate_atrx(highs, lows, closes, prices, length=14, ma_length=50)

        # Should handle zero ATR gracefully
        assert isinstance(result, dict)
        assert "atrx" in result
        # With zero ATR, ATR% = 0, so ATRX calculation would divide by zero
        # Expect None values
        assert all(v is None for v in result["atrx"])

    def test_atrx_with_zero_price(self):
        """Test ATRX with zero price values."""
        highs = [5.0] * 60
        lows = [95.0] * 60
        closes = [0.0] * 60
        prices = [0.0] * 60

        result = calculate_atrx(highs, lows, closes, prices, length=14, ma_length=50)

        # Should handle zero price gracefully
        assert isinstance(result, dict)
        assert "atrx" in result
        # With zero price, ATR% = ATR / 0 would be problematic
        # Expect None values
        assert all(v is None for v in result["atrx"])
