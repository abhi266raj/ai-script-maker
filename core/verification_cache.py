"""Stage 1 verification cache: reuse verified news facts for 24 hours.

If the same news story is verified again within 24 hours, the cached
NewsVerificationReport is reused instead of re-running the validator
(saves API calls and time).

Cache file: .verification_cache.json in the repo root (gitignored).
Only SUCCESSFUL verifications are cached -- failures are never stored.
"""

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 86400  # 24 hours
CACHE_FILE = Path(__file__).resolve().parent.parent / ".verification_cache.json"


def _title_of(news_input: str) -> str:
    """Extract the news title (headline) from the input: the first non-empty
    line. The cache is keyed by TITLE so the same story with a slightly
    different description still hits cache."""
    for line in (news_input or "").splitlines():
        if line.strip():
            return line.strip()
    return (news_input or "").strip()


def _cache_key(news_input: str) -> str:
    """Return a SHA256 hex digest of the news TITLE as the cache key."""
    normalized = _title_of(news_input).lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    """Load the raw cache dict from disk. Returns {} on any problem."""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Verification cache unreadable (%s); starting fresh.", e)
        return {}


def _save_cache(data: dict) -> None:
    """Persist the cache dict to disk. Never raises."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except OSError as e:
        logger.warning("Could not write verification cache: %s", e)


def _entry_age_seconds(entry: dict) -> Optional[float]:
    """Age of a cache entry in seconds, or None if the timestamp is unusable."""
    try:
        return time.time() - float(entry.get("cached_at", 0))
    except (TypeError, ValueError):
        return None


def get_cached_verification(news_input: str) -> Optional[dict]:
    """Return the cached verification dict if fresh (< 24h), else None.

    Handles: file not found, corrupt JSON, missing key, expired entry --
    all return None. Expired entries are pruned opportunistically.
    """
    key = _cache_key(news_input)
    data = _load_cache()
    entry = data.get(key)
    if not isinstance(entry, dict):
        return None
    age = _entry_age_seconds(entry)
    if age is None or age > CACHE_TTL_SECONDS:
        data.pop(key, None)
        _save_cache(data)
        return None
    verification = entry.get("verification")
    return verification if isinstance(verification, dict) else None


def get_cache_age_hours(news_input: str) -> Optional[float]:
    """How old the cached entry is, in hours. None if no fresh entry."""
    key = _cache_key(news_input)
    entry = _load_cache().get(key)
    if not isinstance(entry, dict):
        return None
    age = _entry_age_seconds(entry)
    if age is None or age > CACHE_TTL_SECONDS:
        return None
    return age / 3600.0


def store_verification(news_input: str, verification_dict: dict) -> None:
    """Store a SUCCESSFUL verification result for 24 hours. Never raises."""
    if not isinstance(verification_dict, dict):
        logger.warning("Refusing to cache non-dict verification.")
        return
    data = _load_cache()
    data[_cache_key(news_input)] = {
        "cached_at": time.time(),
        "news_title": _title_of(news_input)[:160],
        "verification": verification_dict,
    }
    _save_cache(data)


def clear_expired() -> int:
    """Remove entries older than 24h. Returns the count removed."""
    data = _load_cache()
    expired_keys = []
    for k, v in data.items():
        if not isinstance(v, dict):
            expired_keys.append(k)
            continue
        age = _entry_age_seconds(v)
        if age is None or age > CACHE_TTL_SECONDS:
            expired_keys.append(k)
    for k in expired_keys:
        data.pop(k, None)
    if expired_keys:
        _save_cache(data)
    return len(expired_keys)
