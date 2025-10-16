import pytest
import os
import json
import tempfile
import unittest.mock
from datetime import datetime
from nodes.core.io.save_output_node import SaveOutputNode
from core.types_registry import AssetSymbol, AssetClass, InstrumentType, NodeValidationError


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for testing file operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def save_node(temp_output_dir):
    """Create a SaveOutputNode with temp directory."""
    node = SaveOutputNode(id=1, params={})
    # Override the output directory for testing
    import unittest.mock
    with unittest.mock.patch('os.path.dirname') as mock_dirname:
        mock_dirname.return_value = temp_output_dir
        with unittest.mock.patch('os.makedirs'):
            yield node


@pytest.mark.asyncio
async def test_save_string_data(save_node, temp_output_dir):
    """Test saving string data."""
    test_data = "Hello, World!"

    # Mock the path operations to use temp directory
    with unittest.mock.patch('os.path.dirname') as mock_dirname, \
         unittest.mock.patch('os.makedirs') as mock_makedirs, \
         unittest.mock.patch('builtins.open', unittest.mock.mock_open()) as mock_open, \
         unittest.mock.patch('os.path.exists') as mock_exists:

        mock_dirname.return_value = temp_output_dir
        mock_makedirs.return_value = None
        mock_exists.return_value = False

        result = await save_node.execute({"data": test_data})

        # Verify the file was opened for writing
        mock_open.assert_called_once()
        filepath = mock_open.call_args[0][0]

        # Verify the data was written
        mock_open().write.assert_called()

        # Check that filepath is returned
        assert "filepath" in result
        assert result["filepath"].endswith(".json")


@pytest.mark.asyncio
async def test_save_asset_symbol(save_node, temp_output_dir):
    """Test saving AssetSymbol data."""
    symbol = AssetSymbol(
        ticker="BTC",
        asset_class=AssetClass.CRYPTO,
        quote_currency="USDT",
        instrument_type=InstrumentType.PERPETUAL
    )

    with unittest.mock.patch('os.path.dirname') as mock_dirname, \
         unittest.mock.patch('os.makedirs') as mock_makedirs, \
         unittest.mock.patch('builtins.open', unittest.mock.mock_open()) as mock_open, \
         unittest.mock.patch('os.path.exists') as mock_exists:

        mock_dirname.return_value = temp_output_dir
        mock_makedirs.return_value = None
        mock_exists.return_value = False

        result = await save_node.execute({"data": symbol})

        # Verify file operations
        mock_open.assert_called_once()
        mock_open().write.assert_called()

        # Verify filepath returned
        assert "filepath" in result


@pytest.mark.asyncio
async def test_save_list_data(save_node, temp_output_dir):
    """Test saving list data."""
    test_data = ["item1", "item2", "item3"]

    with unittest.mock.patch('os.path.dirname') as mock_dirname, \
         unittest.mock.patch('os.makedirs') as mock_makedirs, \
         unittest.mock.patch('builtins.open', unittest.mock.mock_open()) as mock_open, \
         unittest.mock.patch('os.path.exists') as mock_exists:

        mock_dirname.return_value = temp_output_dir
        mock_makedirs.return_value = None
        mock_exists.return_value = False

        result = await save_node.execute({"data": test_data})

        mock_open.assert_called_once()
        mock_open().write.assert_called()
        assert "filepath" in result


@pytest.mark.asyncio
async def test_filename_generation(save_node):
    """Test automatic filename generation."""
    test_data = "test data"

    # Test with string data
    filename = save_node._generate_filename("", test_data)
    assert filename.startswith("text_")
    assert filename.endswith(".json")
    assert len(filename) > 20  # Should include timestamp and UUID

    # Test with AssetSymbol
    symbol = AssetSymbol(ticker="BTC", asset_class=AssetClass.CRYPTO)
    filename = save_node._generate_filename("", symbol)
    assert filename.startswith("assetsymbol_")
    assert filename.endswith(".json")


