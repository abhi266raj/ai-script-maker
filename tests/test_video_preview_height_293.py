"""Video preview height-cap regression tests (issue #293).

Root cause: the story-detail video preview was rendered via a bare
`st.video(str(vpath))` with no height constraint, so tall videos took
the full screen. Streamlit's `st.video` has no height parameter, so the
fix is a CSS cap in `inject_library_css()` (library_ui.py).

The fix constrains ONLY the height (`max-height: 420px`), leaving width
auto / max 100% so the aspect ratio is preserved. Selectors were
verified against the pinned Streamlit 1.64 frontend bundle:
`st.video` renders `<video class="stVideo" data-testid="stVideo">`
(or an `<iframe>` for YouTube embeds).

These tests assert the CSS contract — they fail on pristine develop
(where no such rule exists) and pass with the fix.
"""

import inspect
import re
from pathlib import Path

REPO = Path(inspect.getfile(inspect.currentframe())).resolve().parent.parent
LIB_UI = REPO / "library_ui.py"

# Reasonable preview cap: tall enough to be useful, never full-screen.
MAX_ALLOWED_PX = 600


def _css() -> str:
    src = LIB_UI.read_text()
    blocks = re.findall(r"<style>(.*?)</style>", src, re.S)
    assert blocks, "no <style> blocks in library_ui.py"
    css = "\n".join(blocks)
    # Strip comments so commented-out code can't fake a pass.
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rules(css: str):
    """Yield (selectors: list[str], declarations: str)."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors = [s.strip() for s in m.group(1).split(",") if s.strip()]
        out.append((selectors, m.group(2)))
    return out


def _video_declarations(css: str) -> str:
    """Declarations of the rule targeting the st.video element."""
    for selectors, declarations in _rules(css):
        if any('video[data-testid="stVideo"]' in s for s in selectors):
            return declarations
    return ""


def _decl_value(declarations: str, prop: str):
    m = re.search(rf"(?<![\w-]){prop}\s*:\s*([^;!]+)", declarations)
    return m.group(1).strip() if m else None


def _px(value: str):
    m = re.match(r"([\d.]+)px$", value or "")
    return float(m.group(1)) if m else None


def test_video_rule_exists():
    decls = _video_declarations(_css())
    assert decls, (
        "no CSS rule targets video[data-testid=\"stVideo\"] — "
        "the story-detail video preview has no height cap (#293)"
    )


def test_video_max_height_capped_reasonably():
    decls = _video_declarations(_css())
    assert decls, "video rule missing (#293)"
    value = _decl_value(decls, "max-height")
    assert value, "video rule sets no max-height (#293)"
    px = _px(value)
    assert px is not None, f"max-height must be a px value, got {value!r}"
    assert 0 < px <= MAX_ALLOWED_PX, (
        f"max-height {value!r} is not a reasonable preview cap "
        f"(must be 1–{MAX_ALLOWED_PX}px, #293)"
    )


def test_video_aspect_ratio_preserved():
    # Constraining only the height (width auto) keeps the aspect ratio.
    decls = _video_declarations(_css())
    assert decls, "video rule missing (#293)"
    width = _decl_value(decls, "width")
    assert width == "auto", (
        f"video width must be 'auto' so height-capping preserves aspect "
        f"ratio, got {width!r} (#293)"
    )
    # ...and nothing may force a fixed height that would distort it.
    height = _decl_value(decls, "height")
    assert height in (None, "auto"), (
        f"video must not set a fixed height (would distort aspect ratio), "
        f"got {height!r} (#293)"
    )


def test_video_narrow_screen_safe():
    decls = _video_declarations(_css())
    assert decls, "video rule missing (#293)"
    assert _decl_value(decls, "max-width") == "100%", (
        "video rule must cap max-width at 100% for narrow screens (#293)"
    )


def test_video_iframe_embeds_covered():
    # YouTube embeds render as <iframe data-testid="stVideo">, not <video>.
    css = _css()
    found = any(
        'iframe[data-testid="stVideo"]' in s
        for selectors, _ in _rules(css)
        for s in selectors
    )
    assert found, "iframe[data-testid=\"stVideo\"] not covered (#293)"


def test_video_rule_is_mode_agnostic():
    # No color declarations: the rule must work identically in light and
    # dark modes (HIG §4 — semantic colors only; here, no colors at all).
    decls = _video_declarations(_css())
    assert decls, "video rule missing (#293)"
    assert not re.search(r"#[0-9a-fA-F]{3,8}", decls), (
        f"video rule must not hard-code colors: {decls!r} (#293)"
    )
    assert "color" not in decls.replace("border-radius", ""), (
        f"video rule must not set colors: {decls!r} (#293)"
    )


def test_video_rule_beats_streamlit_native():
    # Streamlit's native video styles must lose: the cap needs !important,
    # per the theme-CSS house pattern.
    decls = _video_declarations(_css())
    assert decls, "video rule missing (#293)"
    assert re.search(r"max-height\s*:[^;]*!important", decls), (
        "max-height needs !important to beat Streamlit native styles (#293)"
    )


def test_library_css_braces_balanced():
    src = LIB_UI.read_text()
    for i, block in enumerate(re.findall(r"<style>(.*?)</style>", src, re.S)):
        stripped = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        assert stripped.count("{") == stripped.count("}"), (
            f"<style> block {i} has unbalanced braces (#293)"
        )
