import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import pandas as pd
from nodes.core.io.asset_symbol_input_node import AssetSymbol
from core.types_registry import AssetClass, Provider, InstrumentType
from custom_nodes.polygon.polygon_custom_bars_node import PolygonCustomBarsNode


@pytest.fixture
def polygon_custom_bars_node():
    return PolygonCustomBarsNode("polygon_bars_id", {
        "multiplier": 1,
        "timespan": "day",
        "lookback_period": "3 months",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
    })


@pytest.fixture
def sample_symbol():
    return AssetSymbol(
        ticker="AAPL",
        asset_class=AssetClass.STOCKS,
        quote_currency=None,
        provider=Provider.POLYGON,
        instrument_type=InstrumentType.SPOT
    )


@pytest.mark.asyncio
async def test_execute_success(polygon_custom_bars_node, sample_symbol):
    """Test successful execution with valid inputs and API response."""
    # Mock datetime.now() to return a consistent date for testing
    mock_now = pd.Timestamp("2024-01-01")
    # The node approximates months as 30 days: 3 * 30 = 90 days
    expected_from_date = (mock_now - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    expected_to_date = mock_now.strftime("%Y-%m-%d")

    mock_response_data = {
        "status": "OK",
        "results": [
            {
                "o": 150.0,
                "h": 155.0,
                "l": 148.0,
                "c": 152.0,
                "v": 1000000,
                "vw": 151.5,
                "n": 5000,
                "t": 1672531200000  # 2023-01-01
            },
            {
                "o": 152.0,
                "h": 158.0,
                "l": 150.0,
                "c": 155.0,
                "v": 1200000,
                "t": 1672617600000  # 2023-01-02
            }
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_class, \
         patch("custom_nodes.polygon.polygon_custom_bars_node.datetime") as mock_datetime:

        mock_datetime.now.return_value = mock_now.to_pydatetime()

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await polygon_custom_bars_node.execute({
            "symbol": sample_symbol,
            "api_key": "test_api_key"
        })

        assert "ohlcv" in result
        ohlcv_data = result["ohlcv"]
        assert isinstance(ohlcv_data, list)
        assert len(ohlcv_data) == 2
        assert ohlcv_data[0]["open"] == 150.0
        assert ohlcv_data[0]["close"] == 152.0
        assert ohlcv_data[0]["high"] == 155.0
        assert ohlcv_data[0]["low"] == 148.0
        assert ohlcv_data[0]["volume"] == 1000000
        assert ohlcv_data[0]["vw"] == 151.5
        assert ohlcv_data[0]["n"] == 5000
        assert ohlcv_data[0]["timestamp"] == 1672531200000
        assert ohlcv_data[1]["high"] == 158.0

        # Verify API call
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        expected_url = f"https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/{expected_from_date}/{expected_to_date}"
        assert call_args[0][0] == expected_url
        params = call_args[1]["params"]
        assert params["apiKey"] == "test_api_key"
        assert params["adjusted"] == "true"
        assert params["sort"] == "asc"
        assert params["limit"] == 5000


@pytest.mark.asyncio
async def test_execute_missing_api_key(polygon_custom_bars_node, sample_symbol):
    """Test error when API key input is missing."""
    with pytest.raises(ValueError, match="Polygon API key input is required"):
        await polygon_custom_bars_node.execute({
            "symbol": sample_symbol,
            "api_key": None
        })


@pytest.mark.asyncio
async def test_execute_missing_symbol(polygon_custom_bars_node):
    """Test error when symbol input is missing."""
    with pytest.raises(ValueError, match="Symbol input is required"):
        await polygon_custom_bars_node.execute({
            "symbol": None,
            "api_key": "test_key"
        })


@pytest.mark.asyncio
async def test_execute_api_error(polygon_custom_bars_node, sample_symbol):
    """Test handling of API errors."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_client.get.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        with pytest.raises(ValueError, match="Failed to fetch bars: HTTP 403"):
            await polygon_custom_bars_node.execute({
                "symbol": sample_symbol,
                "api_key": "invalid_key"
            })


@pytest.mark.asyncio
async def test_execute_api_status_error(polygon_custom_bars_node, sample_symbol):
    """Test handling of Polygon API status errors."""
    mock_response_data = {
        "status": "ERROR",
        "error": "Invalid ticker"
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        with pytest.raises(ValueError, match="Polygon API error: Invalid ticker"):
            await polygon_custom_bars_node.execute({
                "symbol": sample_symbol,
                "api_key": "test_key"
            })


@pytest.mark.asyncio
async def test_execute_empty_results(polygon_custom_bars_node, sample_symbol):
    """Test handling of empty results from API."""
    mock_response_data = {
        "status": "OK",
        "results": []
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await polygon_custom_bars_node.execute({
            "symbol": sample_symbol,
            "api_key": "test_key"
        })

        assert "ohlcv" in result
        ohlcv_data = result["ohlcv"]
        assert isinstance(ohlcv_data, list)
        assert len(ohlcv_data) == 0


@pytest.mark.asyncio
async def test_execute_different_parameters(polygon_custom_bars_node, sample_symbol):
    """Test with different parameter combinations."""
    polygon_custom_bars_node.params.update({
        "multiplier": 5,
        "timespan": "minute",
        "adjusted": False,
        "sort": "desc",
        "limit": 100
    })

    mock_response_data = {
        "status": "OK",
        "results": [{
            "o": 100.0,
            "h": 101.0,
            "l": 99.0,
            "c": 100.5,
            "v": 1000,
            "t": 1672531200000
        }]
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await polygon_custom_bars_node.execute({
            "symbol": sample_symbol,
            "api_key": "test_key"
        })

        # Verify API call with updated params
        call_args = mock_client.get.call_args
        assert "5/minute" in call_args[0][0]
        params = call_args[1]["params"]
        assert params["adjusted"] == "false"
        assert params["sort"] == "desc"
        assert params["limit"] == 100


@pytest.mark.asyncio
async def test_execute_crypto_symbol(polygon_custom_bars_node):
    """Test with crypto symbol formatting."""
    crypto_symbol = AssetSymbol(
        ticker="BTC",
        asset_class=AssetClass.CRYPTO,
        quote_currency="USDT",
        provider=Provider.BINANCE,
        instrument_type=InstrumentType.PERPETUAL
    )

    mock_response_data = {
        "status": "OK",
        "results": [{
            "o": 30000.0,
            "h": 31000.0,
            "l": 29500.0,
            "c": 30500.0,
            "v": 100.0,
            "t": 1672531200000
        }]
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await polygon_custom_bars_node.execute({
            "symbol": crypto_symbol,
            "api_key": "test_key"
        })

        # Verify ticker formatting for crypto
        call_args = mock_client.get.call_args
        assert "BTCUSDT" in call_args[0][0]  # Should use formatted string
