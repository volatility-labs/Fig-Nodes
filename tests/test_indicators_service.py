
import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from hl_bot_v2.indicators.indicators_service import IndicatorsService

@pytest.fixture
def sample_df():
    dates = pd.date_range('2023-01-01', periods=100, freq='h')
    data = {
        'Open': np.random.rand(100) * 100,
        'High': np.random.rand(100) * 100 + 100,
        'Low': np.random.rand(100) * 100,
        'Close': np.random.rand(100) * 100 + 50,
        'Volume': np.random.rand(100) * 1000
    }
    return pd.DataFrame(data, index=dates)

def test_compute_indicators(sample_df):
    service = IndicatorsService()
    indicators = service.compute_indicators(sample_df, '1h')
    assert isinstance(indicators, dict)
    assert len(indicators) > 0
    assert 'evwma' in indicators
    assert 'hurst' in indicators

def test_compute_indicators_empty_df():
    service = IndicatorsService()
    empty_df = pd.DataFrame()
    indicators = service.compute_indicators(empty_df, '1h')
    assert indicators == {}

def test_calculate_evwma(sample_df):
    service = IndicatorsService()
    evwma = service.calculate_evwma(sample_df['Close'], sample_df['Volume'], 325)
    assert isinstance(evwma, float)
    assert 0 < evwma < 200  # Reasonable range based on sample

def test_calculate_evwma_zero_volume(sample_df):
    service = IndicatorsService()
    zero_vol = sample_df.copy()
    zero_vol['Volume'] = 0
    evwma = service.calculate_evwma(zero_vol['Close'], zero_vol['Volume'], 325)
    assert np.isnan(evwma) or evwma == zero_vol['Close'].iloc[-1]  # Depending on handling

def test_is_impulse_bullish_insufficient_data():
    service = IndicatorsService()
    small_df = pd.DataFrame({'Close': [100, 101]})
    assert not service.is_impulse_bullish(small_df)

# Add similar tests for other calculate_ methods, mocking if necessary 