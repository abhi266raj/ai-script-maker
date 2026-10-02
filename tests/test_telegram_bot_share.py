"""Tests for Telegram Bot API sharing (#159 follow-up).

Covers tools/telegram_share.py (fake transport — no network, no httpx
needed) and the library_ui composition/orchestration helpers (streamlit
stubbed, same pattern as the #161 share tests).
"""
import sys
import types
from pathlib import Path

import json

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


def test_send_text_empty_raises_loudly():
    with pytest.raises(tg.TelegramShareError, match="[Ee]mpty"):
        tg.send_text("TOK", 1, "   ", transport=_ok_transport())


def test_send_text_overlong_splits_into_sequential_messages():
    # #186: >4096 chars no longer raises — sent as sequential chunks.
    post = _ok_transport()
    text = "x" * 4097
    results = tg.send_text("TOK", 42, text, transport=post)
    assert len(post.calls) == 2
    assert len(results) == 2
    for call in post.calls:
        assert call["url"] == "https://api.telegram.org/botTOK/sendMessage"
        assert call["data"]["chat_id"] == "42"
        assert len(call["data"]["text"]) <= tg.MAX_TEXT_CHARS
    assert "".join(call["data"]["text"] for call in post.calls) == text


def test_send_text_split_keeps_paragraphs_whole():
    post = _ok_transport()
    text = "y" * 4000 + "\n\n" + "z" * 200
    tg.send_text("TOK", 42, text, transport=post)
    assert len(post.calls) == 2
    assert post.calls[0]["data"]["text"] == "y" * 4000
    assert post.calls[1]["data"]["text"] == "z" * 200


def test_split_text_unit_boundaries():
    assert tg.split_text("") == []
    assert tg.split_text("hi") == ["hi"]
    with pytest.raises(tg.TelegramShareError, match="invalid chunk limit"):
        tg.split_text("hi", 0)


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


def test_discover_chat_id_prefers_newest_private_over_group():
    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": [
            {"update_id": 1,
             "message": {"chat": {"id": 111, "type": "private"}}},
            {"update_id": 2,
             "message": {"chat": {"id": -100222, "type": "supergroup"}}},
        ]})
    assert tg.discover_chat_id("TOK", transport=post) == 111


def test_discover_chat_id_falls_back_to_newest_group_when_no_private():
    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": [
            {"update_id": 1,
             "message": {"chat": {"id": -100111, "type": "group"}}},
            {"update_id": 2,
             "message": {"chat": {"id": -100222, "type": "supergroup"}}},
        ]})
    assert tg.discover_chat_id("TOK", transport=post) == -100222


def test_resolve_chat_id_uses_cache_without_api_call(tmp_path):
    cache = tmp_path / "chat_id.json"
    cache.write_text('{"chat_id": 555}', encoding="utf-8")

    def post(url, *, data=None, files=None, timeout=None):
        raise AssertionError("getUpdates must not run on a cache hit")

    assert tg.resolve_chat_id("TOK", transport=post,
                              chat_id_path=cache) == 555


def test_resolve_chat_id_discovers_and_caches_on_miss(tmp_path):
    cache = tmp_path / "chat_id.json"

    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": [
            {"update_id": 7,
             "message": {"chat": {"id": 777, "type": "private"}}},
        ]})

    assert tg.resolve_chat_id("TOK", transport=post,
                              chat_id_path=cache) == 777
    assert json.loads(cache.read_text(encoding="utf-8")) == {"chat_id": 777}


def test_resolve_chat_id_corrupt_cache_rediscovers(tmp_path):
    cache = tmp_path / "chat_id.json"
    cache.write_text("not json{", encoding="utf-8")

    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": [
            {"update_id": 9,
             "message": {"chat": {"id": 999, "type": "private"}}},
        ]})

    assert tg.resolve_chat_id("TOK", transport=post,
                              chat_id_path=cache) == 999
    assert json.loads(cache.read_text(encoding="utf-8")) == {"chat_id": 999}


def test_resolve_chat_id_loud_error_when_nothing_discoverable(tmp_path):
    cache = tmp_path / "chat_id.json"

    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": []})

    with pytest.raises(tg.TelegramShareError, match="Start"):
        tg.resolve_chat_id("TOK", transport=post, chat_id_path=cache)
    assert not cache.exists()  # nothing cached on failure


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
    # deduped, blank source falls back to the publisher name (#232)
    assert links == "SiteA: https://a.example/1\nB: https://b.example/2"


