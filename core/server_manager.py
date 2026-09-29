"""Server lifecycle management for Hindi Reel Studio.

Provides self-contained start, stop, restart, and status detection
for both frozen PyInstaller binaries and development virtual environments.
"""

import os
import sys
import time
import signal
import shlex
import subprocess
import threading
from typing import Dict, Any, List, Optional


def get_current_port() -> int:
    """Resolve the active server port from environment, sys.argv, or defaults."""
    env_port = os.environ.get("HRS_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass

    # Check command line arguments for --server.port=... or --server.port ...
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--server.port="):
            try:
                return int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg == "--server.port" and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                pass

    # Default release port is 80; fallback to 8501 if standard streamlit dev
    return 80 if getattr(sys, "frozen", False) else 8501


def get_current_host() -> str:
    """Resolve the active server host address."""
    env_host = os.environ.get("HRS_HOST") or os.environ.get("STREAMLIT_SERVER_ADDRESS")
    if env_host:
        return env_host.strip()
    return "::"


def get_server_info() -> Dict[str, Any]:
    """Return dictionary of server status and metadata."""
    port = get_current_port()
    host = get_current_host()
    pid = os.getpid()
    is_frozen = getattr(sys, "frozen", False)

    return {
        "status": "running",
        "pid": pid,
        "port": port,
        "host": host,
        "is_frozen": is_frozen,
        "is_standard_port": port in (80, 443),
    }


def _resolve_launch_command() -> List[str]:
    """Reconstruct the launch command line to safely spawn a replacement process."""
    if getattr(sys, "frozen", False):
        return [sys.executable]

    # Check ps output for the exact original arguments of this process
    try:
        proc = subprocess.run(
            ["ps", "-o", "args=", "-p", str(os.getpid())],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            args = shlex.split(proc.stdout.strip())
            if args:
                return args
    except Exception:
        pass

    # Fallback to standard Python / Streamlit invocation
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_py = os.path.join(project_dir, "app.py")
    port = get_current_port()
    host = get_current_host()

    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_py,
        "--global.developmentMode=false",
        "--server.headless=true",
        f"--server.address={host}",
        f"--server.port={port}",
    ]


def stop_server_async(delay_seconds: float = 0.8) -> None:
    """Schedule the server process to cleanly terminate after allowing the HTTP response to finish."""
    def _shutdown():
        time.sleep(delay_seconds)
        pid = os.getpid()
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        # Hard exit fallback if SIGTERM is intercepted
        time.sleep(1.0)
        os._exit(0)

    t = threading.Thread(target=_shutdown, daemon=True)
    t.start()


def restart_server_async(delay_seconds: float = 0.8) -> None:
    """Schedule server restart by spawning a detached replacement and terminating current process."""
    cmd = _resolve_launch_command()
    cwd = os.getcwd()
    env = os.environ.copy()

    def _restart():
        time.sleep(delay_seconds)
        try:
            # Spawn detached replacement process
            subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                close_fds=True,
                start_new_session=True,
            )
        except Exception as e:
            sys.stderr.write(f"Failed to spawn replacement server process: {e}\n")

        # Terminate current process
        pid = os.getpid()
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(1.0)
        os._exit(0)

    t = threading.Thread(target=_restart, daemon=True)
    t.start()
