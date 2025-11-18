import os
import sys
from pathlib import Path
import builtins
from typing import Any
import pytest
import pytest_asyncio
from unittest.mock import patch


def _ensure_project_root_on_path() -> None:
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_path()

# Import services that register tools to ensure they're available for tests
try:
    from services.tools import web_search  # noqa: F401
except ImportError:
    pass


@pytest.fixture(autouse=True)
def test_env_isolation(tmp_path):
    """Patch find_dotenv to return an isolated temporary .env path for each test."""
    env_dir = tmp_path / "isolated_env"
    env_dir.mkdir()
    dotenv_path = str(env_dir / ".env")
    Path(dotenv_path).touch()

    from core.api_key_vault import APIKeyVault
    APIKeyVault._instance = None
    APIKeyVault._keys.clear()

    with patch('core.api_key_vault.find_dotenv', return_value=dotenv_path):
        yield

    APIKeyVault._instance = None
    APIKeyVault._keys.clear()