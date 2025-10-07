import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
from datetime import datetime, timedelta
from core.types_registry import AssetSymbol, AssetClass
from services.polygon_service import fetch_bars


@pytest.fixture
def sample_symbol():
    return AssetSymbol("AAPL", AssetClass.STOCKS)


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_success(mock_client, sample_symbol):
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "results": [
            {
                "t": 1609459200000,  # 2021-01-01
                "o": 100.0,
                "h": 105.0,
                "l": 95.0,
                "c": 102.0,
                "v": 1000000,
                "vw": 101.5,
                "n": 1000
            },
            {
                "t": 1609545600000,  # 2021-01-02
                "o": 102.0,
                "h": 108.0,
                "l": 98.0,
                "c": 105.0,
                "v": 1100000,
                "otc": True
            }
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get

    params = {"multiplier": 1, "timespan": "day", "lookback_period": "2 days"}
    bars = await fetch_bars(sample_symbol, "test_api_key", params)

    assert len(bars) == 2
    assert bars[0]["timestamp"] == 1609459200000
    assert bars[0]["open"] == 100.0
    assert bars[0]["high"] == 105.0
    assert bars[0]["low"] == 95.0
    assert bars[0]["close"] == 102.0
    assert bars[0]["volume"] == 1000000
    assert bars[0]["vw"] == 101.5
    assert bars[0]["n"] == 1000
    assert "otc" not in bars[0]

    assert bars[1]["otc"] is True


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_api_error(mock_client, sample_symbol):
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get

    params = {"multiplier": 1, "timespan": "day", "lookback_period": "1 day"}
    with pytest.raises(ValueError, match="Failed to fetch bars: HTTP 401"):
        await fetch_bars(sample_symbol, "invalid_key", params)


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_polygon_error_status(mock_client, sample_symbol):
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "ERROR",
        "error": "Invalid ticker"
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get

    params = {"multiplier": 1, "timespan": "day", "lookback_period": "1 day"}
    with pytest.raises(ValueError, match="Polygon API error: Invalid ticker"):
        await fetch_bars(sample_symbol, "test_key", params)


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_delayed_status(mock_client, sample_symbol):
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "DELAYED",
        "results": [{"t": 1609459200000, "o": 100.0, "h": 105.0, "l": 95.0, "c": 102.0, "v": 1000000}]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get

    params = {"multiplier": 1, "timespan": "day", "lookback_period": "1 day"}
    bars = await fetch_bars(sample_symbol, "test_key", params)
    assert len(bars) == 1  # DELAYED status should still work


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_empty_results(mock_client, sample_symbol):
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "results": []
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get

    params = {"multiplier": 1, "timespan": "day", "lookback_period": "1 day"}
    bars = await fetch_bars(sample_symbol, "test_key", params)
    assert bars == []


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_cancellation(mock_client, sample_symbol):
    mock_get = AsyncMock(side_effect=asyncio.CancelledError())
    mock_client.return_value.__aenter__.return_value.get = mock_get

    params = {"multiplier": 1, "timespan": "day", "lookback_period": "1 day"}
    with pytest.raises(asyncio.CancelledError):
        await fetch_bars(sample_symbol, "test_key", params)


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_lookback_period_parsing(mock_client, sample_symbol):
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{"t": 1609459200000, "o": 100.0, "h": 105.0, "l": 95.0, "c": 102.0, "v": 1000000}]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get

    # Test different lookback periods
    test_cases = [
        ("1 day", timedelta(days=1)),
        ("2 weeks", timedelta(weeks=2)),
        ("6 months", timedelta(days=180)),  # 6 * 30
        ("1 year", timedelta(days=365)),
    ]

    for lookback_period, expected_delta in test_cases:
        params = {"multiplier": 1, "timespan": "day", "lookback_period": lookback_period}
        bars = await fetch_bars(sample_symbol, "test_key", params)
        assert len(bars) == 1

        # Verify the URL construction includes the correct date range
        call_args = mock_get.call_args
        url = call_args[0][0]
        query_params = call_args[1]["params"]

        # Should contain from_date and to_date in query params
        assert "apiKey" in query_params
        assert query_params["apiKey"] == "test_key"


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_custom_params(mock_client, sample_symbol):
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{"t": 1609459200000, "o": 100.0, "h": 105.0, "l": 95.0, "c": 102.0, "v": 1000000}]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get

    params = {
        "multiplier": 5,
        "timespan": "minute",
        "lookback_period": "1 day",
        "adjusted": False,
        "sort": "desc",
        "limit": 100
    }
    bars = await fetch_bars(sample_symbol, "test_key", params)

    # Verify parameters are passed correctly
    call_args = mock_get.call_args
    url = call_args[0][0]
    query_params = call_args[1]["params"]

    assert "5/minute" in url
    assert query_params["adjusted"] == "false"
    assert query_params["sort"] == "desc"
    assert query_params["limit"] == 100
    assert query_params["apiKey"] == "test_key"


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_invalid_lookback_format(mock_client, sample_symbol):
    params = {"multiplier": 1, "timespan": "day", "lookback_period": "invalid"}
    with pytest.raises(ValueError, match="Invalid lookback period format"):
        await fetch_bars(sample_symbol, "test_key", params)


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_bars_unsupported_time_unit(mock_client, sample_symbol):
    params = {"multiplier": 1, "timespan": "day", "lookback_period": "1 hour"}
    with pytest.raises(ValueError, match="Unsupported time unit: hour"):
        await fetch_bars(sample_symbol, "test_key", params)
