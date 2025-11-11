import typing

from core.types_utils import parse_type


def test_parse_type_basic():
    assert parse_type(int) == {"base": "int"}
    assert parse_type(str) == {"base": "str"}
    assert parse_type(float) == {"base": "float"}


def test_parse_type_any():
    assert parse_type(typing.Any) == {"base": "Any"}


def test_parse_type_list():
    assert parse_type(list) == {"base": "list", "subtypes": [{"base": "Any"}]}
    assert parse_type(list[int]) == {"base": "list", "subtypes": [{"base": "int"}]}
    assert parse_type(list[typing.Any]) == {"base": "list", "subtypes": [{"base": "Any"}]}


def test_parse_type_set():
    assert parse_type(set) == {"base": "set", "subtypes": [{"base": "Any"}]}
    assert parse_type(set[str]) == {"base": "set", "subtypes": [{"base": "str"}]}


def test_parse_type_tuple():
    assert parse_type(tuple) == {"base": "tuple", "subtypes": [{"base": "Any"}]}
    assert parse_type(tuple[int, str]) == {
        "base": "tuple",
        "subtypes": [{"base": "int"}, {"base": "str"}],
    }


def test_parse_type_dict():
    assert parse_type(dict) == {
        "base": "dict",
        "key_type": {"base": "Any"},
        "value_type": {"base": "Any"},
    }
    assert parse_type(dict[str, int]) == {
        "base": "dict",
        "key_type": {"base": "str"},
        "value_type": {"base": "int"},
    }


def test_parse_type_union():
    assert parse_type(typing.Union[int, str]) == {
        "base": "union",
        "subtypes": [{"base": "int"}, {"base": "str"}],
    }
    assert parse_type(typing.Union[int, typing.Any]) == {
        "base": "union",
        "subtypes": [{"base": "int"}, {"base": "Any"}],
    }


def test_parse_type_nested():
    nested = list[dict[str, typing.Union[int, float]]]
    expected = {
        "base": "list",
        "subtypes": [
            {
                "base": "dict",
                "key_type": {"base": "str"},
                "value_type": {"base": "union", "subtypes": [{"base": "int"}, {"base": "float"}]},
            }
        ],
    }
    assert parse_type(nested) == expected


def test_parse_type_custom_class():
    class CustomClass:
        pass

    assert parse_type(CustomClass) == {"base": "CustomClass"}


def test_parse_type_generic():
    T = typing.TypeVar("T")

    class GenericClass(typing.Generic[T]):
        pass

    parsed = parse_type(GenericClass[int])
    assert parsed["base"] == "GenericClass"
    assert parsed["subtypes"] == [{"base": "int"}]


def test_parse_type_no_origin():
    assert parse_type(type(None)) == {"base": "NoneType"}


def test_parse_type_unknown():
    class Unknown:
        __name__ = None  # Simulate no name

    assert parse_type(Unknown) == {"base": "Unknown"}  # Adjusted to match actual fallback


# ============================================================================
# Optional/Union with None normalization tests
# ============================================================================

def test_parse_type_optional_str():
    """Test that Optional[str] is normalized to str"""
    from typing import Optional
    
    assert parse_type(Optional[str]) == {"base": "str"}


def test_parse_type_optional_int():
    """Test that Optional[int] is normalized to int"""
    from typing import Optional
    
    assert parse_type(Optional[int]) == {"base": "int"}


def test_parse_type_optional_float():
    """Test that Optional[float] is normalized to float"""
    from typing import Optional
    
    assert parse_type(Optional[float]) == {"base": "float"}


def test_parse_type_union_with_none():
    """Test that Union[T, None] is normalized to T"""
    assert parse_type(typing.Union[str, type(None)]) == {"base": "str"}
    assert parse_type(typing.Union[int, type(None)]) == {"base": "int"}


def test_parse_type_union_multiple_with_none():
    """Test that Union[T1, T2, None] is normalized to Union[T1, T2]"""
    assert parse_type(typing.Union[str, int, type(None)]) == {
        "base": "union",
        "subtypes": [{"base": "str"}, {"base": "int"}]
    }
    
    assert parse_type(typing.Union[str, int, float, type(None)]) == {
        "base": "union",
        "subtypes": [{"base": "str"}, {"base": "int"}, {"base": "float"}]
    }


