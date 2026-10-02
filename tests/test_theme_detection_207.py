"""Tests for #207 (revised #258): theme follows Streamlit's rendered theme,
with graceful OS fallback.

Verifies (statically, following the repo's established source-assertion
pattern — see test_dialog_icon_theme_v162.py):
- The injected `studioSyncTheme` JS derives `data-theme` from Streamlit's
  RENDERED DOM (computed styles of Streamlit's theme-painted icon controls),
  probed across several native controls so detection never depends on the
  sidebar existing.
- `prefers-color-scheme` / `matchMedia` appear ONLY in the OS-fallback
  function, which runs solely after the grace period with no probe success;
  a probe success always takes precedence over the fallback.
- Failure is graceful (#258): no error banner, no console.error — one
  console.warn, then the OS value. Fail loudly in tests, gracefully in app.
- The app's own CSS can never poison the probes: no color/background/fill/
  stroke rule may target the probes' icon descendants.
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

PROBE_TESTIDS = [
    "stExpandSidebarButton",
    "stSidebarCollapseButton",
    "stMainMenu",
    "stToolbar",
    "stHeader",
]


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


def _fn_body(script, name):
    """Extract the body of `function <name>() { ... }` via brace matching."""
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


def _app_css():
    """Extract the main <style> CSS block from app.py."""
    src = APP_PY.read_text(encoding="utf-8")
    m = re.search(r'st\.markdown\(\s*"""\n<style>(.*?)</style>', src, re.DOTALL)
    assert m, "main <style> block not found in app.py"
    return re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)


# --- the OS is only a fallback, never the primary signal ---------------------------

def test_os_media_query_only_in_fallback():
    """prefers-color-scheme / matchMedia may appear ONLY in the OS-fallback
    function (#258); the DOM-probe detector must never consult the OS."""
    script = _theme_script_code()
    det_body = _fn_body(script, "studioDetectRenderedTheme")
    assert "matchMedia" not in det_body, \
        "studioDetectRenderedTheme must not use matchMedia (#207)"
    assert "prefers-color-scheme" not in det_body, \
        "studioDetectRenderedTheme must not read the OS media query (#207)"
    fb_body = _fn_body(script, "studioOsFallbackTheme")
    assert "matchMedia" in fb_body, \
        "OS fallback must read matchMedia (#258)"
    assert "prefers-color-scheme" in fb_body, \
        "OS fallback must query prefers-color-scheme (#258)"


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
    # more than the two sidebar buttons: detection must not depend on the
    # sidebar existing (#258).
    assert len(PROBE_TESTIDS) > 2


def test_detection_classifies_by_luminance():
    script = _theme_script()
    assert "studioLuminance" in script, "luminance classifier missing"
    assert "0.5" in script, "luminance threshold missing"


def test_data_theme_written_from_both_paths():
    script = _theme_script_code()
    body = _fn_body(script, "studioSyncTheme")
    assert "studioApplyTheme(themeVal)" in body, \
        "probe path must apply the detected theme"
    assert "studioApplyTheme(osTheme)" in body, \
        "fallback path must apply the OS theme"


def test_probe_success_takes_precedence():
    """When Streamlit's rendered value is known it always wins: the probe
    result is applied (and the tick returns) BEFORE the fallback is ever
    consulted (#207 contract, preserved by #258)."""
    script = _theme_script_code()
    body = _fn_body(script, "studioSyncTheme")
    det = body.find("studioDetectRenderedTheme()")
    fb = body.find("studioOsFallbackTheme()")
    assert det != -1 and fb != -1 and det < fb, \
        "probe must be consulted before the OS fallback"


def test_fallback_gated_by_grace_period():
    """The OS fallback runs only after STUDIO_THEME_FAIL_GRACE_TICKS
    consecutive probe failures — never on the first blind tick."""
    script = _theme_script_code()
    body = _fn_body(script, "studioSyncTheme")
    grace = body.find("STUDIO_THEME_FAIL_GRACE_TICKS")
    fb = body.find("studioOsFallbackTheme()")
    assert grace != -1 and fb != -1 and grace < fb, \
        "OS fallback must be gated behind the grace period"


# --- failure is graceful (#258): warn once, no banner, no console.error -----------

def test_no_error_banner():
    script = _theme_script()
    assert "studio-theme-detection-error" not in script, \
        "the #207 red banner path must be gone (#258)"
    assert "Theme detection failed" not in script, \
        "banner copy must be gone (#258)"


def test_failure_warns_once_never_errors():
    script = _theme_script_code()
    assert "console.warn" in script, \
        "fallback must log one console.warn (#258)"
    assert "console.error" not in script, \
        "theme detection must not console.error in the app (#258)"


# --- the app's CSS must never poison the probes -----------------------------------

def _selector_poisoned(sel_norm, testid):
    """True if the selector paints icon descendants of the probe: such a
    rule would be read as Streamlit's theme color (the skip-inherited guard
    only neutralises paint on the probe root itself)."""
    for m in re.finditer(re.escape(testid), sel_norm):
        rest = sel_norm[m.end() :].split(",")[0]
        if re.search(r"[\s>+~]+[a-zA-Z*]*\b(span|svg|path|button|i)\b", rest):
            return True
    return False


def test_css_does_not_paint_probe_descendants():
    """A color/background/fill/stroke rule targeting a probe's icon
    descendants would make detection read the app's own theme: circular.
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
            if _selector_poisoned(sel_norm, testid):
                poisoned.append(sel_norm[:120])
    assert not poisoned, \
        f"CSS would poison the #207/#258 theme probes: {poisoned}"


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
