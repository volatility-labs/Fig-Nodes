import pytest
import pandas as pd
import numpy as np
from services.indicators_service import IndicatorsService


@pytest.fixture
def indicators_service():
    return IndicatorsService()


@pytest.fixture
def sample_ohlcv_data():
    """Create realistic OHLCV data for testing."""
    dates = pd.date_range('2023-01-01', periods=50, freq='D')
    np.random.seed(42)
    close_prices = 100 + np.cumsum(np.random.normal(0, 1, 50))
    high_prices = close_prices + np.random.uniform(0, 5, 50)
    low_prices = close_prices - np.random.uniform(0, 5, 50)
    open_prices = close_prices + np.random.normal(0, 1, 50)
    volumes = np.random.uniform(10000, 100000, 50)

    df = pd.DataFrame({
        'timestamp': dates,
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    })
    df.set_index('timestamp', inplace=True)
    return df


class TestIndicatorsService:
    """Comprehensive tests for IndicatorsService."""

    def test_compute_indicators_with_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test computing indicators with sufficient data."""
        result = indicators_service.compute_indicators(sample_ohlcv_data, '1d')

        # Check that all expected indicators are present
        expected_keys = {
            'evwma', 'eis_bullish', 'eis_bearish', 'adx', 'tlb', 'vbp', 'hurst',
            'acceleration', 'volume_ratio', 'resistance', 'res_pct',
            'res_tf', 'support', 'sup_pct', 'sup_tf'
        }
        assert set(result.keys()) == expected_keys

        # Check types
        assert isinstance(result['eis_bullish'], bool)
        assert isinstance(result['eis_bearish'], bool)
        assert isinstance(result['adx'], (float, np.floating))
        assert isinstance(result['hurst'], (float, np.floating))
        assert isinstance(result['acceleration'], (float, np.floating))
        assert isinstance(result['volume_ratio'], (float, np.floating))

    def test_compute_indicators_insufficient_data(self, indicators_service):
        """Test computing indicators with insufficient data."""
        # Create DataFrame with only 5 data points
        dates = pd.date_range('2023-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'timestamp': dates,
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109],
            'Low': [95, 96, 97, 98, 99],
            'Close': [102, 103, 104, 105, 106],
            'Volume': [10000, 11000, 12000, 13000, 14000]
        })
        df.set_index('timestamp', inplace=True)

        result = indicators_service.compute_indicators(df, '1d')

        # Should return empty dict for insufficient data
        assert result == {}

    def test_calculate_hurst_exponent_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test Hurst exponent calculation with sufficient data."""
        close_series = sample_ohlcv_data['Close']
        hurst = indicators_service.calculate_hurst_exponent(close_series)

        # Should return a valid float, not NaN
        assert isinstance(hurst, (float, np.floating))
        assert not np.isnan(hurst)
        # Hurst exponent should be between 0 and 2 for meaningful series
        assert 0 <= hurst <= 2

    def test_calculate_hurst_exponent_insufficient_data(self, indicators_service):
        """Test Hurst exponent calculation with insufficient data."""
        # Test with less than 10 data points
        short_series = pd.Series([100, 101, 102, 103, 104])
        hurst = indicators_service.calculate_hurst_exponent(short_series)

        assert np.isnan(hurst)

    def test_calculate_hurst_exponent_empty_series(self, indicators_service):
        """Test Hurst exponent calculation with empty series."""
        empty_series = pd.Series([], dtype=float)
        hurst = indicators_service.calculate_hurst_exponent(empty_series)

        assert np.isnan(hurst)

    def test_calculate_hurst_exponent_none_input(self, indicators_service):
        """Test Hurst exponent calculation with None input."""
        hurst = indicators_service.calculate_hurst_exponent(None)

        assert np.isnan(hurst)

    def test_calculate_adx_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test ADX calculation with sufficient data."""
        adx = indicators_service.calculate_custom_adx(sample_ohlcv_data)

        assert isinstance(adx, (float, np.floating))
        assert not np.isnan(adx)
        # ADX should be non-negative
        assert adx >= 0

    def test_calculate_adx_insufficient_data(self, indicators_service):
        """Test ADX calculation with insufficient data."""
        # Create DataFrame with insufficient data
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'timestamp': dates,
            'Open': range(10),
            'High': range(10, 20),
            'Low': range(5, 15),
            'Close': range(8, 18),
            'Volume': range(1000, 1010)
        })
        df.set_index('timestamp', inplace=True)

        adx = indicators_service.calculate_custom_adx(df)

        assert np.isnan(adx)

    def test_is_impulse_bullish_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test EIS bullish calculation."""
        bullish = indicators_service.is_impulse_bullish(sample_ohlcv_data)

        assert isinstance(bullish, bool)

    def test_is_impulse_bearish_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test EIS bearish calculation."""
        bearish = indicators_service.is_impulse_bearish(sample_ohlcv_data)

        assert isinstance(bearish, bool)

    def test_is_impulse_insufficient_data(self, indicators_service):
        """Test EIS calculation with insufficient data."""
        # Create DataFrame with insufficient data
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'timestamp': dates,
            'Open': range(10),
            'High': range(10, 20),
            'Low': range(5, 15),
            'Close': range(8, 18),
            'Volume': range(1000, 1010)
        })
        df.set_index('timestamp', inplace=True)

        bullish = indicators_service.is_impulse_bullish(df)
        bearish = indicators_service.is_impulse_bearish(df)

        assert bullish is False
        assert bearish is False

    def test_roc_slope_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test ROC slope (acceleration) calculation."""
        acceleration = indicators_service.roc_slope(sample_ohlcv_data['Close'])

        assert isinstance(acceleration, (float, np.floating))
        # Can be negative for declining momentum

    def test_roc_slope_insufficient_data(self, indicators_service):
        """Test ROC slope with insufficient data."""
        short_series = pd.Series([100, 101])
        acceleration = indicators_service.roc_slope(short_series)

        assert acceleration == 0

    def test_calculate_volume_metrics_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test volume ratio calculation."""
        ha_df = indicators_service.calculate_heiken_ashi(sample_ohlcv_data)
        volume_ratio = indicators_service.calculate_volume_metrics(sample_ohlcv_data, ha_df, 325)

        assert isinstance(volume_ratio, (float, np.floating))
        assert not np.isnan(volume_ratio)

    def test_calculate_volume_metrics_empty_data(self, indicators_service):
        """Test volume ratio calculation with empty data."""
        empty_df = pd.DataFrame()
        volume_ratio = indicators_service.calculate_volume_metrics(empty_df, empty_df, 325)

        assert volume_ratio == 1.0

    def test_calculate_heiken_ashi(self, indicators_service, sample_ohlcv_data):
        """Test Heiken Ashi calculation."""
        ha_df = indicators_service.calculate_heiken_ashi(sample_ohlcv_data)

        assert not ha_df.empty
        assert 'HA_Open' in ha_df.columns
        assert 'HA_High' in ha_df.columns
        assert 'HA_Low' in ha_df.columns
        assert 'HA_Close' in ha_df.columns
        assert 'Volume' in ha_df.columns

    def test_calculate_heiken_ashi_empty_data(self, indicators_service):
        """Test Heiken Ashi calculation with empty data."""
        ha_df = indicators_service.calculate_heiken_ashi(pd.DataFrame())

        assert ha_df.empty

    def test_calculate_evwma_sufficient_data(self, indicators_service, sample_ohlcv_data):
        """Test EVWMA calculation."""
        evwma = indicators_service.calculate_evwma(sample_ohlcv_data['Close'], sample_ohlcv_data['Volume'], 325)

        assert isinstance(evwma, (float, np.floating))
        assert not np.isnan(evwma)

    def test_calculate_evwma_empty_data(self, indicators_service):
        """Test EVWMA calculation with empty data."""
        empty_price = pd.Series([], dtype=float)
        empty_volume = pd.Series([], dtype=float)
        evwma = indicators_service.calculate_evwma(empty_price, empty_volume, 325)

        assert np.isnan(evwma) or len(evwma) == 0

    def test_calculate_volume_profile(self, indicators_service, sample_ohlcv_data):
        """Test volume profile calculation."""
        vbp = indicators_service.calculate_volume_profile(sample_ohlcv_data)

        assert isinstance(vbp, pd.Series)
        assert not vbp.empty

    def test_calculate_volume_profile_empty_data(self, indicators_service):
        """Test volume profile calculation with empty data."""
        vbp = indicators_service.calculate_volume_profile(pd.DataFrame())

        assert vbp.empty

    def test_calculate_three_line_break(self, indicators_service, sample_ohlcv_data):
        """Test Three Line Break calculation."""
        tlb = indicators_service.calculate_three_line_break(sample_ohlcv_data)

        assert isinstance(tlb, pd.DataFrame)
        # May be empty if conditions aren't met

    def test_get_next_significant_level(self, indicators_service, sample_ohlcv_data):
        """Test significant level calculation."""
        level, pct, tf = indicators_service.get_next_significant_level(
            sample_ohlcv_data, sample_ohlcv_data['Close'].iloc[-1], 'above', '1d'
        )

        # Results depend on volume profile, but should be consistent types
        if level is not None:
            assert isinstance(level, (float, np.floating))
            assert isinstance(pct, (float, np.floating))
            assert tf == '1d'
        else:
            assert pct is None
            assert tf is None

    def test_calculate_atrx_happy_path(self, indicators_service, sample_ohlcv_data):
        """Test ATRX calculation with sufficient data."""
        atrx = indicators_service.calculate_atrx(sample_ohlcv_data)
        assert isinstance(atrx, float)
        assert not np.isnan(atrx)

    def test_calculate_atrx_insufficient_data(self, indicators_service):
        """Test ATRX with insufficient data."""
        short_df = pd.DataFrame({
            'High': [100, 101],
            'Low': [99, 100],
            'Close': [99.5, 100.5]
        })
        atrx = indicators_service.calculate_atrx(short_df)
        assert np.isnan(atrx)

    def test_calculate_atrx_zero_atr(self, indicators_service):
        """Test ATRX when ATR is zero."""
        # Create data where TR is zero
        constant_df = pd.DataFrame({
            'High': [100] * 60,
            'Low': [100] * 60,
            'Close': [100] * 60
        })
        atrx = indicators_service.calculate_atrx(constant_df)
        assert np.isnan(atrx)

    def test_calculate_atrx_invalid_smoothing(self, indicators_service, sample_ohlcv_data):
        """Test ATRX with invalid smoothing."""
        with pytest.raises(ValueError):
            indicators_service.calculate_atrx(sample_ohlcv_data, smoothing='INVALID')

    def test_calculate_atrx_different_price(self, indicators_service, sample_ohlcv_data):
        """Test ATRX using different price field."""
        atrx_close = indicators_service.calculate_atrx(sample_ohlcv_data, price='Close')
        atrx_open = indicators_service.calculate_atrx(sample_ohlcv_data, price='Open')
        assert atrx_close != atrx_open  # Should differ unless prices are identical

    def test_calculate_sma_happy_path(self, indicators_service, sample_ohlcv_data):
        """Test SMA calculation with sufficient data."""
        period = 10
        sma = indicators_service.calculate_sma(sample_ohlcv_data, period)
        assert isinstance(sma, float)
        assert not np.isnan(sma)
        # Verify against manual calculation
        expected = sample_ohlcv_data['Close'].tail(period).mean()
        assert abs(sma - expected) < 1e-6

    def test_calculate_sma_insufficient_data(self, indicators_service):
        """Test SMA with insufficient data."""
        period = 10
        short_df = pd.DataFrame({
            'Close': [100] * 5
        })
        sma = indicators_service.calculate_sma(short_df, period)
        assert np.isnan(sma)

    def test_calculate_sma_empty_data(self, indicators_service):
        """Test SMA with empty dataframe."""
        period = 10
        empty_df = pd.DataFrame()
        sma = indicators_service.calculate_sma(empty_df, period)
        assert np.isnan(sma)

    def test_calculate_sma_invalid_price_column(self, indicators_service, sample_ohlcv_data):
        """Test SMA with invalid price column."""
        period = 10
        sma = indicators_service.calculate_sma(sample_ohlcv_data, period, price='Invalid')
        assert np.isnan(sma)