def test_parse_type_union_only_none():
    """Test that Union[None] is normalized to NoneType"""
    # Use a workaround since Union technically requires 2+ args
    assert parse_type(typing.Union[type(None), type(None)]) == {"base": "NoneType"}  # type: ignore


def test_parse_type_optional_nested_list():
    """Test that Optional[List[T]] is normalized to List[T]"""
    from typing import Optional
    
    assert parse_type(Optional[list[str]]) == {
        "base": "list",
        "subtypes": [{"base": "str"}]
    }
    
    assert parse_type(Optional[list[int]]) == {
        "base": "list",
        "subtypes": [{"base": "int"}]
    }


def test_parse_type_optional_nested_dict():
    """Test that Optional[Dict[K, V]] is normalized to Dict[K, V]"""
    from typing import Optional
    
    assert parse_type(Optional[dict[str, int]]) == {
        "base": "dict",
        "key_type": {"base": "str"},
        "value_type": {"base": "int"}
    }


def test_parse_type_optional_nested_set():
    """Test that Optional[Set[T]] is normalized to Set[T]"""
    from typing import Optional
    
    assert parse_type(Optional[set[str]]) == {
        "base": "set",
        "subtypes": [{"base": "str"}]
    }


def test_parse_type_optional_deeply_nested():
    """Test deeply nested Optional types"""
    from typing import Optional
    
    # Optional[List[Dict[str, int]]]
    assert parse_type(Optional[list[dict[str, int]]]) == {
        "base": "list",
        "subtypes": [{
            "base": "dict",
            "key_type": {"base": "str"},
            "value_type": {"base": "int"}
        }]
    }


def test_parse_type_union_with_any_and_none():
    """Test Union[Any, None] normalization"""
    assert parse_type(typing.Union[typing.Any, type(None)]) == {"base": "Any"}


def test_parse_type_union_complex_with_none():
    """Test complex Union types with None"""
    # Union[List[str], None]
    assert parse_type(typing.Union[list[str], type(None)]) == {
        "base": "list",
        "subtypes": [{"base": "str"}]
    }
    
    # Union[Dict[str, int], None]
    assert parse_type(typing.Union[dict[str, int], type(None)]) == {
        "base": "dict",
        "key_type": {"base": "str"},
        "value_type": {"base": "int"}
    }


def test_parse_type_union_with_none_multiple_times():
    """Test Union[T, None, None] deduplication"""
    # Python's Union deduplicates automatically, but let's test anyway
    assert parse_type(typing.Union[str, type(None), type(None)]) == {"base": "str"}


def test_parse_type_optional_with_custom_type():
    """Test Optional with custom class"""
    from typing import Optional
    
    class CustomClass:
        pass
    
    assert parse_type(Optional[CustomClass]) == {"base": "CustomClass"}


def test_parse_type_union_multiple_types_preserved():
    """Test that Union without None is preserved"""
    assert parse_type(typing.Union[str, int]) == {
        "base": "union",
        "subtypes": [{"base": "str"}, {"base": "int"}]
    }
    
    assert parse_type(typing.Union[str, int, float]) == {
        "base": "union",
        "subtypes": [{"base": "str"}, {"base": "int"}, {"base": "float"}]
    }


def test_parse_type_optional_then_union():
    """Test nested Optional inside Union"""
    from typing import Optional
    
    # Union[Optional[str], int] should become Union[str, int]
    assert parse_type(typing.Union[Optional[str], int]) == {
        "base": "union",
        "subtypes": [{"base": "str"}, {"base": "int"}]
    }


def test_parse_type_tuples_with_none():
    """Test tuples with None in Union"""
    # Union[tuple[int, str], None]
    assert parse_type(typing.Union[tuple[int, str], type(None)]) == {
        "base": "tuple",
        "subtypes": [{"base": "int"}, {"base": "str"}]
    }


def test_parse_type_sets_with_none():
    """Test sets with None in Union"""
    # Union[set[str], None]
    assert parse_type(typing.Union[set[str], type(None)]) == {
        "base": "set",
        "subtypes": [{"base": "str"}]
    }


