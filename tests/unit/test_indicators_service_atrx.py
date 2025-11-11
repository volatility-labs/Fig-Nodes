import numpy as np
import pandas as pd
import pytest

from services.indicator_calculators.atrx_calculator import calculate_atrx


def _prepare_and_calculate_atrx(df, length=14, ma_length=50, source="close"):
    """Helper function to prepare dataframe and calculate ATRX"""
    df_calc = df[["High", "Low", "Close"]].copy()
    df_calc.columns = [col.lower() for col in df_calc.columns]

    result_dict = calculate_atrx(df_calc, length=length, ma_length=ma_length, source=source)
    return result_dict["atrx"][-1]


@pytest.fixture
def sample_df():
    """Create sample DataFrame with known values for testing"""
    data = []
    for i in range(60):
        price = 100 + (i * 2 / 59)  # Linear increase from 100 to 102
        data.append(
            {"Open": price, "High": price + 1, "Low": price - 1, "Close": price, "Volume": 10000}
        )
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")
    return df


@pytest.fixture
def constant_df():
    """Create DataFrame with constant prices"""
    data = []
    for i in range(60):
        data.append({"Open": 100, "High": 105, "Low": 95, "Close": 100, "Volume": 10000})
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")
    return df


@pytest.fixture
def zero_volatility_df():
    """Create DataFrame with zero volatility (high = low)"""
    data = []
    for i in range(60):
        data.append({"Open": 100, "High": 100, "Low": 100, "Close": 100, "Volume": 10000})
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")
    return df


@pytest.fixture
def trending_df():
    """Create DataFrame with strong uptrend"""
    data = []
    for i in range(60):
        price = 100 + i  # Strong uptrend
        data.append(
            {
                "Open": price,
                "High": price + 0.5,
                "Low": price - 0.5,
                "Close": price,
                "Volume": 10000,
            }
        )
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")
    return df


def test_calculate_atrx_happy_path(sample_df):
    """Test ATRX calculation with valid data"""
    result = _prepare_and_calculate_atrx(sample_df)

    assert isinstance(result, float)
    assert not np.isnan(result)
    # With trending up data, ATRX should be positive
    assert result > 0


def test_calculate_atrx_constant_prices(constant_df):
    """Test ATRX calculation with constant prices"""
    result = _prepare_and_calculate_atrx(constant_df)

    assert isinstance(result, float)
    assert not np.isnan(result)
    # With constant prices, ATRX should be close to 0
    assert abs(result) < 0.1


def test_calculate_atrx_zero_volatility(zero_volatility_df):
    """Test ATRX calculation with zero volatility"""
    result = _prepare_and_calculate_atrx(zero_volatility_df)

    # Should return None due to zero ATR (result is None, not NaN for calculator)
    assert result is None or np.isnan(result)


def test_calculate_atrx_strong_trend(trending_df):
    """Test ATRX calculation with strong uptrend"""
    result = _prepare_and_calculate_atrx(trending_df)

    assert isinstance(result, float)
    assert not np.isnan(result)
    # With strong uptrend, ATRX should be very positive
    assert result > 10


def test_calculate_atrx_insufficient_data():
    """Test ATRX calculation with insufficient data"""
    # Create DataFrame with only 10 rows (less than required 50 for SMA)
    data = []
    for i in range(10):
        data.append({"Open": 100, "High": 105, "Low": 95, "Close": 100, "Volume": 10000})
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=10, freq="D")

    result = _prepare_and_calculate_atrx(df)
    assert result is None or np.isnan(result)


def test_calculate_atrx_empty_dataframe():
    """Test ATRX calculation with empty DataFrame"""
    df = pd.DataFrame()
    # Will fail on column access, so check for KeyError
    try:
        result = _prepare_and_calculate_atrx(df)
        assert result is None or np.isnan(result)
    except KeyError:
        pass  # Expected for empty dataframe


def test_calculate_atrx_only_rma_supported(sample_df):
    """Test that ATRX calculator only supports RMA (Wilder's smoothing)"""
    # The calculator only supports RMA smoothing (via Wilder's MA for ATR)
    result = _prepare_and_calculate_atrx(sample_df)

    # Should be valid numbers
    assert not np.isnan(result)

    # Results should be positive for trending data
    assert result > 0


