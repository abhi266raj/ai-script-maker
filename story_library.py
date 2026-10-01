"""Saved Stories Library (v1.5).

Stories are stored as Markdown files with YAML frontmatter in a shared
``~/Documents/HindiReelStudio/stories/`` directory, so both the Streamlit
app and the native macOS app can read them. Uploaded videos/images live
alongside the story file.

File layout::

    <story-id>.md            # Markdown + frontmatter (the story)
    <story-id>.mp4           # uploaded generated video (if any)
    <story-id>_img1.png      # manually uploaded images (if any)

Enrichment (images + news links + hashtag refresh) runs in background
threads AFTER the story is saved, so saving never waits on the network.
"""

from __future__ import annotations

import datetime
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LIBRARY_ROOT = Path.home() / "Documents" / "HindiReelStudio"
STORIES_DIR = LIBRARY_ROOT / "stories"

_STORY_ID_RE = re.compile(r"^[0-9A-Za-z-]{8,64}$")
_ENRICH_LOCKS: Dict[str, threading.Lock] = {}
_ENRICH_THREADS: Dict[str, threading.Thread] = {}


def library_root() -> Path:
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    return LIBRARY_ROOT


def stories_dir() -> Path:
    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    return STORIES_DIR


def new_story_id() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:6]}"


def _check_id(story_id: str) -> str:
    if not _STORY_ID_RE.match(story_id or ""):
        raise ValueError(f"Invalid story id: {story_id!r}")
    return story_id


def story_path(story_id: str) -> Path:
    return stories_dir() / f"{_check_id(story_id)}.md"


# ---------------------------------------------------------------------------
# Minimal YAML-frontmatter (de)serializer — no new dependencies
# ---------------------------------------------------------------------------

def _yaml_escape(value: str) -> str:
    v = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{v}"'


