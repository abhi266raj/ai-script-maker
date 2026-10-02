"""Tests for popover dismissal (HIG §6: popovers dismiss on outside click).

- Streamlit renders popovers natively and closes them on outside click;
  the app adds a defensive capture-phase guard that dispatches a synthetic
  Escape (Streamlit's own close path) when a click lands outside all
  popover chrome. No timers — HIG popovers never auto-dismiss on a timer.
- The UI contract is pinned to an exact Streamlit version (#200/#254);
  the app fails loudly at startup when the installed version differs,
  instead of silently misbehaving (e.g. popovers that never dismiss).

Run: python -m pytest tests/test_popover_dismissal.py -q
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APP_PY = Path(__file__).resolve().parent.parent / "app.py"
NODE_TEST = Path(__file__).resolve().parent / "test_popover_dismissal.js"

GUARD_MARKER = "_studioPopoverDismissGuard"


def _guard_script():
    """Extract the <script> block that defines the dismissal guard."""
    src = APP_PY.read_text(encoding="utf-8")
    idx = src.index(GUARD_MARKER)
    s_start = src.rindex("<script>", 0, idx) + len("<script>")
    s_end = src.index("</script>", idx)
    return src[s_start:s_end]


def _guard_fns():
    """Exec the pure version-guard functions from app.py into a namespace."""
    src = APP_PY.read_text(encoding="utf-8")
    start = src.index("def _streamlit_pin_from_requirements")
    end = src.index("_check_streamlit_pin(getattr(st,")
    ns = {"os": os, "_app_dir": str(APP_PY.parent)}
    exec(src[start:end], ns)  # noqa: S102 - test-only exec of repo source
    return ns


# ---------------------------------------------------------------------------
# Dismissal guard structure (HIG §6)
# ---------------------------------------------------------------------------

def test_dismissal_guard_present():
    script = _guard_script()
    assert GUARD_MARKER in script


def test_dismissal_guard_uses_streamlit_own_close_path():
    """Outside clicks close via a synthetic Escape — Streamlit's own
    popover keydown handler — never by removing DOM nodes directly."""
    script = _guard_script()
    assert "KeyboardEvent" in script
    assert "'Escape'" in script or '"Escape"' in script
    # Must not rip the popover out of the DOM itself.
    assert "removeChild" not in script
    assert ".remove()" not in script


def test_dismissal_guard_attached_in_capture_phase():
    """Capture phase runs before any bubble-phase stopPropagation in the
    page can swallow the click."""
    script = _guard_script()
    assert re.search(
        r"addEventListener\(\s*['\"]click['\"]\s*,\s*_studioPopoverDismissOnOutsideClick\s*,\s*true\s*\)",
        script,
    ), "guard must attach the click listener with capture=true"


def test_dismissal_guard_inside_check_mirrors_streamlit():
    """Clicks inside the trigger, the popover body, or a nested overlay
    root (e.g. a selectbox dropdown) must not dismiss."""
    script = _guard_script()
    assert '[data-testid="stPopover"]' in script
    assert '[data-testid="stPopoverBody"]' in script
    assert '[data-st-overlay-root="true"]' in script


def test_dismissal_guard_only_acts_when_popover_open():
    """No popover body in the DOM -> the guard stays silent."""
    script = _guard_script()
    assert 'querySelector(\'[data-testid="stPopoverBody"]\')' in script


def test_dismissal_guard_idempotent():
    """The script block re-executes on every Streamlit rerun; it must not
    stack duplicate listeners."""
    script = _guard_script()
    assert "if (window._studioPopoverDismissGuard) return;" in script


def test_no_timer_based_popover_dismissal():
    """HIG: popovers never auto-dismiss on a timer. A timed dismiss would
    strand users mid-interaction with share/confirmation controls."""
    script = _guard_script()
    code = re.sub(r"/\*[\s\S]*?\*/", "", script)
    code = re.sub(r"//[^\n]*", "", code)
    assert "setTimeout" not in code, "no timer-based popover dismissal allowed"
    assert "setInterval" not in code, "no timer-based popover dismissal allowed"


def test_node_behavioral_tests_pass():
    """The node suite stubs a minimal DOM and verifies dispatch behavior."""
    if not shutil.which("node"):
        pytest.skip("node not available")
    assert NODE_TEST.exists(), "node behavioral test missing"
    proc = subprocess.run(
        ["node", str(NODE_TEST)], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, f"node tests failed:\n{proc.stdout}\n{proc.stderr}"


# ---------------------------------------------------------------------------
# Streamlit version guard (#200/#254)
# ---------------------------------------------------------------------------

def test_version_guard_passes_on_match():
    ns = _guard_fns()
    ns["_check_streamlit_pin"]("1.64.0", "1.64.0")  # must not raise


def test_version_guard_fails_loudly_on_mismatch():
    ns = _guard_fns()
    with pytest.raises(RuntimeError, match="Streamlit version mismatch"):
        ns["_check_streamlit_pin"]("1.39.0", "1.64.0")


def test_version_guard_fails_loudly_without_pin():
    ns = _guard_fns()
    with pytest.raises(RuntimeError, match="does not pin streamlit"):
        ns["_check_streamlit_pin"]("1.64.0", None)
    with pytest.raises(RuntimeError, match="does not pin streamlit"):
        ns["_check_streamlit_pin"]("1.64.0", "")


def test_version_guard_error_is_actionable():
    ns = _guard_fns()
    with pytest.raises(RuntimeError) as exc:
        ns["_check_streamlit_pin"]("1.39.0", "1.64.0")
    assert "pip install -r requirements.txt" in str(exc.value)


def test_pin_parsed_from_requirements():
    """The pin is read from requirements.txt (single source of truth) and
    inline comments are stripped — a bad parse would false-positive the
    guard and refuse to start the app."""
    ns = _guard_fns()
    pin = ns["_streamlit_pin_from_requirements"]()
    assert pin == "1.64.0", f"pin parsed as {pin!r}"
    # And the installed venv matches it, or the app would refuse to start.
    import streamlit as st

    assert st.__version__ == pin
