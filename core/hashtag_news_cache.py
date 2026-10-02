"""24-hour cache for hashtags and news search results (#320).

Library mode was making fresh network calls on every hashtag refresh /
news lookup: `fetch_famous_english_hashtags` (X trends + Google Trends)
and `search_news` (5 sources) had no cache. This module provides a
file-based cache with a 24-hour TTL, following the pattern of
`core/verification_cache.py`.

Cache file: .hashtag_news_cache.json in the repo root (gitignored).
Only successful fetches are cached -- failures are never stored.
Pass `force_refresh=True` to bypass the cache (the UI's Force fetch).
"""
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 86400  # 24 hours (#320)
CACHE_FILE = Path(__file__).resolve().parent.parent / ".hashtag_news_cache.json"


def _cache_key(kind: str, query: str) -> str:
    """SHA256 of kind + normalized query."""
    normalized = " ".join((query or "").lower().split())
    raw = f"{kind}:{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_cache() -> Dict[str, Any]:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Hashtag/news cache unreadable (%s); starting fresh.", e)
        return {}


def _save_cache(data: Dict[str, Any]) -> None:
    """Persist the cache dict. Never raises."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except (OSError, ValueError) as e:
        logger.warning("Hashtag/news cache write failed (%s).", e)


def get_cached(kind: str, query: str) -> Optional[List[Dict[str, Any]]]:
    """Return cached entries for kind+query, or None on miss/expiry."""
    key = _cache_key(kind, query)
    entry = _load_cache().get(key)
    if not isinstance(entry, dict):
        return None
    ts = entry.get("ts", 0)
    if time.time() - ts > CACHE_TTL_SECONDS:
        return None
    items = entry.get("items")
    return items if isinstance(items, list) else None


def store_cache(kind: str, query: str, items: List[Dict[str, Any]]) -> None:
    """Cache successful fetch results. Never raises."""
    if not items:
        return
    data = _load_cache()
    data[_cache_key(kind, query)] = {"ts": time.time(), "items": items}
    _save_cache(data)


def cache_age_hours(kind: str, query: str) -> Optional[float]:
    """Age of the cached entry in hours, or None on miss."""
    key = _cache_key(kind, query)
    entry = _load_cache().get(key)
    if not isinstance(entry, dict):
        return None
    ts = entry.get("ts")
    if not isinstance(ts, (int, float)):
        return None
    return (time.time() - ts) / 3600.0
