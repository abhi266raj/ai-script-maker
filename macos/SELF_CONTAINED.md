# Hindi Reel Studio — self-contained macOS app

This note is the current understanding of how the packaged app launches and how its server is controlled. Update this file whenever that behavior changes.

## What the user gets

`Hindi Reel Studio.app` is a self-contained Mac app. Double-clicking it must start the studio by itself. Nothing should depend on a terminal, a separate `streamlit` command, or a browser window.

The native window is `macos/StudioWindow.swift`, compiled to `Contents/MacOS/app_runner`. It shows the Streamlit UI in a `WKWebView` and keeps the app icon in the Dock. Closing the window quits the app and stops a server this launch started.

The Python server is the PyInstaller runtime at `Contents/Resources/runtime/run_standalone`, built from `scripts/run_standalone.py`. That process runs Streamlit headless. If that runtime is missing (a repo checkout, not a frozen app), the launcher falls back to `<project>/.venv/bin/streamlit run app.py`.

## Server controls

Start, stop, and restart all happen off the main thread so the window stays responsive. They are on the window toolbar and under the **Server** menu.

| Action | Shortcut | What it does |
| --- | --- | --- |
| Start | ⌘R | Starts the packaged runtime, or the project virtualenv. If something is already answering on the studio port, it only reloads the window. |
| Stop | ⌘. | Terminates the process this launch started, then sends SIGTERM to anything still listening on the studio port. |
| Restart | ⇧⌘R | Stop, brief pause, then start, then reload the page. |

The window title shows `Starting server…`, `Server running`, `Server stopped`, or `Server failed to start`.

On every open, the app starts the server in the background if the port is not already serving, then loads the page once a short HTTP probe succeeds.

## Why a release build was not launching the script

Older `app_runner` builds probed the port with a blocking read and ignored launch errors (`try?`). A failed packaged binary looked the same as “already running,” so Streamlit never came up. A double-clicked app also inherits a tiny `PATH`, so Homebrew CLIs (`grok`, `codex`) were invisible inside `/Applications`.

Current launcher behavior:

- Probe with a short `URLSession` timeout (IPv6 `[::1]`, IPv4 `127.0.0.1`, then `localhost`).
- Launch the frozen `run_standalone` when that file is executable.
- Put `/opt/homebrew/bin` and the usual system bins on `PATH` for both the packaged runtime and the virtualenv fallback.
- Write launch failures into the server log instead of dropping them.

Port and host come from `Info.plist`: `HRSServerPort`, `HRSServerHTTPSPort`, and `HRSServerHost`. Release uses default port `80` (HTTP) with HTTPS candidate port `443`. Dev uses `8502` and bundle id `com.hindireel.studio.dev`. Release bundle id is `com.hindireel.studio`.

## Menu Bar & Web Lifecycle Controls

Server management is accessible in both the macOS native application and the self-contained Web UI:
- **macOS System Menu Bar (`NSApp.mainMenu`)**:
  - **Server** menu with **Start Server** (`⌘R`), **Stop Server** (`⌘.`), and **Restart Server** (`⇧⌘R`).
  - Native window toolbar with Start, Stop, and Restart icons.
  - Automatic status tracking and window title updates.
- **Web UI Menu Bar ([`app.py`](file:///Users/abhiraj/Documents/news/agent/app.py) & [`core/server_manager.py`](file:///Users/abhiraj/Documents/news/agent/core/server_manager.py))**:
  - Top navigation bar `⚡ Server` menu popover displaying live status, PID, host, and port.
  - In-browser **Stop Server** and **Restart Server** controls with automatic reconnection polling.

## Logs

Writable project directory: `<project>/.server_<port>.log`.

Installed app (for example `/Applications`): `~/Library/Logs/HindiReelStudio/server_<port>.log`.

Last resort: `/tmp/hindi_reel_studio_<port>.log`.

## Rebuild

An already built `.app` or `.dmg` does not pick up Swift changes. After editing `macos/StudioWindow.swift`, rebuild:

```bash
./scripts/build_macos_app.sh --release
```

Python, prompts, and config inside a frozen runtime are copied at freeze time. Those changes need a rebuild too. A dev launch from the repo still reads `app.py` from disk via the virtualenv fallback.

## Version

Server controls, port 80/443 defaults, and `core.workflow` bundling are **1.3.3**. The single version string is `__version__` in `core/version.py`. The build script reads that string, so the next dev app lands in `dev/v1.3.3/` and the next release disk image is `dist/v1.3.3/Hindi-Reel-Studio-v1.3.3-macOS.dmg`.

This work is on branch `fix/background-server-controls`. Do not commit or merge until the user asks.