def test_telegram_share_parts_empty_source_prefers_publisher_name():  # #232
    lui = _library_ui_module()
    meta = {
        "news_links": [
            {"url": "https://timesofindia.indiatimes.com/india/x", "source": ""},
            {"url": "https://unknown-news-site.co.in/y", "source": "  "},
            # publisher_name_from_url finds no host here, but the netloc is
            # usable: it stays as the last resort before the raw URL.
            {"url": "https://---.example/z", "source": ""},
            {"url": "not-a-url", "source": ""},
        ],
    }
    _, links = lui._telegram_share_parts(meta)
    assert links == (
        "Times of India: https://timesofindia.indiatimes.com/india/x\n"
        "Unknown News Site: https://unknown-news-site.co.in/y\n"
        "---.example: https://---.example/z\n"
        "not-a-url: not-a-url"
    )


def test_telegram_share_parts_publisher_lookup_failure_raises_loudly(monkeypatch):  # #232
    lui = _library_ui_module()

    def _boom(url):
        raise RuntimeError("name lookup blew up")

    monkeypatch.setattr(lui, "publisher_name_from_url", _boom)
    meta = {"news_links": [{"url": "https://a.example/1", "source": ""}]}
    with pytest.raises(RuntimeError, match="name lookup blew up"):
        lui._telegram_share_parts(meta)


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


def test_share_bot_sends_video_then_links(libdir, monkeypatch, tmp_path):
    lui = _library_ui_module()
    store = _prefs_double(monkeypatch, {"telegram_bot_token": "TOK",
                                        "telegram_chat_id": 99})
    monkeypatch.setattr(tg, "DEFAULT_GROUPS_PATH", tmp_path / "groups.json")
    sid = _make_story_with_video(libdir, with_video=True)
    story = lib.load_story(sid)
    post = _ok_transport()
    monkeypatch.setattr(tg, "_httpx_post", post)
    msg = lui._share_via_telegram_bot(sid, story["meta"])
    assert msg == ("Sent to Telegram: video + caption, then 1 news link, "
                   "then no group IDs configured — add chat IDs (one per line) "
                   "to ~/Documents/telegrambot/group_ids.txt (forward a group "
                   "message to @getmyid_bot to get them).")
    assert len(post.calls) == 3  # 2 DM sends + 1 group-discovery getUpdates
    assert post.calls[0]["url"].endswith("/sendVideo")
    assert post.calls[0]["data"]["caption"] == "Vid Story\n#Vid"
    assert post.calls[1]["url"].endswith("/sendMessage")
    assert "News1: https://n.example/1" in post.calls[1]["data"]["text"]


def test_share_bot_without_video_sends_caption_as_text(libdir, monkeypatch,
                                                     tmp_path):
    lui = _library_ui_module()
    _prefs_double(monkeypatch, {"telegram_bot_token": "TOK",
                                "telegram_chat_id": 99})
    monkeypatch.setattr(tg, "DEFAULT_GROUPS_PATH", tmp_path / "groups.json")
    sid = _make_story_with_video(libdir, with_video=False)
    story = lib.load_story(sid)
    post = _ok_transport()
    monkeypatch.setattr(tg, "_httpx_post", post)
    msg = lui._share_via_telegram_bot(sid, story["meta"])
    assert "no video attached" in msg
    assert len(post.calls) == 3  # 2 DM sends + 1 group-discovery getUpdates
    assert all(c["url"].endswith("/sendMessage") for c in post.calls[:2])
    assert post.calls[2]["url"].endswith("/getUpdates")
    assert post.calls[0]["data"]["text"] == "Vid Story\n#Vid"


def test_share_bot_discovers_and_remembers_chat_id(libdir, monkeypatch,
                                                    tmp_path):
    lui = _library_ui_module()
    store = _prefs_double(monkeypatch, {"telegram_bot_token": "TOK"})
    monkeypatch.setattr(tg, "DEFAULT_GROUPS_PATH", tmp_path / "groups.json")
    monkeypatch.setattr(tg, "DEFAULT_CHAT_ID_PATH",
                        tmp_path / "chat_id.json")
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


