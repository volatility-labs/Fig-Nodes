import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from core.api_key_vault import APIKeyVault
from core.types_registry import NodeExecutionError
from nodes.custom.polygon.polygon_universe_node import PolygonUniverse


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.APIKeyVault")
@patch("httpx.AsyncClient")
async def test_polygon_universe_with_vault(mock_client, mock_vault_class):
    """Integration test for PolygonUniverse using API key vault."""
    mock_vault_instance = MagicMock()
    mock_vault_instance.get.return_value = "test_polygon_key"
    mock_vault_class.return_value = mock_vault_instance

    node = PolygonUniverse("test_id", {"market": "crypto"})

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
@patch("nodes.custom.polygon.polygon_universe_node.APIKeyVault")
async def test_missing_key_error(mock_vault_class):
    """Test that missing key raises error."""
    mock_vault_instance = MagicMock()
    mock_vault_instance.get.return_value = None
    mock_vault_class.return_value = mock_vault_instance

    node = PolygonUniverse("test_id", {})
    with pytest.raises(NodeExecutionError, match="Node test_id: Execution failed"):
        await node.execute({})
