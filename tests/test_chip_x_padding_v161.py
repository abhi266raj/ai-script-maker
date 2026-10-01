"""v1.6.1 (#68) — hashtag/news-link chip × overlaps the label.

Root cause: #51 moved the × clearance into the pill's own
``padding-right: 34px`` (22px target + 6px inset + 6px breathing room),
but the selector used a DESCENDANT combinator after the marker's
``stElementContainer`` — while the real DOM (verified, and used by every
other marker-scoped rule in this block) has the marker container as an
ADJACENT SIBLING of ``stLayoutWrapper > stHorizontalBlock``. The rule
never matched, so the pill kept only the base 12px right padding and the
× — positioned 6px from the column's trailing edge, and the column hugs
the pill after #56's fit-content caps — landed on top of the label's
last characters (``#NiftyFall×``).

The fix: the two ``.lib-chip`` rules (pill clearance + news-link color)
use the same adjacent-sibling form as every other rule in the block.
These tests pin the selector shape so a future edit can't silently
reintroduce a non-matching combinator — the earlier tests only asserted
the declaration text, which is why #68 slipped through.

Run: python -m pytest tests/test_chip_x_padding_v161.py -q
"""
import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _capture_library_css():
    """Import library_ui with a capturing streamlit stub; return the
    emitted <style> HTML and the loaded module."""
    saved = dict(sys.modules)
    chunks = []
    try:
        fake_mod = types.ModuleType("streamlit")
        fake_mod.markdown = lambda *a, **k: chunks.append(a[0] if a else "")
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui as lui
        lui.inject_library_css()
        return "\n".join(chunks), lui
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _marker_scoped_selector(css: str, tail: str) -> str:
    """Return the normalized selector of the marker-scoped rule whose
    selector ends with ``tail`` (e.g. ``.lib-chip``), or raise loudly."""
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # comments lie
    for m in re.finditer(r"([^{}]+?" + re.escape(tail) + r")\s*\{", clean):
        sel = " ".join(m.group(1).split())
        if "lib-hscroll" in sel:
            return sel
    raise AssertionError(f"no marker-scoped CSS rule found for {tail!r}")


def _css_no_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


# ---------------------------------------------------------------------------
# #68 — the pill clearance selector must match the real DOM
# ---------------------------------------------------------------------------

def test_chip_clearance_uses_sibling_combinator():
    """The 34px padding-right rule must use the adjacent-sibling form
    (marker container + stLayoutWrapper > stHorizontalBlock), exactly
    like every other marker-scoped rule in the block. A descendant
    combinator never matches the real DOM — that was #68."""
    css, _ = _capture_library_css()
    sel = _marker_scoped_selector(css, ".lib-chip")
    assert "+ div" in sel and "stLayoutWrapper" in sel, \
        f"chip clearance rule does not use the sibling combinator: {sel!r}"
    assert "padding-right: 34px !important;" in css


def test_chip_clearance_descendant_form_is_gone():
    """The exact broken shape from #68 — marker container directly
    followed (descendant, no +) by stHorizontalBlock — must not appear
    in any real selector."""
    css, _ = _capture_library_css()
    broken = (
        '[data-marker="lib-hscroll"])\n'
        '        [data-testid="stHorizontalBlock"]'
    )
    assert broken not in _css_no_comments(css), \
        "descendant-combinator chip selector still present (the #68 bug)"


def test_chip_link_color_uses_sibling_combinator():
    """News-link chips share the pill styling; their themed link-color
    rule had the same non-matching descendant selector and is fixed in
    the same way."""
    css, _ = _capture_library_css()
    sel = _marker_scoped_selector(css, ".lib-chip a")
    assert "+ div" in sel and "stLayoutWrapper" in sel, \
        f"chip link-color rule does not use the sibling combinator: {sel!r}"


def test_chip_x_target_still_inside_pill():
    """The #51 design contract is unchanged: the × stays a token-field
    glyph centered in the pill (6px inset), and the pill's own padding
    carries the clearance — the column must not reserve × padding again."""
    css, _ = _capture_library_css()
    assert "padding-right: 30px" not in css, \
        "stale column-padding × reservation reintroduced"
    # 34px = 22px target + 6px inset + 6px breathing room.
    assert "padding-right: 34px !important;" in css
    assert "right: 6px !important;" in css
