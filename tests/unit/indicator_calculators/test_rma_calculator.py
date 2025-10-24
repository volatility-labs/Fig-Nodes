import numpy as np
import pandas as pd
import pytest

from services.indicator_calculators.rma_calculator import calculate_rma


@pytest.fixture
def sample_close_data() -> pd.DataFrame:
    """Create realistic close price data for testing RMA."""
    np.random.seed(42)

    # Create a trending price series
    close_prices = 100 + np.cumsum(np.random.normal(0.1, 2, 50))

    df = pd.DataFrame({"close": close_prices})
    return df


@pytest.fixture
def trending_upward_data() -> pd.DataFrame:
    """Create data with strong upward trend."""
    base_prices = np.linspace(100, 150, 50)
    close_prices = base_prices + np.random.normal(0, 0.5, 50)

    df = pd.DataFrame({"close": close_prices})
    return df


@pytest.fixture
def trending_downward_data() -> pd.DataFrame:
    """Create data with strong downward trend."""
    base_prices = np.linspace(150, 100, 50)
    close_prices = base_prices + np.random.normal(0, 0.5, 50)

    df = pd.DataFrame({"close": close_prices})
    return df


@pytest.fixture
def sideways_data() -> pd.DataFrame:
    """Create data with sideways movement."""
    base_price = 100
    close_prices = base_price + np.random.normal(0, 1, 50)

    df = pd.DataFrame({"close": close_prices})
    return df


class TestCalculateRMA:
    """Tests for RMA calculation."""

    def test_rma_basic_happy_path(self, sample_close_data):
        """Test basic RMA calculation with valid data."""
        result = calculate_rma(sample_close_data, period=14, source="close")

        # Should return dictionary with rma as list
        assert isinstance(result, dict)
        assert "rma" in result

        # Values should be list
        assert isinstance(result["rma"], list)

        # Should have same length as input
        assert len(result["rma"]) == len(sample_close_data)

        # Check that last value is valid (not None)
        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                assert isinstance(last_rma, float)
                assert last_rma > 0

    def test_rma_with_different_periods(self, sample_close_data):
        """Test RMA with different periods."""
        result_14 = calculate_rma(sample_close_data, period=14, source="close")
        result_20 = calculate_rma(sample_close_data, period=20, source="close")

        # Both should return valid results as lists
        assert isinstance(result_14, dict)
        assert isinstance(result_20, dict)
        assert isinstance(result_14["rma"], list)
        assert isinstance(result_20["rma"], list)

        # Both should have same length as input
        assert len(result_14["rma"]) == len(sample_close_data)
        assert len(result_20["rma"]) == len(sample_close_data)

    def test_rma_empty_dataframe(self):
        """Test RMA with empty DataFrame."""
        df = pd.DataFrame(columns=["close"])
        result = calculate_rma(df, period=14, source="close")

        assert result == {"rma": []}

    def test_rma_insufficient_data(self):
        """Test RMA with insufficient data (< period)."""
        df = pd.DataFrame({"close": [100, 101, 102, 103, 104]})
        result = calculate_rma(df, period=14, source="close")

        # Should return None values for insufficient data
        assert isinstance(result, dict)
        assert "rma" in result
        assert all(v is None for v in result["rma"])

    def test_rma_exactly_period_length(self):
        """Test RMA with exactly period length of data."""
        df = pd.DataFrame({"close": [100 + i for i in range(14)]})
        result = calculate_rma(df, period=14, source="close")

        # Should return results
        assert isinstance(result, dict)
        assert "rma" in result
        assert len(result["rma"]) == 14

        # Last value should be calculated
        assert result["rma"][-1] is not None

    def test_rma_period_plus_one(self):
        """Test RMA with period + 1 data points."""
        df = pd.DataFrame({"close": [100 + i for i in range(15)]})
        result = calculate_rma(df, period=14, source="close")

        # Should return some values now
        assert isinstance(result, dict)
        assert "rma" in result
        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                assert isinstance(last_rma, float)

    def test_rma_missing_columns(self):
        """Test RMA with missing required columns."""
        df = pd.DataFrame({"high": [105, 106, 107]})
        result = calculate_rma(df, period=14, source="close")

        # Should return list with None values when column is missing
        assert isinstance(result, dict)
        assert "rma" in result
        assert all(v is None for v in result["rma"])

    def test_rma_invalid_period_zero(self, sample_close_data):
        """Test RMA with zero period."""
        result = calculate_rma(sample_close_data, period=0, source="close")

        assert result == {"rma": [None] * len(sample_close_data)}

    def test_rma_invalid_period_negative(self, sample_close_data):
        """Test RMA with negative period."""
        result = calculate_rma(sample_close_data, period=-5, source="close")

        assert result == {"rma": [None] * len(sample_close_data)}

    def test_rma_with_nan_values(self):
        """Test RMA with NaN values in data."""
        df = pd.DataFrame({"close": [100, 101, np.nan, 103, 104, 105]})
        result = calculate_rma(df, period=5, source="close")

        # Should handle NaN gracefully
        assert isinstance(result, dict)
        assert "rma" in result

    def test_rma_all_nan_values(self):
        """Test RMA with all NaN values."""
        df = pd.DataFrame({"close": [np.nan] * 20})
        result = calculate_rma(df, period=14, source="close")

        # Should return list with None values
        assert isinstance(result["rma"], list)
        assert all(v is None for v in result["rma"])

    def test_rma_consistent_results(self, sample_close_data):
        """Test that RMA gives consistent results for same input."""
        result1 = calculate_rma(sample_close_data, period=14, source="close")
        result2 = calculate_rma(sample_close_data, period=14, source="close")

        # Results should be identical
        assert result1 == result2

    def test_rma_extreme_values(self):
        """Test RMA with extreme price values."""
        df = pd.DataFrame({"close": [1000000.0 + i for i in range(20)]})
        result = calculate_rma(df, period=14, source="close")

        # Should handle large values without error
        assert isinstance(result, dict)
        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                assert isinstance(last_rma, float)

    def test_rma_period_one(self, sample_close_data):
        """Test RMA with period of 1."""
        result = calculate_rma(sample_close_data, period=1, source="close")

        # Should return valid results
        assert isinstance(result, dict)
        assert "rma" in result

    def test_rma_trending_upward_data(self, trending_upward_data):
        """Test RMA with trending upward data."""
        result = calculate_rma(trending_upward_data, period=14, source="close")

        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                # Should track upward trend
                assert isinstance(last_rma, float)

    def test_rma_trending_downward_data(self, trending_downward_data):
        """Test RMA with trending downward data."""
        result = calculate_rma(trending_downward_data, period=14, source="close")

        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                # Should track downward trend
                assert isinstance(last_rma, float)

    def test_rma_sideways_data(self, sideways_data):
        """Test RMA with sideways data."""
        result = calculate_rma(sideways_data, period=14, source="close")

        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                assert isinstance(last_rma, float)