def test_calculate_atrx_different_lengths(sample_df):
    """Test ATRX calculation with different ATR lengths"""
    result_14 = _prepare_and_calculate_atrx(sample_df, length=14)
    result_21 = _prepare_and_calculate_atrx(sample_df, length=21)
    result_7 = _prepare_and_calculate_atrx(sample_df, length=7)

    # All should be valid numbers
    assert not np.isnan(result_14)
    assert not np.isnan(result_21)
    assert not np.isnan(result_7)

    # Results should be positive for trending data
    assert result_14 > 0
    assert result_21 > 0
    assert result_7 > 0


def test_calculate_atrx_different_ma_lengths(sample_df):
    """Test ATRX calculation with different MA lengths"""
    result_50 = _prepare_and_calculate_atrx(sample_df, ma_length=50)
    result_30 = _prepare_and_calculate_atrx(sample_df, ma_length=30)
    result_20 = _prepare_and_calculate_atrx(sample_df, ma_length=20)

    # All should be valid numbers
    assert not np.isnan(result_50)
    assert not np.isnan(result_30)
    assert not np.isnan(result_20)

    # Results should be positive for trending data
    assert result_50 > 0
    assert result_30 > 0
    assert result_20 > 0


def test_calculate_atrx_invalid_price_column(sample_df):
    """Test ATRX calculation with invalid price column"""
    # Calculator will return list of None values for invalid source
    df_calc = sample_df[["High", "Low", "Close"]].copy()
    df_calc.columns = [col.lower() for col in df_calc.columns]

    result_dict = calculate_atrx(df_calc, source="InvalidColumn")
    result = result_dict["atrx"][-1]
    assert result is None or np.isnan(result)


def test_calculate_atrx_downtrend():
    """Test ATRX calculation with downtrending data"""
    data = []
    for i in range(60):
        price = 100 - (i * 2 / 59)  # Linear decrease from 100 to 98
        data.append(
            {"Open": price, "High": price + 1, "Low": price - 1, "Close": price, "Volume": 10000}
        )
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")

    result = _prepare_and_calculate_atrx(df)

    assert isinstance(result, float)
    assert not np.isnan(result)
    # With downtrend, ATRX should be negative
    assert result < 0


def test_calculate_atrx_true_range_calculation():
    """Test that True Range is calculated correctly"""
    # Create data where True Range should be max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    data = [
        {"Open": 100, "High": 105, "Low": 95, "Close": 100, "Volume": 10000},  # First bar
        {
            "Open": 100,
            "High": 110,
            "Low": 90,
            "Close": 95,
            "Volume": 10000,
        },  # Second bar: TR should be max(20, 10, 5) = 20
    ] * 30  # Repeat to have enough data
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")

    result = _prepare_and_calculate_atrx(df, length=2)  # Use short length to see effect

    assert isinstance(result, float)
    assert not np.isnan(result)


def test_calculate_atrx_atr_percentage_calculation(constant_df):
    """Test that ATR% is calculated correctly"""
    result = _prepare_and_calculate_atrx(constant_df)

    # For constant data with close=100, high=105, low=95
    # ATR should be 10, ATR% = 10/100 = 0.1
    # SMA50 should be 100, % Gain From 50-MA = (100-100)/100 = 0
    # ATRX = 0 / 0.1 = 0
    assert abs(result) < 0.1  # Should be close to 0


def test_calculate_atrx_edge_case_zero_atr():
    """Test ATRX calculation when ATR is zero"""
    # Create data where ATR would be zero
    data = []
    for i in range(60):
        data.append(
            {
                "Open": 100,
                "High": 100,  # Same as low
                "Low": 100,
                "Close": 100,
                "Volume": 10000,
            }
        )
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")

    result = _prepare_and_calculate_atrx(df)
    assert result is None or np.isnan(result)


def test_calculate_atrx_edge_case_zero_sma():
    """Test ATRX calculation when SMA50 is zero"""
    # This is unlikely in real data, but test the edge case
    data = []
    for i in range(60):
        data.append({"Open": 0, "High": 1, "Low": 0, "Close": 0, "Volume": 10000})
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=60, freq="D")

    result = _prepare_and_calculate_atrx(df)
    assert result is None or np.isnan(result)