def _dump_frontmatter(data: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, val in data.items():
        if isinstance(val, list):
            if val and isinstance(val[0], dict):
                lines.append(f"{key}:")
                for item in val:
                    first = True
                    for k, v in item.items():
                        prefix = "  - " if first else "    "
                        lines.append(f"{prefix}{k}: {_yaml_escape(v)}")
                        first = False
            else:
                inner = ", ".join(_yaml_escape(v) for v in val)
                lines.append(f"{key}: [{inner}]")
        else:
            lines.append(f"{key}: {_yaml_escape(val)}")
    lines.append("---")
    return "\n".join(lines)


def _unquote(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return token


def _split_inline_list(inner: str) -> List[str]:
    """Split a comma-separated list, ignoring commas inside double quotes."""
    parts: List[str] = []
    buf: List[str] = []
    in_q = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and in_q and i + 1 < len(inner):
            buf.append(ch)
            buf.append(inner[i + 1])
            i += 2
            continue
        if ch == '"':
            in_q = not in_q
        if ch == "," and not in_q:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """Return (frontmatter dict, markdown body)."""
    data: Dict[str, Any] = {}
    if not text.startswith("---"):
        return data, text
    end = text.find("\n---", 3)
    if end == -1:
        return data, text
    raw = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    current_list_key: Optional[str] = None
    current_item: Optional[Dict[str, str]] = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            current_item = {}
            data.setdefault(current_list_key, []).append(current_item)
            rest = line[4:].strip()
            if rest:
                k, _, v = rest.partition(":")
                current_item[k.strip()] = _unquote(v)
        elif line.startswith("    ") and current_item is not None:
            k, _, v = line.strip().partition(":")
            current_item[k.strip()] = _unquote(v)
        elif not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                data[k] = [_unquote(t) for t in _split_inline_list(inner)] if inner else []
                current_list_key, current_item = None, None
            elif v == "":
                data[k] = []
                current_list_key, current_item = k, None
            else:
                data[k] = _unquote(v)
                current_list_key, current_item = None, None
    return data, body


# ---------------------------------------------------------------------------
# Story CRUD
# ---------------------------------------------------------------------------

def build_story_markdown(meta: Dict[str, Any], dialogue_md: str, script_md: str) -> str:
    """Assemble the full .md file content."""
    front = _dump_frontmatter(meta)
    dlg = dialogue_md.strip()
    body = f"{front}\n\n# {meta.get('title', 'Untitled Story')}\n\n"
    if dlg:
        body += f"## Dialogue\n\n{dlg}\n\n"
    body += f"## Script\n\n{script_md.strip()}\n"
    return body


def save_story(
    title: str,
    tone: str,
    hashtags: List[str],
    dialogue_md: str,
    script_md: str,
    source_topic: str = "",
    source_headline: str = "",
) -> str:
    """Save a story immediately (no network). Returns the story id."""
    story_id = new_story_id()
    meta = {
        "id": story_id,
        "title": title or "Untitled Story",
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "tone": tone or "",
        "hashtags": [h for h in (hashtags or []) if h],
        "news_links": [],
        "image_urls": [],
        "uploaded_images": [],
        "video_file": "",
        "enrichment_status": "pending",
        "source_topic": source_topic or "",
        "source_headline": source_headline or "",
    }
    story_path(story_id).write_text(
        build_story_markdown(meta, dialogue_md, script_md), encoding="utf-8")
    return story_id


def load_story(story_id: str) -> Optional[Dict[str, Any]]:
    """Load a story: {'meta': {...}, 'body': '...', 'dialogue': '...', 'script': '...' }."""
    path = story_path(story_id)
    if not path.exists():
        return None
    meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    dialogue, script = _split_sections(body)
    return {"meta": meta, "body": body, "dialogue": dialogue, "script": script}


def _split_sections(body: str) -> tuple[str, str]:
    """Split the markdown body into (dialogue, script) sections."""
    dlg, scr = "", ""
    current = None
    buf: List[str] = []
    for line in body.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("## "):
            if current == "dialogue":
                dlg = "\n".join(buf).strip()
            elif current == "script":
                scr = "\n".join(buf).strip()
            current = "dialogue" if "dialog" in stripped else ("script" if "script" in stripped else None)
            buf = []
        elif current:
            buf.append(line)
    if current == "dialogue":
        dlg = "\n".join(buf).strip()
    elif current == "script":
        scr = "\n".join(buf).strip()
    return dlg, scr


def list_stories() -> List[Dict[str, Any]]:
    """List story metadata (frontmatter only), newest first."""
    stories: List[Dict[str, Any]] = []
    if not STORIES_DIR.exists():
        return stories
    for path in STORIES_DIR.glob("*.md"):
        try:
            meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
            if meta.get("id"):
                stories.append(meta)
        except Exception:
            continue
    stories.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return stories


def update_story_fields(story_id: str, **fields: Any) -> bool:
    """Merge fields into the story's frontmatter (body untouched)."""
    path = story_path(story_id)
    if not path.exists():
        return False
    meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    meta.update(fields)
    path.write_text(
        f"{_dump_frontmatter(meta)}\n\n{body.strip()}\n", encoding="utf-8")
    return True


def delete_story(story_id: str) -> bool:
    """Delete a story and its media files. Returns True if anything was removed."""
    _check_id(story_id)
    removed = False
    md = stories_dir() / f"{story_id}.md"
    if md.exists():
        md.unlink()
        removed = True
    for media in stories_dir().glob(f"{story_id}.*"):
        if media != md and media.is_file():
            try:
                media.unlink()
                removed = True
            except OSError:
                pass
    for media in stories_dir().glob(f"{story_id}_img*"):
        try:
            media.unlink()
            removed = True
        except OSError:
            pass
    return removed


def delete_all_stories() -> int:
    """Delete every story and its media. Returns the story count removed."""
    count = 0
    if not STORIES_DIR.exists():
        return 0
    for path in STORIES_DIR.glob("*.md"):
        try:
            if delete_story(path.stem):
                count += 1
        except Exception:
            continue
    return count


# ---------------------------------------------------------------------------
# Media uploads (video + manual images)
# ---------------------------------------------------------------------------

_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def store_video_upload(story_id: str, data: bytes, filename: str) -> str:
    """Store an uploaded video next to the story. Returns the stored filename."""
    ext = Path(filename).suffix.lower() or ".mp4"
    if ext not in _VIDEO_EXTS:
        raise ValueError(f"Unsupported video type: {ext}")
    _check_id(story_id)
    # Remove any previous video for this story.
    for old in stories_dir().glob(f"{story_id}.*"):
        if old.suffix.lower() in _VIDEO_EXTS:
            old.unlink(missing_ok=True)
    stored = f"{story_id}{ext}"
    (stories_dir() / stored).write_bytes(data)
    update_story_fields(story_id, video_file=stored)
    return stored


def store_image_upload(story_id: str, data: bytes, filename: str) -> str:
    """Store a manually uploaded image next to the story. Returns stored filename."""
    ext = Path(filename).suffix.lower() or ".png"
    if ext not in _IMAGE_EXTS:
        raise ValueError(f"Unsupported image type: {ext}")
    story = load_story(story_id)
    existing = (story["meta"].get("uploaded_images") or []) if story else []
    n = len(existing) + 1
    stored = f"{story_id}_img{n}{ext}"
    (stories_dir() / stored).write_bytes(data)
    update_story_fields(story_id, uploaded_images=[*existing, stored])
    return stored


def media_path(story_id: str, filename: str) -> Optional[Path]:
    """Resolve a stored media filename to a path (guards against traversal)."""
    _check_id(story_id)
    name = Path(filename).name
    if not name.startswith(story_id):
        return None
    path = stories_dir() / name
    return path if path.exists() else None


def remove_fetched_image(story_id: str, url: str) -> bool:
    """Remove one auto-fetched image URL (the overwrite control)."""
    story = load_story(story_id)
    if not story:
        return False
    urls = [u for u in (story["meta"].get("image_urls") or []) if u != url]
    update_story_fields(story_id, image_urls=urls)
    return True


def remove_uploaded_image(story_id: str, filename: str) -> bool:
    """Remove one manually uploaded image file and its frontmatter entry."""
    story = load_story(story_id)
    if not story:
        return False
    path = media_path(story_id, filename)
    try:
        if path:
            path.unlink(missing_ok=True)
    except OSError:
        pass
    uploaded = [f for f in (story["meta"].get("uploaded_images") or []) if f != filename]
    update_story_fields(story_id, uploaded_images=uploaded)
    return True


# ---------------------------------------------------------------------------
# Post-save enrichment (background threads; best-effort; never blocks save)
# ---------------------------------------------------------------------------

def _og_image(article_url: str, timeout: float = 8.0) -> Optional[str]:
    """Best-effort og:image extraction from an article page."""
    try:
        import httpx
        from bs4 import BeautifulSoup
        resp = httpx.get(
            article_url, timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for prop in ("og:image", "twitter:image"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                url = urljoin(article_url, tag["content"].strip())
                if url.startswith(("http://", "https://")) and not url.startswith("data:"):
                    return url
        # Fallbacks some publishers use instead of og:image.
        link_src = soup.find("link", rel="image_src")
        if link_src and link_src.get("href"):
            url = urljoin(article_url, link_src["href"].strip())
            if url.startswith(("http://", "https://")):
                return url
        item = soup.find(attrs={"itemprop": "image"})
        if item:
            content = (item.get("content") or item.get("src") or "").strip()
            if content:
                url = urljoin(article_url, content)
                if url.startswith(("http://", "https://")):
                    return url
    except Exception:
        pass
    return None


def _enrich_worker(story_id: str, topic: str, do_work) -> None:
    """Run do_work under the per-story lock; write back to the story.

    The story's enrichment_status is ALWAYS flipped to done at the end —
    even if every fetch fails — so the UI never sticks on "pending".
    """
    lock = _ENRICH_LOCKS.setdefault(story_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return
    try:
        do_work(story_id, topic)
    finally:
        try:
            update_story_fields(story_id, enrichment_status="done")
        except Exception:
            pass
        lock.release()


def _fetch_news_articles(topic: str, limit: int = 6):
    """Best-effort news search; returns [] on any failure."""
    try:
        from tools.news_fetcher import news_fetcher
        return news_fetcher.search_news(topic, limit=limit) or []
    except Exception:
        return []


def _fetch_article_images(articles) -> List[str]:
    """Best-effort og:image extraction from article pages, in parallel."""
    found: List[str] = []
    found_lock = threading.Lock()
    threads: List[threading.Thread] = []

    def _grab(url: str) -> None:
        img = _og_image(url)
        if img:
            with found_lock:
                if img not in found:
                    found.append(img)

    for a in articles[:4]:
        link = getattr(a, "link", "")
        if link:
            t = threading.Thread(target=_grab, args=(link,), daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join(timeout=12.0)
    return found[:6]


def _tag_words(tag: str) -> set:
    """Word set for a hashtag, splitting camelCase so '#DelhiRain' → delhi, rain."""
    words: set = set()
    for token in re.findall(r"[A-Za-z]{4,}", tag):
        words.add(token.lower())
        for part in re.findall(r"[A-Z]?[a-z]+", token):
            if len(part) >= 4:
                words.add(part.lower())
    return words


def _fetch_trending_hashtags(topic: str) -> List[str]:
    """Trending hashtags matching the topic's words (best-effort)."""
    tags: List[str] = []
    try:
        from tools.news_fetcher import news_fetcher
        trending = news_fetcher.fetch_famous_english_hashtags(limit=12) or []
        words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", topic)}
        for entry in trending:
            tag = entry.get("tag", "") if isinstance(entry, dict) else str(entry)
            if words & _tag_words(tag) and tag not in tags:
                tags.append(tag)
            if len(tags) >= 3:
                break
    except Exception:
        pass
    return tags


def refresh_hashtags(story_id: str, topic: str = "") -> bool:
    """Find trending hashtags for the story's topic and merge them in.

    Returns True when at least one new hashtag was found and saved.
    Never wipes the existing hashtags.
    """
    story = load_story(story_id)
    if not story:
        return False
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        return False
    new_tags = _fetch_trending_hashtags(topic)
    if not new_tags:
        return False
    merged = list(story["meta"].get("hashtags") or [])
    added = False
    for t in new_tags:
        if t not in merged:
            merged.append(t)
            added = True
    if added:
        update_story_fields(story_id, hashtags=merged)
    return added


def refresh_images(story_id: str, topic: str = "") -> bool:
    """Re-fetch news images for the story's topic and replace the fetched set.

    Returns True when new images were found and saved. The existing fetched
    set and manual uploads are kept when the fetch finds nothing.
    """
    story = load_story(story_id)
    if not story:
        return False
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        return False
    found = _fetch_article_images(_fetch_news_articles(topic, limit=6))
    if not found:
        return False
    update_story_fields(story_id, image_urls=found)
    return True


def _do_media_refresh(story_id: str, topic: str) -> None:
    """Retry path: refresh hashtags + images ONLY.

    Never touches news_links and never touches the story content.
    """
    image_urls = _fetch_article_images(_fetch_news_articles(topic, limit=6))
    new_tags = _fetch_trending_hashtags(topic)
    story = load_story(story_id)
    if not story:
        return
    meta = story["meta"]
    merged_tags = list(meta.get("hashtags") or [])
    for t in new_tags:
        if t not in merged_tags:
            merged_tags.append(t)
    update_story_fields(
        story_id,
        image_urls=image_urls or meta.get("image_urls") or [],
        hashtags=merged_tags,
    )


def _do_enrich(story_id: str, topic: str) -> None:
    articles = _fetch_news_articles(topic, limit=6)
    news_links: List[Dict[str, str]] = []
    for a in articles[:6]:
        news_links.append({
            "title": getattr(a, "title", ""),
            "url": getattr(a, "link", ""),
            "source": getattr(a, "source", ""),
        })
    image_urls = _fetch_article_images(articles)
    new_tags = _fetch_trending_hashtags(topic)
    story = load_story(story_id)
    if not story:
        return
    meta = story["meta"]
    merged_tags = list(meta.get("hashtags") or [])
    for t in new_tags:
        if t not in merged_tags:
            merged_tags.append(t)
    update_story_fields(
        story_id,
        news_links=news_links or meta.get("news_links") or [],
        image_urls=image_urls or meta.get("image_urls") or [],
        hashtags=merged_tags,
    )


def start_enrichment(story_id: str, topic: str) -> bool:
    """Kick off post-save enrichment in a daemon thread. Never raises."""
    try:
        _check_id(story_id)
        if not (topic or "").strip():
            update_story_fields(story_id, enrichment_status="done")
            return False
        t = threading.Thread(
            target=_enrich_worker, args=(story_id, topic.strip(), _do_enrich),
            daemon=True, name=f"enrich-{story_id}")
        _ENRICH_THREADS[story_id] = t
        t.start()
        return True
    except Exception:
        return False


def retry_enrichment(story_id: str) -> bool:
    """Re-run the hashtag + image fetch for a story — and nothing else.

    News links and the story content are never touched by a retry.
    """
    story = load_story(story_id)
    if not story:
        return False
    topic = (story["meta"].get("source_topic") or story["meta"].get("title") or "").strip()
    if not topic:
        return False
    try:
        _check_id(story_id)
        update_story_fields(story_id, enrichment_status="pending")
        t = threading.Thread(
            target=_enrich_worker, args=(story_id, topic, _do_media_refresh),
            daemon=True, name=f"retry-{story_id}")
        t.start()
        return True
    except Exception:
        return False
