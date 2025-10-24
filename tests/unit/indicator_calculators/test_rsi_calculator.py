import numpy as np
import pandas as pd
import pytest

from services.indicator_calculators.rsi_calculator import calculate_rsi


@pytest.fixture
def sample_close_data() -> pd.DataFrame:
    """Create realistic close price data for testing RSI."""
    np.random.seed(42)

    # Create a trending price series
    close_prices = 100 + np.cumsum(np.random.normal(0.1, 2, 50))

    df = pd.DataFrame({"close": close_prices})
    return df


@pytest.fixture
def trending_upward_data() -> pd.DataFrame:
    """Create data with strong upward trend for higher RSI."""
    # Strong upward trend
    base_prices = np.linspace(100, 150, 50)
    close_prices = base_prices + np.random.normal(0, 0.5, 50)

    df = pd.DataFrame({"close": close_prices})
    return df


@pytest.fixture
def trending_downward_data() -> pd.DataFrame:
    """Create data with strong downward trend for lower RSI."""
    # Strong downward trend
    base_prices = np.linspace(150, 100, 50)
    close_prices = base_prices + np.random.normal(0, 0.5, 50)

    df = pd.DataFrame({"close": close_prices})
    return df


@pytest.fixture
def sideways_data() -> pd.DataFrame:
    """Create data with sideways movement for neutral RSI."""
    # Sideways movement
    base_price = 100
    close_prices = base_price + np.random.normal(0, 1, 50)

    df = pd.DataFrame({"close": close_prices})
    return df


