import os
from typing import Dict, List, Optional, Set
from dotenv import load_dotenv, find_dotenv, set_key, unset_key
from core.types_registry import NodeRegistry, SerialisableGraph

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
    
    def get_required_for_graph(self, graph: SerialisableGraph, node_registry: NodeRegistry) -> List[str]:
        """Get all required API keys for a given graph.

        Args:
            graph: The serializable graph to analyze
            node_registry: Optional registry of node types. If None, will attempt to import NODE_REGISTRY.
        
        This resolves node classes dynamically from the provided node registry
        to avoid hardcoding specific node types.
        """
        
        required_keys: Set[str] = set()

        for node_data in graph.get('nodes', []):
            node_type = node_data.get('type', '')
            cls = node_registry.get(node_type)
            if not cls:
                continue
            keys = getattr(cls, 'required_keys', []) or []
            for key in keys:
                if isinstance(key, str) and key:
                    required_keys.add(key)
        return list(required_keys)

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
