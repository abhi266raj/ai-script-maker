#!/usr/bin/env python3
"""Entrypoint for the PyInstaller-frozen Hindi Reel Studio.

Launches Streamlit in headless mode, serving app.py on 127.0.0.1.
The native Cocoa window (app_runner) connects to this local server.

Port is read from the HRS_PORT environment variable:
  - Release: 8501 (default)
  - Dev:     8502
"""
import os
import sys


def _setup_paths():
    """Configure paths so frozen Streamlit finds all project modules."""
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

    # Add bundle root to sys.path so 'core', 'agents', 'tools' are importable
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

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
    """Boot Streamlit headlessly on the configured port."""
    bundle_dir = _setup_paths()
    app_py = os.path.join(bundle_dir, "app.py")

    if not os.path.isfile(app_py):
        print(f"❌ app.py not found at: {app_py}", file=sys.stderr)
        sys.exit(1)

    # Port from environment (set by native Cocoa wrapper via Info.plist)
    port = os.environ.get("HRS_PORT", "8501")

    from streamlit.web import cli as st_cli

    sys.argv = [
        "streamlit",
        "run",
        app_py,
        "--server.headless",
        "true",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        port,
    ]
    st_cli.main()


if __name__ == "__main__":
    main()
