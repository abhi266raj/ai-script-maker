"""Regression test for #207: the theme detector must never sample `fill`.

Root cause: `fill`'s CSS initial value is black, so every probe descendant
without an explicit fill (buttons, wrapper spans) computes to rgb(0,0,0).
Sampling it faked a 'light' detection on the first node examined, which meant
`data-theme` was always "light" — dark mode could never engage no matter what
Streamlit rendered, and the OS media-query fallback was neutered by the
always-light data-theme. Streamlit's probe icons carry the theme color as an
explicit `color` (fadedText60 emotion prop, verified against the pinned
Streamlit 1.64.0 frontend bundle), so `color`-only sampling is the true
rendered-theme signal.

Fails on pristine develop (detector samples `cs.fill`), passes with the fix.
The behavioral proof lives in tests/test_theme_detection_207.js, whose fake
DOM models the real initial fill value; it is executed here.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APP_PY = Path(__file__).resolve().parent.parent / "app.py"
NODE_TEST = Path(__file__).resolve().parent / "test_theme_detection_207.js"


def _theme_script_code():
    src = APP_PY.read_text(encoding="utf-8")
    m = re.search(r"<script>([\s\S]*?studioSyncTheme[\s\S]*?)</script>", src)
    assert m, "studioSyncTheme script block not found in app.py"
    script = m.group(1)
    script = re.sub(r"/\*[\s\S]*?\*/", "", script)
    script = re.sub(r"//[^\n]*", "", script)
    return script


def _fn_body(script, name):
    start = script.find("function " + name + "()")
    assert start != -1, f"{name} not found in theme script"
    brace = script.find("{", start)
    depth = 0
    for i in range(brace, len(script)):
        ch = script[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return script[brace + 1 : i]
    raise AssertionError(f"unbalanced braces in {name}")


def test_detector_never_samples_fill():
    """`fill` must not appear in the detection loop: its initial value
    (black) poisons every unsuspecting descendant into a fake 'light'."""
    det_body = _fn_body(_theme_script_code(), "studioDetectRenderedTheme")
    assert "fill" not in det_body.lower(), (
        "studioDetectRenderedTheme must not sample `fill` (#207): "
        "its CSS initial value (black) fakes a 'light' detection"
    )


def test_detector_still_samples_color():
    """The fix removes fill, not the signal: explicit `color` sampling
    (Streamlit's fadedText60 etc.) must remain."""
    det_body = _fn_body(_theme_script_code(), "studioDetectRenderedTheme")
    assert "getComputedStyle" in det_body
    assert "studioParseRgb" in det_body
    assert "studioLuminance" in det_body


def test_node_fill_poison_scenarios():
    """End-to-end behavioral proof via the node fake-DOM suite, which models
    the real initial fill value (rgb(0,0,0))."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available; cannot run JS detection tests")
    assert NODE_TEST.exists(), "node test file missing"
    proc = subprocess.run(
        [node, str(NODE_TEST)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        "node theme-detection checks failed:\n" + proc.stdout + proc.stderr
    )
    assert "ALL NODE CHECKS PASSED" in proc.stdout
