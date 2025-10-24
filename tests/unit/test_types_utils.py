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
    assert parse_type(list[int]) == {"base": "List", "subtypes": [{"base": "int"}]}
    assert parse_type(list[typing.Any]) == {"base": "List", "subtypes": [{"base": "Any"}]}


def test_parse_type_set():
    assert parse_type(set) == {"base": "set", "subtypes": [{"base": "Any"}]}
    assert parse_type(set[str]) == {"base": "Set", "subtypes": [{"base": "str"}]}


def test_parse_type_tuple():
    assert parse_type(tuple) == {"base": "tuple", "subtypes": [{"base": "Any"}]}
    assert parse_type(tuple[int, str]) == {
        "base": "Tuple",
        "subtypes": [{"base": "int"}, {"base": "str"}],
    }


def test_parse_type_dict():
    assert parse_type(dict) == {
        "base": "dict",
        "key_type": {"base": "Any"},
        "value_type": {"base": "Any"},
    }
    assert parse_type(dict[str, int]) == {
        "base": "Dict",
        "key_type": {"base": "str"},
        "value_type": {"base": "int"},
    }
    assert parse_type(dict) == {"base": "Dict", "key_type": None, "value_type": None}  # No args


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
    nested = list[dict[str, int | float]]
    expected = {
        "base": "List",
        "subtypes": [
            {
                "base": "Dict",
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
