import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import pandas as pd
from nodes.core.io.asset_symbol_input_node import AssetSymbol
from core.types_registry import AssetClass, Provider, InstrumentType, NodeExecutionError, NodeValidationError
from nodes.custom.polygon.polygon_custom_bars_node import PolygonCustomBarsNode


@pytest.fixture
def polygon_custom_bars_node():
    return PolygonCustomBarsNode(id=1, params={
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
         patch("services.polygon_service.datetime") as mock_datetime:

        mock_datetime.now.return_value = mock_now.to_pydatetime()

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_api_key"):
            result = await polygon_custom_bars_node.execute({
                "symbol": sample_symbol
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
    """Test error when API key is not found in vault."""
    with patch("core.api_key_vault.APIKeyVault.get", return_value=None):
        with pytest.raises(NodeExecutionError) as exc_info:
            await polygon_custom_bars_node.execute({
                "symbol": sample_symbol
            })
        assert isinstance(exc_info.value.original_exc, ValueError)
        assert str(exc_info.value.original_exc) == "Polygon API key not found in vault"


@pytest.mark.asyncio
async def test_execute_missing_symbol(polygon_custom_bars_node):
    """Test error when symbol input is missing."""
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_api_key"):
        with pytest.raises(NodeValidationError, match="Missing or invalid inputs"):
            await polygon_custom_bars_node.execute({
                # No symbol provided should trigger BaseNode validation error
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

        with patch("core.api_key_vault.APIKeyVault.get", return_value="invalid_key"):
            with pytest.raises(NodeExecutionError) as exc_info:
                await polygon_custom_bars_node.execute({
                    "symbol": sample_symbol
                })
            assert isinstance(exc_info.value.original_exc, ValueError)
            assert str(exc_info.value.original_exc) == "Failed to fetch bars: HTTP 403"


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

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_api_key"):
            with pytest.raises(NodeExecutionError) as exc_info:
                await polygon_custom_bars_node.execute({
                    "symbol": sample_symbol
                })
            assert isinstance(exc_info.value.original_exc, ValueError)
            assert str(exc_info.value.original_exc) == "Polygon API error: Invalid ticker"


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

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_api_key"):
            result = await polygon_custom_bars_node.execute({
                "symbol": sample_symbol
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

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_api_key"):
            result = await polygon_custom_bars_node.execute({
                "symbol": sample_symbol
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

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_api_key"):
            result = await polygon_custom_bars_node.execute({
                "symbol": crypto_symbol,
            })

        # Verify ticker formatting for crypto
        call_args = mock_client.get.call_args
        assert "BTCUSDT" in call_args[0][0]  # Should use formatted string
