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
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LIBRARY_ROOT = Path.home() / "Documents" / "HindiReelStudio"
STORIES_DIR = LIBRARY_ROOT / "stories"
PREFS_PATH = LIBRARY_ROOT / "prefs.json"

_STORY_ID_RE = re.compile(r"^[0-9A-Za-z-]{8,64}$")
_ENRICH_LOCKS: Dict[str, threading.Lock] = {}
_ENRICH_THREADS: Dict[str, threading.Thread] = {}


def library_root() -> Path:
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    return LIBRARY_ROOT


def stories_dir() -> Path:
    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    return STORIES_DIR


# ---------------------------------------------------------------------------
# Preferences (persisted UI choices, e.g. the verifier's "Use AI" engine)
# ---------------------------------------------------------------------------

def load_prefs() -> Dict[str, Any]:
    """Read the persisted prefs file; {} when missing or unreadable."""
    try:
        if PREFS_PATH.exists():
            data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_prefs(updates: Dict[str, Any]) -> None:
    """Merge ``updates`` into the persisted prefs file. Never raises."""
    try:
        prefs = load_prefs()
        prefs.update(updates)
        LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
        PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# AI engines for Library AI processing
# ---------------------------------------------------------------------------
# Mirrors the Studio's ENGINE_OPTIONS (app.py) but lives here so the Library
# UI can offer engine choice without importing app.py (which would be
# circular: app.py imports library_ui which imports this module).
LIBRARY_ENGINE_OPTIONS = {
    "Local First Then Antigravity": "first_local_then_agy",
    "Antigravity": "agy_only",
    "Codex": "codex_only",
    "Grok Low": "grok_low",
    "Grok Medium": "grok_medium",
    "Grok High": "grok_high",
    "On-device": "fm_only",
}
LIBRARY_ENGINE_MODES = frozenset(LIBRARY_ENGINE_OPTIONS.values())
DEFAULT_LIBRARY_AI_ENGINE = "Local First Then Antigravity"


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
    news_links: Optional[List[Dict[str, str]]] = None,
    image_urls: Optional[List[str]] = None,
) -> str:
    """Save a story immediately (no network). Returns the story id."""
    story_id = new_story_id()
    meta = {
        "id": story_id,
        "title": title or "Untitled Story",
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "tone": tone or "",
        "hashtags": [h for h in (hashtags or []) if h],
        "news_links": [dict(l) for l in (news_links or [])],
        "image_urls": [u for u in (image_urls or []) if u],
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


def update_fetched_image_url(story_id: str, index: int, new_url: str) -> bool:
    """Replace one auto-fetched image URL by list position (the edit control).

    Fails loudly with ValueError when the story is unknown, the index is
    out of range, or the new value is not a non-empty http(s) URL — the
    caller surfaces the error instead of silently keeping a bad value.
    """
    story = load_story(story_id)
    if not story:
        raise ValueError(f"Unknown story: {story_id!r}")
    urls = list(story["meta"].get("image_urls") or [])
    if not 0 <= index < len(urls):
        raise ValueError(f"No fetched image at position {index}.")
    u = (new_url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        raise ValueError("The new image address must be a non-empty http(s) URL.")
    urls[index] = u
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
    """Best-effort hero-image extraction from an article page.

    Checks og:image / twitter:image, JSON-LD structured data (where many
    publishers put the hero image), and older link/itemprop fallbacks.
    """
    try:
        import httpx
        import json as _json
        from bs4 import BeautifulSoup
        resp = httpx.get(
            article_url, timeout=timeout, follow_redirects=True,
            headers={
                "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/126.0.0.0 Safari/537.36"),
                "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                           "image/avif,image/webp,*/*;q=0.8"),
                "Accept-Language": "en-US,en;q=0.9",
            })
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        def _ok(url: str) -> Optional[str]:
            url = urljoin(article_url, url.strip())
            if url.startswith(("http://", "https://")):
                return url
            return None

        for prop in ("og:image", "og:image:secure_url", "twitter:image"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                hit = _ok(tag["content"])
                if hit:
                    return hit
        # JSON-LD structured data — many publishers put the hero image here.
        for ld in soup.find_all("script", type="application/ld+json"):
            try:
                data = _json.loads(ld.get_text() or "")
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            queue = list(items)
            while queue:
                item = queue.pop(0)
                if not isinstance(item, dict):
                    continue
                graph = item.get("@graph")
                if isinstance(graph, list):
                    queue.extend(graph)
                img = item.get("image")
                cands = img if isinstance(img, list) else [img]
                for c in cands:
                    u = c.get("url") if isinstance(c, dict) else c
                    if isinstance(u, str) and u.strip():
                        hit = _ok(u)
                        if hit:
                            return hit
        # Fallbacks some publishers use instead of og:image.
        link_src = soup.find("link", rel="image_src")
        if link_src and link_src.get("href"):
            hit = _ok(link_src["href"])
            if hit:
                return hit
        item = soup.find(attrs={"itemprop": "image"})
        if item:
            content = (item.get("content") or item.get("src") or "").strip()
            if content:
                hit = _ok(content)
                if hit:
                    return hit
    except Exception:
        pass
    return None


def _enrich_worker(story_id: str, topic: str, do_work) -> None:
    """Run do_work under the per-story lock; write back to the story.

    The story's enrichment_status is ALWAYS flipped to done at the end —
    even if every fetch fails — so the UI never sticks on "pending".
    When do_work returns a non-empty string it is recorded as the story's
    ``refresh_note`` so the outcome (success / no-change / failure) is
    visible instead of silent.
    """
    lock = _ENRICH_LOCKS.setdefault(story_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return
    note = ""
    try:
        result = do_work(story_id, topic)
        if isinstance(result, str) and result.strip():
            note = result.strip()
    finally:
        try:
            fields: Dict[str, Any] = {"enrichment_status": "done", "refresh_kind": ""}
            if note:
                fields["refresh_note"] = note
            update_story_fields(story_id, **fields)
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


def _url_is_image(url: str) -> bool:
    """Light preflight: accept only URLs that actually serve an image."""
    try:
        import httpx
        try:
            r = httpx.head(url, timeout=8, follow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                return r.headers.get("content-type", "").startswith("image/")
        except Exception:
            pass
        # Some hosts reject HEAD — do a minimal GET and check the content type.
        with httpx.stream("GET", url, timeout=8, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"}) as r:
            return r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")
    except Exception:
        return False


def _search_web_images(topic: str, limit: int = 4) -> List[str]:
    """Fallback: web image search via the bundled image-search CLI.

    Only used when article-page extraction finds nothing at all.
    """
    try:
        import json as _json
        import subprocess
        proc = subprocess.run(
            ["/opt/hatch/bin/image-search", topic, "--max-results", str(limit)],
            capture_output=True, text=True, timeout=45)
        data = _json.loads(proc.stdout or "{}")
        urls: List[str] = []
        for r in data.get("results") or []:
            u = r.get("media_url") or r.get("thumbnail_cdn_url") or ""
            if u.startswith("https://") and u not in urls:
                urls.append(u)
                if len(urls) >= limit:
                    break
        return urls
    except Exception:
        return []


def _grab_og_images(urls: List[str], tries: int = 3) -> List[str]:
    """Parallel og:image hero extraction from a list of page URLs."""
    found: List[str] = []
    found_lock = threading.Lock()
    threads: List[threading.Thread] = []

    def _grab(url: str) -> None:
        for attempt in range(tries):
            img = _og_image(url)
            if img:
                with found_lock:
                    if img not in found:
                        found.append(img)
                return
            time.sleep(1.0 * (attempt + 1))

    for link in urls:
        if link:
            t = threading.Thread(target=_grab, args=(link,), daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join(timeout=30.0)
    return found


def _grab_article_images(urls: List[str], tries: int = 3,
                         per_page: int = 3) -> List[str]:
    """Parallel article-page image extraction from a list of page URLs.

    Each article's HTML is fetched (httpx, timeout, retries) and passed to
    ``tools.story_link.extract_story_images``, which pulls og:image →
    twitter:image → JSON-LD → in-article <img>/<figure> photos. News pages
    carry their real photos in body <img> tags, so this finds images that
    an og:image-only grab misses. Relative and lazy-load URLs are
    absolutized; logos, sprites, SVGs and tracking pixels are filtered.
    """
    from tools.story_link import extract_story_images

    found: List[str] = []
    found_lock = threading.Lock()
    threads: List[threading.Thread] = []

    def _grab(url: str) -> None:
        html = ""
        for attempt in range(tries):
            try:
                import httpx
                resp = httpx.get(
                    url, timeout=12.0, follow_redirects=True,
                    headers={
                        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                                       "Chrome/126.0.0.0 Safari/537.36"),
                        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                                   "image/avif,image/webp,*/*;q=0.8"),
                        "Accept-Language": "en-US,en;q=0.9",
                    })
                ctype = resp.headers.get("content-type", "")
                if resp.status_code == 200 and "html" in ctype.lower():
                    html = resp.text
                    break
            except Exception:
                html = ""
            time.sleep(1.0 * (attempt + 1))
        if not html:
            return
        try:
            imgs = extract_story_images(html, url, limit=per_page)
        except Exception:
            return
        with found_lock:
            for img in imgs:
                if img not in found:
                    found.append(img)

    for link in urls:
        if link:
            t = threading.Thread(target=_grab, args=(link,), daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join(timeout=30.0)
    return found


def _story_direct_link_urls(story: Optional[Dict[str, Any]]) -> List[str]:
    """Direct publisher URLs from the story's verified Stage-1 news links.

    These links were verified at save time to point at the exact story the
    reel was built from, so their hero images are the most on-topic image
    source available. Topic-search links are never allowed to replace these
    verified links — they are only *read* here for hero images.
    """
    urls: List[str] = []
    if not story:
        return urls
    for lk in (story.get("meta") or {}).get("news_links") or []:
        u = (lk.get("url") or "").strip() if isinstance(lk, dict) else ""
        if u.startswith(("http://", "https://")) and u not in urls:
            urls.append(u)
    return urls


def _fetch_images_for_story(story: Optional[Dict[str, Any]], topic: str,
                            tries: int = 3) -> List[str]:
    """Images for a story: verified story links first, then topic search.

    The story's own verified news links point at the exact story's publisher
    pages, so their article images are the most on-topic. Each page's HTML
    is fetched and its og:image → twitter:image → JSON-LD → in-article
    <img> photos are extracted (news sites carry real photos in body <img>
    tags). Only when those yield nothing do we fall back to topic-search
    articles and web image search.
    """
    direct = _story_direct_link_urls(story)
    if direct:
        found = _grab_article_images(direct[:6], tries=tries)
        if found:
            return found[:6]
    articles = _fetch_news_articles(topic, limit=6)
    return _fetch_article_images(articles, topic, tries=tries)


def _fetch_article_images(articles, topic: str = "", tries: int = 3) -> List[str]:
    """Hero images for a topic.

    Tries hero-image extraction from the article pages (parallel, with
    retries). If that finds nothing at all, falls back to a web image search
    for the topic so the story still gets images.
    """
    urls = [getattr(a, "link", "") for a in articles[:6]]
    found = _grab_og_images(urls, tries=tries)
    if not found and topic.strip():
        for u in _search_web_images(topic.strip(), limit=4):
            if _url_is_image(u) and u not in found:
                found.append(u)
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


_HASHTAG_STOPWORDS = {
    "with", "from", "have", "this", "that", "will", "would", "about",
    "into", "over", "after", "before", "between", "through", "during",
    "under", "their", "there", "these", "those", "what", "when", "where",
    "which", "while", "your", "yours", "news", "viral", "video", "watch",
    "says", "said", "told", "more", "most", "very", "just", "scene",
}


def _keyword_list(text: str) -> List[str]:
    """Significant English keywords of a title, in order, de-duplicated."""
    out: List[str] = []
    seen: set = set()
    for w in re.findall(r"[A-Za-z]{4,}", text or ""):
        lw = w.lower()
        if lw in _HASHTAG_STOPWORDS or lw in seen:
            continue
        seen.add(lw)
        out.append(w)
    return out


def _camel_tag(words: List[str], max_words: int = 3) -> str:
    """Build a CamelCase hashtag from keywords, e.g. ['Fat','Dogs','Delhi'] → #FatDogsDelhi."""
    parts = [w[:1].upper() + w[1:].lower() for w in words[:max_words]]
    tag = "#" + "".join(parts)
    return tag if len(tag) > 4 else ""


def _story_content_texts(story: Optional[Dict[str, Any]]) -> List[str]:
    """The story's own words, most specific first: headline, title, topic, script."""
    if not story:
        return []
    meta = story.get("meta") or {}
    return [
        meta.get("source_headline") or "",
        meta.get("title") or "",
        meta.get("source_topic") or "",
        story.get("script") or "",
    ]


def _fetch_trending_hashtags(topic: str, story: Optional[Dict[str, Any]] = None) -> List[str]:
    """Content-first hashtag discovery. Always returns at least one tag.

    1. Tags built from the story's own content (headline/title/topic/script).
    2. Trending hashtags whose words overlap the story's content words.
    3. A tag derived from the topic itself.
    4. Guaranteed fallback so a story never ends up hashtag-less.

    Live article titles are deliberately NOT used: they come from whatever
    a news search happens to return and produce random, off-content tags.
    """
    tags: List[str] = []
    texts = [t for t in _story_content_texts(story) if t] or [topic]
    content = " ".join(texts)
    content_words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", content)}
    content_words -= _HASHTAG_STOPWORDS
    # 1. from the story's own words (headline first — it names the story)
    for text in texts:
        t = _camel_tag(_keyword_list(text))
        if t and t not in tags:
            tags.append(t)
        if len(tags) >= 4:
            break
    # 2. trending tags that actually match the story's content
    try:
        from tools.news_fetcher import news_fetcher
        trending = news_fetcher.fetch_famous_english_hashtags(limit=12) or []
        for entry in trending:
            tag = entry.get("tag", "") if isinstance(entry, dict) else str(entry)
            if tag and (content_words & _tag_words(tag)) and tag not in tags:
                tags.append(tag)
            if len(tags) >= 8:
                break
    except Exception:
        pass
    # 3. derive from the topic itself
    t = _camel_tag(_keyword_list(topic))
    if t and t not in tags and len(tags) < 8:
        tags.append(t)
    # 4. guarantee: never return empty
    if not tags:
        words = re.findall(r"[A-Za-z]{3,}", topic)
        if words:
            tags.append("#" + "".join(w.capitalize() for w in words[:3]))
        else:
            tags.append("#HindiReelStudio")
    return tags[:8]


def _validate_ai_tags(raw_tags: List[str],
                      story: Optional[Dict[str, Any]]) -> List[str]:
    """Keep only AI-suggested tags that are well-formed and story-grounded.

    A tag survives only if it looks like #CamelCase and at least one of its
    words appears in the story's own content words. This keeps the AI honest:
    it may rank and rephrase, but it cannot invent off-topic tags.
    """
    content_words = {w.lower()
                     for w in re.findall(r"[A-Za-z]{4,}", " ".join(_story_content_texts(story)))}
    content_words -= _HASHTAG_STOPWORDS
    out: List[str] = []
    for t in raw_tags or []:
        t = (t or "").strip()
        if not re.fullmatch(r"#[A-Za-z][A-Za-z0-9]{2,29}", t):
            continue
        if t in out:
            continue
        if content_words & _tag_words(t):
            out.append(t)
        if len(out) >= 8:
            break
    return out


def _ai_hashtag_suggestions(story: Dict[str, Any], topic: str,
                            engine_mode: str) -> List[str]:
    """Ask the selected engine for content-aware hashtag suggestions.

    Constrained by design: the model only suggests hashtags built from the
    story's own content, and every suggestion is validated against the
    story's words before use. Raises on engine failure (fail loudly — the
    caller decides the fallback). Never touches the story content, the
    screenplay, verified links, or images.
    """
    if engine_mode not in LIBRARY_ENGINE_MODES:
        raise ValueError(f"Unknown AI engine mode: {engine_mode!r}")
    from core.dual_engine import dual_engine, ModelGenerationError

    texts = _story_content_texts(story)
    headline = texts[0] if len(texts) > 0 else ""
    title = texts[1] if len(texts) > 1 else ""
    script_excerpt = (texts[3] if len(texts) > 3 else "")[:1500]
    prompt = (
        "Suggest hashtags for a short news video. Use ONLY words from the "
        "story below; do not invent names, places, or topics not present in it.\n\n"
        f"HEADLINE: {headline}\n"
        f"TITLE: {title}\n"
        f"TOPIC: {topic}\n"
        f"SCRIPT EXCERPT:\n{script_excerpt}\n\n"
        "Return 4 to 8 hashtags, one per line, each like #CamelCaseWords. "
        "No other text."
    )
    try:
        raw, _engine_used = dual_engine.generate(
            prompt=prompt,
            instructions=("You suggest hashtags grounded strictly in the provided "
                          "story content. Never invent facts, names, or topics."),
            mode=engine_mode,
        )
    except ModelGenerationError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"AI hashtag generation failed ({type(e).__name__}: {e})") from e
    candidates = re.findall(r"#[A-Za-z][A-Za-z0-9]*", raw or "")
    tags = _validate_ai_tags(candidates, story)
    if not tags:
        raise RuntimeError(
            "AI returned no usable hashtags grounded in the story content.")
    return tags


def _suggest_hashtags(story: Dict[str, Any], topic: str,
                      ai_engine: Optional[str] = None) -> Tuple[List[str], str]:
    """Hashtag candidates for a refresh: AI first (when enabled), then deterministic.

    Returns (tags, note). When ``ai_engine`` is set and the AI call fails,
    the deterministic path still runs and the failure is reported in the
    note — fail loudly, never silently. The AI never alters content, links,
    or images; it only suggests tags, each validated against the story.
    """
    ai_note = ""
    ai_tags: List[str] = []
    if ai_engine:
        try:
            ai_tags = _ai_hashtag_suggestions(story, topic, ai_engine)
        except Exception as e:
            ai_note = f"AI hashtag step failed ({e}); used deterministic tags instead."
    det_tags = _fetch_trending_hashtags(topic, story)
    tags = list(ai_tags)
    for t in det_tags:
        if t not in tags:
            tags.append(t)
    return tags[:10], ai_note


def refresh_hashtags(story_id: str, topic: str = "",
                     ai_engine: Optional[str] = None) -> Tuple[bool, str]:
    """Validate every stored hashtag against the story's own content, drop
    the invalid ones, and merge in fresh grounded suggestions.

    Returns (changed, note). `changed` is True when any tag was added or
    removed; the note honestly reports what was validated, removed, and
    added. Never touches the story content, screenplay, verified links,
    or images.
    """
    story = load_story(story_id)
    if not story:
        return False, "Story not found — nothing refreshed."
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        return False, "No topic to find hashtags for."

    # 1. Validate ALL existing hashtags against the story's own content —
    # stale or off-topic tags are removed, not silently kept.
    existing = [h for h in (story["meta"].get("hashtags") or []) if h]
    valid_existing = _validate_ai_tags(existing, story)
    removed = [h for h in existing if h not in valid_existing]

    # 2. Fresh grounded suggestions (AI first when enabled, deterministic always).
    new_tags, ai_note = _suggest_hashtags(story, topic, ai_engine)

    # 3. Merge: keep the validated existing tags, add genuinely new ones.
    merged: List[str] = []
    for t in valid_existing + new_tags:
        if t not in merged:
            merged.append(t)
    added = [t for t in merged if t not in valid_existing]

    parts = [f"Validated {len(existing)} existing hashtag(s)."]
    if removed:
        parts.append(f"Removed {len(removed)} invalid: {', '.join(removed)}.")
    if added:
        parts.append(f"Added {len(added)}: {', '.join(added)}.")
    if not removed and not added:
        parts.append("Everything still valid — nothing new found."
                     if existing else "No hashtags found.")
    if ai_note:
        parts.append(ai_note)
    note = " ".join(parts)

    changed = bool(removed or added)
    if changed:
        update_story_fields(story_id, hashtags=merged)
    return changed, note


def refresh_images(story_id: str, topic: str = "") -> Tuple[bool, str]:
    """Re-fetch news images and ADD them to the story's image list.

    Tries the story's verified news links first (exact-story publisher
    pages, images pulled from the article's own <img> tags), then topic
    search. New images are merged after the existing URLs, deduplicated —
    the user's curated list is never wiped. When the fetch finds nothing,
    the existing list is left untouched. Returns (changed, note).
    Never touches hashtags, links, or story content.
    """
    story = load_story(story_id)
    if not story:
        return False, "Story not found — images unchanged."
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        return False, "No topic to search — images unchanged."
    found = _fetch_images_for_story(story, topic)
    existing = list(story["meta"].get("image_urls") or [])
    if not found:
        return False, f"No new images found; kept {len(existing)} existing."
    merged = list(existing)
    added = 0
    for u in found:
        if u not in merged:
            merged.append(u)
            added += 1
    if not added:
        return False, f"No new images found; kept {len(existing)} existing."
    update_story_fields(story_id, image_urls=merged)
    return True, f"Added {added} new image(s); kept {len(existing)} existing."


def _refresh_worker(story_id: str, kind: str, topic: str,
                    ai_engine: Optional[str] = None) -> None:
    """Background worker for a manual hashtag/image refresh. Never raises.

    Runs in a daemon thread so tab switches (st.rerun) can't stop it.
    The outcome is recorded in the story's ``refresh_note`` frontmatter field
    — success, no-change, busy, and failure are all reported explicitly.
    """
    lock = _ENRICH_LOCKS.setdefault(story_id, threading.Lock())
    if not lock.acquire(blocking=False):
        try:
            update_story_fields(story_id, enrichment_status="done",
                                refresh_note="A refresh is already running — try again shortly.")
        except Exception:
            pass
        return
    try:
        if kind == "hashtags":
            _ok, note = refresh_hashtags(story_id, topic, ai_engine=ai_engine)
        else:
            _ok, note = refresh_images(story_id, topic)
    except Exception as e:
        note = f"Refresh failed: {e}"
    finally:
        lock.release()
    try:
        update_story_fields(story_id, enrichment_status="done", refresh_note=note,
                            refresh_kind="")
    except Exception:
        pass


def start_refresh(story_id: str, kind: str,
                  ai_engine: Optional[str] = None) -> bool:
    """Kick off a background hashtag/image refresh. Never raises.

    ``kind`` is "hashtags" or "images". ``ai_engine`` (an engine mode string
    or None) enables AI-assisted hashtag suggestions for the hashtags kind.
    The fetch runs in a daemon thread, so changing tabs mid-refresh won't
    stop it. Falls back to the story title when ``source_topic`` is missing
    so older stories can still refresh.
    """
    if kind not in ("hashtags", "images"):
        return False
    try:
        story = load_story(story_id)
        if not story:
            return False
        topic = (story["meta"].get("source_topic")
                 or story["meta"].get("title") or "").strip()
        if not topic:
            return False
        _check_id(story_id)
        update_story_fields(story_id, enrichment_status="refreshing", refresh_note="",
                            refresh_kind=kind)
        t = threading.Thread(
            target=_refresh_worker, args=(story_id, kind, topic, ai_engine),
            daemon=True, name=f"refresh-{kind}-{story_id}")
        t.start()
        return True
    except Exception:
        return False


def _do_media_refresh(story_id: str, topic: str,
                      ai_engine: Optional[str] = None) -> str:
    """Retry path: refresh hashtags + images ONLY.

    Never touches news_links and never touches the story content.
    Returns a short outcome note describing what happened (fail loudly).
    """
    try:
        story = load_story(story_id)
        if not story:
            return "Retry failed: story not found."
        image_urls = _fetch_images_for_story(story, topic)
        new_tags, ai_note = _suggest_hashtags(story, topic, ai_engine)
        meta = story["meta"]
        merged_tags = list(meta.get("hashtags") or [])
        tags_added = 0
        for t in new_tags:
            if t not in merged_tags:
                merged_tags.append(t)
                tags_added += 1
        merged_images = list(meta.get("image_urls") or [])
        images_added = 0
        for u in image_urls:
            if u not in merged_images:
                merged_images.append(u)
                images_added += 1
        update_story_fields(
            story_id,
            image_urls=merged_images,
            hashtags=merged_tags,
        )
        parts = []
        parts.append(f"Added {images_added} new image(s); kept "
                     f"{len(merged_images) - images_added} existing."
                     if images_added else "No new images found — kept the existing ones.")
        parts.append(f"{tags_added} new hashtag(s) added."
                     if tags_added else "No new hashtags found — kept the existing ones.")
        if ai_note:
            parts.append(ai_note)
        return " ".join(parts)
    except Exception as e:
        return f"Retry failed: {e}"


def _do_enrich(story_id: str, topic: str) -> None:
    articles = _fetch_news_articles(topic, limit=6)
    news_links: List[Dict[str, str]] = []
    for a in articles[:6]:
        news_links.append({
            "title": getattr(a, "title", ""),
            "url": getattr(a, "link", ""),
            "source": getattr(a, "source", ""),
        })
    story = load_story(story_id)
    if not story:
        return
    image_urls = _fetch_images_for_story(story, topic)
    new_tags = _fetch_trending_hashtags(topic, story)
    meta = story["meta"]
    merged_tags = list(meta.get("hashtags") or [])
    for t in new_tags:
        if t not in merged_tags:
            merged_tags.append(t)
    # Verified Stage-1 links are sacred: they point at the exact story the
    # reel was built from. Never replace them with topic-search results.
    # Images merge: the story may already carry the Stage-1 curated gallery —
    # keep those and add what enrichment found.
    verified_links = meta.get("news_links") or []
    merged_imgs = list(meta.get("image_urls") or [])
    for u in image_urls:
        if u and u not in merged_imgs:
            merged_imgs.append(u)
    update_story_fields(
        story_id,
        news_links=verified_links or news_links,
        image_urls=merged_imgs,
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


def retry_enrichment(story_id: str, ai_engine: Optional[str] = None) -> bool:
    """Re-run the hashtag + image fetch for a story — and nothing else.

    News links and the story content are never touched by a retry.
    ``ai_engine`` (an engine mode string or None) enables AI-assisted
    hashtag suggestions. The outcome is recorded in the story's
    ``refresh_note`` so a retry never finishes silently.
    """
    story = load_story(story_id)
    if not story:
        return False
    topic = (story["meta"].get("source_topic") or story["meta"].get("title") or "").strip()
    if not topic:
        return False
    try:
        from functools import partial
        _check_id(story_id)
        update_story_fields(story_id, enrichment_status="pending", refresh_kind="all")
        t = threading.Thread(
            target=_enrich_worker,
            args=(story_id, topic, partial(_do_media_refresh, ai_engine=ai_engine)),
            daemon=True, name=f"retry-{story_id}")
        t.start()
        return True
    except Exception:
        return False
