"""v1.6 (#51) — chip × redesigned as a macOS token-field remove glyph.

The 22px overlay × was pinned top-right of the chip column like an
image-card corner button: cramped against the label, dim, not reading as
tappable. It is now vertically centered inside the pill, with a crisp
glyph (transparent, no blur bubble): chip-text color at 65% opacity
idle, full opacity + subtle circle on hover.

Image cards keep their inset top-right × over the image corner and the
✎ edit button is untouched — both are excluded by the :has(.lib-chip) /
lib-x-r scoping.

Run: python -m pytest tests/test_chip_cross_v16.py -q
"""
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


def _chip_x_block(css, suffix):
    """Return the declaration block of the chip-scoped × rule whose
    selector ends with `suffix` (container, button, or button:hover)."""
    # #134: the chip × scope covers .lib-chip AND stLinkButton columns
    # (news links are native link buttons now).
    anchor = ('div[data-testid="stColumn"]:has(.lib-chip, [data-testid="stLinkButton"]):has([data-marker="lib-x-r"])\n'
              '        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])\n'
              '        + div[data-testid="stElementContainer"]' + suffix + " {")
    assert anchor in css, f"chip × {suffix or 'container'} rule missing"
    return css.split(anchor, 1)[1].split("}", 1)[0]


# ---------------------------------------------------------------------------
# Centering: the × floats inside the pill, vertically centered
# ---------------------------------------------------------------------------

def test_chip_x_vertically_centered_in_pill():
    css = _capture_library_css()
    assert css.count("{") == css.count("}")
    block = _chip_x_block(css, "")
    for needle in ("top: 50% !important;",
                   "transform: translateY(-50%) !important;",
                   "right: 6px !important;"):
        assert needle in block, needle


def test_chip_x_centering_is_chip_scoped():
    """The centering must require BOTH :has(.lib-chip) and the lib-x-r
    marker — image-card columns (no .lib-chip) and the ✎ (lib-x-l) never
    match."""
    import re
    css = _capture_library_css()
    # Strip /* … */ comments so prose can't trip the selector check.
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # No chip-scoped selector mentions lib-x-l: the ✎ keeps its own rule.
    # (#134: the chip scope is :has(.lib-chip, [data-testid="stLinkButton"]).)
    for line in bare.splitlines():
        if ":has(.lib-chip" in line:
            assert "lib-x-l" not in line


# ---------------------------------------------------------------------------
# Glyph: crisp token-field remove — transparent, chip-text, 65% idle
# ---------------------------------------------------------------------------

def test_chip_x_glyph_idle_style():
    css = _capture_library_css()
    block = _chip_x_block(css, ' [data-testid="stButton"] button')
    for needle in ("background: transparent !important;",
                   "backdrop-filter: none !important;",
                   "box-shadow: none !important;",
                   "border: none !important;",
                   "color: var(--lib-chip-text) !important;",
                   "opacity: 0.65 !important;"):
        assert needle in block, needle


def test_chip_x_glyph_hover_style():
    """Hover: full opacity + a subtle circle behind the glyph (the
    999px radius comes from the generic rule)."""
    css = _capture_library_css()
    block = _chip_x_block(css, ' [data-testid="stButton"] button:hover')
    for needle in ("opacity: 1 !important;",
                   "background: rgba(128, 128, 128, 0.22) !important;",
                   "color: var(--lib-chip-text) !important;"):
        assert needle in block, needle


def test_chip_x_rules_never_force_svg_paint():
    """No global SVG fill/stroke forcing anywhere in the injected CSS —
    Streamlit's icons must keep their own paint."""
    css = _capture_library_css()
    assert "svg" not in css.lower()


# ---------------------------------------------------------------------------
# Untouched: image-card corner × and ✎ keep their rules
# ---------------------------------------------------------------------------

def test_image_card_x_rules_untouched():
    """The generic × rules (top-right corner float, blur bubble) survive
    verbatim for image cards — the chip overrides are strictly more
    specific and additive."""
    css = _capture_library_css()
    generic_anchor = ('div[data-testid="stColumn"]:has([data-marker="lib-x-r"])\n'
                      '        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])\n'
                      '        + div[data-testid="stElementContainer"] {')
    assert generic_anchor in css
    generic_block = css.split(generic_anchor, 1)[1].split("}", 1)[0]
    for needle in ("top: 4px !important;", "right: 4px !important;",
                   "z-index: 10 !important;"):
        assert needle in generic_block, needle
    # The blur-bubble button styling survives for image cards.
    assert "backdrop-filter: blur(6px) !important;" in css


def test_edit_button_rule_untouched():
    """The ✎ (lib-x-l) top-left rule is unchanged."""
    css = _capture_library_css()
    anchor = ('div[data-testid="stColumn"]:has([data-marker="lib-x-l"])\n'
              '        div[data-testid="stElementContainer"]:has([data-marker="lib-x-l"])\n'
              '        + div[data-testid="stElementContainer"] {')
    assert anchor in css
    block = css.split(anchor, 1)[1].split("}", 1)[0]
    for needle in ("top: 4px !important;", "left: 4px !important;"):
        assert needle in block, needle


# ---------------------------------------------------------------------------
# #45 chip colors + #25/#26 no-truncation guarantees preserved
# ---------------------------------------------------------------------------

def test_chip_theme_colors_preserved():
    """#45: both themes keep their chip bg/text/border tokens, which the
    × glyph reuses via var(--lib-chip-text)."""
    css = _capture_library_css()
    for needle in ("--lib-chip-bg: #F0E7D5;", "--lib-chip-text: #5A4227;",
                   "--lib-chip-bg: #4A4034;", "--lib-chip-text: #F2E4C2;"):
        assert needle in css, needle


def test_chip_no_truncation_guarantee_preserved():
    """#25/#26: chips stay single-line with ellipsis; the label clears the
    × via the pill's own 44px padding-right (#68 follow-up)."""
    css = _capture_library_css()
    for needle in ("white-space: nowrap !important;",
                   "text-overflow: ellipsis;",
                   "padding-right: 44px !important;"):
        assert needle in css, needle
