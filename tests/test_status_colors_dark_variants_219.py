"""#219 — hard-coded status colors with no dark variant (HIG §4).

Regression test: the status colors used by .pill-ok / .pill-bad / .step-done /
.banner-error / the "Studio Server Stopped" heading must be semantic CSS
custom properties with BOTH a light and a dark variant (custom colors need
light AND dark variants; never hard-coded color values).

Superseded palette (Khabarwaani admin theme, docs/COLOR_PALETTE.md):
  --ok/--ok-text     -> --success  #3F7D58 / #5DAE7F
  --bad/--bad-text   -> --danger   #B3382C / #E5604F
  --warn/--warn-text -> --warning  #A8741A / #D9A441

Contrast values were measured for (fg, bg) with the per-mode --on-accent
text color (#FFFFFF light / #1C1B19 dark):
  --ok light  #3F7D58  on #ffffff : 4.90:1
  --ok dark   #5DAE7F  on #1C1B19 : 6.41:1
  --bad light #B3382C  on #ffffff : 5.97:1
  --bad dark  #E5604F  on #1C1B19 : 5.01:1
  --ok-text light  #3F7D58 on paper light #F5F3EE : 4.42:1 (tier-2 pin)
  --ok-text dark   #5DAE7F on paper dark  #1C1B19 : 6.41:1
  --ok-text dark   #5DAE7F on card  dark  #262522 : 5.71:1
  --bad-text light #B3382C on card  light #FFFFFF : 5.97:1
  --bad-text dark  #E5604F on paper dark  #1C1B19 : 5.01:1
  --bad-text dark  #E5604F on card  dark  #262522 : 4.46:1 (tier-2 pin)

The two sub-4.5 pairs are the user's explicit spec values, pinned at the
>= 3:1 large-text/UI floor in tests/test_theme_palette_contrast.py.

Run: python -m pytest tests/test_status_colors_dark_variants_219.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = Path(__file__).resolve().parent.parent
SOURCE = (REPO / "app.py").read_text()

TOKENS = ("--ok", "--bad", "--ok-text", "--bad-text")
# Hexes from the superseded PR #266 palette — must not appear anywhere
# in app.py outside the token definitions after this fix.
LEGACY_HEXES = ("#1c7c3a", "#c41e3a", "#cf1322", "#2e7d46", "#c9303f",
                "#4fae63", "#f0787f")

LIGHT_BG_PRIMARY = "#F5F3EE"
LIGHT_BG_SECONDARY = "#FFFFFF"
DARK_BG_PRIMARY = "#1C1B19"
DARK_BG_SECONDARY = "#262522"

ON_ACCENT = {"light": "#FFFFFF", "dark": "#1C1B19"}


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


def _raw_block():
    """Return the raw :root palette block (holds --pal-* values)."""
    m = re.search(r":root\s*\{(.*?)\}", SOURCE, re.DOTALL)
    blocks = [b for b in re.findall(r":root\s*\{(.*?)\}", SOURCE, re.DOTALL)
              if "--pal-paper-light" in b]
    assert len(blocks) == 1, "raw palette block not found exactly once"
    return blocks[0]


def _raw_hex(token):
    matches = re.findall(rf"{re.escape(token)}:\s*(#[0-9A-Fa-f]{{6}})", _raw_block())
    assert len(matches) == 1, f"{token} must be defined exactly once in the raw palette, found {matches!r}"
    return matches[0]


def _token_hex(block, token):
    seen = set()
    current, where = token, block
    while True:
        matches = re.findall(rf"{re.escape(current)}:\s*(#[0-9A-Fa-f]{{6}}|var\(--[a-z0-9-]+\))", where)
        assert len(matches) == 1, f"{current} must be defined exactly once, found {matches!r}"
        value = matches[0]
        m = re.fullmatch(r"var\((--[a-z0-9-]+)\)", value)
        if not m:
            return value
        current = m.group(1)
        assert current not in seen, f"var() cycle resolving {token}"
        seen.add(current)
        # semantic tokens live in the theme block; --pal-* raws live in
        # the raw palette block.
        where = block if re.search(rf"{re.escape(current)}\s*:", block) else _raw_block()


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
    allowed_def = re.compile(
        r"--(ok|bad|ok-text|bad-text|warn|warn-text)\s*:"
        r"|--pal-(success|danger|warning)(-tint)?-(light|dark)\s*:"
    )
    for i, line in enumerate(css_lines, start=1):
        lowered = line.lower()
        for hx in LEGACY_HEXES:
            if hx in lowered:
                assert allowed_def.search(lowered), (
                    f"app.py:{i}: hard-coded status color {hx} survives outside a token definition"
                )


# ---------------------------------------------------------------------------
# Contrast: HIG minimum 4.5:1 for solid fills with per-mode --on-accent
# text; text colors follow the honest tiers in
# tests/test_theme_palette_contrast.py
# ---------------------------------------------------------------------------

def test_solid_status_fills_keep_text_contrast():
    light, dark = _theme_block("light"), _theme_block("attr-dark")
    for theme, block, bg in (("light", light, LIGHT_BG_PRIMARY),
                             ("dark", dark, DARK_BG_PRIMARY)):
        ok, bad = _token_hex(block, "--ok"), _token_hex(block, "--bad")
        text = ON_ACCENT[theme]
        assert _contrast_ratio(text, ok) >= 4.5, f"--ok ({theme}) text contrast"
        assert _contrast_ratio(text, bad) >= 4.5, f"--bad ({theme}) text contrast"


def test_status_text_colors_meet_contrast_on_both_themes():
    light, dark = _theme_block("light"), _theme_block("attr-dark")
    ok_l, ok_d = _token_hex(light, "--ok-text"), _token_hex(dark, "--ok-text")
    bad_l, bad_d = _token_hex(light, "--bad-text"), _token_hex(dark, "--bad-text")
    # Sub-4.5 user-spec pairs are tier-2 pins (see
    # tests/test_theme_palette_contrast.py); the rest clear 4.5:1.
    assert _contrast_ratio(ok_l, LIGHT_BG_PRIMARY) >= 3.0
    assert _contrast_ratio(ok_d, DARK_BG_PRIMARY) >= 4.5
    assert _contrast_ratio(ok_d, DARK_BG_SECONDARY) >= 4.5
    assert _contrast_ratio(bad_l, LIGHT_BG_SECONDARY) >= 4.5
    assert _contrast_ratio(bad_d, DARK_BG_PRIMARY) >= 4.5
    assert _contrast_ratio(bad_d, DARK_BG_SECONDARY) >= 3.0
