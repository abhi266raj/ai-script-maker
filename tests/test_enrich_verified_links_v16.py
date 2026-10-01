"""Regression tests for issue #62 (P1): ``_do_enrich`` crashed with
``NameError`` because it referenced ``verified_links`` without ever
defining it — every post-save enrichment run died.

The stored Stage-1 news links (from save time) are sacred: enrichment
must keep them and never replace them with topic-search results. When
no verified links are stored, the freshly fetched links are used.

Run: python -m pytest tests/test_enrich_verified_links_v16.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from _fake_images import fetch_for  # noqa: E402


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


class _FakeArticle:
    def __init__(self, title, link, source):
        self.title = title
        self.link = link
        self.source = source


def _make_story(**kw):
    kw.setdefault("title", "Dog Showdown Reel")
    kw.setdefault("tone", "funny")
    kw.setdefault("dialogue_md", "")
    kw.setdefault("script_md", "AARAV: chubby dogs voting contest in the park")
    kw.setdefault("source_topic", "chubby dogs voting contest")
    kw.setdefault("source_headline", "Chubby dogs battle in voting contest")
    return lib.save_story(**kw)


def _enrich_mocks(monkeypatch, tags=(), images=(), articles=()):
    monkeypatch.setattr(lib, "_fetch_trending_hashtags",
                        lambda topic, story=None: (list(tags), "tags note"))
    monkeypatch.setattr(lib, "_fetch_images_for_story",
                        lambda story, topic, **k: list(images))
    monkeypatch.setattr(lib, "_fetch_news_articles",
                        lambda topic, limit=6: list(articles))
    monkeypatch.setattr(lib, "_fetch_image_bytes", fetch_for())


# ---------------------------------------------------------------------------
# Issue #62: verified_links must be defined — enrichment must not NameError
# ---------------------------------------------------------------------------

def test_do_enrich_keeps_verified_links_sacred(libdir, monkeypatch):
    verified = [{"title": "Chubby dogs battle in voting contest",
                 "url": "https://example.com/stage1-story",
                 "source": "Ex"}]
    sid = _make_story(hashtags=["#Old"], news_links=verified)
    _enrich_mocks(
        monkeypatch,
        tags=["#FreshTag"],
        articles=[_FakeArticle("Topic hit", "https://example.com/topic-hit",
                               "Ex")],
    )
    # Before the fix this raised NameError: name 'verified_links' is not defined.
    changed, note = lib._do_enrich(sid, "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    # Stored Stage-1 links are sacred: never replaced by topic-search results.
    assert meta["news_links"] == verified
    assert "Kept verified news links." in note
    # Hashtag merge still applied.
    assert "#FreshTag" in meta["hashtags"]


def test_do_enrich_uses_fresh_links_when_none_verified(libdir, monkeypatch):
    sid = _make_story(hashtags=["#Old"])
    _enrich_mocks(
        monkeypatch,
        articles=[_FakeArticle("Topic hit", "https://example.com/topic-hit",
                               "Ex")],
    )
    changed, note = lib._do_enrich(sid, "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    assert meta["news_links"] == [{"title": "Topic hit",
                                   "url": "https://example.com/topic-hit",
                                   "source": "Ex"}]
    assert "Found 1 news link(s)." in note
    assert changed is True


def test_do_enrich_ignores_malformed_stored_links(libdir, monkeypatch):
    sid = _make_story(hashtags=["#Old"])
    lib.update_story_fields(sid, news_links=[
        {"title": "No URL here"},          # dict without url -> not verified
        {"title": "Empty URL", "url": "", "source": "Ex"},  # empty url
        {"title": "Real", "url": "https://example.com/real",
         "source": "Ex"},
    ])
    _enrich_mocks(
        monkeypatch,
        articles=[_FakeArticle("Topic hit", "https://example.com/topic-hit",
                               "Ex")],
    )
    changed, note = lib._do_enrich(sid, "chubby dogs voting contest")
    meta = lib.load_story(sid)["meta"]
    # Only the well-formed stored link counts as verified.
    assert meta["news_links"] == [{"title": "Real",
                                   "url": "https://example.com/real",
                                   "source": "Ex"}]
    assert "Kept verified news links." in note


def test_do_enrich_unknown_story_raises_loudly(libdir, monkeypatch):
    _enrich_mocks(monkeypatch)
    with pytest.raises(RuntimeError, match="story not found"):
        lib._do_enrich("nope-not-a-story", "topic")