@pytest.mark.asyncio
async def test_custom_filename(save_node, temp_output_dir):
    """Test using custom filename."""
    test_data = "test data"
    custom_filename = "my_custom_file"

    save_node.params["filename"] = custom_filename

    with unittest.mock.patch('os.path.dirname') as mock_dirname, \
         unittest.mock.patch('os.makedirs') as mock_makedirs, \
         unittest.mock.patch('builtins.open', unittest.mock.mock_open()) as mock_open, \
         unittest.mock.patch('os.path.exists') as mock_exists:

        mock_dirname.return_value = temp_output_dir
        mock_makedirs.return_value = None
        mock_exists.return_value = False

        result = await save_node.execute({"data": test_data})

        # Check that the custom filename was used
        filepath = mock_open.call_args[0][0]
        assert custom_filename + ".json" in filepath


@pytest.mark.asyncio
async def test_no_data_error(save_node):
    """Test error when no data is provided."""
    with pytest.raises(NodeValidationError, match="Missing or invalid inputs"):
        await save_node.execute({})


@pytest.mark.asyncio
async def test_auto_increment_filename(save_node, temp_output_dir):
    """Test auto-incrementing filename when file exists and overwrite=False."""
    test_data = "test data"
    base_filename = "existing_file"
    save_node.params["filename"] = base_filename
    save_node.params["overwrite"] = False

    with unittest.mock.patch('os.path.dirname') as mock_dirname, \
         unittest.mock.patch('os.makedirs') as mock_makedirs, \
         unittest.mock.patch('builtins.open', unittest.mock.mock_open()) as mock_open, \
         unittest.mock.patch('os.path.exists') as mock_exists:

        mock_dirname.return_value = temp_output_dir
        mock_makedirs.return_value = None

        # Simulate first file exists, second doesn't
        def exists_side_effect(path):
            if 'existing_file.json' in path:
                return True
            if 'existing_file_001.json' in path:
                return False
            return False

        mock_exists.side_effect = exists_side_effect

        result = await save_node.execute({"data": test_data})

        # Verify opened the incremented file
        filepath = mock_open.call_args[0][0]
        assert 'existing_file_001.json' in filepath
        assert result["filepath"] == filepath


@pytest.mark.asyncio
async def test_serialize_asset_symbol(save_node):
    """Test AssetSymbol serialization."""
    symbol = AssetSymbol(
        ticker="BTC",
        asset_class=AssetClass.CRYPTO,
        quote_currency="USDT",
        instrument_type=InstrumentType.SPOT
    )

    serialized = save_node._serialize_value(symbol)

    assert serialized["__type__"] == "AssetSymbol"
    assert "data" in serialized
    data = serialized["data"]
    assert data["ticker"] == "BTC"
    assert data["asset_class"] == "CRYPTO"
    assert data["quote_currency"] == "USDT"
    assert data["instrument_type"] == "SPOT"


@pytest.mark.asyncio
async def test_serialize_list(save_node):
    """Test list serialization."""
    test_list = ["a", "b", 123]

    serialized = save_node._serialize_value(test_list)

    assert serialized["__type__"] == "list"
    assert "items" in serialized
    assert len(serialized["items"]) == 3
    assert serialized["items"][0] == {"__type__": "str", "value": "a"}
    assert serialized["items"][1] == {"__type__": "str", "value": "b"}
    assert serialized["items"][2] == {"__type__": "int", "value": 123}


@pytest.mark.asyncio
async def test_serialize_dict(save_node):
    """Test dict serialization."""
    test_dict = {"key1": "value1", "key2": 42}

    serialized = save_node._serialize_value(test_dict)

    assert serialized["__type__"] == "dict"
    assert "data" in serialized
    data = serialized["data"]
    assert data["key1"] == {"__type__": "str", "value": "value1"}
    assert data["key2"] == {"__type__": "int", "value": 42}


@pytest.mark.asyncio
async def test_ohlcv_bar_detection(save_node):
    """Test OHLCV bar detection."""
    ohlcv_bar = {
        "timestamp": 1640995200000,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": 1000.0
    }

    assert save_node._is_ohlcv_bar(ohlcv_bar)

    # Missing required field
    incomplete_bar = {"timestamp": 123, "open": 100}
    assert not save_node._is_ohlcv_bar(incomplete_bar)


@pytest.mark.asyncio
async def test_llm_chat_message_detection(save_node):
    """Test LLM chat message detection."""
    message = {"role": "user", "content": "Hello"}

    assert save_node._is_llm_chat_message(message)

    # Missing required field
    incomplete = {"role": "user"}
    assert not save_node._is_llm_chat_message(incomplete)