# ---------------------------------------------------------------------------
# Token resolution precedence: default file -> prefs custom -> loud error
# ---------------------------------------------------------------------------

def test_resolve_token_file_wins_over_prefs(tmp_path):
    tok = tmp_path / "bot_token.txt"
    tok.write_text("FILETOK\n")
    assert tg.resolve_token("PREFSTOK", token_path=tok) == "FILETOK"


def test_resolve_token_strips_whitespace_and_newlines(tmp_path):
    tok = tmp_path / "bot_token.txt"
    tok.write_text("  FILETOK  \n\n")
    assert tg.resolve_token(token_path=tok) == "FILETOK"


def test_resolve_token_missing_file_falls_back_to_prefs(tmp_path):
    assert tg.resolve_token("PREFSTOK",
                            token_path=tmp_path / "nope.txt") == "PREFSTOK"


def test_resolve_token_blank_file_falls_back_to_prefs(tmp_path):
    tok = tmp_path / "bot_token.txt"
    tok.write_text("   \n  \n")
    assert tg.resolve_token("PREFSTOK", token_path=tok) == "PREFSTOK"


def test_resolve_token_unreadable_path_falls_back_to_prefs(tmp_path):
    # a directory at the token path raises on read -> treated as missing
    assert tg.resolve_token("PREFSTOK", token_path=tmp_path) == "PREFSTOK"


def test_resolve_token_nothing_configured_raises_loudly(tmp_path):
    with pytest.raises(tg.TelegramShareError, match="bot_token.txt"):
        tg.resolve_token(None, token_path=tmp_path / "nope.txt")
    with pytest.raises(tg.TelegramShareError, match="@BotFather"):
        tg.resolve_token("   ", token_path=tmp_path / "nope.txt")


def test_resolve_token_default_path_constant():
    assert str(tg.DEFAULT_TOKEN_PATH).endswith(
        "Documents/telegrambot/bot_token.txt")


def test_share_bot_uses_default_token_file_when_prefs_empty(
        libdir, monkeypatch, tmp_path):
    lui = _library_ui_module()
    tok = tmp_path / "bot_token.txt"
    tok.write_text("FILETOK\n")
    monkeypatch.setattr(tg, "DEFAULT_TOKEN_PATH", tok)
    monkeypatch.setattr(tg, "DEFAULT_GROUPS_PATH", tmp_path / "groups.json")
    _prefs_double(monkeypatch, {"telegram_chat_id": 99})
    sid = _make_story_with_video(libdir, with_video=False)
    story = lib.load_story(sid)
    post = _ok_transport()
    monkeypatch.setattr(tg, "_httpx_post", post)
    lui._share_via_telegram_bot(sid, story["meta"])
    assert post.calls[0]["url"].startswith(
        "https://api.telegram.org/botFILETOK/")


# ---------------------------------------------------------------------------
# #179: broadcast to every group the bot is in
# ---------------------------------------------------------------------------

def _updates_transport(updates):
    def post(url, *, data=None, files=None, timeout=None):
        return _FakeResp({"ok": True, "result": updates})
    return post


def test_discover_group_ids_harvests_groups_and_supergroups(tmp_path):
    updates = [
        {"update_id": 1,
         "message": {"chat": {"id": 111, "type": "private"}}},
        {"update_id": 2,
         "message": {"chat": {"id": -222, "type": "group"}}},
        {"update_id": 3,
         "message": {"chat": {"id": -333, "type": "supergroup"}}},
        {"update_id": 4,
         "channel_post": {"chat": {"id": -444, "type": "channel"}}},
    ]
    path = tmp_path / "groups.json"
    got = tg.discover_group_ids(
        "TOK", transport=_updates_transport(updates), groups_path=path)
    assert got == [-333, -222]  # private chat and channel excluded
    # persisted: a later call with no new updates still knows them
    assert tg.discover_group_ids(
        "TOK", transport=_updates_transport([]), groups_path=path) == got


def test_discover_group_ids_my_chat_member_removal_drops_group(tmp_path):
    path = tmp_path / "groups.json"
    path.write_text("[-555, -666]")
    updates = [
        {"update_id": 9, "my_chat_member": {
            "chat": {"id": -555, "type": "supergroup"},
            "new_chat_member": {"status": "kicked"}}},
        {"update_id": 10, "my_chat_member": {
            "chat": {"id": -777, "type": "group"},
            "new_chat_member": {"status": "member"}}},
    ]
    got = tg.discover_group_ids(
        "TOK", transport=_updates_transport(updates), groups_path=path)
    assert got == [-777, -666]  # -555 dropped: the bot was kicked


