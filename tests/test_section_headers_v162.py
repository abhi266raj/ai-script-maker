"""v1.6.2 (#107, #94) — section-header alignment.

#107: the "Hashtags" title and the hashtag chips must share ONE line
(title left, chips flowing right), and the same for "News Links".
The title rides in the first column of the chip row — a single
``st.columns`` call — so the DOM guarantees one line. Chip rendering
(weights, × overlay, 44px clearance, vertical centering) is untouched.

#94: the "Video" section title is gone. The row is a one-line
"Upload" title (left) + upload button (right); clicking the button
opens a popover offering Video / Image selection, then the unchanged
upload + processing flow (same widget keys, same store paths).

These tests drive the real ``_render_story_detail`` with a capturing
fake ``streamlit`` and assert the presentation structure + uploader
contracts.

Run: python -m pytest tests/test_section_headers_v162.py -q
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
    """Minimal context manager returned by fake st.columns/popover."""

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
    """Capturing streamlit stub: records columns specs, markdown,
    popover, radio, file_uploader and expander events in render order."""

    def __init__(self, radio_choice="Video"):
        super().__init__("streamlit")
        self.session_state = {}
        self.events = []
        self.radio_choice = radio_choice

    def markdown(self, html, **kwargs):
        self.events.append(("markdown", html))

    def columns(self, spec, **kwargs):
        weights = spec if isinstance(spec, int) else list(spec)
        self.events.append(("columns", weights))
        n = weights if isinstance(weights, int) else len(weights)
        return [_Ctx(self, "columns", (spec,), kwargs) for _ in range(n)]

    def popover(self, label, **kwargs):
        self.events.append(("popover", label, kwargs))
        return _Ctx(self, "popover", (label,), kwargs)

    def expander(self, label, expanded=False, **kwargs):
        self.events.append(("expander", label, expanded))
        return _Ctx(self, "expander", (label,), kwargs)

    def radio(self, label, options, key=None, **kwargs):
        self.events.append(("radio", label, list(options), key))
        return self.radio_choice

    def file_uploader(self, label, type=None, accept_multiple_files=False,
                      key=None, **kwargs):
        self.events.append(("file_uploader", label, key,
                            list(type or []), accept_multiple_files))
        return None

    def button(self, *args, **kwargs):
        return False

    def selectbox(self, label, options, index=0, key=None, **kwargs):
        # Toolbar AI engine dropdown: record + return Streamlit's default
        # (the option at `index`).
        self.events.append(("selectbox", label, list(options), key))
        opts = list(options)
        return opts[index] if opts else None

    def video(self, *args, **kwargs):
        self.events.append(("video",))

    def container(self, border=None, key=None, height=None, **kwargs):
        # #303: panel cards (border=True) and fixed-height scroll lists
        # (height=N); record kwargs for assertions.
        self.events.append(("container", border, key, height, kwargs))
        return _Ctx(self, "container", (), kwargs)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def noop(*a, **k):
            return None
        return noop


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


@pytest.fixture
def lui_st(monkeypatch):
    """Import library_ui bound to the capturing fake streamlit."""
    def _make(radio_choice="Video"):
        fake = _FakeSt(radio_choice=radio_choice)
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


def _make_story(**kw):
    kw.setdefault("title", "Dog Showdown Reel")
    kw.setdefault("tone", "funny")
    kw.setdefault("hashtags", ["#DogShowdown", "#ReelLife"])
    kw.setdefault("dialogue_md", "")
    kw.setdefault("script_md", "AARAV: chubby dogs voting contest in the park")
    kw.setdefault("source_topic", "chubby dogs voting contest")
    kw.setdefault("source_headline", "Chubby dogs battle in voting contest")
    kw.setdefault("news_links", [
        {"title": "T1", "url": "https://a.example/1", "source": "Alpha"},
        {"title": "T2", "url": "https://b.example/2", "source": "Beta"},
    ])
    return lib.save_story(**kw)


def _capture_library_css(lui):
    """Capture the <style> HTML emitted by inject_library_css."""
    chunks = []
    real_markdown = lui.st.markdown
    lui.st.markdown = lambda *a, **k: chunks.append(a[0] if a else "")
    try:
        lui.inject_library_css()
    finally:
        lui.st.markdown = real_markdown
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# #303 — panel title helper/CSS
# ---------------------------------------------------------------------------

def test_panel_title_css_exists(lui_st):
    """#303 replaced the inline chip-row title with panel cards — the
    panel title class must exist and carry no margins."""
    lui, _ = lui_st()
    css = _capture_library_css(lui)
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert ".lib-panel-title" in clean, "panel title CSS must exist"
    assert "margin: 0" in clean


# ---------------------------------------------------------------------------
# #107 — CSS pins the inline title
# ---------------------------------------------------------------------------

def test_inline_section_css_zeroes_margins_and_centers(lui_st):
    lui, _ = lui_st()
    css = _capture_library_css(lui)
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert ".lib-section-inline" in clean
    assert "margin: 0" in clean
    # #112: the title column is vertically centered against the pills via
    # the robust stretch+flex approach (not the old align-self: center).
    assert ":has(.lib-section-inline)" in clean
    assert "justify-content: center" in clean


# ---------------------------------------------------------------------------
# #107 — title + chips share one st.columns row
# ---------------------------------------------------------------------------

def test_hashtags_panel_renders_in_story_detail(libdir, lui_st):
    """#303: the story detail renders the Hashtags panel card — title +
    Load more + Force fetch in the header, no stacked section title."""
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    titles = [e[1] for e in fake.events
              if e[0] == "markdown" and "lib-panel-title" in e[1]
              and "Hashtags" in e[1]]
    assert len(titles) == 1, f"exactly one Hashtags panel title; saw {titles}"
    cards = [e for e in fake.events
             if e[0] == "container" and e[1] is True]
    assert cards, "panels must render as bordered cards"


def test_news_links_panel_renders_in_story_detail(libdir, lui_st):
    """#303: the story detail renders the News Links panel card."""
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    titles = [e[1] for e in fake.events
              if e[0] == "markdown" and "lib-panel-title" in e[1]
              and "News Links" in e[1]]
    assert len(titles) == 1, f"exactly one News Links panel title; saw {titles}"


