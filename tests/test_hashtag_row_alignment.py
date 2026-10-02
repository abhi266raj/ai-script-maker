"""Hashtag-row alignment contract — the "Hashtags" label + chips row.

The user reported (screenshot, 2026-10-02) that the row's alignment and
font sizing kept breaking: the "Hashtags" title rendered at 15px while
the chips were 13px, and the two never shared a baseline. Previous fixes
(#51, #56, #68, #112, #162) each patched one symptom through the fragile
column-stretch selector chain, so the row regressed again and again.

The contract, locked here:
1. The inline title (.lib-section-inline) shares the chip's EXACT font
   system — 13px/600 — so the label can never again render larger than
   its chips.
2. The title shares the chip's EXACT box — inline-flex, align-items
   center, min-height: var(--lib-chip-h), border-box — so title and chips
   are pixel-identical 30px boxes on one baseline. No column-stretch
   fragility.
3. st.markdown wraps inline <span> html in a <p> (block <div> html is
   not wrapped): the chip cell is stMarkdownContainer > p > span.lib-chip
   while the title cell has no <p>. The <p>'s own margins pushed the pill
   down inside its column — zeroed inside scroll rows.
4. The scroll row itself vertically centers its columns
   (align-items: center), backing Streamlit's vertical_alignment="center".

Tests 1–3 FAIL on the pre-fix CSS (verified by stashing the fix);
test 4 is a contract guard that must keep passing.

Run: python -m pytest tests/test_hashtag_row_alignment.py -q
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


def _exact_rule_body(css: str, selector: str):
    """Body of the rule whose selector is EXACTLY ``selector`` (after
    comment stripping + whitespace normalization), or None."""
    want = " ".join(selector.split())
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", _css_no_comments(css)):
        if " ".join(m.group(1).split()) == want:
            return m.group(2)
    return None


def _normalized(s: str) -> str:
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# 1. One font system: inline title == chips (13px/600)
# ---------------------------------------------------------------------------

def test_inline_title_matches_chip_font_size():
    """The "Hashtags"/"News Links" inline title must declare the chip's
    exact font-size (13px) — it previously inherited 15px from
    .lib-section and rendered visibly larger than its chips."""
    css, _ = _capture_library_css()
    title_body = _exact_rule_body(css, ".lib-section-inline")
    assert title_body is not None, "no exact .lib-section-inline rule"
    chip_body = _exact_rule_body(css, ".lib-chip")
    assert chip_body is not None, "no exact .lib-chip rule"
    assert "font-size: 13px !important;" in _normalized(title_body), \
        "inline title lost the 13px chip font-size (regression: title renders larger than chips)"
    assert "font-size: 13px;" in _normalized(chip_body), \
        "chip font-size changed — the shared 13px contract moved"


def test_inline_title_matches_chip_font_weight():
    """"Hashtags" label and chips share font-weight 600 — one typographic
    voice for the row."""
    css, _ = _capture_library_css()
    title_body = _exact_rule_body(css, ".lib-section-inline")
    assert title_body is not None, "no exact .lib-section-inline rule"
    norm = _normalized(title_body)
    assert "font-weight: 600 !important;" in norm, \
        "inline title lost font-weight 600"


# ---------------------------------------------------------------------------
# 2. One box: title is a 30px inline-flex box exactly like the chip
# ---------------------------------------------------------------------------

def test_inline_title_shares_chip_box():
    """The title must be a self-centering 30px box (inline-flex +
    align-items center + min-height: var(--lib-chip-h) + border-box) —
    pixel-identical to the chip, so both sit on one baseline without
    the old fragile column-stretch centering chain."""
    css, _ = _capture_library_css()
    title_body = _exact_rule_body(css, ".lib-section-inline")
    assert title_body is not None, "no exact .lib-section-inline rule"
    norm = _normalized(title_body)
    for decl in ("display: inline-flex !important;",
                 "align-items: center !important;",
                 "min-height: var(--lib-chip-h) !important;",
                 "box-sizing: border-box !important;"):
        assert decl in norm, \
            f"inline title lost {decl!r} — the shared 30px box contract broke"


# ---------------------------------------------------------------------------
# 3. The markdown <p> wrapper must not push the pill down
# ---------------------------------------------------------------------------

def test_markdown_paragraph_margins_zeroed_in_scroll_rows():
    """st.markdown wraps the chip's inline <span> in a <p> (the title's
    block <div> is not wrapped). The <p>'s own margins offset the pill
    downward — a marker-scoped rule must zero them inside scroll rows."""
    css, _ = _capture_library_css()
    clean = _css_no_comments(css)
    found = False
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
        sel, body = _normalized(m.group(1)), _normalized(m.group(2))
        if 'stMarkdownContainer' in sel and sel.rstrip().endswith("p") \
                and "lib-hscroll" in sel \
                and "margin: 0 !important;" in body:
            found = True
            break
    assert found, \
        "no marker-scoped stMarkdownContainer p { margin: 0 } rule — the <p> wrapper will offset chips"


# ---------------------------------------------------------------------------
# 4. Row-level vertical centering (contract guard)
# ---------------------------------------------------------------------------

def test_scroll_row_centers_columns():
    """The hscroll row keeps align-items: center — backs Streamlit's
    vertical_alignment="center" so a missed kwarg can never top-align
    the row again."""
    css, _ = _capture_library_css()
    clean = _css_no_comments(css)
    found = False
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
        sel, body = _normalized(m.group(1)), _normalized(m.group(2))
        if 'data-marker="lib-hscroll"' in sel \
                and 'data-testid="stHorizontalBlock"' in sel \
                and "align-items: center !important;" in body:
            # the row rule itself, not a descendant rule
            if "stColumn" not in sel and ".lib-chip" not in sel \
                    and "stMarkdownContainer" not in sel:
                found = True
                break
    assert found, "scroll row lost align-items: center"
