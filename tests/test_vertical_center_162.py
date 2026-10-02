"""v1.6.2 (#162) — all section row components vertically center content.

``_render_title_row``, ``_render_images_row`` and (since #303) the
``_render_hashtags_panel`` / ``_render_news_links_panel`` header and row
columns must each pass ``vertical_alignment="center"`` to their
``st.columns()`` call, so the section title and controls/rows are
vertically centered relative to each other (Streamlit columns
top-align by default).

These tests drive each component with the recording fake streamlit and
assert the vertical_alignment contract. Visual verification (screenshots
of the real Streamlit render) was done separately during development.

Run: python -m pytest tests/test_vertical_center_162.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from test_library_v15 import libdir  # noqa: F401  (pytest fixture reuse)
from test_one_row_toolbar_v16 import (  # noqa: E402
    _ui_with_recording_st,
)


_LINKS = [
    {"title": "Alpha headline", "source": "Alpha",
     "url": "https://a.example/story-1"},
]


def _assert_single_centered_row(fake, name):
    assert len(fake.column_specs) == 1, (
        f"{name} must render exactly one columns() row; "
        f"saw {len(fake.column_specs)}")
    assert fake.column_valigns == ["center"], (
        f"{name} must pass vertical_alignment='center'; "
        f"saw {fake.column_valigns}")


def test_title_row_is_vertically_centered(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_title_row("sid1", "My Title", editing=False, busy=False)
    _assert_single_centered_row(fake, "_render_title_row")


def test_hashtags_panel_is_vertically_centered(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_hashtags_panel(
        story_id="sid1", tags=["#Alpha", "#Beta"], busy_kinds=set(),
        ai_engine="Dummy")
    # header [10, 1, 1] + one [11, 1] per row: all vertically centered
    assert fake.column_specs, "panel must render columns"
    assert all(v == "center" for v in fake.column_valigns), (
        f"panel header and rows must pass vertical_alignment='center'; "
        f"saw {fake.column_valigns}")


def test_news_links_panel_is_vertically_centered(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_news_links_panel(
        story_id="sid1", links=_LINKS, busy_kinds=set())
    assert fake.column_specs, "panel must render columns"
    assert all(v == "center" for v in fake.column_valigns), (
        f"panel header and rows must pass vertical_alignment='center'; "
        f"saw {fake.column_valigns}")


def test_images_row_is_vertically_centered(libdir):
    lui, fake = _ui_with_recording_st()
    lui._render_images_row("sid1", ["https://img.example/a.jpg"], [], set())
    _assert_single_centered_row(fake, "_render_images_row")


def test_upload_trigger_has_no_row_to_center(libdir):
    """The standalone Upload row is gone — the toolbar trigger renders no
    columns row, so there is nothing to vertically center. (It inherits
    the detail toolbar's vertical centering.)"""
    lui, fake = _ui_with_recording_st()
    lui._render_upload_popover_trigger("sid1")
    assert fake.column_specs == [], (
        f"upload trigger must render no columns() row; "
        f"saw {fake.column_specs}")
