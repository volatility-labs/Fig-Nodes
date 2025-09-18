import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nodes.core.llm.ollama_model_selector_node import OllamaModelSelectorNode

@pytest.fixture
def selector_node():
    return OllamaModelSelectorNode(id=1, params={"host": "http://test:11434", "selected": ""})

@pytest.mark.asyncio
async def test_model_listing(selector_node):
    mock_response = {"models": [{"name": "model1"}, {"name": "model2"}]}
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_resp_obj = MagicMock()
        mock_resp_obj.json.return_value = mock_response
        mock_resp_obj.raise_for_status.return_value = None
        
        mock_client.get = AsyncMock()
        mock_client.get.return_value = mock_resp_obj
        
        mock_aenter = AsyncMock()
        mock_aenter.return_value = mock_client
        mock_client_class.return_value.__aenter__ = mock_aenter
        mock_client_class.return_value.__aexit__ = AsyncMock()
        
        result = await selector_node.execute({})
        assert result["models"] == ["model1", "model2"]
        assert result["model"] == "model1"  # Auto-select first

@pytest.mark.asyncio
async def test_selected_model(selector_node):
    selector_node.params["selected"] = "model2"
    mock_response = {"models": [{"name": "model1"}, {"name": "model2"}]}
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_resp_obj = MagicMock()
        mock_resp_obj.json.return_value = mock_response
        mock_resp_obj.raise_for_status.return_value = None
        
        mock_client.get = AsyncMock()
        mock_client.get.return_value = mock_resp_obj
        
        mock_aenter = AsyncMock()
        mock_aenter.return_value = mock_client
        mock_client_class.return_value.__aenter__ = mock_aenter
        mock_client_class.return_value.__aexit__ = AsyncMock()
        
        result = await selector_node.execute({})
        assert result["model"] == "model2"

@pytest.mark.asyncio
async def test_no_models_error(selector_node):
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_resp_obj = MagicMock()
        mock_resp_obj.json.return_value = {"models": []}
        mock_resp_obj.raise_for_status.return_value = None
        
        mock_client.get = AsyncMock()
        mock_client.get.return_value = mock_resp_obj
        
        mock_aenter = AsyncMock()
        mock_aenter.return_value = mock_client
        mock_client_class.return_value.__aenter__ = mock_aenter
        mock_client_class.return_value.__aexit__ = AsyncMock()
        
        with pytest.raises(ValueError, match="No local Ollama models found. Pull one via 'ollama pull <model>'"):
            await selector_node.execute({})

@pytest.mark.asyncio
async def test_http_error_handling(selector_node):
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_resp_obj = MagicMock()
        mock_resp_obj.raise_for_status.side_effect = Exception("HTTP Error")
        
        mock_client.get = AsyncMock()
        mock_client.get.return_value = mock_resp_obj
        
        mock_aenter = AsyncMock()
        mock_aenter.return_value = mock_client
        mock_client_class.return_value.__aenter__ = mock_aenter
        mock_client_class.return_value.__aexit__ = AsyncMock()
        
        with pytest.raises(ValueError, match="No local Ollama models found. Pull one via 'ollama pull <model>'"):
            await selector_node.execute({})
        # Since exception leads to models_list = [], it raises the no models error
