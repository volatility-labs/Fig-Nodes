import os
from typing import Dict, Any, List, Optional, Set
from dotenv import load_dotenv, find_dotenv, set_key, unset_key


class APIKeyVault:
    """Singleton class for managing API keys stored in environment variables."""

    _instance = None
    _keys: Dict[str, str] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Load environment variables from resolved .env, allowing file to override existing env vars
            load_dotenv(cls._resolve_dotenv_path(), override=True)
            # Cache all keys that start with typical API key prefixes or known keys
            for key, value in os.environ.items():
                if any(prefix in key.upper() for prefix in ['API', 'KEY', 'TOKEN', 'SECRET']) or \
                   key in ['POLYGON_API_KEY', 'TAVILY_API_KEY', 'OLLAMA_API_KEY']:
                    cls._keys[key] = value
        return cls._instance

    def get(self, key: str) -> Optional[str]:
        """Get an API key by name."""
        return self._keys.get(key) or os.getenv(key)

    def set(self, key: str, value: str) -> None:
        """Set an API key and persist it to the .env file."""
        self._keys[key] = value
        dotenv_path = self._resolve_dotenv_path()
        if not dotenv_path:
            # Create .env file relative to cwd only when no test override provided
            dotenv_path = '.env'
        set_key(dotenv_path, key, value)
        # Update environment variable
        os.environ[key] = value

    def get_all(self) -> Dict[str, str]:
        """Get all API keys."""
        # Return a copy of cached keys plus any new ones from environment
        result = self._keys.copy()
        for key, value in os.environ.items():
            if any(prefix in key.upper() for prefix in ['API', 'KEY', 'TOKEN', 'SECRET']) or \
               key in ['POLYGON_API_KEY', 'TAVILY_API_KEY', 'OLLAMA_API_KEY']:
                result[key] = value
        return result

    def get_required_for_graph(self, graph: Dict[str, Any]) -> List[str]:
        """Get all required API keys for a given graph.

        This resolves node classes dynamically from the global NODE_REGISTRY
        to avoid hardcoding specific node types.
        """
        required_keys: Set[str] = set()
        try:
            from core.node_registry import NODE_REGISTRY 
        except Exception:
            NODE_REGISTRY = {}

        for node_data in graph.get('nodes', []):
            node_type = node_data.get('type', '')
            cls = (NODE_REGISTRY or {}).get(node_type)
            if not cls:
                continue
            keys = getattr(cls, 'required_keys', []) or []
            for key in keys:
                if isinstance(key, str) and key:
                    required_keys.add(key)
        return list(required_keys)

    def get_known_key_metadata(self) -> Dict[str, Dict[str, str]]:
        """Return metadata for known API keys for UI tooltips/help.

        Keys may be present or absent in env; this provides descriptions and docs links.
        """
        return {
            'POLYGON_API_KEY': {
                'description': 'API key for Polygon.io market data.',
                'docs_url': 'https://polygon.io'
            },
            'TAVILY_API_KEY': {
                'description': 'API key for Tavily search.',
                'docs_url': 'https://tavily.com'
            },
            'OLLAMA_API_KEY': {
                'description': 'Optional key for Ollama API access.',
                'docs_url': 'https://github.com/ollama/ollama'
            }
        }

    def unset(self, key: str) -> None:
        """Remove an API key from cache, environment, and .env file."""
        if key in self._keys:
            del self._keys[key]
        if key in os.environ:
            del os.environ[key]
        dotenv_path = self._resolve_dotenv_path()
        if dotenv_path:
            unset_key(dotenv_path, key)
        # No error if key didn't exist or .env missing - idempotent

    @staticmethod
    def _resolve_dotenv_path() -> str:
        """Find the .env file using standard dotenv resolution."""
        return find_dotenv()
