"""v1.6 (#25/#26) — chip × truncation fixes in the Library story detail.

#25: hashtag chips cut tag text off under the × overlay button. The ×
clearance now lives in the chip COLUMN's own padding (30px), so the ×
(22px at right:4px of the column) floats 4px clear of the chip edge and
tag text can never slide underneath it — regardless of chip width.

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
# #25 — × clearance lives in the chip column's padding
# ---------------------------------------------------------------------------

def test_chip_column_reserves_x_clearance():
    """The × overlay is absolutely positioned at right:4px of the COLUMN
    (22px diameter). Chip columns must reserve that clearance in the
    column's own padding so tag text can never slide under the button —
    independent of the chip's width or its own padding."""
    css, _ = _capture_library_css()
    assert css.count("{") == css.count("}")
    rule = ('div[data-testid="stColumn"]:has(.lib-chip) {')
    assert rule in css, "chip-column padding rule missing"
    assert "padding-right: 30px !important;" in css


def test_chip_column_rule_is_chip_scoped():
    """The column padding must only hit columns holding a chip — image
    cards keep their inset × over the image corner."""
    css, _ = _capture_library_css()
    # The :has(.lib-chip) scope is what keeps image-card columns out.
    assert 'div[data-testid="stColumn"]:has(.lib-chip)' in css
    # No blanket column padding that would shrink image cards.
    assert 'div[data-testid="stColumn"] {\n        padding-right' not in css


def test_chip_own_padding_back_to_base():
    """The chip itself no longer carries the × clearance (that was the
    fragile 26px that the real render defeated); it keeps the base 12px
    so the label has breathing room before the chip edge."""
    css, _ = _capture_library_css()
    assert "padding-right: 26px" not in css, \
        "stale chip-internal × clearance still present"
    assert "padding-right: 12px !important;" in css


def test_x_overlay_still_pins_to_column_corner():
    """The × overlay behavior itself is unchanged: absolute, top-right of
    the column, above content."""
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