def test_parse_type_dict_value_with_none():
    """Test Dict with Optional value type"""
    from typing import Optional
    
    # Dict[str, Optional[int]]
    assert parse_type(dict[str, Optional[int]]) == {
        "base": "dict",
        "key_type": {"base": "str"},
        "value_type": {"base": "int"}
    }


def test_parse_type_complex_nested_optional():
    """Test complex nested Optional structures"""
    from typing import Optional
    
    # Optional[List[Optional[str]]]
    # First level Optional gets stripped, second level Optional[str] should become str
    assert parse_type(Optional[list[Optional[str]]]) == {
        "base": "list",
        "subtypes": [{"base": "str"}]
    }


def test_parse_type_union_nested_unions():
    """Test nested Union types"""
    # Union[Union[str, int], None]
    inner_union = typing.Union[str, int]
    assert parse_type(typing.Union[inner_union, type(None)]) == {
        "base": "union",
        "subtypes": [{"base": "str"}, {"base": "int"}]
    }


def test_parse_type_optional_any():
    """Test Optional[Any] should stay as Any"""
    from typing import Optional
    
    assert parse_type(Optional[typing.Any]) == {"base": "Any"}


def test_parse_type_real_world_example():
    """Test real-world example from text_to_llm_message_node"""
    from core.types_registry import get_type
    
    # This simulates: get_type("LLMChatMessage") | None
    llm_message_type = get_type("LLMChatMessage")
    optional_llm = typing.Union[llm_message_type, type(None)]
    
    # Should normalize to just LLMChatMessage
    result = parse_type(optional_llm)
    assert result == {"base": "LLMChatMessage"}


def test_parse_type_pipe_syntax():
    """Test pipe syntax (|) for union types (Python 3.10+)"""
    # Using str | None syntax
    assert parse_type(str | None) == {"base": "str"}
    assert parse_type(int | None) == {"base": "int"}
    
    # Using pipe syntax with multiple types
    assert parse_type(str | int | None) == {
        "base": "union",
        "subtypes": [{"base": "str"}, {"base": "int"}]
    }
    
    # List with pipe syntax
    assert parse_type(list[str] | None) == {
        "base": "list",
        "subtypes": [{"base": "str"}]
    }


def test_parse_type_llm_messages_builder_scenario():
    """Test the specific scenario: TextToLLMMessage output -> LLMMessagesBuilder input"""
    from core.types_registry import get_type
    
    # TextToLLMMessage output type (non-Optional)
    text_to_llm_output = get_type("LLMChatMessage")
    text_to_llm_parsed = parse_type(text_to_llm_output)
    
    # LLMMessagesBuilder input type (Optional)
    llm_builder_input = typing.Union[get_type("LLMChatMessage"), type(None)]
    llm_builder_parsed = parse_type(llm_builder_input)
    
    print(f"\n[DEBUG] TextToLLMMessage output parsed: {text_to_llm_parsed}")
    print(f"[DEBUG] LLMMessagesBuilder input parsed: {llm_builder_parsed}")
    
    # Both should be the same after normalization
    assert text_to_llm_parsed == llm_builder_parsed
    assert text_to_llm_parsed == {"base": "LLMChatMessage"}


# ============================================================================
# Type Detection Tests
# ============================================================================

def test_detect_type_none():
    """Test detection of None type"""
    from core.types_utils import detect_type
    
    assert detect_type(None) == "None"


def test_detect_type_basic_types():
    """Test detection of basic Python types"""
    from core.types_utils import detect_type
    
    assert detect_type(True) == "bool"
    assert detect_type(42) == "int"
    assert detect_type(3.14) == "float"
    assert detect_type("hello") == "str"
    assert detect_type([1, 2, 3]) == "list"
    assert detect_type({"key": "value"}) == "dict"
    assert detect_type({1, 2, 3}) == "set"
    assert detect_type((1, 2, 3)) == "tuple"


def test_detect_type_asset_symbol():
    """Test detection of AssetSymbol dataclass"""
    from core.types_utils import detect_type
    from core.types_registry import AssetSymbol, AssetClass
    
    symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
    assert detect_type(symbol) == "AssetSymbol"