def test_discover_group_ids_corrupt_cache_starts_empty(tmp_path):
    path = tmp_path / "groups.json"
    path.write_text("not json{{{")
    updates = [{"update_id": 1,
                "message": {"chat": {"id": -222, "type": "group"}}}]
    assert tg.discover_group_ids(
        "TOK", transport=_updates_transport(updates),
        groups_path=path) == [-222]


def test_broadcast_sends_two_messages_to_each_group_once(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"v")
    post = _ok_transport()
    msg = tg.broadcast_story("TOK", [-222, -333, -222], video_path=vid,
                             caption="Cap", links_text="L1", transport=post)
    assert msg == "Broadcast to 2 Telegram groups."
    by_chat = {}
    for call in post.calls:
        by_chat.setdefault(call["data"]["chat_id"], []).append(call["url"])
    assert sorted(by_chat) == ["-222", "-333"]  # deduped
    for calls in by_chat.values():
        assert [u.rsplit("/", 1)[-1] for u in calls] == [
            "sendVideo", "sendMessage"]


def test_broadcast_no_video_sends_caption_as_text():
    post = _ok_transport()
    msg = tg.broadcast_story("TOK", [-222], caption="Cap", links_text="",
                             transport=post)
    assert msg == "Broadcast to 1 Telegram group."
    assert len(post.calls) == 1
    assert post.calls[0]["url"].endswith("/sendMessage")
    assert post.calls[0]["data"]["text"] == "Cap"


def test_broadcast_failure_names_group_and_still_attempts_rest(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"v")
    attempted = []

    def post(url, *, data=None, files=None, timeout=None):
        attempted.append(data["chat_id"])
        if data["chat_id"] == "-333":
            return _FakeResp({"ok": False, "description": "bot was kicked"})
        return _FakeResp({"ok": True, "result": {"message_id": 1}})

    msg = tg.broadcast_story("TOK", [-222, -333], video_path=vid,
                             caption="C", links_text="L", transport=post)
    assert "-222" in attempted and "-333" in attempted  # all attempted
    assert "sent to 1 group" in msg
    assert "-333" in msg and "bot was kicked" in msg  # failure named loudly


def test_broadcast_empty_group_list_is_not_an_error():
    assert "No Telegram groups" in tg.broadcast_story("TOK", [])


def test_broadcast_rejects_non_numeric_group_id():
    with pytest.raises(tg.TelegramShareError, match="not a number"):
        tg.broadcast_story("TOK", ["nope"], caption="C",
                           transport=_ok_transport())


def test_share_bot_broadcasts_to_groups_skipping_own_chat(
        libdir, monkeypatch, tmp_path):
    lui = _library_ui_module()
    _prefs_double(monkeypatch, {"telegram_bot_token": "TOK",
                                "telegram_chat_id": 99})
    monkeypatch.setattr(tg, "DEFAULT_GROUPS_PATH", tmp_path / "groups.json")
    sid = _make_story_with_video(libdir, with_video=True)
    story = lib.load_story(sid)

    def post(url, *, data=None, files=None, timeout=None):
        post.calls.append({"url": url, "data": dict(data or {})})
        if url.endswith("/getUpdates"):
            return _FakeResp({"ok": True, "result": [
                {"update_id": 1,
                 "message": {"chat": {"id": -222, "type": "group"}}},
                {"update_id": 2,
                 "message": {"chat": {"id": 99, "type": "private"}}},
            ]})
        return _FakeResp({"ok": True, "result": {"message_id": 1}})

    post.calls = []

    monkeypatch.setattr(tg, "_httpx_post", post)
    msg = lui._share_via_telegram_bot(sid, story["meta"])
    assert "Broadcast to 1 Telegram group." in msg
    chat_ids = [c["data"]["chat_id"] for c in post.calls
                if "chat_id" in c["data"]]
    # own chat got the DM only; the group got the broadcast — same 2 msgs
    assert chat_ids.count("99") == 2
    assert chat_ids.count("-222") == 2
