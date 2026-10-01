"""v1.6.1 (#66) — story-detail uploads are a quiet footer, not two big panels.

Bug: the story-detail "Video" section rendered two large dashed
``st.file_uploader`` panels ("Upload generated video" + "Upload images
manually") inline as top-level widgets, so a secondary action dominated
the layout. Streamlit renders each with its full label and the
"Limit 200MB per file · MP4, MOV, ..." caption — verbose headline text
for what is a secondary action.

Fix: both uploaders now live inside a single collapsed
``st.expander("Upload media")`` at the bottom of the section — one
subtle footer-level row. Both capabilities stay reachable; the
size/format constraints remain discoverable inside the expander.
Upload *handling* is unchanged (same keys, labels, types, error paths).

These tests drive the real ``_render_story_detail`` with a capturing
fake ``streamlit`` and assert the presentation structure + that the
uploader contracts are preserved.

Run: python -m pytest tests/test_upload_footer_v161.py -q
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402


class _Ctx:
    """Minimal context manager returned by fake st.columns/expander/popover."""

    def __init__(self, st, name, args, kwargs):
        self.st = st
        self.name = name
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        self.st._ctx_enter(self)
        return self

    def __exit__(self, *exc):
        self.st._ctx_exit(self)
        return False


class _FakeSt(types.ModuleType):
    """Capturing streamlit stub: records expander + file_uploader events."""

    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.events = []
        self._expander_depth = 0

    def _ctx_enter(self, ctx):
        if ctx.name == "expander":
            self._expander_depth += 1
            label = ctx.args[0] if ctx.args else ctx.kwargs.get("label")
            self.events.append(
                ("expander_enter", label, ctx.kwargs.get("expanded")))

    def _ctx_exit(self, ctx):
        if ctx.name == "expander":
            self.events.append(("expander_exit",))
            self._expander_depth -= 1

    def file_uploader(self, label, type=None, accept_multiple_files=False,
                      key=None, **kwargs):
        self.events.append(("file_uploader", label, key,
                            list(type or []), accept_multiple_files,
                            self._expander_depth > 0))
        return None

    def button(self, *args, **kwargs):
        return False

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in ("columns", "expander", "popover", "spinner", "form",
                    "tabs"):
            def factory(*a, **k):
                if name == "columns":
                    weights = a[0] if a else []
                    n = weights if isinstance(weights, int) else len(weights)
                    return [_Ctx(self, name, a, k) for _ in range(n)]
                return _Ctx(self, name, a, k)
            return factory

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
    import sys as _sys
    fake = _FakeSt()
    # library_ui does `import streamlit.components.v1 as components` —
    # stub that submodule chain as well.
    comp = types.ModuleType("streamlit.components")
    comp_v1 = types.ModuleType("streamlit.components.v1")
    comp_v1.html = lambda *a, **k: None
    comp.v1 = comp_v1
    fake.components = comp
    monkeypatch.setitem(_sys.modules, "streamlit", fake)
    monkeypatch.setitem(_sys.modules, "streamlit.components", comp)
    monkeypatch.setitem(_sys.modules, "streamlit.components.v1", comp_v1)
    _sys.modules.pop("library_ui", None)
    import library_ui as lui  # noqa: E402
    yield lui, fake
    _sys.modules.pop("library_ui", None)


def _make_story(**kw):
    kw.setdefault("title", "Dog Showdown Reel")
    kw.setdefault("tone", "funny")
    kw.setdefault("hashtags", ["#DogShowdown"])
    kw.setdefault("dialogue_md", "")
    kw.setdefault("script_md", "AARAV: chubby dogs voting contest in the park")
    kw.setdefault("source_topic", "chubby dogs voting contest")
    kw.setdefault("source_headline", "Chubby dogs battle in voting contest")
    return lib.save_story(**kw)


def test_uploaders_collapsed_into_one_expander(libdir, lui_st):
    lui, fake = lui_st
    sid = _make_story()
    lui._render_story_detail(sid)

    expanders = [e for e in fake.events if e[0] == "expander_enter"]
    assert len(expanders) == 1, \
        f"expected exactly one upload expander, saw {expanders}"
    label, expanded = expanders[0][1], expanders[0][2]
    assert "Upload" in label, f"expander label should read as upload: {label!r}"
    assert expanded is False, "upload expander must be collapsed by default"

    ups = [e for e in fake.events if e[0] == "file_uploader"]
    assert len(ups) == 2, f"expected both uploaders to survive, saw {ups}"
    assert all(u[5] for u in ups), \
        "no uploader may render as a top-level panel (#66)"


def test_uploader_contracts_unchanged(libdir, lui_st):
    lui, fake = lui_st
    sid = _make_story()
    lui._render_story_detail(sid)

    ups = {e[1]: e for e in fake.events if e[0] == "file_uploader"}
    assert set(ups) == {"Upload generated video", "Upload images manually"}

    vid = ups["Upload generated video"]
    assert vid[2] == f"lib_video_{sid}"
    assert set(vid[3]) == {"mp4", "mov", "m4v", "webm"}
    assert vid[4] is False

    imgs = ups["Upload images manually"]
    assert imgs[2] == f"lib_images_{sid}"
    assert set(imgs[3]) == {"png", "jpg", "jpeg", "webp", "gif"}
    assert imgs[4] is True, "image uploader must keep multi-file accept"
