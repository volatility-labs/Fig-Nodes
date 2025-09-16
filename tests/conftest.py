import os
import sys
from pathlib import Path
import builtins
from typing import Any
import pytest
import pytest_asyncio


def _ensure_project_root_on_path() -> None:
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_path()