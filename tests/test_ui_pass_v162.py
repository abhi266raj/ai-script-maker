"""v1.6.2 UI pass — #112, #113, #114.

#112: section titles ("Hashtags", "News Links") vertically centered with
their chips via the robust stretch+flex approach (not the fragile
align-self: center).

#113: "Load more images/news" buttons ride as the last column of their
section's scroll row — same line as the content, inside the scroll view —
instead of an orphan row below.

#114: Upload row polish — popover trigger is icon-only (native material
upload glyph, no "⬆" text/emoji) with a visible theme-safe border; the
dropdown contains the Video/Image selection; title and button vertically
centered.

These tests drive the real ``_render_story_detail`` with a capturing fake
``streamlit`` and assert the presentation structure.

Run: python -m pytest tests/test_ui_pass_v162.py -q
"""
import re
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402


class _Ctx:
    def __init__(self, st, name, args, kwargs):
        self.st = st
        self.name = name
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeSt(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.events = []

    def markdown(self, html, **kwargs):
        self.events.append(("markdown", html))

    def columns(self, spec, **kwargs):
        self.events.append(("columns", spec))
        n = len(spec) if isinstance(spec, (list, tuple)) else spec
        return [_Ctx(self, f"col{i}", (), {}) for i in range(n)]

    def popover(self, label, **kwargs):
        self.events.append(("popover", label, kwargs))
        return _Ctx(self, "popover", (label,), kwargs)

    def button(self, *args, **kwargs):
        label = args[0] if args else kwargs.get("label", "")
        key = kwargs.get("key")
        self.events.append(("button", label, key, kwargs))
        return False

    def link_button(self, label, url, **kwargs):
        # #134: news links are native st.link_button; record for assertions.
        self.events.append(("link_button", label, url, kwargs))
        return False

    def radio(self, label, options, key=None, **kwargs):
        self.events.append(("radio", label, list(options), key))
        return options[0]

    def file_uploader(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def success(self, *args, **kwargs):
        pass

    def rerun(self):
        pass

    def image(self, *args, **kwargs):
        pass

    def video(self, *args, **kwargs):
        pass

    def text_area(self, *args, **kwargs):
        return ""

    def text_input(self, *args, **kwargs):
        return ""

    def expander(self, label, expanded=False, **kwargs):
        # #159: the share popover's Telegram setup expander; recorded
        # like the other containers.
        self.events.append(("expander", label, expanded))
        return _Ctx(self, "expander", (label,), kwargs)

    def spinner(self, text=None, **kwargs):
        # #159: share-progress spinner; a no-op context in tests.
        return _Ctx(self, "spinner", (text,), kwargs)


@pytest.fixture()
def libdir(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARY_DIR", str(tmp_path))


@pytest.fixture()
def lui_st(monkeypatch):
    """Import library_ui bound to the capturing fake streamlit."""
    def _make():
        fake = _FakeSt()
        comp = types.ModuleType("streamlit.components")
        comp_v1 = types.ModuleType("streamlit.components.v1")
        comp_v1.html = lambda *a, **k: None
        comp.v1 = comp_v1
        fake.components = comp
        monkeypatch.setitem(sys.modules, "streamlit", fake)
        monkeypatch.setitem(sys.modules, "streamlit.components", comp)
        monkeypatch.setitem(sys.modules, "streamlit.components.v1", comp_v1)
        sys.modules.pop("library_ui", None)
        import library_ui as lui  # noqa: E402
        return lui, fake
    return _make


def _make_story():
    return lib.save_story(
        title="Test Story",
        tone="",
        hashtags=["#Alpha", "#Beta"],
        dialogue_md="",
        script_md="Test script",
        source_topic="test",
        source_headline="",
        news_links=[
            {"title": "Alpha News", "source": "Alpha", "url": "https://a.example/1"},
            {"title": "Beta News", "source": "Beta", "url": "https://b.example/2"},
        ],
        image_urls=["https://img.example/1.jpg"],
    )


def _css_source(lui):
    """The inject_library_css source with comments stripped."""
    import inspect
    src = inspect.getsource(lui.inject_library_css)
    return re.sub(r"/\*.*?\*/", "", src, flags=re.S)


# ---------------------------------------------------------------------------
# #112 — robust vertical centering
# ---------------------------------------------------------------------------

def test_112_title_centering_css_is_robust(lui_st):
    """The title column uses stretch+flex centering, not fragile align-self."""
    lui, _ = lui_st()
    clean = _css_source(lui)
    assert ":has(.lib-section-inline)" in clean
    assert "justify-content: center" in clean
    assert "align-self: center" not in clean


def test_112_load_more_column_centering_css(lui_st):
    """The inline Load more column gets the same robust centering."""
    lui, _ = lui_st()
    clean = _css_source(lui)
    assert ':has([data-marker="lib-load-more"])' in clean


# ---------------------------------------------------------------------------
# #113 — Load more inline
# ---------------------------------------------------------------------------

def test_113_news_load_more_is_last_column(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    labels = ["Alpha", "Beta"]
    expected = ([lui._section_title_weight("News Links")]
                + lui._chip_col_weights(labels)
                + [lui._load_more_weight("Load more news")])
    col_specs = [e[1] for e in fake.events if e[0] == "columns"]
    assert expected in col_specs

    markers = [e[1] for e in fake.events
               if e[0] == "markdown" and 'data-marker="lib-load-more"' in e[1]]
    assert len(markers) >= 1

    buttons = [(e[1], e[2]) for e in fake.events if e[0] == "button"]
    assert any(label == "Load more news" for label, _key in buttons)


def test_113_images_load_more_is_last_column(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    expected = [1] + [lui._load_more_weight("Load more images")]
    col_specs = [e[1] for e in fake.events if e[0] == "columns"]
    assert expected in col_specs, f"images load-more must be inline; saw {col_specs}"

    buttons = [(e[1], e[2]) for e in fake.events if e[0] == "button"]
    assert any(label == "Load more images" for label, _key in buttons)


def test_113_load_more_weight_is_pure(lui_st):
    lui, _ = lui_st()
    assert lui._load_more_weight("Load more news") == len("Load more news") + 2
    assert lui._load_more_weight("") == 6


# ---------------------------------------------------------------------------
# #114 — Upload row polish
# ---------------------------------------------------------------------------

def test_114_upload_uses_material_icon_not_emoji(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    popovers = [e for e in fake.events if e[0] == "popover"]
    upload_pops = [e for e in popovers if e[2].get("icon") == lui._TB_ICON_UPLOAD]
    assert len(upload_pops) == 1
    assert not any("⬆" in (e[1] or "") for e in popovers)


def test_114_upload_button_border_css(lui_st):
    lui, _ = lui_st()
    clean = _css_source(lui)
    assert ':has([data-marker="lib-upload-btn"])' in clean
    assert "border: 1px solid rgba(128, 128, 128, 0.5)" in clean


def test_114_upload_popover_has_video_image_choice(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    radios = [e for e in fake.events if e[0] == "radio"]
    assert any(e[2] == ["Video", "Image"] for e in radios)


def test_114_edit_buttons_use_material_icon(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    buttons = [e for e in fake.events if e[0] == "button"]
    edit_btns = [e for e in buttons if e[3].get("icon") == lui._TB_ICON_EDIT]
    assert len(edit_btns) >= 2
    assert not any("✏️" in (e[1] or "") for e in buttons)
