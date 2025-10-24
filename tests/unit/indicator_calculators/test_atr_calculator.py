import numpy as np
import pytest

from services.indicator_calculators.atr_calculator import calculate_atr, calculate_tr


@pytest.fixture
def sample_ohlcv_data() -> dict[str, list[float]]:
    """Create realistic OHLCV data for testing ATR."""
    np.random.seed(42)

    # Create a trending price series
    close_prices = 100 + np.cumsum(np.random.normal(0.1, 2, 50))
    high_prices = close_prices + np.random.uniform(0.5, 3, 50)
    low_prices = close_prices - np.random.uniform(0.5, 3, 50)

    return {
        "highs": high_prices.tolist(),
        "lows": low_prices.tolist(),
        "closes": close_prices.tolist(),
    }


@pytest.fixture
def trending_upward_data() -> dict[str, list[float]]:
    """Create data with strong upward trend."""
    base_prices = np.linspace(100, 150, 50)
    high_prices = base_prices + np.random.uniform(1, 3, 50)
    low_prices = base_prices - np.random.uniform(1, 3, 50)
    close_prices = base_prices + np.random.normal(0, 0.5, 50)

    return {
        "highs": high_prices.tolist(),
        "lows": low_prices.tolist(),
        "closes": close_prices.tolist(),
    }


@pytest.fixture
def sideways_data() -> dict[str, list[float]]:
    """Create data with sideways movement."""
    base_price = 100
    high_prices = base_price + np.random.uniform(0.5, 2, 50)
    low_prices = base_price - np.random.uniform(0.5, 2, 50)
    close_prices = base_price + np.random.normal(0, 1, 50)

    return {
        "highs": high_prices.tolist(),
        "lows": low_prices.tolist(),
        "closes": close_prices.tolist(),
    }


@pytest.fixture
def simple_test_data() -> dict[str, list[float]]:
    """Create simple test data for manual calculation verification."""
    return {
        "highs": [100.0, 102.0, 104.0, 103.0, 105.0],
        "lows": [98.0, 100.0, 102.0, 101.0, 103.0],
        "closes": [99.0, 101.0, 103.0, 102.0, 104.0],
    }


class TestCalculateTR:
    """Tests for True Range calculation."""

    def test_tr_first_point(self):
        """Test TR calculation for first point (no previous close)."""
        # First point: TR should be high - low
        tr = calculate_tr(high=100.0, low=98.0, prev_close=None)
        assert tr == 2.0

    def test_tr_normal_case(self):
        """Test TR calculation for normal case."""
        # TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
        # high=102, low=98, prev_close=100
        # max(4, 2, 2) = 4
        tr = calculate_tr(high=102.0, low=98.0, prev_close=100.0)
        assert tr == 4.0

    def test_tr_with_gap_up(self):
        """Test TR with gap up (high - prev_close is largest)."""
        # Gap up case: high=110, low=105, prev_close=100
        # max(5, 10, 5) = 10
        tr = calculate_tr(high=110.0, low=105.0, prev_close=100.0)
        assert tr == 10.0

    def test_tr_with_gap_down(self):
        """Test TR with gap down (low - prev_close is largest)."""
        # Gap down case: high=95, low=90, prev_close=100
        # max(5, 5, 10) = 10
        tr = calculate_tr(high=95.0, low=90.0, prev_close=100.0)
        assert tr == 10.0

    def test_tr_with_none_values(self):
        """Test TR with None values."""
        # If high is None
        tr = calculate_tr(high=None, low=98.0, prev_close=100.0)
        assert tr is None

        # If low is None
        tr = calculate_tr(high=100.0, low=None, prev_close=100.0)
        assert tr is None

        # If both are None
        tr = calculate_tr(high=None, low=None, prev_close=100.0)
        assert tr is None

    def test_tr_with_none_prev_close(self):
        """Test TR with None previous close."""
        # Should return high - low
        tr = calculate_tr(high=100.0, low=98.0, prev_close=None)
        assert tr == 2.0


