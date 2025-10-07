import pytest
from typing import Dict, Any, Type
from core.types_registry import AssetClass, InstrumentType, Provider, AssetSymbol, TYPE_REGISTRY, get_type, register_type, register_asset_class, register_provider, register_indicator_type, IndicatorType, LLMChatMessage
import enum
from enum import auto
import logging

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
    register_type("DuplicateType", int)
    with pytest.warns(UserWarning, match="Type DuplicateType already registered"):
        register_type("DuplicateType", str)

def test_register_asset_class_new():
    new_class = register_asset_class("FOREX")
    assert hasattr(AssetClass, "FOREX")
    assert getattr(AssetClass, "FOREX") == "FOREX"

def test_register_asset_class_existing():
    existing = register_asset_class("crypto")
    assert existing == AssetClass.CRYPTO

def test_register_provider_new():
    new_provider = register_provider("COINBASE")
    assert hasattr(Provider, "COINBASE")
    assert new_provider.name == "COINBASE"
    assert new_provider == enum.auto()  # Test sentinel equality

def test_register_provider_existing():
    existing = register_provider("binance")
    assert existing == Provider.BINANCE

def test_register_indicator_type_new():
    new_type = register_indicator_type("STOCH")
    assert hasattr(IndicatorType, "STOCH")
    assert new_type.name == "STOCH"

def test_union_type_registration():
    from typing import Union
    register_type("UnionTest", Union[str, int])
    union_type = get_type("UnionTest")
    assert union_type == Union[str, int]  # Basic registration

    # Test serialization
    from core.types_utils import parse_type
    parsed = parse_type(Union[str, int])
    assert parsed == {"base": "union", "subtypes": [{"base": "str"}, {"base": "int"}]}

def test_union_in_node_inputs():
    from typing import Union
    from nodes.base.base_node import BaseNode
    from core.types_utils import parse_type

    class TestNode(BaseNode):
        inputs = {"union_input": Union[str, LLMChatMessage]}

    parsed_inputs = {k: parse_type(v) for k, v in TestNode.inputs.items()}
    assert parsed_inputs["union_input"] == {"base": "union", "subtypes": [{"base": "str"}, {"base": "LLMChatMessage"}]}

def test_register_type_duplicate_warning():
    register_type("TestType", str)
    with pytest.warns(UserWarning, match="already registered"):
        register_type("TestType", int)  # Overwrite

# Add tests for AssetSymbol
def test_asset_symbol_str_non_crypto(sample_asset_symbol):
    sym = AssetSymbol("AAPL", AssetClass.STOCKS)
    assert str(sym) == "AAPL"

def test_asset_symbol_from_string_with_metadata():
    sym = AssetSymbol.from_string("ETHUSDT", AssetClass.CRYPTO, Provider.BINANCE, {"exchange": "binance"})
    assert sym.ticker == "ETH"
    assert sym.quote_currency == "USDT"
    assert sym.metadata == {"exchange": "binance"}

def test_asset_symbol_hash_equality():
    sym1 = AssetSymbol("BTC", AssetClass.CRYPTO, "USDT")
    sym2 = AssetSymbol("BTC", AssetClass.CRYPTO, "USDT")
    assert hash(sym1) == hash(sym2)
    assert sym1 == sym2  # Assuming __eq__ is implemented via frozen dataclass

# Test sentinel for Provider
def test_provider_sentinel_equality():
    p1 = register_provider("TEST1")
    p2 = enum.auto()
    assert p1 == p2

# Test AssetSymbol hashability with nested metadata
def test_asset_symbol_hash_with_nested_metadata():
    sym = AssetSymbol(
        ticker="BTC",
        asset_class=AssetClass.CRYPTO,
        metadata={"nested": {"dict": {1: 2}, "list": [3, 4]}}
    )
    # Should not raise TypeError: unhashable type
    hash(sym)
    # Also test in a set
    s = {sym}
    assert sym in s
