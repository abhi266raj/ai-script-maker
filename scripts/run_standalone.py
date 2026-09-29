#!/usr/bin/env python3
"""Entrypoint for the PyInstaller-frozen Hindi Reel Studio.

Launches Streamlit in headless mode, serving app.py on dual-stack localhost,
supporting IPv6 loopback ([::1]) as well as IPv4 (127.0.0.1).
The native Cocoa window (app_runner) connects to this local server.

Configuration via environment variables:
  - HRS_PORT: 8501 (Release default) or 8502 (Dev default)
  - HRS_HOST: Server bind address (default: "localhost" for dual-stack, or "::1" / "127.0.0.1")
"""
import os
import sys
import socket

# Explicit imports to ensure PyInstaller dependency analysis bundles all application modules
try:
    import core.workflow  # noqa: F401
    import core  # noqa: F401
    import agents  # noqa: F401
    import tools  # noqa: F401
except ImportError:
    pass


def _setup_paths():
    """Configure paths so frozen Streamlit finds all project modules."""
    # Ensure Streamlit development mode conflict check is suppressed in frozen build
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    if getattr(sys, "frozen", False):
        # Running inside PyInstaller bundle
        bundle_dir = sys._MEIPASS
    else:
        # Running as a normal script (dev / testing)
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
        # When run from scripts/, go up one level to project root
        project_root = os.path.dirname(bundle_dir)
        if os.path.isfile(os.path.join(project_root, "app.py")):
            bundle_dir = project_root

    # Add bundle root to sys.path so 'workflow', 'core', 'agents', 'tools' are importable
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

    # Ensure PYTHONPATH includes bundle directory for scriptrunner threads
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    if bundle_dir not in existing_pythonpath.split(os.pathsep):
        os.environ["PYTHONPATH"] = f"{bundle_dir}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else bundle_dir

    # Point Streamlit config to bundled config directory
    # PyInstaller bundles .streamlit as _streamlit to avoid dot-prefix issues
    streamlit_config = os.path.join(bundle_dir, "_streamlit")
    if os.path.isdir(streamlit_config):
        os.environ["STREAMLIT_CONFIG_DIR"] = streamlit_config
    else:
        # Fallback: normal .streamlit directory
        streamlit_config = os.path.join(bundle_dir, ".streamlit")
        if os.path.isdir(streamlit_config):
            os.environ["STREAMLIT_CONFIG_DIR"] = streamlit_config

    return bundle_dir


def main():
    """Boot Streamlit headlessly on the configured port and IPv4/IPv6 host."""
    bundle_dir = _setup_paths()
    app_py = os.path.join(bundle_dir, "app.py")

    if not os.path.isfile(app_py):
        print(f"❌ app.py not found at: {app_py}", file=sys.stderr)
        sys.exit(1)

    # Port and host from environment (default: port 80 for release, "::" for simultaneous dual-stack IPv6 + IPv4)
    port_str = os.environ.get("HRS_PORT", "80")
    try:
        port = int(port_str)
    except ValueError:
        port = 80

    raw_host = os.environ.get("HRS_HOST", "::").strip()
    host = raw_host.strip("[]") if raw_host else "::"
    os.environ["STREAMLIT_SERVER_ADDRESS"] = host

    # Validate binding to privileged ports (< 1024) on macOS/Unix without elevated privileges
    if port < 1024:
        can_bind = False
        try:
            test_sock = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.bind(("", port))
            test_sock.close()
            can_bind = True
        except PermissionError:
            can_bind = False
        except Exception:
            can_bind = True

        if not can_bind:
            print(f"⚠️ Port {port} requires root privileges; falling back to 8501 (or run with sudo / fronting reverse proxy)", file=sys.stderr)
            port = 8501
            os.environ["HRS_PORT"] = "8501"

    from streamlit.web import cli as st_cli

    sys.argv = [
        "streamlit",
        "run",
        app_py,
        "--global.developmentMode=false",
        "--server.headless=true",
        f"--server.address={host}",
        f"--server.port={port}",
    ]
    st_cli.main()


if __name__ == "__main__":
    main()
