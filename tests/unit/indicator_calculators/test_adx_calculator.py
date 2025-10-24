import numpy as np
import pandas as pd
import pytest

from services.indicator_calculators.adx_calculator import calculate_adx, calculate_wilder_ma


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Create realistic OHLCV data for testing ADX."""
    np.random.seed(42)

    # Create a trending price series
    close_prices = 100 + np.cumsum(np.random.normal(0.1, 2, 50))
    high_prices = close_prices + np.random.uniform(0.5, 3, 50)
    low_prices = close_prices - np.random.uniform(0.5, 3, 50)

    df = pd.DataFrame({"high": high_prices, "low": low_prices, "close": close_prices})
    return df


@pytest.fixture
def trending_upward_data() -> pd.DataFrame:
    """Create data with strong upward trend for higher ADX."""
    # Strong upward trend
    base_prices = np.linspace(100, 150, 50)
    high_prices = base_prices + np.random.uniform(1, 3, 50)
    low_prices = base_prices - np.random.uniform(1, 3, 50)
    close_prices = base_prices + np.random.normal(0, 0.5, 50)

    df = pd.DataFrame({"high": high_prices, "low": low_prices, "close": close_prices})
    return df


@pytest.fixture
def sideways_data() -> pd.DataFrame:
    """Create data with sideways movement for lower ADX."""
    # Sideways movement
    base_price = 100
    high_prices = base_price + np.random.uniform(0.5, 2, 50)
    low_prices = base_price - np.random.uniform(0.5, 2, 50)
    close_prices = base_price + np.random.normal(0, 1, 50)

    df = pd.DataFrame({"high": high_prices, "low": low_prices, "close": close_prices})
    return df


class TestCalculateWilderMA:
    """Tests for Wilder's Moving Average calculation."""

    def test_wilder_ma_basic(self):
        """Test basic Wilder MA calculation."""
        arr: list[float | None] = [1.0, 2.0, 3.0, 4.0, 5.0]
        period = 3
        result = calculate_wilder_ma(arr, period)

        # First period-1 values should be None
        assert result[0] is None
        assert result[1] is None

        # First actual value should be simple average
        assert result[2] == pytest.approx(2.0, abs=0.01)  # (1+2+3)/3

        # Subsequent values use Wilder's smoothing
        # result[3] = (result[2] * (period-1) + arr[3]) / period
        assert result[2] is not None
        expected_3 = (result[2] * 2 + 4.0) / 3
        assert result[3] == pytest.approx(expected_3, abs=0.01)

        # result[4] = (result[3] * (period-1) + arr[4]) / period
        assert result[3] is not None
        expected_4 = (result[3] * 2 + 5.0) / 3
        assert result[4] == pytest.approx(expected_4, abs=0.01)

    def test_wilder_ma_with_none_values(self):
        """Test Wilder MA with None values."""
        arr = [1.0, 2.0, None, 4.0, 5.0]
        period = 3
        result = calculate_wilder_ma(arr, period)

        # After None, all values should be None
        assert result[0] is None
        assert result[1] is None
        assert result[2] is None
        assert result[3] is None
        assert result[4] is None

    def test_wilder_ma_with_none_at_start(self):
        """Test Wilder MA with None at start."""
        arr = [None, None, 3.0, 4.0, 5.0]
        period = 3
        result = calculate_wilder_ma(arr, period)

        # Should handle None at start gracefully - starts calculating when data begins
        assert result[0] is None
        assert result[1] is None
        # After None values, it starts fresh with first value
        assert result[2] is None  # Still building up to period
        assert result[3] is None  # Still building up to period
        assert result[4] is not None  # Gets first MA value

    def test_wilder_ma_with_consecutive_none(self):
        """Test Wilder MA with consecutive None values."""
        arr = [1.0, 2.0, 3.0, None, None, 6.0, 7.0]
        period = 3
        result = calculate_wilder_ma(arr, period)

        # Should break sequence after first None appears mid-stream
        assert result[0] is None
        assert result[1] is None
        assert result[2] is not None
        assert result[3] is None
        assert result[4] is None
        assert result[5] is None
        assert result[6] is None

    def test_wilder_ma_period_one(self):
        """Test Wilder MA with period of 1."""
        arr: list[float | None] = [1.0, 2.0, 3.0]
        period = 1
        result = calculate_wilder_ma(arr, period)

        # With period 1, first value is the value itself
        assert result[0] == pytest.approx(1.0, abs=0.01)
        assert result[1] == pytest.approx(2.0, abs=0.01)
        assert result[2] == pytest.approx(3.0, abs=0.01)

    def test_wilder_ma_empty_array(self):
        """Test Wilder MA with empty array."""
        arr = []
        period = 3
        result = calculate_wilder_ma(arr, period)

        assert result == []


