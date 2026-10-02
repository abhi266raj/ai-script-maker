"""Tests for #207: theme follows Streamlit's rendered theme, not the OS.

Verifies (statically, following the repo's established source-assertion
pattern — see test_dialog_icon_theme_v162.py):
- The injected `studioSyncTheme` JS derives `data-theme` from Streamlit's
  RENDERED DOM (computed styles of Streamlit's theme-painted sidebar-toggle
  icon), never from `prefers-color-scheme` / `matchMedia` / localStorage.
- Failure is loud: no probe => `data-theme` is left unset (no silent OS
  fallback) and a visible error banner + console.error are surfaced.
- The app's own CSS can never poison the probes: no color/background/fill/
  stroke rule may target the probe selectors.
- The node unit tests exercising the detection logic
  (tests/test_theme_detection_207.js) pass.
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

PROBE_TESTIDS = ["stExpandSidebarButton", "stSidebarCollapseButton"]


def _theme_script():
    """Extract the <script> block that defines studioSyncTheme."""
    src = APP_PY.read_text(encoding="utf-8")
    m = re.search(r"<script>([\s\S]*?studioSyncTheme[\s\S]*?)</script>", src)
    assert m, "studioSyncTheme script block not found in app.py"
    return m.group(1)


def _theme_script_code():
    """The script with JS comments stripped (assertions about behaviour must
    not trip over explanatory prose)."""
    script = _theme_script()
    script = re.sub(r"/\*[\s\S]*?\*/", "", script)
    script = re.sub(r"//[^\n]*", "", script)
    return script


def _app_css():
    """Extract the main <style> CSS block from app.py."""
    src = APP_PY.read_text(encoding="utf-8")
    m = re.search(r'st\.markdown\(\s*"""\n<style>(.*?)</style>', src, re.DOTALL)
    assert m, "main <style> block not found in app.py"
    return re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)


# --- the OS must not be consulted ------------------------------------------------

def test_no_os_media_query_in_theme_script():
    script = _theme_script_code()
    assert "prefers-color-scheme" not in script, \
        "theme detection must not read the OS media query (#207)"


def test_no_match_media_in_theme_script():
    script = _theme_script_code()
    assert "matchMedia" not in script, \
        "theme detection must not use matchMedia (#207)"


def test_no_localstorage_theme_scan():
    script = _theme_script_code()
    assert "localStorage" not in script, \
        "theme detection must not scan localStorage (#207)"


# --- detection reads Streamlit's rendered DOM ------------------------------------

def test_detection_probes_rendered_dom():
    script = _theme_script()
    assert "getComputedStyle" in script, \
        "detection must inspect computed styles of the rendered DOM"
    for testid in PROBE_TESTIDS:
        assert testid in script, \
            f"detection must probe Streamlit's {testid}"


def test_detection_classifies_by_luminance():
    script = _theme_script()
    assert "studioLuminance" in script, "luminance classifier missing"
    assert "0.5" in script, "luminance threshold missing"


def test_data_theme_set_from_detected_value():
    script = _theme_script()
    # data-theme is written from the detected value on all three roots...
    assert script.count("setAttribute('data-theme'") >= 3 or \
        script.count('setAttribute("data-theme"') >= 3 or \
        script.count("setAttribute('data-theme', themeVal)") >= 1, \
        "data-theme must be set from the detected theme value"
    # ...only after detection succeeded (null => early return, no write).
    det_pos = script.find("studioDetectRenderedTheme()")
    null_guard = script.find("if (!themeVal)")
    first_write = script.find("setAttribute('data-theme'")
    assert det_pos != -1 and null_guard != -1 and first_write != -1
    assert det_pos < null_guard < first_write, \
        "detection -> null-guard -> data-theme write ordering broken"


# --- failure is loud, never a silent OS fallback ---------------------------------

def test_failure_surfaces_visible_error():
    script = _theme_script()
    assert "console.error" in script, "detection failure must log loudly"
    assert "studio-theme-detection-error" in script, \
        "detection failure must surface a visible error banner"
    assert 'role", "alert"' in script or "role', 'alert'" in script, \
        "error banner must be announced to assistive tech"


def test_no_silent_os_fallback_on_failure():
    script = _theme_script_code()
    # On detection failure the function returns BEFORE any data-theme write;
    # there is no OS-derived default anywhere in the script.
    assert "prefers-color-scheme" not in script
    assert "matchMedia" not in script
    # The null path returns early (grace-period ticks) instead of defaulting.
    m = re.search(r"if \(!themeVal\) \{([\s\S]*?)\n        \}", script)
    assert m, "null-detection guard missing"
    guard_body = m.group(1)
    assert "return;" in guard_body, "null detection must return without guessing"
    assert "setAttribute" not in guard_body, \
        "null detection must not write data-theme"


# --- the app's CSS must never poison the probes -----------------------------------

def test_css_does_not_paint_probes():
    """A color/background/fill/stroke rule targeting a probe (or its icon
    descendants) would make detection read the app's own theme: circular.
    This test fails loudly if such a rule is ever added."""
    css = _app_css()
    poisoned = []
    for sel, decl in re.findall(r"([^{}]+)\{([^{}]+)\}", css):
        sel_norm = " ".join(sel.split())
        if not re.search(
            r"(?<![a-zA-Z-])(color|background(-color)?|fill|stroke)\s*:",
            decl,
        ):
            continue
        for testid in PROBE_TESTIDS:
            if testid in sel_norm:
                poisoned.append(sel_norm[:120])
        # The probes live under the header/toolbar: those subtrees must not
        # set text color on descendants either (inheritance would poison the
        # icon read).
        if re.search(
            r'\[data-testid="st(Toolbar|Header|SidebarHeader)"\][^\{]*'
            r"(span|svg|button|i)\b",
            sel_norm,
        ):
            poisoned.append(sel_norm[:120])
    assert not poisoned, \
        f"CSS would poison the #207 theme probes: {poisoned}"


# --- node logic tests --------------------------------------------------------------

def test_node_detection_logic():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available; cannot run JS detection tests")
    assert NODE_TEST.exists(), "node test file missing"
    proc = subprocess.run(
        [node, str(NODE_TEST)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(APP_PY.parent),
    )
    assert proc.returncode == 0, \
        f"node detection tests failed:\n{proc.stdout}\n{proc.stderr}"
    assert "ALL NODE CHECKS PASSED" in proc.stdout