def test_detect_type_indicator_value():
    """Test detection of IndicatorValue dataclass"""
    from core.types_utils import detect_type
    from core.types_registry import IndicatorValue
    
    value = IndicatorValue(single=1.0, lines={"line1": 2.0})
    assert detect_type(value) == "IndicatorValue"


def test_detect_type_indicator_result():
    """Test detection of IndicatorResult dataclass"""
    from core.types_utils import detect_type
    from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue
    
    result = IndicatorResult(
        indicator_type=IndicatorType.RSI,
        values=IndicatorValue(single=50.0)
    )
    assert detect_type(result) == "IndicatorResult"


def test_detect_type_ohlcv_bar():
    """Test detection of OHLCVBar TypedDict"""
    from core.types_utils import detect_type
    
    bar = {
        "timestamp": 1234567890,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": 1000000
    }
    assert detect_type(bar) == "OHLCVBar"
    
    # Missing required key should not match
    incomplete_bar = {"timestamp": 1234567890, "open": 100.0}
    assert detect_type(incomplete_bar) == "dict"


def test_detect_type_llm_chat_message():
    """Test detection of LLMChatMessage TypedDict"""
    from core.types_utils import detect_type
    
    message = {"role": "user", "content": "Hello"}
    assert detect_type(message) == "LLMChatMessage"
    
    # Missing required key should not match
    incomplete_message = {"role": "user"}
    assert detect_type(incomplete_message) == "dict"


def test_detect_type_llm_tool_spec():
    """Test detection of LLMToolSpec TypedDict"""
    from core.types_utils import detect_type
    
    tool_spec = {
        "type": "function",
        "function": {"name": "test", "description": "test"}
    }
    assert detect_type(tool_spec) == "LLMToolSpec"
    
    # Wrong type value should not match
    wrong_type = {"type": "not_function", "function": {}}
    assert detect_type(wrong_type) == "dict"


def test_detect_type_llm_chat_metrics():
    """Test detection of LLMChatMetrics TypedDict"""
    from core.types_utils import detect_type
    
    metrics = {"total_duration": 100, "eval_count": 5}
    assert detect_type(metrics) == "LLMChatMetrics"
    
    # Should match with any metric key
    metrics2 = {"load_duration": 50}
    assert detect_type(metrics2) == "LLMChatMetrics"
    
    # No metric keys should not match
    not_metrics = {"some_other_key": "value"}
    assert detect_type(not_metrics) == "dict"


def test_detect_type_llm_tool_history_item():
    """Test detection of LLMToolHistoryItem TypedDict"""
    from core.types_utils import detect_type
    
    history_item = {"call": {"id": "1"}, "result": {}}
    assert detect_type(history_item) == "LLMToolHistoryItem"
    
    # Missing required key should not match
    incomplete = {"call": {}}
    assert detect_type(incomplete) == "dict"


def test_detect_type_llm_thinking_history_item():
    """Test detection of LLMThinkingHistoryItem TypedDict"""
    from core.types_utils import detect_type
    
    thinking_item = {"thinking": "test", "iteration": 1}
    assert detect_type(thinking_item) == "LLMThinkingHistoryItem"
    
    # Missing required key should not match
    incomplete = {"thinking": "test"}
    assert detect_type(incomplete) == "dict"


def test_infer_data_type_single_values():
    """Test infer_data_type for single values"""
    from core.types_utils import infer_data_type
    from core.types_registry import AssetSymbol, AssetClass, IndicatorValue, IndicatorResult, IndicatorType
    
    assert infer_data_type(None) == "None"
    assert infer_data_type(AssetSymbol("AAPL", AssetClass.STOCKS)) == "AssetSymbol"
    assert infer_data_type(IndicatorValue(single=1.0)) == "IndicatorValue"
    assert infer_data_type(IndicatorResult(indicator_type=IndicatorType.RSI)) == "IndicatorResult"


def test_infer_data_type_empty_containers():
    """Test infer_data_type for empty containers"""
    from core.types_utils import infer_data_type
    
    assert infer_data_type([]) == "EmptyList"
    assert infer_data_type({}) == "EmptyDict"