class TestCalculateATR:
    """Tests for ATR calculation."""

    def test_atr_basic_happy_path(self, sample_ohlcv_data):
        """Test basic ATR calculation with valid data."""
        result = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=14,
        )

        # Should return dictionary with atr as list
        assert isinstance(result, dict)
        assert "atr" in result

        # Values should be list
        assert isinstance(result["atr"], list)

        # Should have same length as input
        assert len(result["atr"]) == len(sample_ohlcv_data["highs"])

        # Check that values are valid (either None or positive float)
        for val in result["atr"]:
            assert val is None or (isinstance(val, float) and val >= 0)

    def test_atr_with_different_periods(self, sample_ohlcv_data):
        """Test ATR with different periods."""
        result_14 = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=14,
        )
        result_20 = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=20,
        )

        # Both should return valid results as lists
        assert isinstance(result_14, dict)
        assert isinstance(result_20, dict)
        assert isinstance(result_14["atr"], list)
        assert isinstance(result_20["atr"], list)

        # Both should have same length as input
        assert len(result_14["atr"]) == len(sample_ohlcv_data["highs"])
        assert len(result_20["atr"]) == len(sample_ohlcv_data["highs"])

    def test_atr_simple_manual_calculation(self, simple_test_data):
        """Test ATR with simple data for manual verification."""
        result = calculate_atr(
            simple_test_data["highs"],
            simple_test_data["lows"],
            simple_test_data["closes"],
            length=3,
        )

        # Check structure
        assert isinstance(result, dict)
        assert "atr" in result
        assert len(result["atr"]) == 5

        # First 2 values should be None (insufficient data for period=3)
        assert result["atr"][0] is None
        assert result["atr"][1] is None

        # From index 2 onwards, should have valid values
        assert result["atr"][2] is not None
        assert result["atr"][3] is not None
        assert result["atr"][4] is not None

        # ATR values should be positive
        assert result["atr"][2] > 0
        assert result["atr"][3] > 0
        assert result["atr"][4] > 0

    def test_atr_empty_data(self):
        """Test ATR with empty data."""
        result = calculate_atr([], [], [], length=14)

        assert result == {"atr": []}

    def test_atr_zero_length(self, sample_ohlcv_data):
        """Test ATR with length=0."""
        result = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=0,
        )

        # Should return all None values
        assert isinstance(result, dict)
        assert "atr" in result
        assert all(v is None for v in result["atr"])

    def test_atr_negative_length(self, sample_ohlcv_data):
        """Test ATR with negative length."""
        result = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=-5,
        )

        # Should return all None values
        assert isinstance(result, dict)
        assert "atr" in result
        assert all(v is None for v in result["atr"])

    def test_atr_insufficient_data(self):
        """Test ATR with insufficient data (< period)."""
        highs = [100.0, 102.0, 104.0]
        lows = [98.0, 100.0, 102.0]
        closes = [99.0, 101.0, 103.0]

        result = calculate_atr(highs, lows, closes, length=14)

        # Should return all None values
        assert isinstance(result, dict)
        assert "atr" in result
        assert all(v is None for v in result["atr"])

    def test_atr_exactly_period_length(self):
        """Test ATR with exactly period length of data."""
        highs = [100.0 + i for i in range(14)]
        lows = [98.0 + i for i in range(14)]
        closes = [99.0 + i for i in range(14)]

        result = calculate_atr(highs, lows, closes, length=14)

        # Should return results
        assert isinstance(result, dict)
        assert "atr" in result
        assert len(result["atr"]) == 14

        # First period-1 values should be None
        for i in range(13):
            assert result["atr"][i] is None

        # Last value should be calculated
        assert result["atr"][13] is not None
        assert result["atr"][13] > 0

    def test_atr_unequal_list_lengths(self):
        """Test ATR with unequal list lengths."""
        highs = [100.0, 102.0, 104.0]
        lows = [98.0, 100.0]
        closes = [99.0, 101.0, 103.0]

        result = calculate_atr(highs, lows, closes, length=14)

        # Should return all None values
        assert isinstance(result, dict)
        assert "atr" in result
        assert all(v is None for v in result["atr"])

    def test_atr_with_none_values(self):
        """Test ATR with None values in data."""
        highs = [100.0, None, 104.0, 103.0, 105.0]
        lows = [98.0, 100.0, None, 101.0, 103.0]
        closes = [99.0, 101.0, 103.0, 102.0, 104.0]

        result = calculate_atr(highs, lows, closes, length=3)

        # Should handle None values gracefully
        assert isinstance(result, dict)
        assert "atr" in result
        assert len(result["atr"]) == 5

    def test_atr_all_none_values(self):
        """Test ATR with all None values."""
        highs = [None, None, None]
        lows = [None, None, None]
        closes = [None, None, None]

        result = calculate_atr(highs, lows, closes, length=2)

        # Should return None values
        assert isinstance(result, dict)
        assert "atr" in result
        assert all(v is None for v in result["atr"])

    def test_atr_consistency(self, sample_ohlcv_data):
        """Test ATR calculation consistency."""
        # Calculate twice and should get same results
        result1 = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=14,
        )
        result2 = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=14,
        )

        assert result1 == result2

    def test_atr_trending_data(self, trending_upward_data):
        """Test ATR with trending upward data."""
        result = calculate_atr(
            trending_upward_data["highs"],
            trending_upward_data["lows"],
            trending_upward_data["closes"],
            length=14,
        )

        # Should return valid ATR values
        assert isinstance(result, dict)
        assert "atr" in result

        # Extract last valid ATR value
        valid_atr_values = [v for v in result["atr"] if v is not None]
        if valid_atr_values:
            last_atr = valid_atr_values[-1]
            assert last_atr > 0

    def test_atr_sideways_data(self, sideways_data):
        """Test ATR with sideways data."""
        result = calculate_atr(
            sideways_data["highs"],
            sideways_data["lows"],
            sideways_data["closes"],
            length=14,
        )

        # Should return valid ATR values
        assert isinstance(result, dict)
        assert "atr" in result

        # Extract last valid ATR value
        valid_atr_values = [v for v in result["atr"] if v is not None]
        if valid_atr_values:
            last_atr = valid_atr_values[-1]
            assert last_atr > 0

    def test_atr_single_data_point(self):
        """Test ATR with single data point."""
        result = calculate_atr([100.0], [98.0], [99.0], length=14)

        # Should return single None value (insufficient data)
        assert isinstance(result, dict)
        assert "atr" in result
        assert len(result["atr"]) == 1
        assert result["atr"][0] is None

    def test_atr_two_data_points(self):
        """Test ATR with two data points."""
        result = calculate_atr([100.0, 102.0], [98.0, 100.0], [99.0, 101.0], length=14)

        # Should return None values (insufficient data)
        assert isinstance(result, dict)
        assert "atr" in result
        assert len(result["atr"]) == 2
        assert all(v is None for v in result["atr"])

    def test_atr_large_period(self, sample_ohlcv_data):
        """Test ATR with period larger than data length."""
        result = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=100,
        )

        # Should return all None values
        assert isinstance(result, dict)
        assert "atr" in result
        assert all(v is None for v in result["atr"])

    def test_atr_period_one(self, sample_ohlcv_data):
        """Test ATR with period=1."""
        result = calculate_atr(
            sample_ohlcv_data["highs"],
            sample_ohlcv_data["lows"],
            sample_ohlcv_data["closes"],
            length=1,
        )

        # Should return valid values starting from index 0
        assert isinstance(result, dict)
        assert "atr" in result

        # All values should be non-None (period=1 means all can be calculated)
        valid_values = [v for v in result["atr"] if v is not None]
        assert len(valid_values) > 0

    def test_atr_very_small_values(self):
        """Test ATR with very small price values."""
        highs = [0.01, 0.02, 0.03, 0.04, 0.05]
        lows = [0.009, 0.019, 0.029, 0.039, 0.049]
        closes = [0.010, 0.020, 0.030, 0.040, 0.050]

        result = calculate_atr(highs, lows, closes, length=3)

        # Should handle small values
        assert isinstance(result, dict)
        assert "atr" in result
        assert len(result["atr"]) == 5

        # Valid values should be positive
        valid_values = [v for v in result["atr"] if v is not None]
        assert all(v > 0 for v in valid_values)

    def test_atr_very_large_values(self):
        """Test ATR with very large price values."""
        highs = [1000000.0, 1002000.0, 1004000.0, 1003000.0, 1005000.0]
        lows = [999800.0, 1000000.0, 1002000.0, 1001000.0, 1003000.0]
        closes = [999900.0, 1001000.0, 1003000.0, 1002000.0, 1004000.0]

        result = calculate_atr(highs, lows, closes, length=3)

        # Should handle large values
        assert isinstance(result, dict)
        assert "atr" in result
        assert len(result["atr"]) == 5

        # Valid values should be positive
        valid_values = [v for v in result["atr"] if v is not None]
        assert all(v > 0 for v in valid_values)