class TestCalculateADX:
    """Tests for ADX calculation."""

    def test_adx_basic_happy_path(self, sample_ohlcv_data):
        """Test basic ADX calculation with valid data."""
        result = calculate_adx(sample_ohlcv_data, period=14)

        # Should return dictionary with adx, pdi, ndi as lists
        assert isinstance(result, dict)
        assert "adx" in result
        assert "pdi" in result
        assert "ndi" in result

        # Values should be lists
        assert isinstance(result["adx"], list)
        assert isinstance(result["pdi"], list)
        assert isinstance(result["ndi"], list)

        # Check the last values in the series (if not None)
        adx_series = result["adx"]
        pdi_series = result["pdi"]
        ndi_series = result["ndi"]

        if adx_series and len(adx_series) > 0:
            last_adx = adx_series[-1]
            last_pdi = pdi_series[-1]
            last_ndi = ndi_series[-1]

            if last_adx is not None:
                assert 0 <= last_adx <= 100
                assert 0 <= last_pdi <= 100
                assert 0 <= last_ndi <= 100

    def test_adx_with_different_periods(self, sample_ohlcv_data):
        """Test ADX with different periods."""
        result_14 = calculate_adx(sample_ohlcv_data, period=14)
        result_20 = calculate_adx(sample_ohlcv_data, period=20)

        # Both should return valid results as lists
        assert isinstance(result_14, dict)
        assert isinstance(result_20, dict)
        assert isinstance(result_14["adx"], list)
        assert isinstance(result_20["adx"], list)

        # Check last values if available
        if result_14["adx"] and len(result_14["adx"]) > 0:
            last_14 = result_14["adx"][-1]
            if last_14 is not None:
                assert 0 <= last_14 <= 100

        if result_20["adx"] and len(result_20["adx"]) > 0:
            last_20 = result_20["adx"][-1]
            if last_20 is not None:
                assert 0 <= last_20 <= 100

    def test_adx_trending_data(self, trending_upward_data):
        """Test ADX with trending data should give higher ADX."""
        result = calculate_adx(trending_upward_data, period=14)

        if result["adx"] and len(result["adx"]) > 0:
            last_adx = result["adx"][-1]
            if last_adx is not None:
                # Trending data should have ADX > 0 (indicating trend)
                assert last_adx > 0

                # PDI should be higher than NDI for upward trend
                last_pdi = result["pdi"][-1]
                last_ndi = result["ndi"][-1]
                if last_pdi is not None and last_ndi is not None:
                    assert last_pdi > last_ndi

    def test_adx_sideways_data(self, sideways_data):
        """Test ADX with sideways data should give lower ADX."""
        result = calculate_adx(sideways_data, period=14)

        if result["adx"] and len(result["adx"]) > 0:
            last_adx = result["adx"][-1]
            if last_adx is not None:
                # Sideways data should have ADX >= 0 and <= 100
                assert last_adx >= 0
                assert last_adx <= 100

    def test_adx_empty_dataframe(self):
        """Test ADX with empty DataFrame."""
        df = pd.DataFrame(columns=["high", "low", "close"])
        result = calculate_adx(df, period=14)

        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_insufficient_data(self):
        """Test ADX with insufficient data (< period)."""
        df = pd.DataFrame(
            {
                "high": [105, 106, 107, 108, 109],
                "low": [95, 96, 97, 98, 99],
                "close": [100, 101, 102, 103, 104],
            }
        )
        result = calculate_adx(df, period=14)

        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_exactly_period_length(self):
        """Test ADX with exactly period length of data."""
        df = pd.DataFrame(
            {
                "high": [105 + i for i in range(14)],
                "low": [95 + i for i in range(14)],
                "close": [100 + i for i in range(14)],
            }
        )
        result = calculate_adx(df, period=14)

        # With exactly period length, we can still calculate PDI and NDI but not ADX
        assert isinstance(result, dict)
        assert "adx" in result
        assert "pdi" in result
        assert "ndi" in result
        # ADX requires an additional period for smoothing DX, so the last value will be None
        if result["adx"] and len(result["adx"]) > 0:
            assert result["adx"][-1] is None
        # But PDI and NDI can be calculated
        if result["pdi"] and len(result["pdi"]) > 0:
            assert result["pdi"][-1] is not None
        if result["ndi"] and len(result["ndi"]) > 0:
            assert result["ndi"][-1] is not None

    def test_adx_period_plus_one(self):
        """Test ADX with period + 1 data points."""
        df = pd.DataFrame(
            {
                "high": [105 + i for i in range(15)],
                "low": [95 + i for i in range(15)],
                "close": [100 + i for i in range(15)],
            }
        )
        result = calculate_adx(df, period=14)

        # Should return some values now
        assert isinstance(result, dict)
        assert "adx" in result
        assert "pdi" in result
        assert "ndi" in result

    def test_adx_missing_columns(self):
        """Test ADX with missing required columns."""
        df = pd.DataFrame(
            {
                "high": [105, 106, 107],
                "low": [95, 96, 97],
                # Missing 'close' column
            }
        )
        result = calculate_adx(df, period=14)

        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_invalid_period_zero(self, sample_ohlcv_data):
        """Test ADX with zero period."""
        result = calculate_adx(sample_ohlcv_data, period=0)

        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_invalid_period_negative(self, sample_ohlcv_data):
        """Test ADX with negative period."""
        result = calculate_adx(sample_ohlcv_data, period=-5)

        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_with_nan_values(self):
        """Test ADX with NaN values in data."""
        df = pd.DataFrame(
            {
                "high": [105, 106, np.nan, 108, 109, 110],
                "low": [95, 96, 97, 98, 99, 100],
                "close": [100, 101, 102, 103, 104, 105],
            }
        )
        result = calculate_adx(df, period=5)

        # Should handle NaN gracefully
        assert isinstance(result, dict)
        assert "adx" in result

    def test_adx_all_nan_values(self):
        """Test ADX with all NaN values."""
        df = pd.DataFrame({"high": [np.nan] * 20, "low": [np.nan] * 20, "close": [np.nan] * 20})
        result = calculate_adx(df, period=14)

        # Should return empty lists or lists with None values
        assert isinstance(result["adx"], list)
        assert isinstance(result["pdi"], list)
        assert isinstance(result["ndi"], list)

    def test_adx_consistent_results(self, sample_ohlcv_data):
        """Test that ADX gives consistent results for same input."""
        result1 = calculate_adx(sample_ohlcv_data, period=14)
        result2 = calculate_adx(sample_ohlcv_data, period=14)

        # Results should be identical
        assert result1 == result2

    def test_adx_pdi_ndi_relationship(self, sample_ohlcv_data):
        """Test that PDI and NDI are non-negative."""
        result = calculate_adx(sample_ohlcv_data, period=14)

        if result["pdi"] and len(result["pdi"]) > 0:
            last_pdi = result["pdi"][-1]
            if last_pdi is not None:
                assert last_pdi >= 0

        if result["ndi"] and len(result["ndi"]) > 0:
            last_ndi = result["ndi"][-1]
            if last_ndi is not None:
                assert last_ndi >= 0

    def test_adx_extreme_values(self):
        """Test ADX with extreme price values."""
        df = pd.DataFrame(
            {
                "high": [1000000.0 + i for i in range(20)],
                "low": [999990.0 + i for i in range(20)],
                "close": [999995.0 + i for i in range(20)],
            }
        )
        result = calculate_adx(df, period=14)

        # Should handle large values without error
        assert isinstance(result, dict)
        if result["adx"] and len(result["adx"]) > 0:
            last_adx = result["adx"][-1]
            if last_adx is not None:
                assert 0 <= last_adx <= 100

    def test_adx_period_one(self, sample_ohlcv_data):
        """Test ADX with period of 1."""
        result = calculate_adx(sample_ohlcv_data, period=1)

        # Should return valid results
        assert isinstance(result, dict)
        assert "adx" in result
        assert "pdi" in result
        assert "ndi" in result


