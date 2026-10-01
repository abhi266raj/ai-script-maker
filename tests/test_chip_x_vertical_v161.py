"""v1.6.1 (#68 follow-up) — chip × is bottom-aligned in the pill.

The user's dark-mode screenshot showed the × hugging the BOTTOM edge of
hashtag pills (``#GurugramMetroRelief``, ``#MetroPhase2Gurgaon``) instead
of sitting vertically centered.

Root cause: the ``lib-x-r``/``lib-x-l`` marker divs are ``display:none``
themselves, but their ``stElementContainer`` wrapper still occupies one
inter-element gap in the column's vertical block — the exact #24 / #53
pattern (those fixes collapsed ``lib-danger-`` / ``lib-spin-`` marker
wrappers but left ``lib-x-`` untouched). The column becomes taller than
the pill, so the chip × — ``top: 50%`` + ``translateY(-50%)`` of the
COLUMN — lands BELOW the pill's vertical center.

The fix collapses the marker wrapper (sibling selectors keep matching on
DOM order) and, per the user's explicit follow-up ("add more space for
cross"), grows the pill clearance 34px → 44px (22px target + 6px inset +
16px breathing room).

These tests pin both. The two bug-specific tests (wrapper collapse,
44px clearance) fail on the pre-fix CSS — verified against a pristine
``origin/develop`` tree. The other two are contract-preservation guards
(centering declarations, image-card pinning) that must keep passing.

Run: python -m pytest tests/test_chip_x_vertical_v161.py -q
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


def _rule_bodies(css: str, needle: str):
    """All rule bodies whose selector contains ``needle`` (no comments)."""
    clean = _css_no_comments(css)
    return [
        m.group(2)
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean)
        if needle in m.group(1)
    ]


def _normalized(s: str) -> str:
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# #68 follow-up — the × must be vertically centered in the pill
# ---------------------------------------------------------------------------

def test_x_marker_wrapper_collapses():
    """The lib-x- marker's stElementContainer wrapper must not occupy
    vertical space (the #24/#53 pattern). Without this, the column is
    taller than the pill and the × (top: 50% of the COLUMN) renders
    bottom-aligned — the bug in the user's screenshot."""
    css, _ = _capture_library_css()
    bodies = _rule_bodies(css, '[data-marker^="lib-x-"]')
    collapse = [b for b in bodies if "display: none !important;" in b]
    assert collapse, (
        "no rule collapses the lib-x- marker wrapper — the × will render "
        "bottom-aligned (the #68 follow-up bug)"
    )
    # The collapse rule must be marker-scoped with the sibling combinator
    # (it must actually match the real DOM), not a global rule.
    clean = _css_no_comments(css)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
        if "display: none !important;" in m.group(2) \
                and '[data-marker^="lib-x-"]' in m.group(1):
            sel = _normalized(m.group(1))
            assert "+ div" in sel and "lib-hscroll" in sel, \
                f"marker-wrapper collapse rule is not marker-scoped: {sel!r}"
            return
    raise AssertionError("collapse rule exists but is not marker-scoped")


def test_chip_x_vertical_centering_declarations():
    """The chip × rule keeps the #51 vertical-centering contract:
    top: 50% + translateY(-50%), scoped to columns holding a chip.
    #134: the scope is :has(.lib-chip, [data-testid="stLinkButton"])."""
    css, _ = _capture_library_css()
    clean = _css_no_comments(css)
    found = False
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
        sel, body = m.group(1), m.group(2)
        if ":has(.lib-chip" in sel and "lib-x-r" in sel \
                and "top: 50% !important;" in body \
                and "translateY(-50%) !important;" in body:
            found = True
            assert "right: 6px !important;" in body, \
                "chip × lost its 6px trailing inset"
            break
    assert found, "chip × vertical-centering rule missing or broken"


def test_chip_clearance_is_44px():
    """#68 follow-up: the user asked for MORE space for the × —
    44px = 22px target + 6px inset + 16px breathing room. The old 34px
    contract is gone."""
    css, _ = _capture_library_css()
    assert "padding-right: 44px !important;" in css
    assert "padding-right: 34px !important;" not in css, \
        "stale 34px × clearance reintroduced"


def test_image_card_x_overlay_still_top_pinned():
    """Image-card ×/✎ overlays are untouched: still pinned to the top
    corners (top: 4px), not recentered by the chip fix."""
    css, _ = _capture_library_css()
    clean = _css_no_comments(css)
    top_pinned = False
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
        sel, body = m.group(1), m.group(2)
        # generic (non-chip-scoped) × rule: top: 4px, no .lib-chip :has.
        # (#134: chip scope is :has(.lib-chip, ...).)
        if "lib-x-r" in sel and ":has(.lib-chip" not in sel \
                and "top: 4px !important;" in body:
            top_pinned = True
            break
    assert top_pinned, "image-card × lost its top-corner pinning"


def test_story_title_hides_heading_anchor_link_icon():
    """#68 follow-up: no 🔗 link icon on the story title.

    The user's dark-mode screenshot showed Streamlit's heading-anchor link
    icon after the story title. Streamlit appends that anchor to h1–h6
    rendered through st.markdown — including the legacy raw-HTML
    <h2 class="lib-doc-title"> title. #60 replaced the h2 with the glyph +
    popover, so this rule is belt-and-braces, but the icon must never come
    back on any title render path.
    """
    css, _ = _capture_library_css()
    bodies = _rule_bodies(css, ".lib-doc-title a")
    assert bodies, "no .lib-doc-title anchor rule in library CSS"
    assert any("display: none !important;" in _normalized(b) for b in bodies), \
        "story-title heading anchor is not hidden"
