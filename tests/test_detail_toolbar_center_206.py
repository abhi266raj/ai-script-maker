"""#206 — the story-detail toolbar and the title-edit toolbar must pass
``vertical_alignment="center"`` to their ``st.columns()`` call, like every
other row component (HIG §1 alignment: icon buttons vs popover triggers
must not sit 1–2px off from each other).

These tests drive ``_render_story_detail`` in both modes with the recording
fake streamlit and assert the toolbar ``columns()`` row is vertically
centered. Sub-pixel visual confirmation on real Streamlit still needs a Mac
screenshot — these tests lock the code contract.

Run: python -m pytest tests/test_detail_toolbar_center_206.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_one_row_toolbar_v16 import (  # noqa: E402
    _story,
    _ui_with_recording_st,
)


def _toolbar_valign(fake, weights):
    """Return the vertical_alignment of the toolbar columns() row whose
    spec matches ``weights`` (there is exactly one)."""
    matches = [
        valign for spec, valign in zip(fake.column_specs, fake.column_valigns)
        if isinstance(spec, list) and len(spec) == len(weights)
        and all(abs(a - b) < 1e-9 for a, b in zip(spec, weights))]
    assert len(matches) == 1, (
        f"expected exactly one toolbar row with weights {weights}; "
        f"saw specs {fake.column_specs}")
    return matches[0]


def test_detail_toolbar_is_vertically_centered(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    assert _toolbar_valign(fake, lui._DETAIL_TOOLBAR_WEIGHTS) == "center", (
        f"detail toolbar must pass vertical_alignment='center'; "
        f"saw {fake.column_valigns}")


def test_title_edit_toolbar_is_vertically_centered(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    fake.session_state["lib_edit_title_sid1"] = True
    lui._render_story_detail("sid1")
    assert _toolbar_valign(fake, lui._TITLE_EDIT_TOOLBAR_WEIGHTS) == "center", (
        f"title-edit toolbar must pass vertical_alignment='center'; "
        f"saw {fake.column_valigns}")
