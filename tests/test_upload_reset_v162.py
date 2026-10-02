"""#145: uploads must work end-to-end and never process the same file twice.

Regression: st.file_uploader keeps its file in widget state across reruns.
The old upload flow called st.rerun() after a successful store without
resetting the uploader, so every subsequent run re-stored the same file —
an endless rerun loop for video, unbounded duplicate images for images.

These tests simulate two consecutive Streamlit runs: the fake's
file_uploader mimics real widget-state persistence (it keeps returning the
selected file until its key is deleted from session_state, exactly like the
real widget). _render_upload_popover must store once, reset the uploader,
and not re-store on the second run.
"""

import sys
import types

import pytest

import story_library as lib


class _Rerun(Exception):
    pass


class _FakeFile:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


class _FakeSt(types.ModuleType):
    """Simulates Streamlit widget persistence across runs."""

    def __init__(self, radio_choice="Video"):
        super().__init__("streamlit")
        self.session_state = {}
        self.radio_choice = radio_choice
        self.events = []

    def radio(self, label, options, key=None, **kwargs):
        return self.radio_choice

    def file_uploader(self, label, type=None, accept_multiple_files=False,
                      key=None, **kwargs):
        # Real Streamlit: the widget keeps returning the selected file on
        # every later run until its key is removed from session state.
        return self.session_state.get(key)

    def success(self, msg):
        self.events.append(("success", msg))

    def toast(self, msg, icon=None):
        # #88: transient status funnels through _notify -> st.toast.
        self.events.append(("toast", msg, icon))

    def error(self, msg):
        self.events.append(("error", msg))

    def warning(self, msg):
        self.events.append(("warning", msg))

    def rerun(self):
        self.events.append(("rerun",))
        raise _Rerun()

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
def lui(monkeypatch):
    def _make(radio_choice="Video"):
        fake = _FakeSt(radio_choice=radio_choice)
        monkeypatch.setitem(sys.modules, "streamlit", fake)
        sys.modules.pop("library_ui", None)
        import library_ui as lui_mod  # noqa: E402
        return lui_mod, fake
    return _make


def _story():
    return lib.save_story("T", "funny", ["#x"], "dlg", "script")


def _run_popover(lui_mod, fake, story_id):
    """One simulated Streamlit run; returns True if it ended in rerun."""
    try:
        lui_mod._render_upload_popover(story_id)
    except _Rerun:
        return True
    return False


def test_video_upload_stored_once_across_runs(lui, libdir):
    lui_mod, fake = lui("Video")
    sid = _story()
    fake.session_state["lib_video_" + sid] = _FakeFile("clip.mp4", b"vid-bytes")
    assert _run_popover(lui_mod, fake, sid) is True  # success -> rerun
    assert ("lib_video_" + sid) not in fake.session_state  # uploader reset
    # Second run (widget would still hold the file without the reset).
    assert _run_popover(lui_mod, fake, sid) is False
    st = lib.load_story(sid)
    assert st["meta"]["video_file"] == sid + ".mp4"
    assert ("toast", f"Video attached: {sid}.mp4", ":material/check_circle:") in fake.events
    assert sum(e[0] == "toast" for e in fake.events) == 1


def test_image_upload_stored_once_across_runs(lui, libdir):
    lui_mod, fake = lui("Image")
    sid = _story()
    fake.session_state["lib_images_" + sid] = [
        _FakeFile("a.png", b"png-bytes"), _FakeFile("b.jpg", b"jpg-bytes")]
    assert _run_popover(lui_mod, fake, sid) is True
    assert ("lib_images_" + sid) not in fake.session_state
    assert _run_popover(lui_mod, fake, sid) is False
    st = lib.load_story(sid)
    assert st["meta"]["uploaded_images"] == [sid + "_img1.png", sid + "_img2.jpg"]
    assert sum(e[0] == "toast" for e in fake.events) == 1


def test_video_upload_error_is_loud_and_not_retried(lui, libdir, monkeypatch):
    lui_mod, fake = lui("Video")
    sid = _story()

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(lib, "store_video_upload", boom)
    fake.session_state["lib_video_" + sid] = _FakeFile("clip.mp4", b"vid-bytes")
    assert _run_popover(lui_mod, fake, sid) is False  # error -> no rerun
    assert any(e[0] == "error" and "disk full" in e[1] for e in fake.events)
    # Uploader reset: the failing file is not retried on the next run.
    assert ("lib_video_" + sid) not in fake.session_state
    assert _run_popover(lui_mod, fake, sid) is False
    assert sum(e[0] == "error" for e in fake.events) == 1


def test_partial_image_failure_warns_loudly(lui, libdir, monkeypatch):
    lui_mod, fake = lui("Image")
    sid = _story()
    real_store = lib.store_image_upload

    def flaky(sid_, data, name):
        if name == "bad.png":
            raise OSError("corrupt")
        return real_store(sid_, data, name)
    monkeypatch.setattr(lib, "store_image_upload", flaky)
    fake.session_state["lib_images_" + sid] = [
        _FakeFile("good.png", b"png-bytes"), _FakeFile("bad.png", b"bad-bytes")]
    assert _run_popover(lui_mod, fake, sid) is False  # warning -> no rerun
    assert any(e[0] == "error" and "bad.png" in e[1] for e in fake.events)
    assert any(e[0] == "warning" and "1 of 2" in e[1] for e in fake.events)
    st = lib.load_story(sid)
    assert st["meta"]["uploaded_images"] == [sid + "_img1.png"]
