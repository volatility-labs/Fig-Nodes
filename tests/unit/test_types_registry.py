import pytest
from typing import Dict, Any, Type
from core.types_registry import AssetClass, InstrumentType, Provider, AssetSymbol, TYPE_REGISTRY, get_type, register_type, register_asset_class, register_provider
from enum import auto

@pytest.fixture
def sample_asset_symbol():
    return AssetSymbol(ticker="BTC", asset_class=AssetClass.CRYPTO, quote_currency="USDT", provider=Provider.BINANCE, exchange="binance", instrument_type=InstrumentType.PERPETUAL, metadata={"key": "value"})

def test_asset_symbol_str(sample_asset_symbol):
    assert str(sample_asset_symbol) == "BTCUSDT"

def test_asset_symbol_from_string_crypto():
    sym = AssetSymbol.from_string("BTCUSDT", AssetClass.CRYPTO, Provider.BINANCE, {"extra": "data"})
    assert sym.ticker == "BTC"
    assert sym.quote_currency == "USDT"
    assert sym.provider == Provider.BINANCE
    assert sym.metadata == {"extra": "data"}

def test_asset_symbol_from_string_non_crypto():
    sym = AssetSymbol.from_string("AAPL", AssetClass.STOCKS)
    assert sym.ticker == "AAPL"
    assert sym.asset_class == AssetClass.STOCKS
    assert sym.quote_currency is None

def test_asset_symbol_to_dict(sample_asset_symbol):
    expected = {
        "ticker": "BTC",
        "asset_class": AssetClass.CRYPTO,
        "quote_currency": "USDT",
        "provider": "BINANCE",
        "instrument_type": "PERPETUAL",
        "metadata": {"key": "value"}
    }
    assert sample_asset_symbol.to_dict() == expected

def test_asset_symbol_hash(sample_asset_symbol):
    sym2 = AssetSymbol(ticker="BTC", asset_class=AssetClass.CRYPTO, quote_currency="USDT", provider=Provider.BINANCE, exchange="binance", instrument_type=InstrumentType.PERPETUAL, metadata={"key": "value"})
    assert hash(sample_asset_symbol) == hash(sym2)
    sym3 = AssetSymbol(ticker="ETH", asset_class=AssetClass.CRYPTO)
    assert hash(sample_asset_symbol) != hash(sym3)

def test_get_type_existing():
    assert get_type("AssetSymbol") == AssetSymbol

def test_get_type_unknown():
    with pytest.raises(ValueError, match="Unknown type: UnknownType"):
        get_type("UnknownType")

def test_register_type_new():
    class TestType:
        pass
    register_type("TestType", TestType)
    assert get_type("TestType") == TestType

def test_register_type_duplicate():
    with pytest.raises(ValueError, match="Type DuplicateType already registered"):
        register_type("DuplicateType", int)
        register_type("DuplicateType", int)

def test_register_asset_class_new():
    new_class = register_asset_class("commodities")
    assert new_class == "COMMODITIES"
    assert hasattr(AssetClass, "COMMODITIES")
    assert AssetClass.COMMODITIES == "COMMODITIES"  # Assuming str values

def test_register_asset_class_existing():
    existing = register_asset_class("crypto")
    assert existing == AssetClass.CRYPTO

def test_register_provider_new():
    new_provider = register_provider("new_exchange")
    assert new_provider.name == "NEW_EXCHANGE"
    assert hasattr(Provider, "NEW_EXCHANGE")
    assert Provider.NEW_EXCHANGE == auto()  # Enum value

def test_register_provider_existing():
    existing = register_provider("binance")
    assert existing == Provider.BINANCE
