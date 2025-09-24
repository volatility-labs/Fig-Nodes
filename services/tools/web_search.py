from typing import Any, Dict, List
import os
import asyncio
import json

import httpx

from .registry import register_tool_object, ToolHandler, register_tool_factory, get_credential_from_context


async def _tavily_search(query: str, k: int, time_range: str, lang: str, topic: str, timeout_s: int, api_key: str) -> Dict[str, Any]:
    if not api_key:
        return {"error": "missing_api_key", "message": "API key is required"}

    payload = {
        "query": query,
        "max_results": max(1, min(int(k or 5), 10)),
        "search_depth": "basic",
        "time_range": time_range or "month",
        "topic": topic or "general",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post("https://api.tavily.com/search", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return {"error": "provider_error", "message": str(e)}

    items = []
    for it in data.get("results", [])[: payload["max_results"]]:
        items.append({
            "title": it.get("title") or "",
            "url": it.get("url") or it.get("link") or "",
            "snippet": it.get("content") or it.get("snippet") or "",
        })

    return {"results": items, "used_provider": "tavily"}


class WebSearchTool(ToolHandler):
    def __init__(self):
        # No API key required in constructor - will get from context during execution
        pass

    @property
    def name(self) -> str:
        return "web_search"

    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "Search the web and return concise findings with sources.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                        "time_range": {
                            "type": "string",
                            "enum": ["day", "week", "month", "year"],
                            "default": "month",
                        },
                        "topic": {
                            "type": "string",
                            "enum": ["general", "news", "finance"],
                            "default": "general",
                            "description": "Search topic category"
                        },
                        "lang": {"type": "string", "description": "Language code like en, fr", "default": "en"},
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        # Get API key from context
        api_key = get_credential_from_context(context or {}, "tavily_api_key")
        if not api_key:
            return {"error": "missing_api_key", "message": "TAVILY_API_KEY credential not available"}

        query = (arguments or {}).get("query") or ""
        if not isinstance(query, str) or not query.strip():
            return {"error": "invalid_arguments", "message": "'query' is required and must be a string"}

        k = (arguments or {}).get("k") or 5
        time_range = (arguments or {}).get("time_range") or "month"
        lang = (arguments or {}).get("lang") or "en"
        topic = (arguments or {}).get("topic") or "general"
        try:
            timeout_s = int(os.getenv("WEB_SEARCH_TIMEOUT_S", "12"))
        except (ValueError, TypeError):
            timeout_s = 12  # Fallback to default

        return await _tavily_search(query=query, k=k, time_range=time_range, lang=lang, topic=topic, timeout_s=timeout_s, api_key=api_key)


# Register the web search tool factory
def _create_web_search_tool() -> WebSearchTool:
    return WebSearchTool()

register_tool_factory("web_search", _create_web_search_tool)


