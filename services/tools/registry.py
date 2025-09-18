from typing import Any, Awaitable, Callable, Dict, List, Optional
from abc import ABC, abstractmethod
import asyncio
import json


# A lightweight registry for LLM tool schemas and async handlers.
# Handlers should be async callables: async def handler(arguments: Dict[str, Any], context: Dict[str, Any]) -> Any

_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {}
_TOOL_HANDLERS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Any]]] = {}


def register_tool_schema(name: str, schema: Dict[str, Any]) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("Tool schema name must be a non-empty string")
    if not isinstance(schema, dict) or not schema:
        raise ValueError("Tool schema must be a non-empty dict")
    _TOOL_SCHEMAS[name] = schema


def get_tool_schema(name: str) -> Optional[Dict[str, Any]]:
    return _TOOL_SCHEMAS.get(name)


def list_tool_names() -> List[str]:
    return sorted(_TOOL_SCHEMAS.keys())


def list_tool_schemas() -> List[Dict[str, Any]]:
    return [
        _TOOL_SCHEMAS[name]
        for name in list_tool_names()
        if name in _TOOL_SCHEMAS
    ]


def register_tool_handler(
    name: str,
    handler: Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Any]],
) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("Tool handler name must be a non-empty string")
    if not callable(handler):
        raise ValueError("Tool handler must be callable")
    _TOOL_HANDLERS[name] = handler


def get_tool_handler(name: str) -> Optional[Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Any]]]:
    return _TOOL_HANDLERS.get(name)


class ToolHandler(ABC):
    """
    Standard interface for implementing tool providers.

    Implementations must define a stable tool name (function.name), return a JSON schema
    describing the tool, and provide an async execute method that accepts arguments
    and a context dict.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        raise NotImplementedError


def register_tool_object(tool: ToolHandler) -> None:
    """
    Registers both schema and handler from a ToolHandler implementation.
    """
    register_tool_schema(tool.name, tool.schema())
    # Bind the object's execute method as the handler
    async def _bound_handler(arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        return await tool.execute(arguments, context)
    register_tool_handler(tool.name, _bound_handler)


# Default web_search tool schema
_DEFAULT_WEB_SEARCH_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web and return concise findings with sources.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                "time_range": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year", "all"],
                    "default": "month",
                },
                "lang": {
                    "type": "string",
                    "description": "Language code like en, fr",
                    "default": "en",
                },
            },
            "required": ["query"],
        },
    },
}


async def _default_unimplemented_handler(arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
    # Provide a deterministic, JSON-serializable error payload for unconfigured tools
    return {
        "error": "handler_not_configured",
        "message": "No handler is registered for this tool on the server.",
        "arguments_echo": arguments,
    }


# Register defaults at import time
register_tool_schema("web_search", _DEFAULT_WEB_SEARCH_SCHEMA)
register_tool_handler("web_search", _default_unimplemented_handler)

# Try to import provider-backed implementations which may override defaults
try:
    # Registers real handlers if available
    from services.tools import web_search as _ws  # noqa: F401
except Exception:
    # Keep defaults if provider module is unavailable
    pass