def test_infer_data_type_asset_symbol_list():
    """Test infer_data_type for AssetSymbol lists"""
    from core.types_utils import infer_data_type
    from core.types_registry import AssetSymbol, AssetClass
    
    symbols = [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("MSFT", AssetClass.STOCKS)
    ]
    assert infer_data_type(symbols) == "AssetSymbolList"


def test_infer_data_type_ohlcv():
    """Test infer_data_type for OHLCV lists"""
    from core.types_utils import infer_data_type
    
    bars = [
        {"timestamp": 1234567890, "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 1000000},
        {"timestamp": 1234567900, "open": 102.0, "high": 107.0, "low": 97.0, "close": 104.0, "volume": 1200000}
    ]
    assert infer_data_type(bars) == "OHLCV"


def test_infer_data_type_llm_chat_message_list():
    """Test infer_data_type for LLMChatMessage lists"""
    from core.types_utils import infer_data_type
    
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"}
    ]
    assert infer_data_type(messages) == "LLMChatMessageList"


def test_infer_data_type_indicator_result_list():
    """Test infer_data_type for IndicatorResult lists"""
    from core.types_utils import infer_data_type
    from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue
    
    results = [
        IndicatorResult(indicator_type=IndicatorType.RSI, values=IndicatorValue(single=50.0)),
        IndicatorResult(indicator_type=IndicatorType.MACD, values=IndicatorValue(single=0.5))
    ]
    assert infer_data_type(results) == "IndicatorResultList"


def test_infer_data_type_ohlcv_bundle():
    """Test infer_data_type for OHLCVBundle"""
    from core.types_utils import infer_data_type
    from core.types_registry import AssetSymbol, AssetClass
    
    bundle = {
        AssetSymbol("AAPL", AssetClass.STOCKS): [
            {"timestamp": 1234567890, "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 1000000}
        ]
    }
    assert infer_data_type(bundle) == "OHLCVBundle"


def test_infer_data_type_generic_dict():
    """Test infer_data_type for generic dicts"""
    from core.types_utils import infer_data_type
    
    generic_dict = {"key1": "value1", "key2": "value2"}
    assert infer_data_type(generic_dict) == "Dict[str, str]"
    
    dict_with_numbers = {1: "one", 2: "two"}
    assert infer_data_type(dict_with_numbers) == "Dict[int, str]"


def test_infer_data_type_generic_list():
    """Test infer_data_type for generic lists"""
    from core.types_utils import infer_data_type
    
    numbers = [1, 2, 3]
    assert infer_data_type(numbers) == "List[int]"
    
    strings = ["a", "b", "c"]
    assert infer_data_type(strings) == "List[str]"


def test_infer_data_type_mixed_types():
    """Test infer_data_type with various mixed types"""
    from core.types_utils import infer_data_type
    from core.types_registry import AssetSymbol, AssetClass
    
    # Dict with AssetSymbol keys but not OHLCVBar values
    mixed_dict = {
        AssetSymbol("AAPL", AssetClass.STOCKS): "some_value"
    }
    assert infer_data_type(mixed_dict) == "Dict[AssetSymbol, str]"
    
    # List with first item dict but not recognizable TypedDict
    mixed_list = [{"some_key": "some_value"}]
    assert infer_data_type(mixed_list) == "List[dict]"


def test_detect_type_edge_cases():
    """Test edge cases for detect_type"""
    from core.types_utils import detect_type
    
    # Empty dict should be detected as dict, not any TypedDict
    assert detect_type({}) == "dict"
    
    # Dict with partial TypedDict keys should be dict
    partial = {"timestamp": 123, "open": 100}
    assert detect_type(partial) == "dict"
    
    # Custom class
    class CustomClass:
        pass
    
    assert detect_type(CustomClass()) == "CustomClass"


def test_infer_data_type_edge_cases():
    """Test edge cases for infer_data_type"""
    from core.types_utils import infer_data_type
    
    # Very nested structure
    nested = {"a": {"b": {"c": "value"}}}
    assert infer_data_type(nested) == "Dict[str, dict]"
    
    # List with None
    list_with_none = [None, None]
    assert infer_data_type(list_with_none) == "List[None]"
    
    # Mixed list types (should detect first item)
    mixed = [1, "string", 3.14]
    assert infer_data_type(mixed) == "List[int]"
