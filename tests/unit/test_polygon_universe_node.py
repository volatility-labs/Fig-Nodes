import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from nodes.custom.polygon.polygon_universe_node import PolygonUniverse
from core.types_registry import AssetClass, NodeExecutionError


@pytest.fixture
def polygon_node():
    return PolygonUniverse(id=1, params={"market": "crypto"})


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_fetch_symbols(mock_client, mock_vault_get, mock_market_open, polygon_node):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True  # Market is open
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [{
            "ticker": "X:BTCUSD",
            "todaysChangePerc": 5.0,
            "day": {"v": 1000, "c": 50000},
            "prevDay": {"v": 800, "c": 48000},
            "primary_exchange": "Crypto"
        }]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    result = await polygon_node.execute({})
    symbols = result["symbols"]
    assert len(symbols) == 1
    assert symbols[0].ticker == "BTC"
    assert symbols[0].quote_currency == "USD"
    assert symbols[0].asset_class == AssetClass.CRYPTO
    assert symbols[0].metadata.get("original_ticker") == "X:BTCUSD"


@pytest.mark.asyncio
@patch("core.api_key_vault.APIKeyVault.get")
async def test_polygon_no_api_key(mock_vault_get, polygon_node):
    mock_vault_get.return_value = None
    with pytest.raises(NodeExecutionError) as exc_info:
        await polygon_node.execute({})
    # BaseNode wraps execution errors; verify original exception and message
    assert isinstance(exc_info.value.original_exc, ValueError)
    assert "POLYGON_API_KEY is required but not set in vault" in str(exc_info.value.original_exc)


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_single_request(mock_client, mock_vault_get, mock_market_open, polygon_node):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": 1.0, "day": {"v": 100, "c": 50000}, "prevDay": {"v": 90, "c": 49000}},
            {"ticker": "X:ETHUSD", "todaysChangePerc": 2.0, "day": {"v": 200, "c": 3000}, "prevDay": {"v": 180, "c": 2950}}
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    polygon_node._execute_inputs = {"api_key": "test_key"}
    symbols = await polygon_node._fetch_symbols()
    assert len(symbols) == 2


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_filtering_min_change_perc(mock_client, mock_vault_get, mock_market_open):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True  # Market open so change filtering applies
    node = PolygonUniverse(id=1, params={"market": "crypto", "min_change_perc": 2.0})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 50000}, "prevDay": {"v": 900, "c": 49500}},
            {"ticker": "X:ETHUSD", "todaysChangePerc": 3.0, "day": {"v": 1000, "c": 3000}, "prevDay": {"v": 900, "c": 2910}}
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    assert tickers == {"ETH"}


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_filtering_max_change_perc(mock_client, mock_vault_get, mock_market_open):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "crypto", "max_change_perc": 2.0})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 50000}, "prevDay": {"v": 900, "c": 49500}},
            {"ticker": "X:ETHUSD", "todaysChangePerc": 3.0, "day": {"v": 1000, "c": 3000}, "prevDay": {"v": 900, "c": 2910}}
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    assert tickers == {"BTC"}


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_filtering_change_perc_range_positive(mock_client, mock_vault_get, mock_market_open):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "crypto", "min_change_perc": 1.5, "max_change_perc": 2.5})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 50000}, "prevDay": {"v": 900, "c": 49500}},
            {"ticker": "X:ETHUSD", "todaysChangePerc": 2.0, "day": {"v": 1000, "c": 3000}, "prevDay": {"v": 900, "c": 2940}},
            {"ticker": "X:SOLUSD", "todaysChangePerc": 3.0, "day": {"v": 1000, "c": 150}, "prevDay": {"v": 900, "c": 145}}
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    assert tickers == {"ETH"}


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_filtering_change_perc_range_negative(mock_client, mock_vault_get, mock_market_open):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "crypto", "min_change_perc": -5.0, "max_change_perc": -1.0})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": -6.0, "day": {"v": 1000, "c": 48000}, "prevDay": {"v": 900, "c": 51060}},  # below min
            {"ticker": "X:ETHUSD", "todaysChangePerc": -3.0, "day": {"v": 1000, "c": 2800}, "prevDay": {"v": 900, "c": 2887}},   # within
            {"ticker": "X:SOLUSD", "todaysChangePerc": 2.0, "day": {"v": 1000, "c": 160}, "prevDay": {"v": 900, "c": 157}}     # positive
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    assert tickers == {"ETH"}


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_invalid_change_range_raises(mock_client, mock_vault_get, mock_market_open):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "crypto", "min_change_perc": 5.0, "max_change_perc": 2.0})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tickers": []}
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    with pytest.raises(ValueError, match="min_change_perc cannot be greater than max_change_perc"):
        await node._fetch_symbols()


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_missing_todays_change_defaults_zero(mock_client, mock_vault_get, mock_market_open):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "crypto", "min_change_perc": 0})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    # One ticker missing todaysChangePerc – treated as 0 and should pass min=0
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "day": {"v": 1000, "c": 50000}, "prevDay": {"v": 900, "c": 49500}},
            {"ticker": "X:ETHUSD", "todaysChangePerc": -0.1, "day": {"v": 1000, "c": 3000}, "prevDay": {"v": 900, "c": 3003}},
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    assert tickers == {"BTC"}


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_market_variants_and_otc_flags(mock_client, mock_vault_get, mock_market_open):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    # Stocks
    node_stocks = PolygonUniverse(id=1, params={"market": "stocks"})
    # Indices
    node_indices = PolygonUniverse(id=2, params={"market": "indices"})
    # FX
    node_fx = PolygonUniverse(id=3, params={"market": "fx"})
    # OTC flag passed via stocks
    node_otc = PolygonUniverse(id=4, params={"market": "stocks", "include_otc": True})

    # Mock responses for different endpoints
    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [{"ticker": "AAPL", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 150}, "prevDay": {"v": 900, "c": 148}}]
    }

    types_response = MagicMock()
    types_response.status_code = 200
    types_response.raise_for_status = MagicMock()
    types_response.json.return_value = {
        "results": [
            {"code": "ETF", "description": "Exchange Traded Fund"},
        ]
    }

    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "results": [
            {"ticker": "AAPL", "type": "CS", "market": "stocks"},
        ],
        "next_url": None
    }

    async def mock_get_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "tickers/types" in url:
            return types_response
        elif "reference/tickers" in url and "tickers/" not in url:
            return metadata_response
        else:
            return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    # Stocks
    node_stocks._execute_inputs = {"api_key": "test_key"}
    symbols = await node_stocks._fetch_symbols()
    assert len(symbols) == 1 and symbols[0].asset_class == AssetClass.STOCKS

    # Indices (now defaults to STOCKS since INDICES is not in the mapping)
    node_indices._execute_inputs = {"api_key": "test_key"}
    symbols = await node_indices._fetch_symbols()
    assert len(symbols) == 1 and symbols[0].asset_class == AssetClass.STOCKS

    # FX
    snapshot_response.json.return_value = {"tickers": [{"ticker": "C:EURUSD", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 1.05}, "prevDay": {"v": 900, "c": 1.04}}]}
    node_fx._execute_inputs = {"api_key": "test_key"}
    symbols = await node_fx._fetch_symbols()
    assert len(symbols) == 1 and symbols[0].ticker == "EUR" and symbols[0].quote_currency == "USD" and symbols[0].asset_class == AssetClass.STOCKS

    # Include OTC flag
    snapshot_response.json.return_value = {"tickers": [{"ticker": "AAPL", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 150}, "prevDay": {"v": 900, "c": 148}}]}
    node_otc._execute_inputs = {"api_key": "test_key"}
    _ = await node_otc._fetch_symbols()
    # Check if include_otc is in params for snapshot call
    # Find the snapshot call in the call list
    snapshot_calls = [
        call for call in mock_get.call_args_list
        if call[0] and len(call[0]) > 0 and "snapshot" in str(call[0][0])
    ]
    assert len(snapshot_calls) > 0
    # Check last snapshot call (should be from node_otc)
    last_snapshot_call = snapshot_calls[-1]
    if len(last_snapshot_call) > 1 and isinstance(last_snapshot_call[1], dict):
        assert last_snapshot_call[1].get("params", {}).get("include_otc") is True


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_api_error_propagates(mock_client, mock_vault_get, mock_market_open, polygon_node):
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"
    mock_response.reason_phrase = "Too Many Requests"
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    polygon_node._execute_inputs = {"api_key": "test_key"}
    with pytest.raises(ValueError, match="Failed to fetch snapshot: 429 - Rate limit exceeded"):
        await polygon_node._fetch_symbols()


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_closed_market_uses_prevday_and_skips_change_filter(mock_client, mock_vault_get, mock_market_open):
    """When market is closed, use prevDay data and skip change percentage filtering"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = False  # Market is closed
    node = PolygonUniverse(id=1, params={"market": "crypto", "min_change_perc": 2.0})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": 1.0, "day": {"v": 0, "c": 50000}, "prevDay": {"v": 1000, "c": 49000}},
            {"ticker": "X:ETHUSD", "todaysChangePerc": 3.0, "day": {"v": 0, "c": 3000}, "prevDay": {"v": 800, "c": 2850}}
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    # Both should pass because change filtering is skipped when market is closed
    assert len(symbols) == 2
    tickers = {s.ticker for s in symbols}
    assert tickers == {"BTC", "ETH"}


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_zero_volume_filtered_out(mock_client, mock_vault_get, mock_market_open):
    """Tickers with zero volume in both day and prevDay should be filtered out"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "crypto"})
    mock_get = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": 1.0, "day": {"v": 0, "c": 50000}, "prevDay": {"v": 0, "c": 49500}},
            {"ticker": "X:ETHUSD", "todaysChangePerc": 2.0, "day": {"v": 1000, "c": 3000}, "prevDay": {"v": 900, "c": 2940}}
        ]
    }
    mock_get.return_value = mock_response
    mock_client.return_value.__aenter__.return_value.get = mock_get
    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    assert len(symbols) == 1
    assert symbols[0].ticker == "ETH"


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_exclude_etfs_filters_out_etfs(mock_client, mock_vault_get, mock_market_open):
    """Test that exclude_etfs=True filters out ETFs and keeps only stocks"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "stocks", "exclude_etfs": True})

    # Mock snapshot response with one stock and one ETF
    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [
            {"ticker": "AAPL", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 150}, "prevDay": {"v": 900, "c": 148}},
            {"ticker": "SPY", "todaysChangePerc": 0.5, "day": {"v": 2000, "c": 400}, "prevDay": {"v": 1900, "c": 398}},
        ]
    }

    # Mock ticker types endpoint - returns ETF type codes
    types_response = MagicMock()
    types_response.status_code = 200
    types_response.raise_for_status = MagicMock()
    types_response.json.return_value = {
        "results": [
            {"code": "ETF", "description": "Exchange Traded Fund"},
            {"code": "ETN", "description": "Exchange Traded Note"},
            {"code": "ETP", "description": "Exchange Traded Product"},
        ]
    }

    # Mock ticker metadata endpoint - returns tickers with their types
    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "results": [
            {"ticker": "AAPL", "type": "CS", "market": "stocks"},
            {"ticker": "SPY", "type": "ETF", "market": "stocks"},
        ],
        "next_url": None
    }

    async def mock_get_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "tickers/types" in url:
            return types_response
        elif "reference/tickers" in url and "tickers/" not in url:
            # Bulk ticker metadata endpoint
            return metadata_response
        else:
            # Snapshot endpoint
            return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    # Should only have AAPL (stock), not SPY (ETF)
    assert tickers == {"AAPL"}
    assert len(symbols) == 1


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_exclude_etfs_false_keeps_only_etfs(mock_client, mock_vault_get, mock_market_open):
    """Test that exclude_etfs=False keeps only ETFs"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "stocks", "exclude_etfs": False})

    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [
            {"ticker": "AAPL", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 150}, "prevDay": {"v": 900, "c": 148}},
            {"ticker": "SPY", "todaysChangePerc": 0.5, "day": {"v": 2000, "c": 400}, "prevDay": {"v": 1900, "c": 398}},
        ]
    }

    types_response = MagicMock()
    types_response.status_code = 200
    types_response.raise_for_status = MagicMock()
    types_response.json.return_value = {
        "results": [
            {"code": "ETF", "description": "Exchange Traded Fund"},
        ]
    }

    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "results": [
            {"ticker": "AAPL", "type": "CS", "market": "stocks"},
            {"ticker": "SPY", "type": "ETF", "market": "stocks"},
        ],
        "next_url": None
    }

    async def mock_get_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "tickers/types" in url:
            return types_response
        elif "reference/tickers" in url and "tickers/" not in url:
            return metadata_response
        else:
            return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    # Should only have SPY (ETF), not AAPL (stock)
    assert tickers == {"SPY"}
    assert len(symbols) == 1


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_etf_check_api_error_defaults_to_not_etf(mock_client, mock_vault_get, mock_market_open):
    """Test that ticker types API errors default to fallback ETF detection"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "stocks", "exclude_etfs": True})

    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [
            {"ticker": "AAPL", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 150}, "prevDay": {"v": 900, "c": 148}},
            {"ticker": "SPY", "todaysChangePerc": 0.5, "day": {"v": 2000, "c": 400}, "prevDay": {"v": 1900, "c": 398}},
        ]
    }

    # Simulate API error for ticker types endpoint
    types_error_response = MagicMock()
    types_error_response.status_code = 500
    types_error_response.raise_for_status.side_effect = Exception("API Error")

    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "results": [
            {"ticker": "AAPL", "type": "CS", "market": "stocks"},
            {"ticker": "SPY", "type": "ETF", "market": "stocks"},
        ],
        "next_url": None
    }

    async def mock_get_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "tickers/types" in url:
            return types_error_response
        elif "reference/tickers" in url and "tickers/" not in url:
            return metadata_response
        else:
            return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    # Should keep AAPL because fallback ETF detection should still work
    assert len(symbols) == 1
    assert symbols[0].ticker == "AAPL"


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_etf_check_not_applied_to_crypto(mock_client, mock_vault_get, mock_market_open):
    """Test that ETF check is not applied to crypto market"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "crypto", "exclude_etfs": True})

    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [
            {"ticker": "X:BTCUSD", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 50000}, "prevDay": {"v": 900, "c": 49500}},
        ]
    }

    async def mock_get_side_effect(*args, **kwargs):
        # For crypto, only snapshot endpoint should be called
        return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    # Should have BTC, ETF check should not be called
    assert len(symbols) == 1
    assert symbols[0].ticker == "BTC"
    # Verify only snapshot endpoint was called (no ticker types or metadata endpoints)
    assert mock_get.call_count == 1


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_etf_check_with_etp_market_type(mock_client, mock_vault_get, mock_market_open):
    """Test that ETF check correctly identifies ETFs with market='etp'"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "stocks", "exclude_etfs": True})

    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [
            {"ticker": "QQQ", "todaysChangePerc": 0.3, "day": {"v": 1500, "c": 350}, "prevDay": {"v": 1400, "c": 349}},
        ]
    }

    types_response = MagicMock()
    types_response.status_code = 200
    types_response.raise_for_status = MagicMock()
    types_response.json.return_value = {
        "results": [
            {"code": "ETF", "description": "Exchange Traded Fund"},
        ]
    }

    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "results": [
            {"ticker": "QQQ", "type": "ETF", "market": "etp"},
        ],
        "next_url": None
    }

    async def mock_get_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "tickers/types" in url:
            return types_response
        elif "reference/tickers" in url and "tickers/" not in url:
            return metadata_response
        else:
            return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    # Should filter out QQQ because it's an ETF (market='etp')
    assert len(symbols) == 0


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_etf_check_multiple_tickers(mock_client, mock_vault_get, mock_market_open):
    """Test ETF filtering with multiple tickers (mix of ETFs and stocks)"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "stocks", "exclude_etfs": True})

    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [
            {"ticker": "AAPL", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 150}, "prevDay": {"v": 900, "c": 148}},
            {"ticker": "MSFT", "todaysChangePerc": 0.8, "day": {"v": 1200, "c": 300}, "prevDay": {"v": 1100, "c": 298}},
            {"ticker": "SPY", "todaysChangePerc": 0.5, "day": {"v": 2000, "c": 400}, "prevDay": {"v": 1900, "c": 398}},
            {"ticker": "QQQ", "todaysChangePerc": 0.3, "day": {"v": 1500, "c": 350}, "prevDay": {"v": 1400, "c": 349}},
        ]
    }

    types_response = MagicMock()
    types_response.status_code = 200
    types_response.raise_for_status = MagicMock()
    types_response.json.return_value = {
        "results": [
            {"code": "ETF", "description": "Exchange Traded Fund"},
        ]
    }

    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "results": [
            {"ticker": "AAPL", "type": "CS", "market": "stocks"},
            {"ticker": "MSFT", "type": "CS", "market": "stocks"},
            {"ticker": "SPY", "type": "ETF", "market": "stocks"},
            {"ticker": "QQQ", "type": "ETF", "market": "stocks"},
        ],
        "next_url": None
    }

    async def mock_get_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "tickers/types" in url:
            return types_response
        elif "reference/tickers" in url and "tickers/" not in url:
            return metadata_response
        else:
            return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    tickers = {s.ticker for s in symbols}
    # Should only have stocks (AAPL, MSFT), not ETFs (SPY, QQQ)
    assert tickers == {"AAPL", "MSFT"}
    assert len(symbols) == 2


