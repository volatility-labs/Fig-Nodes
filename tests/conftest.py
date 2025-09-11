import os
import sys
from pathlib import Path
import builtins
from typing import Any
import pytest
import websockets
from unittest.mock import MagicMock


def _ensure_project_root_on_path() -> None:
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_path()


# Python 3.9 shim for built-in anext used in tests
if not hasattr(builtins, "anext"):
    async def _anext(ait):
        return await ait.__anext__()
    builtins.anext = _anext  # type: ignore[attr-defined]


@pytest.fixture
def mock_connect(monkeypatch):
    """Fixture to mock websockets.connect and allow tests to control it."""
    mock = MagicMock()
    monkeypatch.setattr(websockets, "connect", mock)
    return mock


