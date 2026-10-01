"""v1.6 (#25/#26, redesigned by #51) — chip × truncation fixes in the
Library story detail.

#25: hashtag chips cut tag text off under the × overlay button.
#51 redesign: the × is now a macOS token-field remove glyph centered
INSIDE the pill (22px at 6px from the pill's trailing edge), so the ×
clearance lives in the chip's own padding-right (34px = 22px target +
6px inset + 6px breathing room) — tag text can never slide underneath
it, regardless of chip width.

#26: news-link chips had the same × truncation, and their label was the
full headline ("title (source)"). The chip now shows the source website
name when known; the headline stays available as the link tooltip.

Run: python -m pytest tests/test_chip_truncation_v16.py -q
"""
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


# ---------------------------------------------------------------------------
# #25 — × clearance lives in the chip's own padding (#51 redesign)
# ---------------------------------------------------------------------------

def test_chip_column_no_longer_reserves_x_clearance():
    """#51 redesign: the × moved INSIDE the pill (token-field glyph), so
    the chip column no longer reserves 30px of padding for it — that
    dead space after every chip is gone. The clearance now lives in the
    chip's own padding-right (see below)."""
    css, _ = _capture_library_css()
    assert css.count("{") == css.count("}")
    assert "padding-right: 30px" not in css, \
        "stale column-padding × reservation still present"


def test_chip_x_rules_are_chip_scoped():
    """The chip × centering/glyph rules must only hit columns holding a
    chip — the :has(.lib-chip) scope is what keeps image-card columns on
    their inset top-right × over the image corner."""
    css, _ = _capture_library_css()
    assert 'div[data-testid="stColumn"]:has(.lib-chip):has([data-marker="lib-x-r"])' in css
    # No blanket × restyle that would also hit image cards.
    assert 'div[data-testid="stColumn"]:has([data-marker="lib-x-r"])\n' \
        '        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])\n' \
        '        + div[data-testid="stElementContainer"] {\n' \
        '        top: 50%' not in css


def test_chip_own_padding_clears_x_target():
    """The pill's own padding-right must clear the 22px × target sitting
    6px inside the pill edge: 34px = 22px + 6px inset + 6px breathing
    room — tag text can never slide underneath the ×. This is the
    #25/#26 no-truncation guarantee under the #51 design."""
    css, _ = _capture_library_css()
    assert "padding-right: 34px !important;" in css


def test_image_card_x_overlay_unchanged():
    """The image-card × overlay behavior itself is unchanged: absolute,
    top-right corner of the column, above content — the generic rule the
    chip-scoped #51 rules override only for chip columns."""
    css, _ = _capture_library_css()
    for needle in ("position: absolute", "z-index: 10", "top: 4px",
                   "right: 4px"):
        assert needle in css, needle


# ---------------------------------------------------------------------------
# #26 — news-link chip label prefers the source site name
# ---------------------------------------------------------------------------

def test_news_chip_label_prefers_source():
    _, lui = _capture_library_css()
    assert lui._news_chip_label("Big Long Headline Here", "The Times of India") \
        == "The Times of India"


def test_news_chip_label_falls_back_to_title():
    _, lui = _capture_library_css()
    assert lui._news_chip_label("Big Long Headline Here", "") \
        == "Big Long Headline Here"
    assert lui._news_chip_label("Big Long Headline Here", "   ") \
        == "Big Long Headline Here"


def test_news_chip_label_never_empty():
    _, lui = _capture_library_css()
    assert lui._news_chip_label("", "") == "News link"
    assert lui._news_chip_label(None, None) == "News link"
    assert lui._news_chip_label("  ", "  ") == "News link"


def test_news_chip_label_strips_whitespace():
    _, lui = _capture_library_css()
    assert lui._news_chip_label("  Headline  ", "  NDTV  ") == "NDTV"