def test_panel_row_markup_uses_single_line_rows(libdir, lui_st):
    """#303: panel rows are single-line read-only text (lib-panel-row),
    not chips."""
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    rows = [e[1] for e in fake.events
            if e[0] == "markdown" and 'class="lib-panel-row"' in e[1]]
    assert len(rows) == 2, f"two hashtag rows expected; saw {rows}"
    assert "#DogShowdown" in rows[0] and "#ReelLife" in rows[1]


# ---------------------------------------------------------------------------
# #94 — upload row
# ---------------------------------------------------------------------------

def test_video_section_title_is_gone(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    video_titles = [e[1] for e in fake.events
                    if e[0] == "markdown" and e[1] == '<div class="lib-section">Video</div>']
    assert not video_titles, "the 'Video' section title must be gone (#94)"


def test_no_upload_expander(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    expanders = [e for e in fake.events if e[0] == "expander"]
    # #94's intent is the *upload* expander; the Telegram share popover
    # legitimately adds its own unrelated setup expander (#159).
    upload_expand = [e for e in expanders if "upload" in e[1].lower()]
    assert not upload_expand, \
        f"upload expander must be gone (#94); saw {upload_expand}"


def test_upload_trigger_in_toolbar_no_standalone_row(libdir, lui_st):
    """The standalone one-line Upload row is gone — no inline 'Upload'
    title. The icon-only upload popover trigger lives in the detail
    toolbar beside Share/Copy."""
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    inline = [e[1] for e in fake.events
              if e[0] == "markdown" and "lib-section-inline" in e[1] and ">Upload<" in e[1]]
    assert len(inline) == 0, "standalone 'Upload' title must be gone"

    # #114: the popover trigger is icon-only (native material upload
    # glyph, no text/emoji).
    popovers = [e for e in fake.events if e[0] == "popover"]
    assert any(e[2].get("icon") == lui._TB_ICON_UPLOAD for e in popovers), (
        f"upload popover must use the material upload icon; saw {popovers}")


def test_upload_popover_offers_video_image_selection(libdir, lui_st):
    lui, fake = lui_st()
    sid = _make_story()
    lui._render_story_detail(sid)

    radios = [e for e in fake.events if e[0] == "radio"]
    assert len(radios) == 1, f"expected one Video/Image selector; saw {radios}"
    assert radios[0][2] == ["Video", "Image"]


def test_video_uploader_contract_unchanged(libdir, lui_st):
    lui, fake = lui_st(radio_choice="Video")
    sid = _make_story()
    lui._render_story_detail(sid)

    ups = {e[1]: e for e in fake.events if e[0] == "file_uploader"}
    assert set(ups) == {"Upload generated video"}, f"saw {set(ups)}"
    vid = ups["Upload generated video"]
    assert vid[2] == f"lib_video_{sid}"
    assert set(vid[3]) == {"mp4", "mov", "m4v", "webm"}
    assert vid[4] is False


def test_image_uploader_contract_unchanged(libdir, lui_st):
    lui, fake = lui_st(radio_choice="Image")
    sid = _make_story()
    lui._render_story_detail(sid)

    ups = {e[1]: e for e in fake.events if e[0] == "file_uploader"}
    assert set(ups) == {"Upload images manually"}, f"saw {set(ups)}"
    imgs = ups["Upload images manually"]
    assert imgs[2] == f"lib_images_{sid}"
    assert set(imgs[3]) == {"png", "jpg", "jpeg", "webp", "gif"}
    assert imgs[4] is True, "image uploader must keep multi-file accept"


def test_uploads_still_exempt_from_image_cap(libdir):
    """#94 must not route uploads through the fetched-image cap (#83):
    manual uploads live in uploaded_images, untouched by the cap."""
    sid = _make_story()
    lib.store_image_upload(sid, b"fake-bytes", "manual.png")
    meta = lib.load_story(sid)["meta"]
    assert len(meta["uploaded_images"]) == 1
    assert meta.get("image_urls") in (None, [])