@pytest.mark.asyncio
@patch("nodes.custom.polygon.polygon_universe_node.is_us_market_open")
@patch("core.api_key_vault.APIKeyVault.get")
@patch("httpx.AsyncClient")
async def test_polygon_etf_check_otc_market(mock_client, mock_vault_get, mock_market_open):
    """Test that ETF check is applied to OTC market"""
    mock_vault_get.return_value = "test_key"
    mock_market_open.return_value = True
    node = PolygonUniverse(id=1, params={"market": "otc", "exclude_etfs": True})

    snapshot_response = MagicMock()
    snapshot_response.status_code = 200
    snapshot_response.json.return_value = {
        "tickers": [
            {"ticker": "OTCTEST", "todaysChangePerc": 1.0, "day": {"v": 1000, "c": 5}, "prevDay": {"v": 900, "c": 4.95}},
        ]
    }

    types_response = MagicMock()
    types_response.status_code = 200
    types_response.raise_for_status = MagicMock()
    types_response.json.return_value = {
        "results": [
            {"code": "ETF", "description": "Exchange Traded Fund"},
        ]
    }

    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "results": [
            {"ticker": "OTCTEST", "type": "CS", "market": "otc"},
        ],
        "next_url": None
    }

    async def mock_get_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "tickers/types" in url:
            return types_response
        elif "reference/tickers" in url and "tickers/" not in url:
            return metadata_response
        else:
            return snapshot_response

    mock_get = AsyncMock(side_effect=mock_get_side_effect)
    mock_client.return_value.__aenter__.return_value.get = mock_get

    node._execute_inputs = {"api_key": "test_key"}
    symbols = await node._fetch_symbols()
    # Should pass because OTC market applies ETF check
    assert len(symbols) == 1
    assert symbols[0].ticker == "OTCTEST"


