"""v1.6 — chip color polish in the Library story detail.

The dark-mode chip fill was a muddy flat brown (#3A3129 / #D8C49A);
light mode (#F0E9DB / #6B5433) also lacked definition. Chips are now
cleaner warm pills with a hairline border and stronger text contrast in
both themes, following the Apple-HIG flat-pill look (no shadow).

CSS-only change: no Python behavior is touched. The #25/#26 x-clearance
(column padding, chip-scoped rules) and the chip height/gap system are
asserted unchanged here as regression guards.

Run: python -m pytest tests/test_chip_colors_v16.py -q
"""
import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _capture_library_css():
    """Import library_ui with a capturing streamlit stub; return the
    emitted <style> HTML."""
    saved = dict(sys.modules)
    chunks = []
    try:
        fake_mod = types.ModuleType("streamlit")
        fake_mod.markdown = lambda *a, **k: chunks.append(a[0] if a else "")
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui as lui
        lui.inject_library_css()
        return "\n".join(chunks)
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _token_values(css, token):
    """Token hex values in file order: [light, dark]."""
    return re.findall(rf"{re.escape(token)}:\s*(#[0-9A-Fa-f]{{6}})", css)


def _contrast_ratio(fg, bg):
    def lum(h):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

        def f(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    la, lb = lum(fg), lum(bg)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------------------
# New token values, both themes
# ---------------------------------------------------------------------------

def test_chip_tokens_have_expected_values():
    css = _capture_library_css()
    bg = _token_values(css, "--lib-chip-bg")
    text = _token_values(css, "--lib-chip-text")
    assert bg == ["#F0E7D5", "#4A4034"], bg
    assert text == ["#5A4227", "#F2E4C2"], text


def test_old_muddy_chip_colors_are_gone():
    css = _capture_library_css()
    for stale in ("#3A3129", "#D8C49A", "#F0E9DB", "#6B5433"):
        assert stale not in css, f"stale chip color still present: {stale}"


def test_chip_border_tokens_exist_in_both_themes():
    css = _capture_library_css()
    borders = re.findall(r"--lib-chip-border:\s*([^;]+);", css)
    assert len(borders) == 2, borders
    assert "90, 66, 39" in borders[0]      # light hairline
    assert "242, 228, 194" in borders[1]   # dark hairline


def test_chip_base_rule_uses_border_token():
    """The hairline lives on the chip itself (chip-scoped .lib-chip
    selector), with border-box so the 30px pill height is preserved."""
    css = _capture_library_css()
    m = re.search(r"\.lib-chip \{(.*?)\}", css, re.S)
    assert m, ".lib-chip base rule missing"
    body = m.group(1)
    assert "border: 1px solid var(--lib-chip-border);" in body
    assert "box-sizing: border-box;" in body


def test_chip_text_contrast_meets_wcag_aa():
    """Honest contrast check: chip text over chip fill must clear 4.5:1
    in both themes (WCAG AA for normal text)."""
    css = _capture_library_css()
    bg = _token_values(css, "--lib-chip-bg")
    text = _token_values(css, "--lib-chip-text")
    for theme, (t, b) in zip(("light", "dark"), zip(text, bg)):
        ratio = _contrast_ratio(t, b)
        assert ratio >= 4.5, f"{theme}: {t} on {b} = {ratio:.2f} < 4.5"


# ---------------------------------------------------------------------------
# Regression guards: #25/#26, height/gap system, no global SVG forcing
# ---------------------------------------------------------------------------

def test_x_clearance_rules_untouched():
    """#25/#26 (as redesigned by #51): the × clearance lives in the
    chip's own padding-right (34px, chip-scoped) — the × sits inside the
    pill, so tag text can never slide underneath it."""
    css = _capture_library_css()
    assert 'div[data-testid="stColumn"]:has(.lib-chip):has([data-marker="lib-x-r"])' in css
    assert "padding-right: 34px !important;" in css
    assert "padding-right: 30px" not in css
    assert "padding-right: 26px" not in css


def test_chip_height_gap_system_untouched():
    css = _capture_library_css()
    assert "--lib-chip-h: 30px;" in css
    assert "--lib-chip-gap: 10px;" in css


def test_no_global_svg_forcing():
    """Never force SVG fill/stroke globally (breaks Streamlit icons)."""
    css = _capture_library_css().lower()
    assert "svg{fill" not in css.replace(" ", "")
    assert "svg { fill" not in css
    assert "svg{stroke" not in css.replace(" ", "")
