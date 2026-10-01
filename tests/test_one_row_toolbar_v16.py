"""v1.6 (#46) — the story-detail toolbar is ONE row.

Share / Copy dropdowns used to render on a second row below the hairline;
they now live in the single detail toolbar row alongside Update Hashtags /
Update Images / Reset, with Delete trailing. This file also covers the
doubled-chevron fix: the popover labels are plain "Share"/"Copy" because
Streamlit's native popover trigger already renders its own chevron.

Run: python -m pytest tests/test_one_row_toolbar_v16.py -q
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import _FakeSt, _FakeCtx, _ui_with_fake_st  # noqa: E402


class _RecordingSt(_FakeSt):
    """_FakeSt that records st.columns specs and tolerates the media
    widgets used below the toolbar (image/video/text_area/text_input/
    file_uploader) with benign return values."""

    def __init__(self, clicks=()):
        super().__init__(clicks)
        self.column_specs = []

    def columns(self, spec, **k):
        self.column_specs.append(
            list(spec) if not isinstance(spec, int) else spec)
        return super().columns(spec)

    def image(self, *a, **k):
        return None

    def video(self, *a, **k):
        return None

    def text_area(self, *a, **k):
        return ""

    def text_input(self, *a, **k):
        return ""

    def file_uploader(self, *a, **k):
        return None


def _ui_with_recording_st(clicks=()):
    """Import library_ui bound to a recording fake streamlit."""
    saved = dict(sys.modules)
    fake = _RecordingSt(clicks)
    try:
        fake_mod = types.ModuleType("streamlit")
        for name in ("markdown", "caption", "success", "error", "rerun",
                     "button", "columns", "popover", "expander", "link_button",
                     "code", "image", "video", "text_area", "text_input",
                     "file_uploader"):
            setattr(fake_mod, name, getattr(fake, name))
        fake_mod.session_state = fake.session_state
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui, fake
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _story(monkeypatch, lui, **meta_over):
    meta = {"title": "T", "hashtags": [], "news_links": [],
            "image_urls": [], "uploaded_images": []}
    meta.update(meta_over)
    monkeypatch.setattr(lui.lib, "load_story",
                        lambda sid: {"meta": meta, "script": "hello"})
    monkeypatch.setattr(lui.lib, "load_prefs", lambda: {})
    monkeypatch.setattr(lui, "_copy_button",
                        lambda label, text, key: None)


# ---------------------------------------------------------------------------
# #46 — one toolbar row: hashtag/image refresh icons (#71), Reset, Share,
# Copy, Delete (trailing). Weights still total 10.0 (#24 layout preserved);
# the icon columns shrank to icon width and the freed weight moved to the
# spacer, so the row stays full-width with no dead space (#71).
# ---------------------------------------------------------------------------

def test_detail_toolbar_weights_single_row():
    lui, _fake = _ui_with_fake_st()
    w = lui._DETAIL_TOOLBAR_WEIGHTS
    assert len(w) == 7  # tags, images, reset, share, copy, spacer, delete
    assert abs(sum(w) - 10.0) < 1e-9
    assert w[0] >= 0.8  # "#" icon button
    assert w[1] >= 0.8  # "🖼" icon button
    assert w[2] >= 1.4  # "Reset" + chevron
    assert w[3] >= 1.0  # Share + native chevron
    assert w[4] >= 1.0  # Copy + native chevron
    assert w[5] > 1.0   # #71: spacer absorbs the freed icon-column weight
    assert w[6] >= 1.5  # Delete stays trailing
    assert w[6] >= 1.5  # Delete + chevron, trailing


def test_title_edit_toolbar_weights_single_row():
    lui, _fake = _ui_with_fake_st()
    w = lui._TITLE_EDIT_TOOLBAR_WEIGHTS
    assert len(w) == 6  # save, cancel, share, copy, spacer, delete
    assert abs(sum(w) - 10.0) < 1e-9
    assert w[-1] >= 1.4  # Delete + chevron, trailing


def test_toolbar_renders_share_copy_in_same_row(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    toolbars = [s for s in fake.column_specs
                if isinstance(s, list) and len(s) == 7
                and abs(sum(s) - 10.0) < 1e-9]
    assert len(toolbars) == 1  # exactly one 7-column toolbar row
    # Render order inside that row: Reset, Share, Copy, Delete popovers.
    assert [p["label"] for p in fake.popovers] == [
        "Reset", "Share", "Copy", "Delete"]


def test_title_edit_toolbar_renders_share_copy(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    fake.session_state["lib_edit_title_sid1"] = True
    lui._render_story_detail("sid1")
    toolbars = [s for s in fake.column_specs
                if isinstance(s, list) and len(s) == 6
                and abs(sum(s) - 10.0) < 1e-9]
    assert len(toolbars) == 1
    assert [p["label"] for p in fake.popovers] == [
        "Share", "Copy", "Delete"]


# ---------------------------------------------------------------------------
# #46 — doubled chevron: labels must not bake in "⌄"; the native popover
# chevron is the only indicator.
# ---------------------------------------------------------------------------

def test_share_copy_labels_have_no_baked_chevron(monkeypatch):
    lui, fake = _ui_with_fake_st()
    monkeypatch.setattr(lui, "_copy_button",
                        lambda label, text, key: None)
    lui._render_share_popover("sid1", "https://example.com/a\n\n#X")
    lui._render_copy_popover("sid1", {"hashtags": []}, "script")
    labels = [p["label"] for p in fake.popovers]
    assert labels == ["Share", "Copy"]
    assert all("⌄" not in label and "∨" not in label for label in labels)