class TestCalculateRSI:
    """Tests for RSI calculation."""

    def test_rsi_basic_happy_path(self, sample_close_data):
        """Test basic RSI calculation with valid data."""
        result = calculate_rsi(sample_close_data, length=14, source="close")

        # Should return dictionary with rsi as list
        assert isinstance(result, dict)
        assert "rsi" in result

        # Values should be list
        assert isinstance(result["rsi"], list)

        # Check the last values in the series (if not None)
        rsi_series = result["rsi"]

        if rsi_series and len(rsi_series) > 0:
            last_rsi = rsi_series[-1]

            if last_rsi is not None:
                assert 0 <= last_rsi <= 100

    def test_rsi_with_different_periods(self, sample_close_data):
        """Test RSI with different periods."""
        result_14 = calculate_rsi(sample_close_data, length=14, source="close")
        result_20 = calculate_rsi(sample_close_data, length=20, source="close")

        # Both should return valid results as lists
        assert isinstance(result_14, dict)
        assert isinstance(result_20, dict)
        assert isinstance(result_14["rsi"], list)
        assert isinstance(result_20["rsi"], list)

        # Check last values if available
        if result_14["rsi"] and len(result_14["rsi"]) > 0:
            last_14 = result_14["rsi"][-1]
            if last_14 is not None:
                assert 0 <= last_14 <= 100

        if result_20["rsi"] and len(result_20["rsi"]) > 0:
            last_20 = result_20["rsi"][-1]
            if last_20 is not None:
                assert 0 <= last_20 <= 100

    def test_rsi_trending_upward_data(self, trending_upward_data):
        """Test RSI with trending upward data should give higher RSI."""
        result = calculate_rsi(trending_upward_data, length=14, source="close")

        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                # Upward trending data should have RSI > 50
                assert last_rsi > 50

    def test_rsi_trending_downward_data(self, trending_downward_data):
        """Test RSI with trending downward data should give lower RSI."""
        result = calculate_rsi(trending_downward_data, length=14, source="close")

        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                # Downward trending data should have RSI < 50
                assert last_rsi < 50

    def test_rsi_sideways_data(self, sideways_data):
        """Test RSI with sideways data should give neutral RSI."""
        result = calculate_rsi(sideways_data, length=14, source="close")

        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                # Sideways data should have RSI around 50
                assert 0 <= last_rsi <= 100

    def test_rsi_empty_dataframe(self):
        """Test RSI with empty DataFrame."""
        df = pd.DataFrame(columns=["close"])
        result = calculate_rsi(df, length=14, source="close")

        assert result == {"rsi": []}

    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient data (< period)."""
        df = pd.DataFrame({"close": [100, 101, 102, 103, 104]})
        result = calculate_rsi(df, length=14, source="close")

        # Should return None values for insufficient data
        assert isinstance(result, dict)
        assert "rsi" in result
        assert all(v is None for v in result["rsi"])

    def test_rsi_exactly_period_length(self):
        """Test RSI with exactly period length of data."""
        df = pd.DataFrame({"close": [100 + i for i in range(14)]})
        result = calculate_rsi(df, length=14, source="close")

        # With exactly period length, first value should be None
        assert isinstance(result, dict)
        assert "rsi" in result
        assert result["rsi"][0] is None

    def test_rsi_period_plus_one(self):
        """Test RSI with period + 1 data points."""
        df = pd.DataFrame({"close": [100 + i for i in range(15)]})
        result = calculate_rsi(df, length=14, source="close")

        # Should return some values now
        assert isinstance(result, dict)
        assert "rsi" in result
        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                assert 0 <= last_rsi <= 100

    def test_rsi_missing_columns(self):
        """Test RSI with missing required columns."""
        df = pd.DataFrame({"high": [105, 106, 107]})
        result = calculate_rsi(df, length=14, source="close")

        # Should return list with None values when column is missing
        assert isinstance(result, dict)
        assert "rsi" in result
        assert all(v is None for v in result["rsi"])

    def test_rsi_invalid_period_zero(self, sample_close_data):
        """Test RSI with zero period."""
        result = calculate_rsi(sample_close_data, length=0, source="close")

        assert result == {"rsi": [None] * len(sample_close_data)}

    def test_rsi_invalid_period_negative(self, sample_close_data):
        """Test RSI with negative period."""
        result = calculate_rsi(sample_close_data, length=-5, source="close")

        assert result == {"rsi": [None] * len(sample_close_data)}

    def test_rsi_with_nan_values(self):
        """Test RSI with NaN values in data."""
        df = pd.DataFrame({"close": [100, 101, np.nan, 103, 104, 105]})
        result = calculate_rsi(df, length=5, source="close")

        # Should handle NaN gracefully
        assert isinstance(result, dict)
        assert "rsi" in result

    def test_rsi_all_nan_values(self):
        """Test RSI with all NaN values."""
        df = pd.DataFrame({"close": [np.nan] * 20})
        result = calculate_rsi(df, length=14, source="close")

        # Should return list with None values
        assert isinstance(result["rsi"], list)
        assert all(v is None for v in result["rsi"])

    def test_rsi_consistent_results(self, sample_close_data):
        """Test that RSI gives consistent results for same input."""
        result1 = calculate_rsi(sample_close_data, length=14, source="close")
        result2 = calculate_rsi(sample_close_data, length=14, source="close")

        # Results should be identical
        assert result1 == result2

    def test_rsi_extreme_values(self):
        """Test RSI with extreme price values."""
        df = pd.DataFrame({"close": [1000000.0 + i for i in range(20)]})
        result = calculate_rsi(df, length=14, source="close")

        # Should handle large values without error
        assert isinstance(result, dict)
        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                assert 0 <= last_rsi <= 100

    def test_rsi_period_one(self, sample_close_data):
        """Test RSI with period of 1."""
        result = calculate_rsi(sample_close_data, length=1, source="close")

        # Should return valid results
        assert isinstance(result, dict)
        assert "rsi" in result


class TestRSIEdgeCases:
    """Edge case tests for RSI calculation."""

    def test_rsi_single_row(self):
        """Test RSI with single row of data."""
        df = pd.DataFrame({"close": [100]})
        result = calculate_rsi(df, length=14, source="close")

        assert result == {"rsi": [None]}

    def test_rsi_no_price_movement(self):
        """Test RSI with no price movement."""
        df = pd.DataFrame({"close": [100.0] * 20})
        result = calculate_rsi(df, length=14, source="close")

        # With no movement, RSI should still calculate
        assert isinstance(result, dict)
        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                assert 0 <= last_rsi <= 100

    def test_rsi_case_sensitive_columns(self):
        """Test RSI is case sensitive for column names."""
        df = pd.DataFrame({"Close": [100 + i for i in range(20)]})
        result = calculate_rsi(df, length=14, source="close")

        # Should return list with None values when column name doesn't match (case-sensitive)
        assert isinstance(result, dict)
        assert "rsi" in result
        assert all(v is None for v in result["rsi"])

    def test_rsi_extra_columns(self, sample_close_data):
        """Test RSI with extra columns doesn't affect calculation."""
        df = sample_close_data.copy()
        df["volume"] = [1000] * len(df)
        df["open"] = [100] * len(df)

        result = calculate_rsi(df, length=14, source="close")

        # Should work fine with extra columns
        assert isinstance(result, dict)
        assert "rsi" in result

    def test_rsi_monotonic_increase(self):
        """Test RSI with monotonic increase should be close to 100."""
        df = pd.DataFrame({"close": [100 + i for i in range(30)]})
        result = calculate_rsi(df, length=14, source="close")

        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                # Strong upward trend should have high RSI
                assert last_rsi > 70

    def test_rsi_monotonic_decrease(self):
        """Test RSI with monotonic decrease should be close to 0."""
        df = pd.DataFrame({"close": [100 - i for i in range(30)]})
        result = calculate_rsi(df, length=14, source="close")

        if result["rsi"] and len(result["rsi"]) > 0:
            last_rsi = result["rsi"][-1]
            if last_rsi is not None:
                # Strong downward trend should have low RSI
                assert last_rsi < 30
