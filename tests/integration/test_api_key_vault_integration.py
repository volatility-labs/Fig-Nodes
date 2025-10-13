import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from core.api_key_vault import APIKeyVault
from nodes.custom.polygon.polygon_universe_node import PolygonUniverseNode


@pytest.mark.asyncio
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_universe_with_vault(mock_client, mock_vault_get):
    """Integration test for PolygonUniverseNode using API key vault."""
    mock_vault_get.return_value = "test_polygon_key"

    node = PolygonUniverseNode("test_id", {"market": "crypto"})

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [{
            "ticker": "X:BTCUSD",
            "todaysChangePerc": 1.0,
            "day": {"v": 1000, "c": 50000}
        }]
    }
    mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

    result = await node.execute({})
    symbols = result["symbols"]
    assert len(symbols) == 1
    assert symbols[0].ticker == "BTC"


@pytest.mark.asyncio
@patch("core.api_key_vault.APIKeyVault.get")
async def test_missing_key_error(mock_vault_get):
    """Test that missing key raises error."""
    mock_vault_get.return_value = None

    node = PolygonUniverseNode("test_id", {})
    with pytest.raises(ValueError, match="POLYGON_API_KEY is required but not set in vault"):
        await node.execute({})
