
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from hl_bot_v2.services.scoring_service import ScoringService

@pytest.fixture
def mock_indicators_service():
    service = MagicMock()
    service.compute_indicators.return_value = {
        'hurst': 0.6,
        'acceleration': 0.05,
        'adx': 25,
        'volume_ratio': 1.2,
        'res_pct': 10.0,
        'sup_pct': 2.0
    }
    return service

@pytest.mark.parametrize("indicators, expected_score", [
    ({'hurst': 0.5, 'acceleration': 0.0, 'adx': 20, 'volume_ratio': 1.0, 'res_pct': 5.0, 'sup_pct': 1.0}, 3.325),  # rr=5
    ({'hurst': 0.6, 'acceleration': 0.05, 'adx': 25, 'volume_ratio': 1.2, 'res_pct': 10.0, 'sup_pct': 2.0}, 4.5175),  # rr=5
    ({}, 0.0),
    # Edge: Division by zero in RR
    ({'res_pct': 10.0, 'sup_pct': 0.0}, 2.175),  # RR=0
    # Edge: Negative values
    ({'hurst': -0.5, 'acceleration': -0.05, 'adx': -25, 'volume_ratio': -1.2, 'res_pct': -10.0, 'sup_pct': -2.0}, -3.2525),  # Negative score
    # Edge: All zeros
    ({'hurst': 0, 'acceleration': 0, 'adx': 0, 'volume_ratio': 0, 'res_pct': 0, 'sup_pct': 1}, -0.1),  # RR=0
])
def test_compute_score(mock_indicators_service, indicators, expected_score):
    scoring = ScoringService(mock_indicators_service)
    score = scoring.compute_score(indicators)
    assert pytest.approx(score) == expected_score

def test_update_score(mock_indicators_service):
    scoring = ScoringService(mock_indicators_service)
    df = pd.DataFrame()  # Dummy df
    scoring.update_score('BTC', '1h', df)
    assert 'BTC' in scoring._score_cache
    assert len(scoring._score_cache['BTC']['scores']) == 1
    assert 'score' in scoring._score_cache['BTC']['scores'][0]

def test_is_warmed_up(mock_indicators_service):
    scoring = ScoringService(mock_indicators_service)
    now = datetime.now(timezone.utc)
    scoring._score_cache['BTC'] = {
        'scores': [
            {'score': 80, 'timestamp': now - timedelta(minutes=1), 'passes': True},
            {'score': 75, 'timestamp': now - timedelta(minutes=2), 'passes': True},
            {'score': 85, 'timestamp': now - timedelta(minutes=3), 'passes': True},
        ],
        'last_update': now
    }
    assert scoring.is_warmed_up('BTC')
    scoring._score_cache['ETH'] = {
        'scores': [
            {'score': 60, 'timestamp': now - timedelta(minutes=1), 'passes': False},
            {'score': 65, 'timestamp': now - timedelta(minutes=2), 'passes': False},
        ],
        'last_update': now
    }
    assert not scoring.is_warmed_up('ETH')

def test_get_top_tradable(mock_indicators_service):
    scoring = ScoringService(mock_indicators_service)
    scoring._score_cache = {
        'BTC': {'scores': [{'score': 85, 'timestamp': datetime.now(timezone.utc), 'passes': True}] * 3, 'last_update': datetime.now(timezone.utc)},
        'ETH': {'scores': [{'score': 75, 'timestamp': datetime.now(timezone.utc), 'passes': True}] * 3, 'last_update': datetime.now(timezone.utc)},
        'SOL': {'scores': [{'score': 90, 'timestamp': datetime.now(timezone.utc), 'passes': True}] * 3, 'last_update': datetime.now(timezone.utc)},
        'XRP': {'scores': [{'score': 80, 'timestamp': datetime.now(timezone.utc), 'passes': True}] * 2, 'last_update': datetime.now(timezone.utc)},  # Not warmed up
    }
    top = scoring.get_top_tradable(3)
    assert len(top) == 3
    assert top[0]['symbol'] == 'SOL'
    assert top[1]['symbol'] == 'BTC'
    assert top[2]['symbol'] == 'ETH' 

@pytest.mark.asyncio
async def test_warmup_timestamp_edges(mock_indicators_service):
    scoring = ScoringService(mock_indicators_service)
    now = datetime.now(timezone.utc)
    scoring._score_cache['BTC'] = {
        'scores': [
            {'score': 80, 'timestamp': now - timedelta(minutes=14), 'passes': True},
            {'score': 75, 'timestamp': now - timedelta(minutes=15), 'passes': True},  # Exactly at boundary
            {'score': 85, 'timestamp': now - timedelta(minutes=16), 'passes': True},  # Outside
        ],
        'last_update': now
    }
    assert not scoring.is_warmed_up('BTC')  # Only 1 within window 