class TestRMAEdgeCases:
    """Edge case tests for RMA calculation."""

    def test_rma_single_row(self):
        """Test RMA with single row of data."""
        df = pd.DataFrame({"close": [100]})
        result = calculate_rma(df, period=14, source="close")

        assert result == {"rma": [None]}

    def test_rma_no_price_movement(self):
        """Test RMA with no price movement."""
        df = pd.DataFrame({"close": [100.0] * 20})
        result = calculate_rma(df, period=14, source="close")

        # With no movement, RMA should still calculate
        assert isinstance(result, dict)
        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                assert last_rma == 100.0

    def test_rma_case_sensitive_columns(self):
        """Test RMA is case sensitive for column names."""
        df = pd.DataFrame({"Close": [100 + i for i in range(20)]})
        result = calculate_rma(df, period=14, source="close")

        # Should return list with None values when column name doesn't match (case-sensitive)
        assert isinstance(result, dict)
        assert "rma" in result
        assert all(v is None for v in result["rma"])

    def test_rma_extra_columns(self, sample_close_data):
        """Test RMA with extra columns doesn't affect calculation."""
        df = sample_close_data.copy()
        df["volume"] = [1000] * len(df)
        df["open"] = [100] * len(df)

        result = calculate_rma(df, period=14, source="close")

        # Should work fine with extra columns
        assert isinstance(result, dict)
        assert "rma" in result

    def test_rma_with_different_source(self, sample_close_data):
        """Test RMA with different source column."""
        df = sample_close_data.copy()
        df["high"] = df["close"] + 1

        result = calculate_rma(df, period=14, source="high")

        # Should work with different source
        assert isinstance(result, dict)
        assert "rma" in result
        if result["rma"] and len(result["rma"]) > 0:
            last_rma = result["rma"][-1]
            if last_rma is not None:
                assert isinstance(last_rma, float)

    def test_rma_manual_calculation(self):
        """Test RMA with simple data for manual verification."""
        # Simple ascending data
        df = pd.DataFrame({"close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]})
        result = calculate_rma(df, period=5, source="close")

        # Check structure
        assert isinstance(result, dict)
        assert "rma" in result
        assert len(result["rma"]) == 11

        # First 4 values should be None (insufficient data for period=5)
        for i in range(4):
            assert result["rma"][i] is None

        # From index 4 onwards, should have valid values
        for i in range(4, 11):
            assert result["rma"][i] is not None
            assert isinstance(result["rma"][i], float)
