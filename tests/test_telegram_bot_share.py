"""Tests for Telegram Bot API sharing (#159 follow-up).

Covers tools/telegram_share.py (fake transport — no network, no httpx
needed) and the library_ui composition/orchestration helpers (streamlit
stubbed, same pattern as the #161 share tests).
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import story_library as lib  # noqa: E402

# tools/telegram_share.py is loaded directly by path: the test env has no
# httpx/feedparser/bs4, so executing the real tools/__init__ (which imports
# news_fetcher) is impossible here. A minimal "tools" package stub is seeded
# so library_ui's lazy ``from tools import telegram_share`` (inside
# _share_via_telegram_bot) resolves to this exact module object without
# running the real __init__. (No other test module runs after this one that
# imports tools; verified via grep.)
import importlib.util as _ilu  # noqa: E402

_repo_root = Path(__file__).resolve().parent.parent
_tg_spec = _ilu.spec_from_file_location(
    "tools.telegram_share", _repo_root / "tools" / "telegram_share.py")
_tg_mod = _ilu.module_from_spec(_tg_spec)
_tools_pkg = types.ModuleType("tools")
_tools_pkg.__path__ = [str(_repo_root / "tools")]
_tools_pkg.telegram_share = _tg_mod
sys.modules["tools"] = _tools_pkg
sys.modules["tools.telegram_share"] = _tg_mod
_tg_spec.loader.exec_module(_tg_mod)
tg = _tg_mod


def _library_ui_module():
    """Import library_ui with a stubbed streamlit (not installed in test env)."""
    for name in ("streamlit", "streamlit.components", "streamlit.components.v1"):
        sys.modules.setdefault(name, types.ModuleType(name))
    import library_ui
    return library_ui


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


# ---------------------------------------------------------------------------
# Fake Bot API transport
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _ok_transport(result=None):
    calls = []

    def post(url, *, data=None, files=None, timeout=None):
        entry = {"url": url, "data": dict(data or {}), "timeout": timeout}
        if files:
            name, fh, ctype = files["video"]
            entry["file"] = (name, fh.read(), ctype)
        calls.append(entry)
        return _FakeResp({"ok": True, "result": result or {"message_id": 7}})

    post.calls = calls
    return post


# ---------------------------------------------------------------------------
# tools/telegram_share.py — API client
# ---------------------------------------------------------------------------

def test_send_video_posts_multipart_with_caption(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"\x00\x00fake-video")
    post = _ok_transport()
    out = tg.send_video("TOK", 123, vid, "My Title\n#tag", transport=post)
    assert out == {"message_id": 7}
    (call,) = post.calls
    assert call["url"] == "https://api.telegram.org/botTOK/sendVideo"
    assert call["data"]["chat_id"] == "123"
    assert call["data"]["caption"] == "My Title\n#tag"
    assert call["data"]["supports_streaming"] == "true"
    name, content, ctype = call["file"]
    assert name == "clip.mp4" and content == b"\x00\x00fake-video"
    assert ctype.startswith("video/")


def test_send_video_missing_file_raises_loudly(tmp_path):
    with pytest.raises(tg.TelegramShareError, match="not found"):
        tg.send_video("TOK", 1, tmp_path / "nope.mp4", "cap",
                      transport=_ok_transport())


def test_send_video_caption_over_limit_raises():
    with pytest.raises(tg.TelegramShareError, match="1024"):
        tg.send_video("TOK", 1, __file__, "x" * 1025,
                      transport=_ok_transport())


def test_send_text_posts_message():
    post = _ok_transport()
    tg.send_text("TOK", 42, "hello", transport=post)
    (call,) = post.calls
    assert call["url"] == "https://api.telegram.org/botTOK/sendMessage"
    assert call["data"] == {"chat_id": "42", "text": "hello"}


def test_send_text_empty_and_overlong_raise():
    with pytest.raises(tg.TelegramShareError, match="[Ee]mpty"):
        tg.send_text("TOK", 1, "   ", transport=_ok_transport())
    with pytest.raises(tg.TelegramShareError, match="4096"):
        tg.send_text("TOK", 1, "x" * 4097, transport=_ok_transport())


def test_api_rejection_surfaces_description():
    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": False, "description": "Unauthorized"})
    with pytest.raises(tg.TelegramShareError, match="Unauthorized"):
        tg.send_text("BAD", 1, "hi", transport=post)


def test_api_non_json_response_raises():
    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp(ValueError("no json"))
    with pytest.raises(tg.TelegramShareError, match="non-JSON"):
        tg.send_text("TOK", 1, "hi", transport=post)


def test_transport_failure_raises_actionable_error():
    def post(url, *, data=None, files=None, timeout=None):
        raise ConnectionError("dns boom")
    with pytest.raises(tg.TelegramShareError, match="Couldn't reach"):
        tg.send_text("TOK", 1, "hi", transport=post)


def test_missing_token_raises_with_setup_hint():
    with pytest.raises(tg.TelegramShareError, match="@BotFather"):
        tg.send_text("", 1, "hi", transport=_ok_transport())


def test_discover_chat_id_returns_newest_chat():
    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": [
            {"update_id": 1, "message": {"chat": {"id": 111}}},
            {"update_id": 2, "message": {"chat": {"id": 222}}},
        ]})
    assert tg.discover_chat_id("TOK", transport=post) == 222


def test_discover_chat_id_with_no_updates_raises_with_start_instruction():
    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": []})
    with pytest.raises(tg.TelegramShareError, match="Start"):
        tg.discover_chat_id("TOK", transport=post)


# ---------------------------------------------------------------------------
# library_ui composition helpers
# ---------------------------------------------------------------------------

def test_telegram_share_parts_caption_then_links():
    lui = _library_ui_module()
    meta = {
        "title": "Big Story",
        "hashtags": ["#One", "#Two"],
        "news_links": [
            {"title": "T1", "url": "https://a.example/1", "source": "SiteA"},
            {"title": "T2", "url": "https://b.example/2", "source": ""},
            {"title": "T1dup", "url": "https://a.example/1", "source": "SiteA"},
        ],
    }
    caption, links = lui._telegram_share_parts(meta)
    assert caption == "Big Story\n#One #Two"
    # deduped, blank source falls back to the domain
    assert links == "SiteA: https://a.example/1\nb.example: https://b.example/2"


def test_telegram_share_parts_empty_story():
    lui = _library_ui_module()
    caption, links = lui._telegram_share_parts({})
    assert caption == "Untitled Story"
    assert links == ""


def test_story_video_path_missing_file_raises_loudly(libdir):
    lui = _library_ui_module()
    sid = lib.save_story(title="T", tone="funny", hashtags=[],
                         dialogue_md="", script_md="x",
                         source_topic="t", source_headline="h",
                         news_links=[], image_urls=[])
    lib.update_story_fields(sid, video_file="ghost.mp4")
    story = lib.load_story(sid)
    with pytest.raises(RuntimeError, match="missing from the stories directory"):
        lui._story_video_path(sid, story["meta"])
    assert lui._story_video_path(sid, {}) is None


# ---------------------------------------------------------------------------
# Orchestration: _share_via_telegram_bot
# ---------------------------------------------------------------------------

def _prefs_double(monkeypatch, initial):
    store = dict(initial)

    def fake_load():
        return dict(store)

    def fake_save(updates):
        store.update(updates)

    monkeypatch.setattr(lib, "load_prefs", fake_load)
    monkeypatch.setattr(lib, "save_prefs", fake_save)
    return store


def _make_story_with_video(libdir, with_video=True):
    sid = lib.save_story(title="Vid Story", tone="funny",
                         hashtags=["#Vid"], dialogue_md="", script_md="x",
                         source_topic="t", source_headline="h",
                         news_links=[
                             {"title": "N1", "url": "https://n.example/1",
                              "source": "News1"}],
                         image_urls=[])
    if with_video:
        lib.store_video_upload(sid, b"videobytes", "clip.mp4")
    return sid


def test_share_bot_sends_video_then_links(libdir, monkeypatch):
    lui = _library_ui_module()
    store = _prefs_double(monkeypatch, {"telegram_bot_token": "TOK",
                                        "telegram_chat_id": 99})
    sid = _make_story_with_video(libdir, with_video=True)
    story = lib.load_story(sid)
    post = _ok_transport()
    monkeypatch.setattr(tg, "_httpx_post", post)
    msg = lui._share_via_telegram_bot(sid, story["meta"])
    assert msg == ("Sent to Telegram: video + caption, then 1 news link.")
    assert len(post.calls) == 2
    assert post.calls[0]["url"].endswith("/sendVideo")
    assert post.calls[0]["data"]["caption"] == "Vid Story\n#Vid"
    assert post.calls[1]["url"].endswith("/sendMessage")
    assert "News1: https://n.example/1" in post.calls[1]["data"]["text"]


def test_share_bot_without_video_sends_caption_as_text(libdir, monkeypatch):
    lui = _library_ui_module()
    _prefs_double(monkeypatch, {"telegram_bot_token": "TOK",
                                "telegram_chat_id": 99})
    sid = _make_story_with_video(libdir, with_video=False)
    story = lib.load_story(sid)
    post = _ok_transport()
    monkeypatch.setattr(tg, "_httpx_post", post)
    msg = lui._share_via_telegram_bot(sid, story["meta"])
    assert "no video attached" in msg
    assert len(post.calls) == 2
    assert all(c["url"].endswith("/sendMessage") for c in post.calls)
    assert post.calls[0]["data"]["text"] == "Vid Story\n#Vid"


def test_share_bot_discovers_and_remembers_chat_id(libdir, monkeypatch):
    lui = _library_ui_module()
    store = _prefs_double(monkeypatch, {"telegram_bot_token": "TOK"})
    sid = _make_story_with_video(libdir, with_video=False)
    story = lib.load_story(sid)

    def post(url, *, data=None, files=None, timeout=None):
        if url.endswith("/getUpdates"):
            return _FakeResp({"ok": True, "result": [
                {"update_id": 5, "message": {"chat": {"id": 4242}}}]})
        return _FakeResp({"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr(tg, "_httpx_post", post)
    lui._share_via_telegram_bot(sid, story["meta"])
    assert store["telegram_chat_id"] == 4242


def test_share_bot_missing_video_file_raises_before_any_http(libdir, monkeypatch):
    lui = _library_ui_module()
    _prefs_double(monkeypatch, {"telegram_bot_token": "TOK",
                                "telegram_chat_id": 99})
    sid = _make_story_with_video(libdir, with_video=False)
    lib.update_story_fields(sid, video_file="ghost.mp4")
    story = lib.load_story(sid)
    post = _ok_transport()
    monkeypatch.setattr(tg, "_httpx_post", post)
    with pytest.raises(RuntimeError, match="missing from the stories directory"):
        lui._share_via_telegram_bot(sid, story["meta"])
    assert post.calls == []


def test_share_bot_without_token_raises_with_setup_hint(libdir, monkeypatch):
    lui = _library_ui_module()
    _prefs_double(monkeypatch, {})
    sid = _make_story_with_video(libdir, with_video=False)
    story = lib.load_story(sid)
    with pytest.raises(tg.TelegramShareError, match="@BotFather"):
        lui._share_via_telegram_bot(sid, story["meta"])