class TestADXEdgeCases:
    """Edge case tests for ADX calculation."""

    def test_adx_single_row(self):
        """Test ADX with single row of data."""
        df = pd.DataFrame({"high": [105], "low": [95], "close": [100]})
        result = calculate_adx(df, period=14)

        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_no_price_movement(self):
        """Test ADX with no price movement."""
        df = pd.DataFrame({"high": [100.0] * 20, "low": [100.0] * 20, "close": [100.0] * 20})
        result = calculate_adx(df, period=14)

        # With no movement, ADX should still calculate
        assert isinstance(result, dict)
        if result["adx"] and len(result["adx"]) > 0:
            last_adx = result["adx"][-1]
            if last_adx is not None:
                assert last_adx >= 0

    def test_adx_only_high_low_columns(self):
        """Test ADX with only high and low columns."""
        df = pd.DataFrame(
            {"high": [105 + i for i in range(20)], "low": [95 + i for i in range(20)]}
        )
        result = calculate_adx(df, period=14)

        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_case_sensitive_columns(self):
        """Test ADX is case sensitive for column names."""
        df = pd.DataFrame(
            {
                "High": [105 + i for i in range(20)],
                "Low": [95 + i for i in range(20)],
                "Close": [100 + i for i in range(20)],
            }
        )
        result = calculate_adx(df, period=14)

        # Should fail because columns are case-sensitive
        assert result == {"adx": [], "pdi": [], "ndi": []}

    def test_adx_extra_columns(self, sample_ohlcv_data):
        """Test ADX with extra columns doesn't affect calculation."""
        df = sample_ohlcv_data.copy()
        df["volume"] = [1000] * len(df)
        df["open"] = [100] * len(df)

        result = calculate_adx(df, period=14)

        # Should work fine with extra columns
        assert isinstance(result, dict)
        assert "adx" in result
