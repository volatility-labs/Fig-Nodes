import os
import tempfile
import pytest
from unittest.mock import patch
from core.api_key_vault import APIKeyVault


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("POLYGON_API_KEY=test_polygon_key\n")
        f.write("TAVILY_API_KEY=test_tavily_key\n")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


def test_singleton_behavior():
    """Test that APIKeyVault is a singleton."""
    vault1 = APIKeyVault()
    vault2 = APIKeyVault()
    assert vault1 is vault2


def test_get_existing_key(temp_env_file, monkeypatch):
    """Test getting an existing key."""
    # Reset singleton for test
    APIKeyVault._instance = None
    with patch('core.api_key_vault.find_dotenv', return_value=temp_env_file):
        vault = APIKeyVault()
        assert vault.get("POLYGON_API_KEY") == "test_polygon_key"


def test_get_nonexistent_key():
    """Test getting a key that doesn't exist."""
    vault = APIKeyVault()
    assert vault.get("NONEXISTENT_KEY") is None


def test_set_key(temp_env_file, monkeypatch):
    """Test setting a key."""
    APIKeyVault._instance = None
    with patch('core.api_key_vault.find_dotenv', return_value=temp_env_file):
        vault = APIKeyVault()
        vault.set("NEW_KEY", "new_value")
        assert vault.get("NEW_KEY") == "new_value"


def test_get_all_keys(temp_env_file, monkeypatch):
    """Test getting all keys."""
    APIKeyVault._instance = None
    with patch('core.api_key_vault.find_dotenv', return_value=temp_env_file):
        vault = APIKeyVault()
        all_keys = vault.get_all()
        assert "POLYGON_API_KEY" in all_keys
        assert "TAVILY_API_KEY" in all_keys


def test_get_required_for_graph():
    """Test getting required keys for a graph."""
    vault = APIKeyVault()
    graph = {
        "nodes": [
            {"type": "PolygonUniverseNode", "id": 1},
            {"type": "WebSearchToolNode", "id": 2},
            {"type": "TextInputNode", "id": 3}  # No required keys
        ]
    }
    required = vault.get_required_for_graph(graph)
    assert "POLYGON_API_KEY" in required
    assert "TAVILY_API_KEY" in required


def test_set_key_creates_env(tmpdir, monkeypatch):
    """Test setting a key creates .env if missing."""
    monkeypatch.chdir(tmpdir)  # Set cwd to tmpdir for isolation
    APIKeyVault._instance = None
    monkeypatch.setattr('core.api_key_vault.find_dotenv', lambda: '')  # Simulate no .env
    vault = APIKeyVault()
    vault.set("TEST_KEY", "test_value")
    assert vault.get("TEST_KEY") == "test_value"
    env_path = tmpdir.join('.env')
    assert env_path.exists()
    with open(env_path, 'r') as f:
        content = f.read()
        assert "TEST_KEY='test_value'" in content  # Match dotenv's quoted format

def test_unset_existing_key(temp_env_file, monkeypatch):
    """Test unsetting an existing key."""
    APIKeyVault._instance = None
    with patch('core.api_key_vault.find_dotenv', return_value=temp_env_file):
        vault = APIKeyVault()
        assert vault.get("POLYGON_API_KEY") == "test_polygon_key"
        vault.unset("POLYGON_API_KEY")
        assert vault.get("POLYGON_API_KEY") is None
        assert "POLYGON_API_KEY" not in os.environ
        with open(temp_env_file, 'r') as f:
            assert "POLYGON_API_KEY" not in f.read()

def test_unset_nonexistent_key(temp_env_file, monkeypatch):
    """Test unsetting a nonexistent key (no-op)."""
    APIKeyVault._instance = None
    with patch('core.api_key_vault.find_dotenv', return_value=temp_env_file):
        vault = APIKeyVault()
        original_keys = vault.get_all().copy()
        vault.unset("NONEXISTENT_KEY")
        assert vault.get_all() == original_keys  # No change
        assert "NONEXISTENT_KEY" not in os.environ

def test_unset_no_env_file(tmpdir, monkeypatch):
    """Test unset when no .env file (no error)."""
    monkeypatch.chdir(tmpdir)
    APIKeyVault._instance = None
    monkeypatch.setattr('core.api_key_vault.find_dotenv', lambda: '')
    vault = APIKeyVault()
    vault.set("TEMP_KEY", "value")
    assert vault.get("TEMP_KEY") == "value"
    vault.unset("TEMP_KEY")
    assert vault.get("TEMP_KEY") is None
    assert "TEMP_KEY" not in os.environ

def test_get_required_for_graph_unknown_node():
    """Test get_required_for_graph skips unknown nodes."""
    vault = APIKeyVault()
    graph = {
        "nodes": [
            {"type": "UnknownNode", "id": 1},
            {"type": "PolygonUniverseNode", "id": 2}
        ]
    }
    required = vault.get_required_for_graph(graph)
    assert required == ["POLYGON_API_KEY"]  # Only known node

def test_get_required_for_graph_duplicates():
    """Test required keys are unique across duplicates."""
    vault = APIKeyVault()
    graph = {
        "nodes": [
            {"type": "PolygonUniverseNode", "id": 1},
            {"type": "PolygonUniverseNode", "id": 2}
        ]
    }
    required = vault.get_required_for_graph(graph)
    assert required == ["POLYGON_API_KEY"]  # No duplicates

def test_get_required_for_graph_empty():
    """Test empty graph returns no keys."""
    vault = APIKeyVault()
    graph = {"nodes": []}
    required = vault.get_required_for_graph(graph)
    assert required == []

def test_singleton_after_set_unset():
    """Test singleton state persists after set/unset."""
    vault1 = APIKeyVault()
    vault1.set("SINGLETON_KEY", "value")
    vault2 = APIKeyVault()
    assert vault2.get("SINGLETON_KEY") == "value"
    vault2.unset("SINGLETON_KEY")
    assert vault1.get("SINGLETON_KEY") is None
