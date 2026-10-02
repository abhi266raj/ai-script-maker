"""#320 — 24h cache for hashtags/news; force-refresh bypasses it."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import hashtag_news_cache as hnc


def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(hnc, "CACHE_FILE", tmp_path / "cache.json")


def test_store_and_hit(tmp_path, monkeypatch):
    _isolated_cache(tmp_path, monkeypatch)
    hnc.store_cache("news", "Delhi Metro", [{"title": "A"}])
    assert hnc.get_cached("news", "Delhi Metro") == [{"title": "A"}]


def test_miss_returns_none(tmp_path, monkeypatch):
    _isolated_cache(tmp_path, monkeypatch)
    assert hnc.get_cached("news", "nope") is None


def test_expired_returns_none(tmp_path, monkeypatch):
    _isolated_cache(tmp_path, monkeypatch)
    hnc.store_cache("news", "old", [{"title": "A"}])
    monkeypatch.setattr(hnc, "CACHE_TTL_SECONDS", -1)  # everything expired
    assert hnc.get_cached("news", "old") is None


def test_empty_items_not_stored(tmp_path, monkeypatch):
    _isolated_cache(tmp_path, monkeypatch)
    hnc.store_cache("news", "empty", [])
    assert hnc.get_cached("news", "empty") is None


def test_query_normalized(tmp_path, monkeypatch):
    _isolated_cache(tmp_path, monkeypatch)
    hnc.store_cache("news", "  Delhi   METRO ", [{"title": "A"}])
    assert hnc.get_cached("news", "delhi metro") == [{"title": "A"}]


def test_search_news_prefers_cache():
    from tools.news_fetcher import NewsFetcher
    f = NewsFetcher()
    fake_articles = [{"title": "Cached", "link": "https://x.com/a",
                      "source": "X", "snippet": "", "published": "",
                      "age_hours": None, "time_label": ""}]
    with patch("tools.news_fetcher._cache_get", return_value=fake_articles) as gc, \
         patch.object(NewsFetcher, "search_news_multi") as multi:
        arts = f.search_news("delhi metro", limit=5)
        assert len(arts) == 1 and arts[0].title == "Cached"
        gc.assert_called_once()
        multi.assert_not_called()  # no network on cache hit


def test_search_news_force_refresh_skips_cache():
    from tools.news_fetcher import NewsFetcher
    from core.models import NewsArticle
    f = NewsFetcher()
    live = [NewsArticle(title="Live", link="https://y.com/b", source="Y")]
    with patch("tools.news_fetcher._cache_get") as gc, \
         patch.object(NewsFetcher, "search_news_multi",
                      return_value=(live, [])) as multi, \
         patch("tools.news_fetcher._cache_store") as sc:
        arts = f.search_news("delhi metro", force_refresh=True)
        assert arts[0].title == "Live"
        gc.assert_not_called()  # cache not consulted
        multi.assert_called_once()
        sc.assert_called_once()  # fresh result re-cached


def test_hashtags_prefer_cache():
    from tools.news_fetcher import NewsFetcher
    f = NewsFetcher()
    cached = [{"tag": "#Cached", "headline": "h", "link": "", "source": "X"}]
    with patch("tools.news_fetcher._cache_get", return_value=cached):
        with patch.object(NewsFetcher, "_fetch_x_trend_labels",
                          side_effect=AssertionError("network hit!")):
            assert f.fetch_famous_english_hashtags() == cached


def test_hashtags_force_refresh_skips_cache():
    from tools.news_fetcher import NewsFetcher
    f = NewsFetcher()
    with patch("tools.news_fetcher._cache_get") as gc, \
         patch.object(NewsFetcher, "_fetch_x_trend_labels", return_value=[]), \
         patch.object(NewsFetcher, "_fetch_google_trends_topics", return_value=[]), \
         patch("tools.news_fetcher._cache_store") as sc:
        assert f.fetch_famous_english_hashtags(force_refresh=True) == []
        gc.assert_not_called()
        sc.assert_called_once()
