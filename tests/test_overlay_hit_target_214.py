"""#214 — 22px hit targets on ×/✎ overlay buttons (HIG §2: 44pt minimum).

The × remove buttons on news links, hashtags, fetched/uploaded images
and the ✎ address-editor button were hard-sized to 22×22px
(--lib-x-size) — and most of them perform destructive removes.

The fix keeps the visible 22px glyph (--lib-x-size) and pads the
tappable area out to 44×44 (--lib-x-hit) with a transparent ::after on
the button itself. Because the ::after is part of the <button> element,
clicks anywhere in the 44×44 box hit the button; the button keeps its
22px box and position, so no row geometry, chip padding, or corner
position moves.

These tests pin:
  * the --lib-x-hit: 44px token exists;
  * the generic marker-scoped overlay-button rule carries a
    button::after with -11px on all four sides
    (22 + 2×11 = 44px hit area);
  * the button keeps its 22px visual box (glyph unchanged) plus the
    position:relative / overflow:visible guards the ::after needs
    (overflow:hidden would silently clip the hit area back to 22px);
  * the chip-scoped × override does not cancel the ::after or its
    guards (it only restyles the glyph).

Run: python -m pytest tests/test_overlay_hit_target_214.py -q
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


def _css_no_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule_block(css: str, selector_tail: str) -> str:
    """Return the declaration block of the marker-scoped overlay rule
    whose selector ends with ``selector_tail`` (e.g.
    ``[data-testid="stButton"] button::after``), or raise loudly."""
    clean = _css_no_comments(css)
    for m in re.finditer(
        r"([^{}]+?" + re.escape(selector_tail) + r")\s*\{([^{}]*)\}", clean
    ):
        sel = " ".join(m.group(1).split())
        if "lib-hscroll" in sel and "lib-x-" in sel:
            return m.group(2)
    raise AssertionError(
        f"no marker-scoped overlay CSS rule found for {selector_tail!r}"
    )


# ---------------------------------------------------------------------------
# #214 — hit target tokens and ::after expansion
# ---------------------------------------------------------------------------

def test_hit_token_is_44px():
    """--lib-x-hit declares the HIG §2 minimum 44pt hit region."""
    css, _ = _capture_library_css()
    assert "--lib-x-hit: 44px" in css, \
        "overlay hit-area token --lib-x-hit: 44px missing"


def test_glyph_stays_22px():
    """The visible glyph box must remain 22px — the fix expands the hit
    area, not the glyph."""
    css, _ = _capture_library_css()
    assert "--lib-x-size: 22px" in css, \
        "glyph token --lib-x-size: 22px missing"
    block = _rule_block(css, '[data-testid="stButton"] button')
    assert "width: var(--lib-x-size) !important;" in block, \
        "overlay button box no longer uses the 22px glyph token"
    assert "height: var(--lib-x-size) !important;" in block


def test_after_expands_hit_area_to_44px():
    """The transparent ::after pads the tappable area to 44×44:
    (44 − 22) / 2 = 11px on every side."""
    css, _ = _capture_library_css()
    block = _rule_block(css, '[data-testid="stButton"] button::after')
    for side, decl in (
        ("top", "top: -11px !important;"),
        ("right", "right: -11px !important;"),
        ("bottom", "bottom: -11px !important;"),
        ("left", "left: -11px !important;"),
    ):
        assert decl in block, \
            f"::after {side} offset missing — hit area is not 44×44: {block!r}"
    assert 'content: "" !important;' in block, \
        "::after has no content — it generates no hit box"
    assert "position: absolute !important;" in block, \
        "::after must be absolute so it never shifts layout"


def test_button_guards_after_against_clipping():
    """The ::after needs position:relative on the button (its containing
    block) and overflow:visible — an overflow clip would silently shrink
    the hit area back to 22px."""
    css, _ = _capture_library_css()
    block = _rule_block(css, '[data-testid="stButton"] button')
    assert "position: relative !important;" in block, \
        "button lost position:relative — ::after offsets mis-anchor"
    assert "overflow: visible !important;" in block, \
        "button lost overflow:visible — ::after could be clipped to 22px"


def test_no_fixed_22px_button_box_without_expansion():
    """No marker-scoped overlay-button rule may hard-size a tappable
    control to 22px without the ::after expansion present."""
    css, _ = _capture_library_css()
    clean = _css_no_comments(css)
    # Every overlay button box declaration must go through the 22px
    # glyph token (visual) — never a bare 22px width/height on a button.
    for m in re.finditer(
        r"([^{}]+?\[data-testid=\"stButton\"\] button)\s*\{([^{}]*)\}", clean
    ):
        sel = " ".join(m.group(1).split())
        if "lib-hscroll" not in sel or "lib-x-" not in sel:
            continue
        if "::after" in sel:
            continue
        assert "width: 22px" not in m.group(2), \
            f"bare 22px button width without hit expansion: {sel!r}"
        assert "height: 22px" not in m.group(2), \
            f"bare 22px button height without hit expansion: {sel!r}"
    # ...and the expansion itself must exist.
    _rule_block(css, '[data-testid="stButton"] button::after')


def test_chip_variant_keeps_expansion():
    """The chip-scoped × override (transparent token-field glyph)
    restyles the glyph only — it must not reset the ::after, its
    position anchor, or its overflow guard."""
    css, _ = _capture_library_css()
    clean = _css_no_comments(css)
    blocks = []
    for m in re.finditer(
        r"([^{}]+?\[data-testid=\"stButton\"\] button)\s*\{([^{}]*)\}", clean
    ):
        sel = " ".join(m.group(1).split())
        if "lib-hscroll" in sel and ".lib-chip" in sel and "::after" not in sel:
            blocks.append((sel, m.group(2)))
    assert blocks, "chip-scoped × override rule missing"
    for sel, block in blocks:
        for prop in ("position:", "overflow:", "width:", "height:"):
            assert prop not in block, \
                f"chip override cancels the hit-area fix ({prop} in {sel!r})"
        assert "button::after" not in block and "display: none" not in block, \
            f"chip override hides the hit-area ::after: {sel!r}"


def test_overlay_button_docstring_mentions_hit_area():
    """The helper's contract documents the 22px-glyph / 44px-hit split
    so a future reader doesn't 'simplify' the ::after away."""
    _, lui = _capture_library_css()
    doc = lui._overlay_button.__doc__ or ""
    assert "44" in doc and "22px" in doc, \
        "_overlay_button docstring no longer documents the hit-area split"
