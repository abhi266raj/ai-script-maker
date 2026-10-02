"""#219 — hard-coded status colors with no dark variant (HIG §4).

Regression test: the status colors used by .pill-ok / .pill-bad / .step-done /
.banner-error / the "Studio Server Stopped" heading must be semantic CSS
custom properties with BOTH a light and a dark variant (custom colors need
light AND dark variants; never hard-coded color values), and every variant
pair documented here must meet the HIG 4.5:1 minimum contrast.

Contrast values were measured for (fg, bg):
  --ok light  #1c7c3a  on white text #ffffff : 5.26:1
  --ok dark   #2e7d46  on white text #ffffff : 5.07:1
  --bad light #c41e3a  on white text #ffffff : 5.84:1
  --bad dark  #c9303f  on white text #ffffff : 5.28:1
  --ok-text light  #1c7c3a on --bg-primary light #FAF7F0 : 4.91:1
  --ok-text dark   #4fae63 on --bg-primary dark  #2C261F : 5.39:1
  --ok-text dark   #4fae63 on --bg-secondary dark #3A3229 : 4.54:1
  --bad-text light #cf1322 on --bg-secondary light #FFFCF6 : 5.44:1
  --bad-text dark  #f0787f on --bg-secondary dark  #3A3229 : 4.61:1
  --bad-text dark  #f0787f on --bg-primary dark   #2C261F : 5.48:1

Run: python -m pytest tests/test_status_colors_dark_variants_219.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = Path(__file__).resolve().parent.parent
SOURCE = (REPO / "app.py").read_text()

TOKENS = ("--ok", "--bad", "--ok-text", "--bad-text")
# Hexes from the original hard-coded status colors — must not appear anywhere
# in app.py outside the token definitions after this fix.
LEGACY_HEXES = ("#1c7c3a", "#c41e3a", "#cf1322")

LIGHT_BG_PRIMARY = "#FAF7F0"
LIGHT_BG_SECONDARY = "#FFFCF6"
DARK_BG_PRIMARY = "#2C261F"
DARK_BG_SECONDARY = "#3A3229"


def _theme_block(kind):
    """Return the CSS custom-property block for the given theme kind."""
    if kind == "light":
        start = SOURCE.index('[data-theme="light"] {')
        end = SOURCE.index("@media (prefers-color-scheme: dark)", start)
    elif kind == "media-dark":
        start = SOURCE.index("@media (prefers-color-scheme: dark)")
        end = SOURCE.index(':root[data-theme="dark"]', start)
    elif kind == "attr-dark":
        start = SOURCE.index(':root[data-theme="dark"]')
        end = SOURCE.index("\n    }", start)
    else:
        raise AssertionError(kind)
    return SOURCE[start:end]


def _token_hex(block, token):
    matches = re.findall(rf"{re.escape(token)}:\s*(#[0-9A-Fa-f]{{6}})", block)
    assert len(matches) == 1, f"{token} must be defined exactly once per theme block, found {matches!r}"
    return matches[0]


def _contrast_ratio(fg, bg):
    def lum(h):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

        def f(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    hi, lo = max(lum(fg), lum(bg)), min(lum(fg), lum(bg))
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------------------
# Every status token has a light AND a dark variant (HIG §4)
# ---------------------------------------------------------------------------

def test_status_tokens_defined_in_all_theme_blocks():
    blocks = {kind: _theme_block(kind) for kind in ("light", "media-dark", "attr-dark")}
    for token in TOKENS:
        hexes = {kind: _token_hex(block, token) for kind, block in blocks.items()}
        # Light and dark must differ: a copy-paste of the light value would be
        # the exact bug this issue is about.
        assert hexes["light"] != hexes["media-dark"], f"{token} has no dark variant in the media block"
        assert hexes["light"] != hexes["attr-dark"], f"{token} has no dark variant in the data-theme block"
        # Both dark blocks must agree (the app declares them in both).
        assert hexes["media-dark"] == hexes["attr-dark"], f"{token} dark variants disagree between blocks"


# ---------------------------------------------------------------------------
# Consumers reference the tokens; no hard-coded status hex survives
# ---------------------------------------------------------------------------

def test_consumers_use_semantic_tokens():
    css = SOURCE
    assert re.search(r"\.pill-ok\s*\{[^}]*var\(--ok\)", css), ".pill-ok must use var(--ok)"
    assert re.search(r"\.pill-bad\s*\{[^}]*var\(--bad\)", css), ".pill-bad must use var(--bad)"
    assert re.search(r"\.step-done\s*\{[^}]*var\(--ok-text\)", css), ".step-done must use var(--ok-text)"
    assert re.search(r"\.banner-error\s*\{[^}]*var\(--bad\)", css), ".banner-error must use var(--bad)"
    assert "Studio Server Stopped" in css
    assert re.search(
        r"color:\s*var\(--bad-text\)[^>]*>🛑 Studio Server Stopped", css
    ), "Stopped heading must use var(--bad-text)"


def test_no_hard_coded_status_hex_outside_token_definitions():
    css_lines = SOURCE.splitlines()
    for i, line in enumerate(css_lines, start=1):
        lowered = line.lower()
        for hx in LEGACY_HEXES:
            if hx in lowered:
                assert re.search(rf"--(ok|bad|ok-text|bad-text):\s*{re.escape(hx)}", lowered), (
                    f"app.py:{i}: hard-coded status color {hx} survives outside a token definition"
                )


# ---------------------------------------------------------------------------
# Contrast: HIG minimum 4.5:1 for every token/background pair in use
# ---------------------------------------------------------------------------

def test_solid_status_fills_keep_white_text_contrast():
    light, dark = _theme_block("light"), _theme_block("attr-dark")
    for theme, block in (("light", light), ("dark", dark)):
        ok, bad = _token_hex(block, "--ok"), _token_hex(block, "--bad")
        assert _contrast_ratio("#ffffff", ok) >= 4.5, f"--ok ({theme}) white-text contrast"
        assert _contrast_ratio("#ffffff", bad) >= 4.5, f"--bad ({theme}) white-text contrast"


def test_status_text_colors_meet_contrast_on_both_themes():
    light, dark = _theme_block("light"), _theme_block("attr-dark")
    ok_l, ok_d = _token_hex(light, "--ok-text"), _token_hex(dark, "--ok-text")
    bad_l, bad_d = _token_hex(light, "--bad-text"), _token_hex(dark, "--bad-text")
    assert _contrast_ratio(ok_l, LIGHT_BG_PRIMARY) >= 4.5
    assert _contrast_ratio(ok_d, DARK_BG_PRIMARY) >= 4.5
    assert _contrast_ratio(ok_d, DARK_BG_SECONDARY) >= 4.5
    assert _contrast_ratio(bad_l, LIGHT_BG_SECONDARY) >= 4.5
    assert _contrast_ratio(bad_d, DARK_BG_PRIMARY) >= 4.5
    assert _contrast_ratio(bad_d, DARK_BG_SECONDARY) >= 4.5
