
import pytest
from unittest.mock import patch, MagicMock
import sys
import signal
from pathlib import Path
import subprocess
from main import run_dev, run_prod, main, _needs_build, _build_frontend, _which, _start_process, _terminate_process

@pytest.fixture
def mock_paths():
    with patch("main.REPO_ROOT", Path("/fake/root")), \
         patch("main.UI_DIR", Path("/fake/ui")), \
         patch("main.DIST_DIR", Path("/fake/dist")):
        yield

def test_which_found():
    with patch("shutil.which", return_value="/path/to/cmd"):
        assert _which("cmd") == "/path/to/cmd"

def test_which_not_found():
    with patch("shutil.which", return_value=None):
        assert _which("missing") is None

def test_needs_build_no_dist(mock_paths):
    with patch("pathlib.Path.exists", return_value=False):
        assert _needs_build() is True

def test_needs_build_no_index(mock_paths):
    with patch("pathlib.Path.exists", side_effect=[True, False]):
        assert _needs_build() is True

def test_needs_build_ok(mock_paths):
    with patch("pathlib.Path.exists", return_value=True):
        assert _needs_build() is False

@patch("subprocess.check_call")
def test_build_frontend_yarn(mock_check_call, mock_paths):
    with patch("main._select_node_pm", return_value=(["yarn"], "yarn")):
        _build_frontend()
        mock_check_call.assert_called_with(["yarn", "build"], cwd=str(Path("/fake/ui")))

@patch("subprocess.Popen")
def test_start_process_posix(mock_popen):
    with patch("os.name", "posix"), patch("os.setsid"):
        _start_process(["cmd"], cwd=Path("/dir"))
        mock_popen.assert_called()

@patch("subprocess.Popen")
def test_terminate_process_posix(mock_popen):
    proc = MagicMock()
    proc.poll.return_value = None
    with patch("os.name", "posix"), patch("os.getpgid"), patch("os.killpg"):
        _terminate_process(proc)
        proc.poll.assert_called()

@patch("main._start_process")
@patch("main._terminate_process")
def test_run_dev(mock_terminate, mock_start, mock_paths):
    be_proc = MagicMock()
    fe_proc = MagicMock()
    mock_start.side_effect = [be_proc, fe_proc]
    with patch("time.sleep") as mock_sleep, \
         patch("sys.stdout"), \
         patch("sys.stderr"):
        mock_sleep.side_effect = KeyboardInterrupt
        run_dev("localhost", 8000, 5173)
        mock_terminate.assert_called()

@patch("main._build_frontend")
@patch("main._start_process")
@patch("main._terminate_process")
def test_run_prod(mock_terminate, mock_start, mock_build, mock_paths):
    proc = MagicMock()
    mock_start.return_value = proc
    with patch("main._needs_build", return_value=True):
        run_prod("localhost", 8000, force_build=False)
        mock_build.assert_called()
        mock_terminate.assert_called()

@patch("main.parse_args")
@patch("main.run_dev")
@patch("main.run_prod")
def test_main(mock_prod, mock_dev, mock_parse):
    mock_args = MagicMock(dev=True)
    mock_parse.return_value = mock_args
    main()
    mock_dev.assert_called()

# Add more tests for edge cases, signals, etc.
