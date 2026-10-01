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
import traceback
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

# Set once per process by recover_orphaned_refreshes().
_RECOVERY_DONE = False

# Refresh state machine (persisted as ``enrichment_status`` frontmatter).
#   pending      — queued; set at save time / when a retry is kicked off.
#   running      — a worker thread is actively refreshing.
#   succeeded    — the worker finished and changed something.
#   no_change    — the worker finished; nothing needed changing.
#   failed       — the worker raised; ``refresh_note`` carries the real error.
#   interrupted  — recovered at startup: a previous process died mid-refresh.
# Legacy values "refreshing" (busy) and "done" (terminal) are still
# recognized when *reading* old stories, but are never written anymore.
BUSY_STATES = ("pending", "refreshing", "running")

# Hard wall-clock bound for one AI hashtag-discovery call inside a refresh.
_AI_HASHTAG_TIMEOUT_S = 45

# Fail-loud message when hashtag discovery is asked for with AI off.
_AI_DISABLED_MSG = ("AI processing is disabled — enable AI processing in "
                    "Library settings to find trending hashtags.")


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

def _run_bounded(fn, timeout_s: float, step_name: str):
    """Run ``fn()`` with a hard wall-clock bound.

    The callable runs in a daemon thread; if it is still alive after
    ``timeout_s`` seconds, ``TimeoutError`` is raised naming the step.
    Threads can't be killed — the orphaned daemon thread keeps running in
    the background but its result is discarded, so a stuck network call
    can never hang a refresh. ``fn`` must be side-effect free (pure
    fetch); all persistence happens in the caller after the bound
    returns. Exceptions raised by ``fn`` itself are re-raised loudly.
    """
    result: Dict[str, Any] = {}

    def _target() -> None:
        try:
            result["value"] = fn()
        except Exception as e:  # re-raised in the caller, loudly
            result["error"] = e

    t = threading.Thread(target=_target, daemon=True,
                         name=f"bounded-{step_name}")
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        raise TimeoutError(f"{step_name} timed out after {timeout_s:g}s")
    if "error" in result:
        raise result["error"]
    return result.get("value")


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
    """Run do_work under the per-story lock; write back an honest state.

    ``do_work`` returns ``(changed, note)``. The story's
    ``enrichment_status`` becomes ``succeeded`` / ``no_change`` /
    ``failed`` accordingly — a failure is never recorded as a success,
    and the real error text lands in ``refresh_note``. A failure to
    persist the final state is printed loudly, never swallowed.
    """
    lock = _ENRICH_LOCKS.setdefault(story_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return
    try:
        try:
            changed, note = do_work(story_id, topic)
            status = "succeeded" if changed else "no_change"
        except Exception as e:
            status = "failed"
            note = f"Enrichment failed: {type(e).__name__}: {e}"
        try:
            update_story_fields(story_id, enrichment_status=status,
                                refresh_kind="", refresh_note=note or "")
        except Exception:
            traceback.print_exc()
    finally:
        lock.release()


def recover_orphaned_refreshes() -> int:
    """Mark stories stuck in a busy refresh state as interrupted.

    Refresh workers live only in this process's memory: when the
    Streamlit process restarts, any persisted busy state (``pending`` /
    ``refreshing`` / ``running``) is orphaned and its buttons would stay
    stuck forever. Runs once per process — at process start no worker of
    ours can be alive, so every busy state found here is orphaned by
    definition. Recovered stories get ``interrupted`` plus an honest
    note; nothing else is touched. Returns the number recovered.
    """
    global _RECOVERY_DONE
    if _RECOVERY_DONE:
        return 0
    _RECOVERY_DONE = True
    recovered = 0
    for summary in list_stories():
        sid = summary.get("id") or ""
        if not sid:
            continue
        try:
            story = load_story(sid)
        except Exception:
            continue
        if not story:
            continue
        if (story.get("meta") or {}).get("enrichment_status") in BUSY_STATES:
            try:
                update_story_fields(
                    sid,
                    enrichment_status="interrupted",
                    refresh_kind="",
                    refresh_note=("A previous refresh was interrupted (the app "
                                  "restarted while it was running). Nothing was "
                                  "changed — try again."),
                )
                recovered += 1
            except Exception:
                traceback.print_exc()
    return recovered


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
            r = httpx.head(url, timeout=5, follow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                return r.headers.get("content-type", "").startswith("image/")
        except Exception:
            pass
        # Some hosts reject HEAD — do a minimal GET and check the content type.
        with httpx.stream("GET", url, timeout=5, follow_redirects=True,
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
            capture_output=True, text=True, timeout=25)
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

    Every step runs under a hard wall-clock bound (via ``_run_bounded``):
    a stuck host raises ``TimeoutError`` naming the step instead of
    hanging the refresh. Pure fetch — no persistence here.
    """
    direct = _story_direct_link_urls(story)
    if direct:
        found = _run_bounded(
            lambda: _grab_article_images(direct[:6], tries=tries),
            40.0, "article image fetch")
        if found:
            return found[:6]
    articles = _fetch_news_articles(topic, limit=6)
    return _run_bounded(
        lambda: _fetch_article_images(articles, topic, tries=tries),
        90.0, "topic image fetch")


def _fetch_article_images(articles, topic: str = "", tries: int = 3) -> List[str]:
    """Hero images for a topic.

    Tries hero-image extraction from the article pages (parallel, with
    retries). If that finds nothing at all, falls back to a web image search
    for the topic so the story still gets images. Candidate preflights run
    in parallel under a bounded join — sequential HEAD+GET checks used to
    cost up to 16s per URL.
    """
    urls = [getattr(a, "link", "") for a in articles[:6]]
    found = _grab_og_images(urls, tries=tries)
    if not found and topic.strip():
        candidates = _search_web_images(topic.strip(), limit=4)
        good: List[str] = []
        good_lock = threading.Lock()
        check_threads: List[threading.Thread] = []

        def _check(u: str) -> None:
            if u and _url_is_image(u):
                with good_lock:
                    if u not in good:
                        good.append(u)

        for u in candidates:
            t = threading.Thread(target=_check, args=(u,), daemon=True)
            t.start()
            check_threads.append(t)
        for t in check_threads:
            t.join(timeout=20.0)
        for u in good:
            if u not in found:
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


def _relevance_words(story: Optional[Dict[str, Any]], topic: str = "") -> set:
    """Words a hashtag must relate to: the story's topic + headline + title.

    The script's words are deliberately excluded — hashtags describe the
    story for discovery; they are never built from screenplay internals,
    and screenplay wording must never validate a tag as "relevant".
    """
    meta = (story.get("meta") or {}) if story else {}
    texts = [
        topic or meta.get("source_topic") or "",
        meta.get("source_headline") or "",
        meta.get("title") or "",
    ]
    words = {w.lower() for t in texts for w in re.findall(r"[A-Za-z]{4,}", t)}
    return words - _HASHTAG_STOPWORDS


def _fetch_trending_hashtags(topic: str, story: Optional[Dict[str, Any]] = None) -> Tuple[List[str], str]:
    """Deterministic hashtag discovery: trending tags, then headline/topic fallback.

    Primary: hashtags trending on social media (X trends + Google Trends via
    ``news_fetcher``) — only tags whose words overlap the story's
    topic/headline/title words are kept. Fewer relevant tags beat many
    irrelevant ones. No tag is ever invented from raw script keywords.

    Fallback (clearly reported in the note): when no trending tag is
    relevant or the lookup fails, deterministic tags built from the
    headline/topic words, so a story is never left hashtag-less.

    Returns (tags, note). The note is empty when trending tags were used;
    otherwise it says why the fallback fired (fail loudly, never silently).
    Live article titles are deliberately NOT a tag source: they come from
    whatever a news search happens to return and produce random tags.
    """
    tags: List[str] = []
    relevance = _relevance_words(story, topic)
    note = ""
    try:
        from tools.news_fetcher import news_fetcher
        trending = news_fetcher.fetch_famous_english_hashtags(limit=12) or []
    except Exception as e:
        trending = []
        note = (f"Trending-hashtag lookup failed ({type(e).__name__}: {e}); "
                "used headline/topic fallback tags instead.")
    for entry in trending:
        tag = entry.get("tag", "") if isinstance(entry, dict) else str(entry)
        if tag and (relevance & _tag_words(tag)) and tag not in tags:
            tags.append(tag)
        if len(tags) >= 6:
            break
    if tags:
        return tags[:6], note
    # Fallback: deterministic tags from the headline/topic words.
    meta = (story.get("meta") or {}) if story else {}
    for text in (meta.get("source_headline") or "", topic):
        t = _camel_tag(_keyword_list(text))
        if t and t not in tags:
            tags.append(t)
    if not tags:
        words = re.findall(r"[A-Za-z]{3,}", topic)
        if words:
            tags.append("#" + "".join(w.capitalize() for w in words[:3]))
        else:
            tags.append("#HindiReelStudio")
    if not note:
        note = ("No trending hashtags relevant to this story; "
                "used fallback tags from the story headline/topic.")
    return tags, note


def _validate_ai_tags(raw_tags: List[str],
                      story: Optional[Dict[str, Any]]) -> List[str]:
    """Keep only well-formed tags relevant to the story's topic/headline/title.

    A tag survives only if it looks like #CamelCase and at least one of its
    words appears in the story's topic, headline, or title words. Script
    words do NOT count: a tag built from screenplay internals is not
    relevant to the story for discovery purposes, however trending it
    claims to be.
    """
    relevance = _relevance_words(story)
    out: List[str] = []
    for t in raw_tags or []:
        t = (t or "").strip()
        if not re.fullmatch(r"#[A-Za-z][A-Za-z0-9]{2,29}", t):
            continue
        if t in out:
            continue
        if relevance & _tag_words(t):
            out.append(t)
        if len(out) >= 8:
            break
    return out


def _ai_hashtag_suggestions(story: Dict[str, Any], topic: str,
                            engine_mode: str) -> List[str]:
    """Ask the AI for recently trending hashtags for the story's topic.

    The model may use its own knowledge of what is currently trending on
    social media — it is NOT restricted to the story's words for discovery.
    Every suggestion is still validated for relevance to the topic/headline
    before use, so an irrelevant tag is dropped however trending it claims
    to be. Raises on engine failure (fail loudly — the caller decides the
    fallback). Never touches the story content, the screenplay, verified
    links, or images.
    """
    if engine_mode not in LIBRARY_ENGINE_MODES:
        raise ValueError(f"Unknown AI engine mode: {engine_mode!r}")
    from core.dual_engine import dual_engine, ModelGenerationError

    meta = story.get("meta") or {}
    headline = meta.get("source_headline") or ""
    title = meta.get("title") or ""
    links = _story_direct_link_urls(story)
    link_lines = "\n".join(f"- {u}" for u in links[:4]) or "- (none)"
    prompt = (
        "Find recent trending hashtags for the news topic below. Use your "
        "own knowledge of what is currently trending on social media; do "
        "not limit yourself to the words in the headline — but every "
        "hashtag you return must be genuinely relevant to this topic.\n\n"
        f"TOPIC: {topic}\n"
        f"HEADLINE: {headline}\n"
        f"TITLE: {title}\n"
        f"STORY LINKS:\n{link_lines}\n\n"
        "Return only hashtags, one per line, each like #CamelCaseWords. "
        "No other text."
    )
    try:
        raw, _engine_used = dual_engine.generate(
            prompt=prompt,
            instructions=("You find hashtags that are genuinely trending on "
                          "social media for the given news topic. Every tag "
                          "must be relevant to the topic; never invent "
                          "unrelated trends."),
            mode=engine_mode,
            # Bounded: an AI call must never hang a refresh. On timeout the
            # caller falls back to deterministic tags with an honest note.
            timeout=_AI_HASHTAG_TIMEOUT_S,
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
            "AI returned no usable hashtags relevant to the story topic.")
    return tags


def _resolve_library_engine_mode(preferred: Optional[str] = None) -> str:
    """Engine mode for AI hashtag discovery.

    ``preferred`` may be a mode or a label (explicit callers pass modes).
    Otherwise the persisted ``library_ai_engine`` label is used, falling
    back to ``DEFAULT_LIBRARY_AI_ENGINE`` when nothing is persisted. An
    unknown label also falls back to the default — never raises, so a bad
    pref can never break hashtag discovery.
    """
    if preferred in LIBRARY_ENGINE_MODES:
        return preferred  # already a mode
    label = preferred if preferred in LIBRARY_ENGINE_OPTIONS else None
    if label is None:
        try:
            label = (load_prefs().get("library_ai_engine")
                     or DEFAULT_LIBRARY_AI_ENGINE)
        except Exception:
            label = DEFAULT_LIBRARY_AI_ENGINE
    return LIBRARY_ENGINE_OPTIONS.get(
        label, LIBRARY_ENGINE_OPTIONS[DEFAULT_LIBRARY_AI_ENGINE])


def _suggest_hashtags(story: Dict[str, Any], topic: str,
                      ai_engine: Optional[str] = None) -> Tuple[List[str], str]:
    """Hashtag candidates: AI-found trending first, deterministic fallback.

    The AI is always asked first (engine: explicit ``ai_engine``, else the
    persisted ``library_ai_engine`` label, else the default engine). When
    the AI call fails or yields nothing usable, the deterministic path runs
    instead.

    Returns (tags, note). The note states which path produced the tags —
    fail loudly, never silently. Neither path alters content, links, or
    images; every tag is validated for relevance to the topic/headline.
    """
    mode = _resolve_library_engine_mode(ai_engine)
    try:
        ai_tags = _ai_hashtag_suggestions(story, topic, mode)
    except Exception as e:
        ai_tags = []
        failure_note = (f"AI hashtag step failed ({e}); "
                        "used deterministic fallback instead.")
    else:
        failure_note = ""
    if ai_tags:
        return ai_tags[:10], "Tags from AI-found trending hashtags."
    det_tags, det_note = _fetch_trending_hashtags(topic, story)
    notes = [failure_note] if failure_note else [
        "AI returned no usable trending hashtags; "
        "used deterministic fallback instead."]
    if det_note:
        notes.append(det_note)
    return det_tags[:10], " ".join(n for n in notes if n)


def refresh_hashtags(story_id: str, topic: str = "",
                     ai_engine: Optional[str] = None) -> Tuple[bool, str]:
    """Validate every stored hashtag against the story's topic/headline/title,
    drop the ones that are not relevant, and merge in fresh suggestions.

    Suggestions come from AI-found trending hashtags first, with a
    deterministic fallback; the note states which path produced them.
    Returns (changed, note). `changed` is True when any tag was added or
    removed; the note honestly reports what was validated, removed, and
    added. Never touches the story content, screenplay, verified links,
    or images.

    Raises RuntimeError when no AI engine is configured (the "Enable AI
    processing" toggle is off): discovering *trending* hashtags without
    the AI is impossible, so this fails loudly instead of silently
    serving deterministic fallback tags. Nothing is changed in that case.
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — nothing refreshed.")
    if ai_engine is None:
        raise RuntimeError(_AI_DISABLED_MSG)
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        raise RuntimeError("No topic to find hashtags for.")

    # 1. Validate ALL existing hashtags against the story's topic/headline —
    # stale or irrelevant tags are removed, not silently kept.
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
        parts.append(f"Removed {len(removed)} not relevant to the story topic/headline: "
                     f"{', '.join(removed)}.")
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
        raise RuntimeError("Story not found — images unchanged.")
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        raise RuntimeError("No topic to search — images unchanged.")
    existing = list(story["meta"].get("image_urls") or [])
    try:
        found = _fetch_images_for_story(story, topic)
    except TimeoutError as e:
        # The fetch names the step that timed out; existing media survives.
        return False, f"Image refresh timed out ({e}); kept {len(existing)} existing."
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
    The outcome is recorded honestly in ``enrichment_status``
    (``succeeded`` / ``no_change`` / ``failed``) with the real detail in
    ``refresh_note`` — a failure is never written as a success, and the
    toggle-off AI error surfaces verbatim.
    """
    lock = _ENRICH_LOCKS.setdefault(story_id, threading.Lock())
    if not lock.acquire(blocking=False):
        # Another worker owns this story's refresh state — leave it alone.
        # Writing anything here (even "already running") would clobber the
        # in-flight "running" state and flip the UI back to idle while
        # work is still running. The owning worker writes the honest
        # terminal state when it finishes.
        return
    try:
        try:
            if kind == "hashtags":
                changed, note = refresh_hashtags(story_id, topic, ai_engine=ai_engine)
            elif kind == "images":
                changed, note = refresh_images(story_id, topic)
            else:
                changed, note = False, f"Unknown refresh kind: {kind!r}."
            status = "succeeded" if changed else "no_change"
        except Exception as e:
            status = "failed"
            label = "Hashtag" if kind == "hashtags" else "Image"
            note = f"{label} refresh failed: {e}"
        try:
            update_story_fields(story_id, enrichment_status=status,
                                refresh_note=note or "", refresh_kind="")
        except Exception:
            traceback.print_exc()
    finally:
        lock.release()


def start_refresh(story_id: str, kind: str,
                  ai_engine: Optional[str] = None) -> Tuple[bool, str]:
    """Kick off a background hashtag/image refresh. Never raises.

    ``kind`` is "hashtags" or "images". ``ai_engine`` (an engine mode string
    or None) enables AI-assisted hashtag suggestions for the hashtags kind —
    None means the "Enable AI processing" toggle is off, in which case the
    worker fails loudly with a clear message instead of silently falling
    back. The fetch runs in a daemon thread, so changing tabs mid-refresh
    won't stop it. Falls back to the story title when ``source_topic`` is
    missing so older stories can still refresh.

    Returns (started, reason): ``reason`` is "" when the refresh started,
    otherwise a human-readable explanation of why it could not start.
    """
    if kind not in ("hashtags", "images"):
        return False, f"Unknown refresh kind: {kind!r}."
    try:
        story = load_story(story_id)
        if not story:
            return False, "Story not found."
        if (story["meta"].get("enrichment_status") or "") in BUSY_STATES:
            # The buttons disable while busy, but a double-kick can still
            # race here — refuse instead of starting a second worker that
            # would fight the first over the story's refresh state.
            return False, "A refresh is already running — try again shortly."
        topic = (story["meta"].get("source_topic")
                 or story["meta"].get("title") or "").strip()
        if not topic:
            return False, "No topic or title to refresh."
        _check_id(story_id)
        update_story_fields(story_id, enrichment_status="running", refresh_note="",
                            refresh_kind=kind)
        t = threading.Thread(
            target=_refresh_worker, args=(story_id, kind, topic, ai_engine),
            daemon=True, name=f"refresh-{kind}-{story_id}")
        t.start()
        return True, ""
    except Exception as e:
        return False, f"Could not start refresh: {type(e).__name__}: {e}"


def _do_media_refresh(story_id: str, topic: str,
                      ai_engine: Optional[str] = None) -> Tuple[bool, str]:
    """Retry path: refresh hashtags + images ONLY.

    Never touches news_links and never touches the story content.
    Returns (changed, note) describing the outcome (fail loudly).

    Raises RuntimeError when no AI engine is configured: the retry
    refreshes hashtags through AI discovery, and with AI processing off
    there is nothing honest to do — so it fails loudly and changes
    nothing instead of silently serving deterministic tags.
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Retry failed: story not found.")
    if ai_engine is None:
        raise RuntimeError(_AI_DISABLED_MSG)
    meta = story["meta"]
    image_note = ""
    try:
        image_urls = _fetch_images_for_story(story, topic)
    except TimeoutError as e:
        image_urls = []
        image_note = f"Image fetch timed out ({e}); kept the existing ones."
    new_tags, ai_note = _suggest_hashtags(story, topic, ai_engine)
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
    if image_note:
        parts.append(image_note)
    elif images_added:
        parts.append(f"Added {images_added} new image(s); kept "
                     f"{len(merged_images) - images_added} existing.")
    else:
        parts.append("No new images found — kept the existing ones.")
    parts.append(f"{tags_added} new hashtag(s) added."
                 if tags_added else "No new hashtags found — kept the existing ones.")
    if ai_note:
        parts.append(ai_note)
    changed = bool(images_added or tags_added)
    return changed, " ".join(parts)


def _do_enrich(story_id: str, topic: str) -> Tuple[bool, str]:
    """Post-save enrichment body: news links + images + hashtags.

    Deterministic only — save-time enrichment never calls the AI, so a
    story always saves cleanly with AI processing off. Returns
    (changed, note); raises loudly on failure.
    """
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
        raise RuntimeError("Enrichment failed: story not found.")
    try:
        image_urls = _fetch_images_for_story(story, topic)
    except TimeoutError as e:
        image_urls = []
        img_note = f"Image fetch timed out ({e}); kept the existing ones."
    else:
        img_note = ""
    new_tags, _det_note = _fetch_trending_hashtags(topic, story)
    meta = story["meta"]
    merged_tags = list(meta.get("hashtags") or [])
    tags_added = 0
    for t in new_tags:
        if t not in merged_tags:
            merged_tags.append(t)
            tags_added += 1
    # Verified Stage-1 links are sacred: they point at the exact story the
    # reel was built from. Never replace them with topic-search results.
    # Images merge: the story may already carry the Stage-1 curated gallery —
    # keep those and add what enrichment found.
    verified_links = meta.get("news_links") or []
    merged_imgs = list(meta.get("image_urls") or [])
    imgs_added = 0
    for u in image_urls:
        if u and u not in merged_imgs:
            merged_imgs.append(u)
            imgs_added += 1
    links_added = 0 if verified_links else len(news_links)
    update_story_fields(
        story_id,
        news_links=verified_links or news_links,
        image_urls=merged_imgs,
        hashtags=merged_tags,
    )
    changed = bool(tags_added or imgs_added or links_added)
    bits = []
    bits.append(f"Found {links_added} news link(s)."
                if links_added else "Kept verified news links.")
    bits.append(img_note or (f"Added {imgs_added} image(s)."
                             if imgs_added else "No new images found."))
    bits.append(f"Added {tags_added} hashtag(s)."
                if tags_added else "No new hashtags found.")
    return changed, "Enrichment complete: " + " ".join(bits)


def start_enrichment(story_id: str, topic: str) -> Tuple[bool, str]:
    """Kick off post-save enrichment in a daemon thread. Never raises.

    Returns (started, reason): ``reason`` is "" when enrichment started,
    otherwise a human-readable explanation.
    """
    try:
        _check_id(story_id)
        if not (topic or "").strip():
            update_story_fields(story_id, enrichment_status="no_change",
                                refresh_note="No topic — enrichment skipped.",
                                refresh_kind="")
            return False, "No topic — enrichment skipped."
        update_story_fields(story_id, enrichment_status="running",
                            refresh_kind="enrich", refresh_note="")
        t = threading.Thread(
            target=_enrich_worker, args=(story_id, topic.strip(), _do_enrich),
            daemon=True, name=f"enrich-{story_id}")
        _ENRICH_THREADS[story_id] = t
        t.start()
        return True, ""
    except Exception as e:
        return False, f"Could not start enrichment: {type(e).__name__}: {e}"


def retry_enrichment(story_id: str, ai_engine: Optional[str] = None) -> Tuple[bool, str]:
    """Re-run the hashtag + image fetch for a story — and nothing else.

    News links and the story content are never touched by a retry.
    ``ai_engine`` (an engine mode string or None) enables AI-assisted
    hashtag suggestions — None means the "Enable AI processing" toggle is
    off, in which case the retry fails loudly instead of silently falling
    back. The outcome is recorded in the story's ``refresh_note`` so a
    retry never finishes silently.

    Returns (started, reason): ``reason`` is "" when the retry started,
    otherwise a human-readable explanation.
    """
    story = load_story(story_id)
    if not story:
        return False, "Story not found."
    if (story["meta"].get("enrichment_status") or "") in BUSY_STATES:
        return False, "A refresh is already running — try again shortly."
    topic = (story["meta"].get("source_topic") or story["meta"].get("title") or "").strip()
    if not topic:
        return False, "No topic or title to retry."
    try:
        from functools import partial
        _check_id(story_id)
        update_story_fields(story_id, enrichment_status="running", refresh_kind="all")
        t = threading.Thread(
            target=_enrich_worker,
            args=(story_id, topic, partial(_do_media_refresh, ai_engine=ai_engine)),
            daemon=True, name=f"retry-{story_id}")
        t.start()
        return True, ""
    except Exception as e:
        return False, f"Could not start retry: {type(e).__name__}: {e}"
