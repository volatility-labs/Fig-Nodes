"""
Unified entrypoint to run the FastAPI backend and the Vite frontend.

Usage examples:
    poetry run python main.py --dev
    poetry run python main.py --prod

Dev mode:
  - Starts Uvicorn (backend) on port 8000
  - Starts Vite dev server in ui/static (default port 5173) with proxy to backend

Prod mode:
  - Optionally builds the frontend (if --build or dist missing)
  - Serves built assets via FastAPI (mounted at /static)
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent
UI_DIR = REPO_ROOT / "ui" / "static"
DIST_DIR = UI_DIR / "dist"


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _select_node_pm(cwd: Path) -> Tuple[List[str], str]:
    """Select node package manager and dev/build command.

    Preference order: yarn (if yarn.lock exists and yarn is available) -> npm
    """
    yarn_lock = (cwd / "yarn.lock").exists()
    if yarn_lock and _which("yarn"):
        return ["yarn"], "yarn"
    if _which("npm"):
        return ["npm"], "npm"
    # Fallback to npx vite directly if no PM is detected
    if _which("npx"):
        return ["npx"], "npx"
    raise RuntimeError("No suitable Node package manager found (need yarn, npm or npx) for frontend.")


def _start_process(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> subprocess.Popen:
    kwargs = dict(cwd=str(cwd) if cwd else None, env=env or os.environ.copy())

    if os.name == "posix":
        # Start new process group so we can terminate descendants cleanly
        return subprocess.Popen(cmd, preexec_fn=os.setsid, stdout=sys.stdout, stderr=sys.stderr, **kwargs)
    else:
        # Windows
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        return subprocess.Popen(cmd, creationflags=creationflags, stdout=sys.stdout, stderr=sys.stderr, **kwargs)


def _terminate_process(proc: subprocess.Popen, sig: int = signal.SIGTERM, timeout: float = 3.0) -> None:
    """Terminate a process and all its children, with protection against interruption."""
    if proc.poll() is not None:
        return

    # Use SIGKILL for dev servers since they often ignore SIGTERM
    kill_sig = signal.SIGKILL if os.name == "posix" else signal.SIGTERM

    try:
        if os.name == "posix":
            # Kill the entire process group to catch all children
            os.killpg(os.getpgid(proc.pid), kill_sig)
        else:
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
    except Exception:
        # Fallback to terminate the main process
        try:
            proc.kill()
        except Exception:
            pass

    # Wait for termination, but protect against KeyboardInterrupt
    start = time.time()
    while proc.poll() is None and (time.time() - start) < timeout:
        try:
            time.sleep(0.05)  # Shorter sleep for more responsive termination
        except KeyboardInterrupt:
            # If interrupted during wait, immediately force kill
            try:
                if os.name == "posix":
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
            except Exception:
                pass
            break

    # Final check - if still running, force kill
    if proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass


def run_dev(host: str, backend_port: int, vite_port: int) -> int:
    # Backend (Uvicorn) with auto-reload
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "ui.server:app",
        "--host",
        host,
        "--port",
        str(backend_port),
        "--reload",
    ]

    backend_proc = _start_process(backend_cmd, cwd=REPO_ROOT)

    # Frontend (Vite dev) with proxy to backend (configured in vite.config.ts)
    pm_cmd, pm_name = _select_node_pm(UI_DIR)
    if pm_name == "yarn":
        fe_cmd = ["npx", "--yes", "yarn@1.22.22", "dev", "--", f"--port={vite_port}"]
    elif pm_name == "npm":
        fe_cmd = pm_cmd + ["run", "dev", "--", f"--port={vite_port}"]
    else:  # npx fallback
        fe_cmd = pm_cmd + ["vite", "--port", str(vite_port)]

    env = os.environ.copy()
    env.setdefault("BROWSER", "none")
    frontend_proc = _start_process(fe_cmd, cwd=UI_DIR, env=env)

    print(f"\nDev servers starting:")
    print(f"- Backend:    http://{host}:{backend_port}")
    print(f"- Frontend:   http://localhost:{vite_port}/static/  (Vite dev)")
    print("Press Ctrl+C to stop both.")

    exit_code = 0
    try:
        # Wait on either process to exit
        while True:
            if backend_proc.poll() is not None:
                exit_code = backend_proc.returncode or 0
                print("Backend process exited; shutting down frontend...")
                break
            if frontend_proc.poll() is not None:
                exit_code = frontend_proc.returncode or 0
                print("Frontend process exited; shutting down backend...")
                break
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping dev servers...")
    finally:
        # Ensure both processes are terminated, even if interrupted
        try:
            _terminate_process(frontend_proc)
        except KeyboardInterrupt:
            # If interrupted during frontend termination, still try backend
            pass
        try:
            _terminate_process(backend_proc)
        except KeyboardInterrupt:
            # If interrupted during backend termination, at least we tried
            pass

    return exit_code


def _needs_build() -> bool:
    return not DIST_DIR.exists() or not (DIST_DIR / "index.html").exists()


def _build_frontend() -> None:
    pm_cmd, pm_name = _select_node_pm(UI_DIR)
    if pm_name == "yarn":
        build_cmd = pm_cmd + ["build"]
    elif pm_name == "npm":
        build_cmd = pm_cmd + ["run", "build"]
    else:  # npx fallback
        build_cmd = pm_cmd + ["vite", "build"]

    print("Building frontend (Vite)...")
    subprocess.check_call(build_cmd, cwd=str(UI_DIR))


def run_prod(host: str, backend_port: int, force_build: bool) -> int:
    if force_build or _needs_build():
        _build_frontend()

    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "ui.server:app",
        "--host",
        host,
        "--port",
        str(backend_port),
    ]

    print(f"Starting backend on http://{host}:{backend_port} serving built UI at root '/' ...")
    backend_proc = _start_process(backend_cmd, cwd=REPO_ROOT)
    exit_code = 0
    try:
        backend_proc.wait()
        exit_code = backend_proc.returncode or 0
    except KeyboardInterrupt:
        pass
    finally:
        _terminate_process(backend_proc)

    print(f"App available at http://{host}:{backend_port}/")
    return exit_code


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run backend and frontend together")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dev", action="store_true", help="Run Vite dev server and backend with reload")
    mode.add_argument("--prod", action="store_true", help="Serve built frontend from backend")
    default_host = os.environ.get("HOST", "0.0.0.0")
    default_port = int(os.environ.get("PORT", "8000"))
    default_vite_port = int(os.environ.get("VITE_PORT", "5173"))
    parser.add_argument("--host", default=default_host, help=f"Backend host (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Backend port (default: {default_port})")
    parser.add_argument("--vite-port", type=int, default=default_vite_port, help=f"Vite dev port (default: {default_vite_port})")
    parser.add_argument("--build", action="store_true", help="Force build frontend in prod mode")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    # Default to dev if neither specified
    if not args.dev and not args.prod:
        args.dev = True

    if args.dev:
        return run_dev(args.host, args.port, args.vite_port)
    else:
        return run_prod(args.host, args.port, args.build)


if __name__ == "__main__":
    raise SystemExit(main())


