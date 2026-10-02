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
import hashlib
import json
import re
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import urllib.parse
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LIBRARY_ROOT = Path.home() / "Documents" / "HindiReelStudio"
STORIES_DIR = LIBRARY_ROOT / "stories"
PREFS_PATH = LIBRARY_ROOT / "prefs.json"

_STORY_ID_RE = re.compile(r"^[0-9A-Za-z-]{8,64}$")
_ENRICH_LOCKS: Dict[tuple, threading.Lock] = {}
_ENRICH_THREADS: Dict[str, threading.Thread] = {}
_META_WRITE_LOCKS: Dict[str, threading.RLock] = {}

# Per-story write lock guarding every read-modify-write of a story's
# frontmatter file (#53/#54: concurrent per-kind workers must not clobber
# each other). Keyed by story_id; independent from _ENRICH_LOCKS (which are
# per (story_id, kind) and guard "is this kind already running").

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

# ---------------------------------------------------------------------------
# Refresh-state model (#53/#54)
# ---------------------------------------------------------------------------
# Refresh work is tracked PER KIND, not with a single busy flag:
#
# - ``_REFRESH_KINDS``: the manual-refresh kinds. ``"hashtags"``,
#   ``"images"`` and ``"news"`` are independent and may run concurrently
#   (#54, #80); ``"more_images"`` / ``"more_news"`` (#91) are the explicit
#   "load more" batches — independent of everything except their sibling
#   kind (``"images"``/``"more_images"`` and ``"news"``/``"more_news"``
#   both write the same field, so each pair is mutually exclusive);
#   ``"reset"`` is destructive and exclusive; ``"enrich"`` is the
#   save-time enrichment and also exclusive with manual refreshes.
# - ``refresh_busy`` (frontmatter, list of kind names): the kinds currently
#   running. A list round-trips through _dump_frontmatter/_parse_frontmatter
#   (nested dicts do not — never store one in frontmatter).
# - ``refresh_outcome_pending`` (frontmatter, list of JSON strings): one
#   entry per finished kind, ``{"kind", "status", "note"}``. The UI toasts
#   each entry exactly once and drains it. JSON-per-entry keeps the
#   hand-rolled frontmatter format honest.
#
# The legacy single-flag format (``enrichment_status`` + ``refresh_kind``)
# is still read by refresh_busy_kinds() as a migration fallback, and
# ``enrichment_status``/``refresh_note`` are still WRITTEN (back-compat),
# but they are no longer authoritative for "is anything busy".
#
# All read-modify-write cycles on the frontmatter go through
# _meta_write_lock(story_id): concurrent per-kind workers must not clobber
# each other's updates. Lock order is always kind-lock (_ENRICH_LOCKS) THEN
# meta-lock — never the reverse (deadlock avoidance).
_REFRESH_KINDS = ("hashtags", "images", "news", "more_images", "more_news",
                 "reset", "enrich")
_EXCLUSIVE_KINDS = ("reset", "enrich")

# #91: kinds that write the SAME story field must not run together — the
# second writer would silently clobber the first's appended batch
# (last-writer-wins on the whole list). "Load more images" is refused
# while "Update Images" runs and vice versa; same for the news pair.
_SIBLING_KINDS = {"images": "more_images", "more_images": "images",
                  "news": "more_news", "more_news": "news"}

# #91: one "load more" click fetches at most this many genuinely new items.
_LOAD_MORE_BATCH = 5

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
    """Save a story immediately (no network). Returns the story id.

    Fetched image URLs are deduplicated by normalized URL before
    storing — the same image is never stored twice (issue #21). This
    stays deliberately network-free: byte-identical or visual duplicates
    under different URLs that slip through here are collapsed by every
    later image refresh, which backfills content/perceptual hashes and
    collapses stored duplicates (issue #57).
    """
    story_id = new_story_id()
    image_urls, _, _ = _dedupe_stored_image_entries(image_urls, [], [])
    meta = {
        "id": story_id,
        "title": title or "Untitled Story",
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "tone": tone or "",
        "hashtags": [h for h in (hashtags or []) if h],
        "news_links": [dict(l) for l in (news_links or [])],
        "image_urls": image_urls,
        "image_hashes": [],
        "image_phashes": [],
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
    """Load a story: {'meta': {...}, 'body': '...', 'dialogue': '...', 'script': '...' }.

    Migration (issue #21): stories saved before dedupe may carry the
    same image twice (or trivial URL variants). The stored list is
    collapsed by normalized URL on load so the detail view shows each
    image once, and the cleanup is persisted back so it sticks. The
    returned view is always deduped, even if the write-back fails.
    Byte-identical / visual duplicates under different URLs need the
    network to detect, so they are NOT collapsed here — the image
    refresh backfills hashes and collapses them (issue #57).
    """
    path = story_path(story_id)
    if not path.exists():
        return None
    meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    dialogue, script = _split_sections(body)
    stored_urls = [u for u in (meta.get("image_urls") or []) if u]
    stored_hashes = meta.get("image_hashes")
    had_hashes = "image_hashes" in meta
    stored_phashes = meta.get("image_phashes")
    had_phashes = "image_phashes" in meta
    urls, hashes, phashes = _dedupe_stored_image_entries(
        stored_urls, stored_hashes, stored_phashes)
    meta["image_urls"] = urls
    meta["image_hashes"] = hashes
    meta["image_phashes"] = phashes
    if (urls != stored_urls or not had_hashes or stored_hashes != hashes
            or not had_phashes or stored_phashes != phashes):
        # Best-effort write-back: the in-memory view above is already
        # clean, so a failed write is simply retried on the next load.
        try:
            update_story_fields(story_id, image_urls=urls, image_hashes=hashes,
                                image_phashes=phashes)
        except Exception:
            pass
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


def _meta_write_lock(story_id: str) -> threading.RLock:
    """Return the per-story RLock guarding frontmatter read-modify-write.

    A single module-level dict of locks (not a global lock) keeps
    concurrent workers on DIFFERENT stories fully parallel; workers on the
    same story serialize only for the brief file update (#53/#54).
    """
    return _META_WRITE_LOCKS.setdefault(story_id, threading.RLock())


def _read_meta_body(story_id: str) -> Optional[tuple]:
    """Read (meta, body) for a story, or None if the file is gone.

    Callers hold _meta_write_lock(story_id) so the returned meta is a
    consistent snapshot for an atomic read-modify-write cycle.
    """
    path = story_path(story_id)
    if not path.exists():
        return None
    return _parse_frontmatter(path.read_text(encoding="utf-8"))


def _write_meta_body(story_id: str, meta: Dict[str, Any], body: str) -> None:
    """Persist (meta, body); caller must hold _meta_write_lock(story_id)."""
    story_path(story_id).write_text(
        f"{_dump_frontmatter(meta)}\n\n{body.strip()}\n", encoding="utf-8")


def refresh_busy_kinds(meta: Optional[Dict[str, Any]]) -> Set[str]:
    """Return the set of refresh kinds currently running for this story.

    Reads the authoritative ``refresh_busy`` list first. Stories written
    before the per-kind model (#53/#54) carry only the legacy single-flag
    ``enrichment_status`` (+ ``refresh_kind``): a busy status with a known
    kind maps to that kind; a busy status with an unknown/empty kind maps
    to ``{"enrich"}`` (exclusive — the old code blocked everything while
    busy, so exclusivity is the safe migration). Never raises: unreadable
    state reads as idle; start_refresh re-checks honestly before kicking.
    """
    if not isinstance(meta, dict):
        return set()
    raw = meta.get("refresh_busy")
    if isinstance(raw, list):
        return {k for k in raw if k in _REFRESH_KINDS}
    # Legacy single-flag fallback.
    if meta.get("enrichment_status") in BUSY_STATES:
        kind = meta.get("refresh_kind")
        if kind in _REFRESH_KINDS:
            return {kind}
        return {"enrich"}
    return set()


def _outcome_entry_kind(entry: Any) -> Optional[str]:
    """Return the kind recorded in a refresh_outcome_pending entry, or None
    if the entry is malformed (it is then dropped by the drain)."""
    parsed = parse_refresh_outcome(entry)
    return parsed["kind"] if parsed else None


def parse_refresh_outcome(entry: Any) -> Optional[Dict[str, str]]:
    """Parse one refresh_outcome_pending entry.

    Returns {"kind", "status", "note"} (all strings) or None when the
    entry is malformed. The UI uses this to toast finished outcomes (#53);
    malformed entries are reported loudly and dropped, never toasted.
    """
    if not isinstance(entry, str):
        return None
    try:
        data = json.loads(entry)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    kind = data.get("kind")
    status = data.get("status")
    if kind not in _REFRESH_KINDS or not isinstance(status, str):
        return None
    return {"kind": kind, "status": status,
            "note": str(data.get("note") or "")}


def _drop_pending_outcomes(meta: Dict[str, Any], kind: str) -> None:
    """Remove pending outcome entries for kind (a new run toasts fresh)."""
    pending = meta.get("refresh_outcome_pending")
    if not isinstance(pending, list):
        meta.pop("refresh_outcome_pending", None)
        return
    kept = [e for e in pending if _outcome_entry_kind(e) != kind]
    if kept:
        meta["refresh_outcome_pending"] = kept
    else:
        meta.pop("refresh_outcome_pending", None)


def _set_refresh_busy(story_id: str, kind: str) -> bool:
    """Mark kind busy (idempotent). Clears that kind's stale pending
    outcomes and makes the per-kind list authoritative (legacy single-flag
    fields are reset). Returns False if the story file is gone."""
    with _meta_write_lock(story_id):
        snap = _read_meta_body(story_id)
        if snap is None:
            return False
        meta, body = snap
        busy = sorted(refresh_busy_kinds(meta) | {kind})
        meta["refresh_busy"] = busy
        meta["enrichment_status"] = "running"
        meta["refresh_kind"] = ""
        _drop_pending_outcomes(meta, kind)
        _write_meta_body(story_id, meta, body)
        return True


def _finish_refresh(story_id: str, kind: str, status: str, note: str) -> bool:
    """Clear kind's busy flag and record its outcome (atomic, per-kind).

    Only kind's own state is touched — a concurrently running sibling kind
    keeps its busy flag and its pending outcomes (#54). While any kind is
    still busy the legacy ``enrichment_status`` stays "running"; otherwise
    it takes this run's terminal status. Returns False if the story file
    is gone (e.g. deleted mid-refresh — nothing left to record).
    """
    with _meta_write_lock(story_id):
        snap = _read_meta_body(story_id)
        if snap is None:
            return False
        meta, body = snap
        busy = sorted(refresh_busy_kinds(meta) - {kind})
        if busy:
            meta["refresh_busy"] = busy
        else:
            meta.pop("refresh_busy", None)
        pending = meta.get("refresh_outcome_pending")
        if not isinstance(pending, list):
            pending = []
        pending = [e for e in pending if _outcome_entry_kind(e) != kind]
        pending.append(json.dumps(
            {"kind": kind, "status": status, "note": note or ""}))
        meta["refresh_outcome_pending"] = pending
        meta["enrichment_status"] = "running" if busy else status
        meta["refresh_kind"] = ""
        meta["refresh_note"] = note or ""
        _write_meta_body(story_id, meta, body)
        return True


def update_story_fields(story_id: str, **fields: Any) -> bool:
    """Merge fields into the story's frontmatter (body untouched).

    Serialized per story via _meta_write_lock: refresh workers and the UI
    may update the same file concurrently (#53/#54) and must not clobber
    each other's read-modify-write cycles.
    """
    path = story_path(story_id)
    if not path.exists():
        return False
    with _meta_write_lock(story_id):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        meta.update(fields)
        path.write_text(
            f"{_dump_frontmatter(meta)}\n\n{body.strip()}\n", encoding="utf-8")
    return True


def update_story_script(story_id: str, script_md: str) -> None:
    """Replace the story's ``## Script`` section, preserving the title,
    dialogue, and all frontmatter.

    Raises FileNotFoundError if the story does not exist, ValueError for
    a blank script or an invalid id. Any write error propagates — the
    caller must surface it (fail loud), never pretend the save landed.
    """
    _check_id(story_id)
    if not (script_md or "").strip():
        raise ValueError("Script text must not be empty.")
    path = story_path(story_id)
    if not path.exists():
        raise FileNotFoundError(f"Story not found: {story_id}")
    meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    dialogue, _old_script = _split_sections(body)
    path.write_text(
        build_story_markdown(meta, dialogue, script_md.strip()),
        encoding="utf-8")


# ---------------------------------------------------------------------------
# Fine-tune history (#105)
# ---------------------------------------------------------------------------
# Every "Fine tune script" turn is recorded here so the conversation carries
# across turns (the LLM sees all prior instructions + refined scripts) and so
# script versioning (#104) can later adopt the history as versions.
#
# Stored as ``fine_tune_history`` frontmatter: a list of JSON strings, one
# per turn, ``{"instruction": ..., "script": ...}`` — JSON-per-entry keeps
# the hand-rolled frontmatter format honest (the same pattern as
# ``refresh_outcome_pending``; JSON encoding protects newlines/quotes
# through _yaml_escape/_unquote). Capped at _FINE_TUNE_HISTORY_MAX_TURNS
# turns so frontmatter can't grow without bound.
_FINE_TUNE_HISTORY_KEY = "fine_tune_history"
_FINE_TUNE_HISTORY_MAX_TURNS = 20


def get_fine_tune_history(story_id: str) -> List[Dict[str, str]]:
    """Return the story's fine-tune turns, oldest first.

    Each turn is ``{"instruction": str, "script": str}``. Malformed entries
    are skipped (a corrupt entry must not brick the story view); the writer
    (``record_fine_tune_turn``) validates strictly instead.

    Raises FileNotFoundError if the story does not exist.
    """
    _check_id(story_id)
    path = story_path(story_id)
    if not path.exists():
        raise FileNotFoundError(f"Story not found: {story_id}")
    meta, _body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    turns: List[Dict[str, str]] = []
    for entry in meta.get(_FINE_TUNE_HISTORY_KEY) or []:
        if not isinstance(entry, str):
            continue
        try:
            turn = json.loads(entry)
        except (ValueError, TypeError):
            continue
        if not isinstance(turn, dict):
            continue
        instruction = turn.get("instruction")
        script = turn.get("script")
        if not isinstance(instruction, str) or not isinstance(script, str):
            continue
        if not instruction.strip() or not script.strip():
            continue
        turns.append({"instruction": instruction.strip(),
                      "script": script.strip()})
    return turns


def record_fine_tune_turn(story_id: str, instruction: str,
                          refined_script: str) -> None:
    """Append a fine-tune turn and save the refined script as a new version.

    The refined script becomes a NEW script version (#104) — latest on top —
    and the default, so the versions list shows it immediately (expanded)
    and the ``## Script`` mirror, Copy / Share / export all use it. The
    pre-turn text stays recoverable as the previous version; nothing is
    overwritten in place.

    The version is written FIRST: a recorded turn always reflects the stored
    script — a turn is never recorded without its script landing.

    Raises ValueError for blank instruction/script, FileNotFoundError if the
    story does not exist. Any write error propagates — the caller must
    surface it (fail loud), never pretend the refinement landed.
    """
    _check_id(story_id)
    instruction_text = (instruction or "").strip()
    if not instruction_text:
        raise ValueError("Fine-tune instruction must not be empty.")
    refined_text = (refined_script or "").strip()
    if not refined_text:
        raise ValueError("Refined script must not be empty.")
    # #104/#191: the refined script becomes a NEW version (latest on top)
    # and the default. Overwriting the default version's text in place hid
    # the result whenever the latest version wasn't the default (#191):
    # the versions list expands the latest version, so the refined text
    # sat invisible inside a collapsed "Version N · Default" expander
    # while the expanded latest version still showed the old text.
    # create_script_version seeds the new version from the current default
    # text; update + make-default then land the refinement on it and mirror
    # it to ## Script. Each primitive is fail-loud on its own.
    new_n = create_script_version(story_id)
    update_script_version_text(story_id, new_n, refined_text)
    set_default_script_version(story_id, new_n)
    history = get_fine_tune_history(story_id)
    history.append({"instruction": instruction_text, "script": refined_text})
    del history[:-_FINE_TUNE_HISTORY_MAX_TURNS]
    entries = [json.dumps(turn, ensure_ascii=False) for turn in history]
    if not update_story_fields(story_id, **{_FINE_TUNE_HISTORY_KEY: entries}):
        raise FileNotFoundError(f"Story not found: {story_id}")


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


# ---------------------------------------------------------------------------
# Script versioning (#104)
# ---------------------------------------------------------------------------
# Each story keeps multiple script versions. Versions live in a sidecar
# ``<story-id>.versions.json`` next to the story file; the ``## Script``
# section of ``<story-id>.md`` ALWAYS mirrors the *default* version's text,
# so every existing reader (the native macOS app, Copy / Share / export)
# keeps working unchanged — the default version IS the story's script.
#
# Sidecar schema::
#
#     {"default": 1, "next_n": 2,
#      "versions": [{"n": 1, "text": "...", "created_at": "..."}, ...]}
#
# ``next_n`` is a monotonic counter: deleted version numbers are never
# reused, so "Version 3" always means the same text.
#
# Migration: stories saved before versioning have no sidecar; the first
# version access seeds v1 from the current ``## Script`` text and persists
# it, so nothing is ever lost. Corrupt sidecar JSON raises loudly — it is
# never silently rebuilt or dropped.
#
# Invariants (enforced by every mutator below):
#   * v1 (the original) can never be deleted.
#   * Exactly one version is the default at all times.
#   * Deleting the default version falls back to v1 as the default.
#   * The ``## Script`` section always equals the default version's text.

_VERSIONS_SUFFIX = ".versions.json"


def _versions_path(story_id: str) -> Path:
    return stories_dir() / f"{_check_id(story_id)}{_VERSIONS_SUFFIX}"


def _validate_versions_doc(doc: Any, story_id: str) -> tuple[List[Dict[str, Any]], int, int]:
    """Validate a parsed sidecar doc → (versions ascending by n, default_n, next_n).

    Raises ValueError with a loud, actionable message on any corruption —
    the caller must surface it, never silently rebuild the history.
    """
    if not isinstance(doc, dict):
        raise ValueError(
            f"Corrupt script versions for story {story_id}: "
            f"top-level JSON must be an object, got {type(doc).__name__}.")
    versions = doc.get("versions")
    default_n = doc.get("default")
    next_n = doc.get("next_n")
    if not isinstance(versions, list) or not versions:
        raise ValueError(
            f"Corrupt script versions for story {story_id}: "
            "'versions' must be a non-empty list.")
    seen: Set[int] = set()
    clean: List[Dict[str, Any]] = []
    for i, v in enumerate(versions):
        if not isinstance(v, dict):
            raise ValueError(
                f"Corrupt script versions for story {story_id}: "
                f"version entry #{i} is not an object.")
        n = v.get("n")
        text = v.get("text")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError(
                f"Corrupt script versions for story {story_id}: "
                f"version entry #{i} has invalid 'n': {n!r}.")
        if n in seen:
            raise ValueError(
                f"Corrupt script versions for story {story_id}: "
                f"duplicate version number {n}.")
        if not isinstance(text, str):
            raise ValueError(
                f"Corrupt script versions for story {story_id}: "
                f"version {n} has non-string 'text'.")
        seen.add(n)
        clean.append({"n": n, "text": text,
                      "created_at": str(v.get("created_at") or "")})
    if (not isinstance(default_n, int) or isinstance(default_n, bool)
            or default_n not in seen):
        raise ValueError(
            f"Corrupt script versions for story {story_id}: "
            f"'default' ({default_n!r}) does not match any version.")
    if (not isinstance(next_n, int) or isinstance(next_n, bool)
            or next_n <= max(seen)):
        raise ValueError(
            f"Corrupt script versions for story {story_id}: "
            f"'next_n' ({next_n!r}) must exceed every existing version number.")
    clean.sort(key=lambda v: v["n"])
    return clean, default_n, next_n


def _read_versions_doc(story_id: str) -> Optional[Dict[str, Any]]:
    """Read the raw sidecar JSON, or None when the story has no sidecar yet.

    Raises FileNotFoundError for an unknown story, ValueError on corrupt JSON.
    """
    path = story_path(story_id)
    if not path.exists():
        raise FileNotFoundError(f"Story not found: {story_id}")
    vpath = _versions_path(story_id)
    if not vpath.exists():
        return None
    try:
        return json.loads(vpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        raise ValueError(
            f"Corrupt script versions for story {story_id}: {e}. "
            f"Delete {vpath.name} only if you are sure the history is expendable.") from e


def _write_versions_doc(story_id: str, versions: List[Dict[str, Any]],
                        default_n: int, next_n: int) -> None:
    """Persist the sidecar. Caller must hold _meta_write_lock(story_id)."""
    doc = {"default": default_n, "next_n": next_n,
           "versions": [{"n": v["n"], "text": v["text"],
                         "created_at": v.get("created_at", "")}
                        for v in sorted(versions, key=lambda v: v["n"])]}
    _versions_path(story_id).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_versions(story_id: str) -> tuple[List[Dict[str, Any]], int, int]:
    """Return (versions ascending, default_n, next_n), migrating legacy stories.

    Stories saved before versioning get v1 seeded from the current
    ``## Script`` text and persisted — the original is never lost.
    Caller must hold _meta_write_lock(story_id).
    """
    doc = _read_versions_doc(story_id)
    if doc is not None:
        return _validate_versions_doc(doc, story_id)
    # Legacy story: seed v1 from the current script section.
    _meta, body = _parse_frontmatter(story_path(story_id).read_text(encoding="utf-8"))
    _dialogue, script = _split_sections(body)
    created = _meta.get("created_at") or datetime.datetime.now().isoformat(timespec="seconds")
    versions = [{"n": 1, "text": script.strip(), "created_at": str(created)}]
    _write_versions_doc(story_id, versions, 1, 2)
    return versions, 1, 2


def _version_text(versions: List[Dict[str, Any]], n: int) -> str:
    for v in versions:
        if v["n"] == n:
            return v["text"]
    raise ValueError(f"Story has no script version {n}.")


def get_script_versions(story_id: str) -> tuple[List[Dict[str, Any]], int]:
    """Return (versions latest-first, default_n) for a story (#104).

    Each version is ``{"n": int, "text": str, "created_at": str}``.
    Migrates legacy stories on first access. Raises FileNotFoundError for
    an unknown story and ValueError on corrupt version data — both loud,
    never silent.
    """
    _check_id(story_id)
    with _meta_write_lock(story_id):
        versions, default_n, _ = _ensure_versions(story_id)
    versions = [dict(v) for v in reversed(versions)]
    return versions, default_n


def create_script_version(story_id: str) -> int:
    """Create a new version seeded from the current default text (#104).

    The new version is NOT made the default — the default only changes via
    an explicit ``set_default_script_version``. Returns the new version
    number (monotonic: deleted numbers are never reused).
    """
    _check_id(story_id)
    with _meta_write_lock(story_id):
        versions, default_n, next_n = _ensure_versions(story_id)
        new_n = next_n
        versions.append({
            "n": new_n,
            "text": _version_text(versions, default_n),
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        })
        _write_versions_doc(story_id, versions, default_n, next_n + 1)
    return new_n


def update_script_version_text(story_id: str, n: int, text: str) -> None:
    """Replace a version's text (#104, per-version edit).

    When the edited version is the default, the story's ``## Script``
    section is rewritten too, so Copy / Share / export keep using it.
    Raises ValueError for blank text or an unknown version number.
    """
    _check_id(story_id)
    if not (text or "").strip():
        raise ValueError("Script version text must not be empty.")
    with _meta_write_lock(story_id):
        versions, default_n, next_n = _ensure_versions(story_id)
        found = False
        for v in versions:
            if v["n"] == n:
                v["text"] = text.strip()
                found = True
        if not found:
            raise ValueError(f"Story has no script version {n}.")
        _write_versions_doc(story_id, versions, default_n, next_n)
        if n == default_n:
            # Keep the .md mirror in sync: the default version IS the story's script.
            update_story_script(story_id, text.strip())


def delete_script_version(story_id: str, n: int) -> None:
    """Delete a version (#104).

    v1 (the original) is protected and can never be deleted. Deleting the
    default version falls the default back to v1 and rewrites the story's
    ``## Script`` section with v1's text. Raises ValueError otherwise.
    """
    _check_id(story_id)
    if n == 1:
        raise ValueError("The original version (v1) cannot be deleted.")
    with _meta_write_lock(story_id):
        versions, default_n, next_n = _ensure_versions(story_id)
        remaining = [v for v in versions if v["n"] != n]
        if len(remaining) == len(versions):
            raise ValueError(f"Story has no script version {n}.")
        new_default = default_n
        if n == default_n:
            new_default = 1  # Delete-default fallback: the original becomes default.
        _write_versions_doc(story_id, remaining, new_default, next_n)
        if n == default_n:
            update_story_script(story_id, _version_text(remaining, 1))


def set_default_script_version(story_id: str, n: int) -> None:
    """Make version ``n`` the default (#104): exactly one default at a time.

    The story's ``## Script`` section is rewritten with the version's text,
    so Copy / Share / export immediately use it. Raises ValueError for an
    unknown version number.
    """
    _check_id(story_id)
    with _meta_write_lock(story_id):
        versions, _old_default, next_n = _ensure_versions(story_id)
        text = _version_text(versions, n)  # raises ValueError when unknown
        _write_versions_doc(story_id, versions, n, next_n)
        update_story_script(story_id, text)


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
    """Remove one auto-fetched image URL (the overwrite control).

    Content hashes stay aligned with the surviving URLs.
    """
    story = load_story(story_id)
    if not story:
        return False
    urls = list(story["meta"].get("image_urls") or [])
    hashes = _align_hashes(urls, story["meta"].get("image_hashes"))
    phashes = _align_hashes(urls, story["meta"].get("image_phashes"))
    kept = [(u, h, p) for u, h, p in zip(urls, hashes, phashes) if u != url]
    update_story_fields(story_id,
                        image_urls=[u for u, _, _ in kept],
                        image_hashes=[h for _, h, _ in kept],
                        image_phashes=[p for _, _, p in kept])
    return True


def update_fetched_image_url(story_id: str, index: int, new_url: str) -> bool:
    """Replace one auto-fetched image URL by list position (the edit control).

    Fails loudly with ValueError when the story is unknown, the index is
    out of range, the new value is not a non-empty http(s) URL, or the
    new address is already attached to the story (normalized-URL dedupe,
    issue #21) — the caller surfaces the error instead of silently
    keeping a bad or duplicate value. The replaced entry's content hash
    and perceptual hash are invalidated so the next refresh re-hashes
    the new bytes.
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
    new_key = normalize_image_url(u)
    for i, old in enumerate(urls):
        if i != index and normalize_image_url(old) == new_key:
            raise ValueError("That image is already attached to this story.")
    urls[index] = u
    hashes = _align_hashes(urls, story["meta"].get("image_hashes"))
    hashes[index] = ""
    phashes = _align_hashes(urls, story["meta"].get("image_phashes"))
    phashes[index] = ""
    update_story_fields(story_id, image_urls=urls, image_hashes=hashes,
                        image_phashes=phashes)
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


def remove_hashtag(story_id: str, tag: str) -> bool:
    """Remove one hashtag from a story's tag list (manual user removal).

    Fails loudly with ValueError when the story is unknown or the tag is
    not on it — the caller surfaces the error instead of silently
    pretending the tag is gone.
    """
    story = load_story(story_id)
    if not story:
        raise ValueError(f"Unknown story: {story_id!r}")
    tags = [t for t in (story["meta"].get("hashtags") or []) if t]
    if tag not in tags:
        raise ValueError(f"Hashtag {tag!r} is not on this story.")
    tags = [t for t in tags if t != tag]
    update_story_fields(story_id, hashtags=tags)
    return True


def remove_news_link(story_id: str, url: str) -> bool:
    """Remove one verified news link (manual user removal ONLY).

    Refresh/reset workers must NEVER call this — individual news links are
    only ever removed by the user. Fails loudly with ValueError when the
    story is unknown or the URL is not among its links.
    """
    story = load_story(story_id)
    if not story:
        raise ValueError(f"Unknown story: {story_id!r}")
    links = [lk for lk in (story["meta"].get("news_links") or [])
             if isinstance(lk, dict)]
    if not any((lk.get("url") or "") == url for lk in links):
        raise ValueError("That news link is not on this story.")
    links = [lk for lk in links if (lk.get("url") or "") != url]
    update_story_fields(story_id, news_links=links)
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
# ---------------------------------------------------------------------------
# Google News redirect resolution
# ---------------------------------------------------------------------------

def _google_news_article_id(url: str) -> Optional[str]:
    """Extract the article token from a Google News redirect URL.

    Handles ``news.google.com/rss/articles/<token>``,
    ``news.google.com/articles/<token>`` and the legacy
    ``news.google.com/__i/rss/rd/articles/<token>`` form. Returns None for
    any non-Google-News URL.
    """
    try:
        from urllib.parse import urlparse, unquote
        p = urlparse(url)
        if (p.hostname or "").lower() not in ("news.google.com",
                                              "www.news.google.com"):
            return None
        parts = [seg for seg in p.path.split("/") if seg]
        if len(parts) >= 2 and parts[-2] == "articles" and parts[-1]:
            return unquote(parts[-1])
        return None
    except Exception:
        return None


def _resolve_google_news_url(url: str, timeout: float = 12.0) -> Optional[str]:
    """Resolve a Google News redirect URL to the publisher's article URL.

    New-style Google News tokens are opaque signatures — the mapping only
    exists on Google's servers, and the redirect itself is performed by
    client-side JS, so a plain GET never yields the publisher URL. The
    article page embeds per-fetch ``data-n-a-sg`` / ``data-n-a-ts`` tokens;
    those are POSTed to Google's batchexecute ``garturlreq`` RPC, which
    returns the publisher URL. Returns None when resolution fails for any
    reason (network, changed RPC format, rate limit) — callers fall back to
    the original URL and report honestly. Bounded by ``timeout`` per call.
    """
    token = _google_news_article_id(url)
    if not token:
        return None
    try:
        import httpx
        import json as _json
        import re as _re
        import urllib.parse as _up
        headers = {
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0.0.0 Safari/537.36"),
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "*/*;q=0.8"),
            "Accept-Language": "en-US,en;q=0.9",
        }
        # Blank hl/gl/ceid: Google serves the resolver shell for this form
        # (a plain ?oc=5 fetch hangs for non-browser clients).
        page_url = ("https://news.google.com/rss/articles/"
                    f"{token}?hl=&gl=&ceid=")
        resp = httpx.get(page_url, timeout=timeout, follow_redirects=True,
                         headers=headers)
        if resp.status_code != 200:
            return None
        sg_m = _re.search(rb'data-n-a-sg="([^"]+)"', resp.content)
        ts_m = _re.search(rb'data-n-a-ts="([^"]+)"', resp.content)
        if not (sg_m and ts_m):
            return None
        try:
            ts = int(ts_m.group(1))
        except ValueError:
            return None
        sg = sg_m.group(1).decode("ascii", "ignore")
        # garturlreq envelope (Google's internal RPC; if Google changes it
        # this POST fails and we return None — never a guessed URL).
        inner = ["garturlreq",
                 [["en-US", "US", ["FINANCE_TOP_INDICES", "WEB_TEST_1_0_0"],
                   None, None, 1, 1, "US:en", None, 180, None, None, None,
                   None, None, 0, None, None, [1608992183, 723341000]],
                  "en-US", "US", 1, [2, 3, 4, 8], 1, 0, "655000234",
                  0, 0, None, 0],
                 token, ts, sg]
        freq = [[["Fbv4je", _json.dumps(inner, separators=(",", ":")),
                  None, "generic"]]]
        body = "f.req=" + _up.quote(_json.dumps(freq, separators=(",", ":")))
        r2 = httpx.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute"
            "?rpcids=Fbv4je",
            content=body, timeout=timeout,
            headers={**headers,
                     "Content-Type":
                         "application/x-www-form-urlencoded;charset=utf-8",
                     "Referer": page_url,
                     "Origin": "https://news.google.com",
                     "x-same-domain": "1"})
        if r2.status_code != 200:
            return None
        # The payload is backslash-escaped inside the RPC envelope.
        text = r2.text.replace('\\"', '"')
        m = _re.search(r'\["garturlres",\s*"(https?://[^"]+)"', text)
        if not m:
            return None
        resolved = m.group(1)
        # Sanity: must be a real publisher URL, never another Google wrapper.
        host = (_up.urlparse(resolved).hostname or "").lower()
        if not host or "google." in host:
            return None
        return resolved
    except Exception:
        return None


def _resolve_article_url(url: str) -> str:
    """Return the fetchable article URL for a news link.

    Google News redirect URLs are resolved to the publisher's article URL
    (their HTML is what carries the og:image the preview needs). Every
    other URL passes through unchanged. Never raises and never invents a
    URL: on any failure the original URL is returned so callers keep their
    existing behavior and honest failure notes.
    """
    if not url:
        return url
    try:
        resolved = _resolve_google_news_url(url)
    except Exception:
        resolved = None
    return resolved or url


def _og_image(article_url: str, timeout: float = 8.0) -> Optional[str]:
    """Best-effort hero-image extraction from an article page.

    Checks og:image / twitter:image, JSON-LD structured data (where many
    publishers put the hero image), and older link/itemprop fallbacks.

    Google News redirect URLs are resolved to the publisher's article URL
    first — the redirect is client-side JS, so fetching the wrapper directly
    only ever hangs.
    """
    article_url = _resolve_article_url(article_url)
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
    """Run do_work under the per-kind lock; write back an honest state.

    ``do_work`` returns ``(changed, note)``. The outcome is recorded
    honestly (``succeeded`` / ``no_change`` / ``failed``) — a failure is
    never recorded as a success, and the real error text lands in the
    note. A failure to persist the final state is printed loudly, never
    swallowed. Save-time enrichment is the exclusive "enrich" kind: it
    never clobbers a manual refresh's per-kind state (#53/#54).
    """
    lock = _ENRICH_LOCKS.setdefault((story_id, "enrich"), threading.Lock())
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
            _finish_refresh(story_id, "enrich", status, note or "")
        except Exception:
            traceback.print_exc()
    finally:
        lock.release()


def recover_orphaned_refreshes() -> int:
    """Mark stories stuck in a busy refresh state as interrupted.

    Refresh workers live only in this process's memory: when the
    Streamlit process restarts, any persisted busy state is orphaned and
    its buttons would stay stuck forever. Runs once per process — at
    process start no worker of ours can be alive, so every busy state
    found here is orphaned by definition. Each orphaned kind is cleared
    and gets an ``interrupted`` pending-outcome entry so the UI toasts
    the honest note (#53); nothing else is touched. Understands both the
    current per-kind ``refresh_busy`` list and the legacy single-flag
    ``enrichment_status`` format. Returns the number recovered.
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
        try:
            with _meta_write_lock(sid):
                snap = _read_meta_body(sid)
                if snap is None:
                    continue
                meta, body = snap
                busy = refresh_busy_kinds(meta)
                if not busy:
                    continue
                meta.pop("refresh_busy", None)
                pending = meta.get("refresh_outcome_pending")
                if not isinstance(pending, list):
                    pending = []
                noted = {_outcome_entry_kind(e) for e in pending}
                for kind in sorted(busy):
                    if kind not in noted:
                        pending.append(json.dumps({
                            "kind": kind,
                            "status": "interrupted",
                            "note": ("A previous refresh was interrupted (the "
                                     "app restarted while it was running). "
                                     "Nothing was changed — try again."),
                        }))
                meta["refresh_outcome_pending"] = pending
                meta["enrichment_status"] = "interrupted"
                meta["refresh_kind"] = ""
                meta["refresh_note"] = ("A previous refresh was interrupted (the "
                                        "app restarted while it was running). "
                                        "Nothing was changed — try again.")
                _write_meta_body(sid, meta, body)
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


class ImageDedupeError(RuntimeError):
    """An image dedupe check could not be completed honestly.

    Fetching image bytes for content-hash dedupe must never be skipped
    silently: any failure surfaces here so the refresh fails loudly
    instead of storing a possibly-duplicate image unchecked.
    """


def normalize_image_url(url: str) -> str:
    """Canonical dedupe key for an image URL.

    Collapses trivial variants — host case, default ports, trailing
    slashes, duplicate slashes, query-parameter order, fragments and
    empty queries — so the same address stored twice is recognised as
    one image. Deliberately conservative: the scheme (http vs https) and
    the host (www vs bare) are preserved — true duplicates across those
    are caught by content hashing instead of key collapsing.
    """
    u = (url or "").strip()
    try:
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
        parts = urlsplit(u)
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").lower()
        if not host:
            return u
        try:
            port = parts.port
        except ValueError:
            return u
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            port = None
        netloc = host if port is None else f"{host}:{port}"
        path = parts.path or "/"
        while "//" in path:
            path = path.replace("//", "/")
        if len(path) > 1:
            path = path.rstrip("/") or "/"
        query = ""
        if parts.query.strip("?/"):
            q = parse_qsl(parts.query, keep_blank_values=True)
            query = urlencode(sorted(q))
        return urlunsplit((scheme, netloc, path, query, ""))
    except Exception:
        return u


def _fetch_image_bytes(url: str, timeout: float = 10.0) -> bytes:
    """Download raw image bytes for content-hash dedupe.

    Never returns a guess: any network failure, non-200 status or empty
    body raises :class:`ImageDedupeError` naming the URL — the caller
    fails loudly instead of silently skipping the dedupe check.
    """
    try:
        import httpx
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
    except Exception as e:
        raise ImageDedupeError(
            f"Image dedupe failed: could not fetch {url} "
            f"({type(e).__name__}: {e})") from e
    if resp.status_code != 200:
        raise ImageDedupeError(
            f"Image dedupe failed: {url} returned HTTP {resp.status_code}")
    data = resp.content
    if not data:
        raise ImageDedupeError(
            f"Image dedupe failed: {url} returned an empty body")
    return data


def _image_content_hash(url: str) -> str:
    """SHA-256 hex of the image bytes at ``url``.

    Raises :class:`ImageDedupeError` when the bytes cannot be fetched —
    never a placeholder hash.
    """
    return hashlib.sha256(_fetch_image_bytes(url)).hexdigest()


# Hamming-distance duplicate threshold for 64-bit dHashes (issue #44).
# Calibrated on real photos (see tests/test_perceptual_hash_v16.py):
# JPEG re-saves and resizes score 0, ~5% crops score <= 4, while
# genuinely different photos score >= 24. A threshold of 10 catches
# re-sized, re-compressed and slightly cropped variants with a wide
# margin against false positives on different photos.
_PHASH_DUP_THRESHOLD = 10


# Max auto-fetched images kept per story (issue #83). Manually uploaded
# images live in the separate ``uploaded_images`` field and are NEVER
# capped — only fetched candidates pass through the cap. Callers that
# must exceed the cap (e.g. "Load more", issue #91) omit it.
_MAX_FETCHED_IMAGES = 5


def _image_dhash(data: bytes, url: str) -> int:
    """64-bit difference-hash of raw image bytes — PIL only, no new deps.

    Grayscale → 9x8 LANCZOS shrink → 64 horizontal-gradient bits. Images
    that look the same (re-sized, re-compressed, slightly cropped) land
    within a few bits of each other; different photos land far apart
    (see ``_PHASH_DUP_THRESHOLD``).

    Raises :class:`ImageDedupeError` naming ``url`` when the bytes cannot
    be decoded as an image — never a placeholder hash.
    """
    from PIL import Image
    import io
    try:
        with Image.open(io.BytesIO(data)) as img:
            px = img.convert("L").resize((9, 8), Image.LANCZOS).tobytes()
    except Exception as e:
        raise ImageDedupeError(
            f"Image dedupe failed: could not decode image bytes from {url} "
            f"({type(e).__name__}: {e})") from e
    bits = 0
    for row in range(8):
        off = row * 9
        for col in range(8):
            bits = (bits << 1) | (1 if px[off + col] > px[off + col + 1] else 0)
    return bits


def _hamming_distance(a: int, b: int) -> int:
    """Bit differences between two dHash ints."""
    return bin(a ^ b).count("1")


def _dhash_to_hex(ph: int) -> str:
    """64-bit dHash as a 16-char hex string for frontmatter storage."""
    return f"{ph:016x}"


def _parse_dhash(s: str) -> Optional[int]:
    """Parse a stored dHash hex string; ``None`` when missing/corrupt.

    A corrupt stored value is treated as missing (backfilled on the next
    merge) rather than failing the whole dedupe — the corruption is in
    our own bookkeeping, not the image.
    """
    try:
        return int((s or "").strip(), 16)
    except (ValueError, TypeError):
        return None


def _image_fingerprints(url: str) -> Tuple[str, int]:
    """``(SHA-256 hex, 64-bit dHash)`` for the image at ``url`` — one fetch.

    Raises :class:`ImageDedupeError` (naming the URL) on any fetch or
    decode failure — the dedupe check is never silently skipped.
    """
    data = _fetch_image_bytes(url)
    return hashlib.sha256(data).hexdigest(), _image_dhash(data, url)


def _align_hashes(urls: List[str], hashes: Optional[List[str]]) -> List[str]:
    """Align a stored ``image_hashes`` list with ``image_urls``.

    Unknown hashes become ``""``; the result always matches ``urls`` in
    length and order. Pure — no network.
    """
    hs = [(h or "") for h in (hashes or [])]
    if len(hs) < len(urls):
        hs += [""] * (len(urls) - len(hs))
    return hs[:len(urls)]


def _dedupe_stored_image_entries(
        urls: Optional[List[str]],
        hashes: Optional[List[str]],
        phashes: Optional[List[str]] = None) -> Tuple[List[str], List[str], List[str]]:
    """Order-preserving normalized-URL dedupe of stored image entries.

    Returns ``(urls, hashes, phashes)`` with duplicates dropped (first
    occurrence wins); all three lists stay aligned. Pure — no network;
    used by the save/load migration paths.
    """
    clean = [u for u in (urls or []) if u]
    hs = _align_hashes(clean, hashes)
    ps = _align_hashes(clean, phashes)
    seen: set = set()
    out_urls: List[str] = []
    out_hashes: List[str] = []
    out_phashes: List[str] = []
    for u, h, p in zip(clean, hs, ps):
        key = normalize_image_url(u)
        if key in seen:
            continue
        seen.add(key)
        out_urls.append(u)
        out_hashes.append(h)
        out_phashes.append(p)
    return out_urls, out_hashes, out_phashes


def _merge_story_images(
    existing_urls: Optional[List[str]],
    existing_hashes: Optional[List[str]],
    existing_phashes: Optional[List[str]],
    candidates,
    cap: Optional[int] = None,
) -> Tuple[List[str], List[str], List[str], Dict[str, int]]:
    """Merge image candidates into a story's image list with full dedupe.

    ``candidates`` is an iterable of ``(url, alt_text)`` pairs; a bare
    URL string is also accepted and treated as alt-less (backward
    compatibility for callers that do not carry alt text).

    Steps, in order:
    1. Alt-text relevance filter — the primary signal. Images whose alt
       text marks them as logos/icons/avatars/ads/share-buttons/decorative
       are excluded. Missing alt text is NOT a pass: the URL junk rules
       and content-type preflights applied at extraction still stand.
    2. Normalized-URL dedupe against existing images and within the batch.
    3. Content-hash backfill + collapse of EXISTING entries. This always
       runs — even when no fresh candidates survived — so a refresh that
       finds nothing new still cleans stored duplicates (issue #57).
       Backfill fetches bytes only for entries missing hashes (SHA-256
       and dHash, one fetch per URL; one-time cost, then persisted), so
       candidates are compared against real content, never skipped. ANY
       fetch failure raises :class:`ImageDedupeError` — the check is
       never silently skipped. Existing entries that turn out to be
       identical bytes collapse here (first occurrence wins).
    4. Perceptual-hash dedupe (issue #44): byte-different look-alikes
       (re-sized, re-compressed, slightly cropped) that survived step 3
       are caught by 64-bit dHash — an entry within
       ``_PHASH_DUP_THRESHOLD`` bits of any kept image is a visual
       duplicate and is dropped. Existing entries collapse the same way
       (first occurrence wins); then each surviving fresh candidate is
       checked against everything kept. Undecodable image bytes raise
       :class:`ImageDedupeError` naming the URL — never silently skipped.
    5. Cap (issue #83): only when ``cap`` is passed. After ALL dedupe,
       the merged list is trimmed to ``cap`` entries — the first N are
       kept (existing entries first, then fresh candidates in
       publisher-declared order: og:image → twitter:image → JSON-LD →
       in-article), so the tail is what goes. The trim count is
       reported in ``stats["trimmed"]``.

    Returns ``(merged_urls, merged_hashes, merged_phashes, stats)``;
    ``stats`` counts ``added`` / ``dup_url`` / ``dup_content`` /
    ``dup_visual`` / ``rejected_alt`` / ``removed_existing_dupes`` /
    ``trimmed``.
    Existing order is preserved; genuinely new images are appended.
    """
    from tools.story_link import image_alt_is_unwanted

    existing_urls = [u for u in (existing_urls or []) if u]
    hashes = _align_hashes(existing_urls, existing_hashes)
    phashes = _align_hashes(existing_urls, existing_phashes)
    stats = {"added": 0, "dup_url": 0, "dup_content": 0, "dup_visual": 0,
             "rejected_alt": 0, "removed_existing_dupes": 0, "trimmed": 0}

    # 1. Alt-text filter (primary signal).
    screened: List[str] = []
    for item in candidates or []:
        if isinstance(item, (tuple, list)):
            url = item[0] if len(item) > 0 else ""
            alt = item[1] if len(item) > 1 else None
        else:
            url, alt = item, None
        url = (url or "").strip()
        if not url:
            continue
        if image_alt_is_unwanted(alt):
            stats["rejected_alt"] += 1
            continue
        screened.append(url)

    # 2. Normalized-URL dedupe against existing images and within the batch.
    seen_urls = {normalize_image_url(u) for u in existing_urls}
    fresh: List[str] = []
    for url in screened:
        key = normalize_image_url(url)
        if key in seen_urls:
            stats["dup_url"] += 1
            continue
        seen_urls.add(key)
        fresh.append(url)

    merged_urls = list(existing_urls)
    merged_hashes = list(hashes)
    merged_phashes = list(phashes)

    # 3. Content-hash backfill + collapse of existing entries. ALWAYS
    #    runs, even when no fresh candidates exist (issue #57): a refresh
    #    that finds nothing new must still clean stored duplicates.
    #    Backfill fetches bytes only for entries missing hashes (one-time
    #    cost, then persisted); the collapse against stored hashes is
    #    pure. ANY fetch/decode failure raises ImageDedupeError — never
    #    silently skipped.
    for i, url in enumerate(merged_urls):
        if not merged_hashes[i] or not merged_phashes[i]:
            h, ph = _image_fingerprints(url)
            if not merged_hashes[i]:
                merged_hashes[i] = h
            if not merged_phashes[i]:
                merged_phashes[i] = _dhash_to_hex(ph)
    # Collapse existing entries that turn out to be identical bytes
    # (first occurrence wins).
    deduped_urls: List[str] = []
    deduped_hashes: List[str] = []
    deduped_phashes: List[str] = []
    seen_hashes: set = set()
    for url, h, p in zip(merged_urls, merged_hashes, merged_phashes):
        if h in seen_hashes:
            stats["removed_existing_dupes"] += 1
            continue
        seen_hashes.add(h)
        deduped_urls.append(url)
        deduped_hashes.append(h)
        deduped_phashes.append(p)
    merged_urls, merged_hashes, merged_phashes = (
        deduped_urls, deduped_hashes, deduped_phashes)

    # 4. Perceptual-hash dedupe. Collapse existing entries that are visual
    #    near-duplicates first (order preserved, first wins), then check
    #    each surviving candidate against everything kept.
    kept_dhashes: List[int] = []
    vis_urls: List[str] = []
    vis_hashes: List[str] = []
    vis_phashes: List[str] = []
    for url, h, p in zip(merged_urls, merged_hashes, merged_phashes):
        ph = _parse_dhash(p)
        if (ph is not None and any(
                _hamming_distance(ph, k) <= _PHASH_DUP_THRESHOLD
                for k in kept_dhashes)):
            stats["removed_existing_dupes"] += 1
            continue
        vis_urls.append(url)
        vis_hashes.append(h)
        vis_phashes.append(p)
        if ph is not None:
            kept_dhashes.append(ph)
    merged_urls, merged_hashes, merged_phashes = vis_urls, vis_hashes, vis_phashes
    seen_hashes = set(merged_hashes)

    # Fresh candidates. The loop is a no-op when empty — but the
    # existing-entries backfill + collapse above already ran, so stored
    # duplicates are cleaned and missing hashes are backfilled even when
    # the fetch found nothing new (issue #57).
    for url in fresh:
        h, ph = _image_fingerprints(url)
        if h in seen_hashes:
            stats["dup_content"] += 1
            continue
        if any(_hamming_distance(ph, k) <= _PHASH_DUP_THRESHOLD
               for k in kept_dhashes):
            stats["dup_visual"] += 1
            continue
        seen_hashes.add(h)
        kept_dhashes.append(ph)
        merged_urls.append(url)
        merged_hashes.append(h)
        merged_phashes.append(_dhash_to_hex(ph))
        stats["added"] += 1

    # 5. Cap (issue #83): after ALL dedupe, trim to the cap — the first N
    #    are kept (existing entries first, fresh candidates appended in
    #    publisher-declared order), so the tail is what goes. The trim
    #    count is reported in stats["trimmed"] for an honest outcome
    #    note. Only when `cap` is passed — "Load more" (issue #91)
    #    omits it and bypasses the cap.
    if cap is not None and len(merged_urls) > cap:
        stats["trimmed"] = len(merged_urls) - cap
        merged_urls = merged_urls[:cap]
        merged_hashes = merged_hashes[:cap]
        merged_phashes = merged_phashes[:cap]
    return merged_urls, merged_hashes, merged_phashes, stats


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
                         per_page: int = 3,
                         report: Optional[Dict[str, Any]] = None
                         ) -> List[Tuple[str, Optional[str]]]:
    """Parallel article-page image extraction from a list of page URLs.

    Each article's HTML is fetched (httpx, timeout, retries) and passed to
    ``tools.story_link.extract_story_images_with_alt``, which pulls
    og:image → twitter:image → JSON-LD → in-article story-body photos
    as ``(url, alt_text)`` pairs (issue #86: in-article extraction is
    scoped to the story body — site chrome under header/nav/footer/aside
    is excluded). News pages carry their real photos in body <img> tags,
    so this finds images that an og:image-only grab misses. Relative and
    lazy-load URLs are absolutized; logos, sprites, SVGs, tracking pixels
    and alt-text-flagged unwanted assets are filtered. Batch results are
    deduplicated by normalized URL.

    When ``report`` (a dict) is supplied, ``report["unscoped_pages"]`` is
    set to the number of pages where no article body could be identified
    and the extractor fell back to a whole-page scan — the caller
    surfaces this honestly in the refresh outcome note.
    """
    from tools.story_link import extract_story_images_with_alt

    found: List[Tuple[str, Optional[str]]] = []
    seen: set = set()
    found_lock = threading.Lock()
    threads: List[threading.Thread] = []
    unscoped_pages = 0

    def _grab(url: str) -> None:
        nonlocal unscoped_pages
        # Resolve Google News wrappers to the publisher page first — the
        # wrapper's own HTML is a JS shell with no article images.
        url = _resolve_article_url(url)
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
        scope_report: Dict[str, Any] = {}
        try:
            imgs = extract_story_images_with_alt(html, url, limit=per_page,
                                                 scope_report=scope_report)
        except Exception:
            return
        with found_lock:
            if scope_report.get("scoped") is False:
                unscoped_pages += 1
            for img_url, alt in imgs:
                key = normalize_image_url(img_url)
                if key not in seen:
                    seen.add(key)
                    found.append((img_url, alt))

    for link in urls:
        if link:
            t = threading.Thread(target=_grab, args=(link,), daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join(timeout=30.0)
    if report is not None:
        report["unscoped_pages"] = unscoped_pages
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
                            tries: int = 3,
                            report: Optional[Dict[str, Any]] = None
                            ) -> List[Tuple[str, Optional[str]]]:
    """Images for a story: verified story links first, then topic search.

    The story's own verified news links point at the exact story's publisher
    pages, so their article images are the most on-topic. Each page's HTML
    is fetched and its og:image → twitter:image → JSON-LD → in-article
    <img> photos are extracted (news sites carry real photos in body <img>
    tags). Only when those yield nothing do we fall back to topic-search
    articles and web image search.

    Returns ``(url, alt_text)`` pairs — alt text drives the relevance
    filter in the merge step. Hero/web-search images carry no alt text
    (``None``).

    When ``report`` (a dict) is supplied it is passed to the article-image
    grab, which records ``report["unscoped_pages"]`` — pages where no
    article body could be identified (issue #86 fallback).

    Every step runs under a hard wall-clock bound (via ``_run_bounded``):
    a stuck host raises ``TimeoutError`` naming the step instead of
    hanging the refresh. Pure fetch — no persistence here.
    """
    direct = _story_direct_link_urls(story)
    if direct:
        found = _run_bounded(
            lambda: _grab_article_images(direct[:6], tries=tries,
                                         report=report),
            40.0, "article image fetch")
        if found:
            return found[:6]
    articles = _fetch_news_articles(topic, limit=6)
    return _run_bounded(
        lambda: _fetch_article_images(articles, topic, tries=tries),
        90.0, "topic image fetch")


def _fetch_article_images(articles, topic: str = "", tries: int = 3
                          ) -> List[Tuple[str, Optional[str]]]:
    """Hero images for a topic.

    Tries hero-image extraction from the article pages (parallel, with
    retries). If that finds nothing at all, falls back to a web image search
    for the topic so the story still gets images. Candidate preflights run
    in parallel under a bounded join — sequential HEAD+GET checks used to
    cost up to 16s per URL. Hero and web-search images have no alt text.
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
    return [(u, None) for u in found[:6]]


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
    search. New images are merged after the existing URLs — the user's
    curated list is never wiped. Adding an image that is already attached
    is a no-op: duplicates are detected by normalized URL AND by
    identical content (SHA-256 of the fetched bytes), so the same image
    served from a different address is still recognised (issue #21).
    Images whose alt text marks them as unwanted (logos, avatars, ads)
    are excluded; missing alt text is not a pass by itself.

    A fetch/hash failure raises ImageDedupeError — the dedupe check is
    never silently skipped. When the fetch finds nothing new, the merge
    still runs: stored duplicates (byte-identical or visual) are
    collapsed and missing hashes are backfilled, and that cleanup is
    written back and reported (issue #57). Returns (changed, note).
    Never touches hashtags, links, or story content.
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — images unchanged.")
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        raise RuntimeError("No topic to search — images unchanged.")
    existing = list(story["meta"].get("image_urls") or [])
    existing_hashes = list(story["meta"].get("image_hashes") or [])
    existing_phashes = list(story["meta"].get("image_phashes") or [])
    img_report: Dict[str, Any] = {}
    try:
        found = _fetch_images_for_story(story, topic, report=img_report)
    except TimeoutError as e:
        # The fetch names the step that timed out; existing media survives.
        # Hash backfill needs the network too, so it would fail as well —
        # the honest timeout note stands and nothing is written.
        return False, f"Image refresh timed out ({e}); kept {len(existing)} existing."
    # The merge ALWAYS runs — even when the fetch found nothing new — so
    # stored duplicates are collapsed and missing hashes are backfilled
    # (issue #57). The collapse against stored hashes is pure; only the
    # backfill touches the network.
    merged_urls, merged_hashes, merged_phashes, stats = _merge_story_images(
        existing, existing_hashes, existing_phashes, found,
        cap=_MAX_FETCHED_IMAGES)
    added = stats["added"]
    aligned_hashes = _align_hashes(existing, existing_hashes)
    aligned_phashes = _align_hashes(existing, existing_phashes)
    urls_changed = merged_urls != existing
    hashes_changed = (merged_hashes != aligned_hashes
                      or merged_phashes != aligned_phashes)
    extras: List[str] = []
    if stats["rejected_alt"]:
        extras.append(f"Excluded {stats['rejected_alt']} unwanted image(s) "
                      f"(logo/avatar/ad per alt text).")
    if stats["removed_existing_dupes"]:
        extras.append(f"Removed {stats['removed_existing_dupes']} duplicate "
                      f"image(s) already stored.")
    if img_report.get("unscoped_pages"):
        # Issue #86: say it honestly — these pages were scanned
        # page-wide because no story body could be identified.
        _n = img_report["unscoped_pages"]
        extras.append(f"Note: {_n} article page(s) had no identifiable story "
                      f"body — images were scanned page-wide and may "
                      f"include site images.")
    if stats["trimmed"]:
        extras.append(f"Capped fetched images at {_MAX_FETCHED_IMAGES} "
                      f"({stats['trimmed']} extra not kept; "
                      f"uploads are never capped).")
    extra = (" " + " ".join(extras)) if extras else ""
    if added or urls_changed or hashes_changed:
        update_story_fields(story_id, image_urls=merged_urls,
                            image_hashes=merged_hashes,
                            image_phashes=merged_phashes)
    if not added:
        note = f"No new images found; kept {len(merged_urls)} existing."
        dupes = stats["dup_url"] + stats["dup_content"] + stats["dup_visual"]
        if dupes:
            note += f" ({dupes} already stored.)"
        return urls_changed or hashes_changed, (note + extra).strip()
    return True, f"Added {added} new image(s); kept {len(existing)} existing.{extra}"


def _normalize_news_url(url: str) -> str:
    """Canonical dedupe key for a news-link URL (#80).

    Conservative: strip whitespace, lowercase the whole URL and drop a
    trailing slash. Deliberately lighter than ``normalize_image_url`` —
    news links are article pages, not byte-compared assets, so scheme /
    query collapsing is left alone (Google News redirect links differ
    from the canonical article URL and must still match when re-found).
    """
    u = (url or "").strip().lower()
    return u[:-1] if u.endswith("/") and len(u) > 1 else u


# Issue #82: news links target at least 5 related links per story, max 5.
NEWS_LINKS_TARGET = 5


def _news_query_variants(topic: str) -> List[str]:
    """Progressively looser Google News queries for one topic (#82).

    The full topic is tried first; when it under-fetches (a very
    specific headline matches few articles), looser variants follow:
    the first clause (parentheticals, quoted segments and trailing
    ``; : ! ?`` clauses dropped), then the significant-keyword core
    (reuses ``_keyword_list``). Variants are distinct and non-empty;
    an empty topic yields [].
    """
    t = re.sub(r"\s+", " ", (topic or "")).strip()
    if not t:
        return []
    variants: List[str] = []

    def _push(q: str) -> None:
        q = re.sub(r"\s+", " ", q).strip(" ;:!?-\u2013\u2014()[]\"'")
        if len(q) >= 3 and q.lower() not in {v.lower() for v in variants}:
            variants.append(q)

    _push(t)
    # Looser: drop parentheticals/quotes, keep the first clause.
    loose = re.sub(r"\(.*?\)|\[.*?\]|\"[^\"]*\"|'[^']*'", " ", t)
    loose = re.split(r"[;:!?\u2014\u2013]", loose, maxsplit=1)[0]
    _push(loose)
    # Loosest: significant keywords only.
    _push(" ".join(_keyword_list(loose)[:8]))
    return variants


def _fetch_news_link_candidates(topic: str, count: int = NEWS_LINKS_TARGET,
                                exclude_urls=()) -> List[Dict[str, str]]:
    """Fetch up to ``count`` NEW news links for ``topic`` (#82).

    Reusable "fetch up to N new links for topic T excluding existing
    URLs" primitive — #91 (load more news references) composes with
    this rather than duplicating it.

    Tries the topic's query variants in order (full topic, then looser
    variants) and pulls a pool from ``news_fetcher.search_news`` per
    variant, keeping distinct links (normalized-URL dedupe, #21) that
    are not in ``exclude_urls``. Stops as soon as ``count`` candidates
    are gathered. ``count <= 0`` returns [] without searching.

    Fail-loud: when every variant's search raises, raises RuntimeError
    naming the cause — a fetch failure is never reported as an empty
    result. A shortfall (fewer than ``count`` genuinely related links
    exist) is an honest short list, never padded or invented; callers
    report it in their outcome note.
    """
    count = max(0, int(count or 0))
    if count == 0:
        return []
    topic = (topic or "").strip()
    if not topic:
        raise RuntimeError("No topic to search — news links unchanged.")
    from tools.news_fetcher import news_fetcher
    excluded = {_normalize_news_url(u) for u in (exclude_urls or ())}
    seen = set(excluded)
    found: List[Dict[str, str]] = []
    errors: List[str] = []
    for variant in _news_query_variants(topic):
        if len(found) >= count:
            break
        try:
            articles = (news_fetcher.search_news(
                variant, limit=max(count * 3, 12)) or [])
        except Exception as e:  # noqa: BLE001 - collected, raised loudly below
            errors.append(f"{variant!r}: {type(e).__name__}: {e}")
            continue
        for a in articles:
            url = (getattr(a, "link", "") or "").strip()
            if not url:
                continue
            key = _normalize_news_url(url)
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "title": getattr(a, "title", "") or "",
                "url": url,
                "source": getattr(a, "source", "") or "",
            })
            if len(found) >= count:
                break
    if not found and errors:
        raise RuntimeError(
            f"News search failed ({errors[0]}) — news links unchanged.")
    return found


def refresh_news_links(story_id: str, topic: str = "") -> Tuple[bool, str]:
    """Re-fetch news links (sources) and ADD the new ones to the story.

    Runs the same Google News search as save-time enrichment, then
    merges genuinely new links after the existing ones — the stored
    list is never wiped, and verified Stage-1 links keep their place
    (#62). Duplicates are detected by normalized URL, so a source found
    again is not stored twice. Issue #82: tops the story up toward
    ``NEWS_LINKS_TARGET`` (5) links, never beyond it — the fetch tries
    progressively looser queries until the target is reached.
    Never touches hashtags, images, or story content.

    Fail-loud: a story with no topic, a missing story, or a search
    failure raises RuntimeError with the honest cause — a network
    failure is never reported as "nothing new". A shortfall (fewer
    than 5 genuinely related links exist) is an honest "now at N of 5"
    note, not an error. Returns (changed, note).
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — news links unchanged.")
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        raise RuntimeError("No topic to search — news links unchanged.")
    # #143: repair any stored redirect URLs to their final destinations
    # before topping up — stories saved before universal resolution may
    # still hold aggregator/shortener links.
    try:
        _repaired, _repair_note = repair_news_link_urls(story_id)
    except Exception:
        _repaired, _repair_note = False, ""
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — news links unchanged.")
    existing = [lk for lk in (story["meta"].get("news_links") or [])
                if isinstance(lk, dict) and lk.get("url")]
    room = NEWS_LINKS_TARGET - len(existing)
    if room <= 0:
        return False, (f"Kept {len(existing)} existing news link(s) "
                       f"(at the {NEWS_LINKS_TARGET}-link cap).")
    added = _fetch_news_link_candidates(
        topic, count=room,
        exclude_urls=[lk["url"] for lk in existing])
    if added:
        update_story_fields(story_id, news_links=existing + added)
        total = len(existing) + len(added)
        note = (f"Added {len(added)} new news link(s); "
                f"now at {total} of {NEWS_LINKS_TARGET}.")
        if total < NEWS_LINKS_TARGET:
            note += f" Only {total} related article(s) found."
        return True, note
    return False, (f"No new news links found; kept {len(existing)} "
                   "existing.")


def repair_news_link_urls(story_id: str) -> Tuple[bool, str]:
    """Re-resolve stored news-link URLs to their final destinations (#143).

    Repairs stories saved before universal redirect resolution: every
    stored news-link URL is followed through its full redirect chain
    and updated when the final URL differs. #153: the source label is
    refreshed to the final publisher's name whenever the URL changes
    or the stored source is a stale aggregator name ("Bing News"/
    "DuckDuckGo"/"News Wire"/"Live Wire") — the chip must show the
    publisher, not the aggregator. Unresolvable redirect URLs
    (known aggregator hosts) are dropped loudly; other unresolvable
    URLs are kept (fail-open — likely direct links blocking bots).
    #230: a stale aggregator label is refreshed from the URL's domain
    whether or not resolution succeeds — fail-open applies to the
    URL, not the label.

    Runs in background threads (called from refresh paths), never on
    the render path. Returns (changed, note).
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — news link URLs unchanged.")
    existing = [lk for lk in (story["meta"].get("news_links") or [])
                if isinstance(lk, dict) and lk.get("url")]
    if not existing:
        return False, "No stored news links to repair."
    from tools.news_fetcher import news_fetcher, publisher_name_from_url
    repaired = 0
    dropped = 0
    sources_refreshed = 0
    kept: List[Dict[str, str]] = []
    for lk in existing:
        url = (lk.get("url") or "").strip()
        if not url:
            dropped += 1
            continue
        final = news_fetcher.resolve_final_url(url)
        # #230: a stale aggregator label is refreshed from the URL's
        # domain whether or not resolution succeeds — the publisher is
        # fully determined by the domain, no network call needed.
        # Fail-open applies to the URL, not the label.
        old_source = (lk.get("source") or "").strip()
        new_source = old_source
        if old_source in _STALE_AGGREGATOR_SOURCES:
            new_source = publisher_name_from_url(final or url) or old_source
        if final:
            url_changed = final != url
            if url_changed:
                new_source = publisher_name_from_url(final) or new_source
            if url_changed:
                repaired += 1
            if new_source != old_source:
                sources_refreshed += 1
            kept.append(dict(lk, url=final, source=new_source))
            continue
        # Unresolvable: drop loudly only known redirect hosts (#143);
        # otherwise fail-open on the URL but keep the refreshed label (#230).
        try:
            host = urllib.parse.urlparse(url).netloc.lower()
        except Exception:
            host = ""
        if host in news_fetcher._AGGREGATOR_REDIRECT_HOSTS:
            dropped += 1
        elif new_source != old_source:
            sources_refreshed += 1
            kept.append(dict(lk, source=new_source))
        else:
            kept.append(lk)
    if repaired or dropped or sources_refreshed:
        update_story_fields(story_id, news_links=kept)
    parts = []
    if repaired:
        parts.append(f"re-resolved {repaired} redirect URL(s) to final destinations")
    if sources_refreshed:
        parts.append(f"refreshed {sources_refreshed} source label(s) to final publishers")
    if dropped:
        parts.append(f"dropped {dropped} unresolvable redirect URL(s)")
    note = "; ".join(parts) if parts else "All stored news link URLs already final."
    return bool(parts), note


# Fetch-time source labels that name the aggregator/search engine rather
# than the publisher (#153). When a stored link carries one of these,
# the source is refreshed from the URL's domain — even when redirect
# resolution fails (#230).
_STALE_AGGREGATOR_SOURCES = frozenset(
    {"Bing News", "DuckDuckGo", "News Wire", "Live Wire"}
)


def refresh_stale_news_link_source(source: str, url: str) -> str:
    """Normalize a stored news-link source label to the publisher name (#231).

    The label-refresh half of repair_news_link_urls (#153), without any
    network I/O: when ``source`` is a stale fetch-time engine/aggregator
    name ("Bing News"/"DuckDuckGo"/"News Wire"/"Live Wire") it is replaced
    by the publisher name derived from ``url`` via publisher_name_from_url.
    Any other label is returned unchanged, and the original label is kept
    when no publisher name can be derived from the URL.

    Pure and offline-safe — the Telegram share path (#231) calls this as
    its first step so every user-facing render shows normalized labels
    even when no refresh or repair ran between story creation and sharing.
    A broken tools import propagates loudly (fail-loud); an unparseable
    URL simply keeps its stored label (fail-open — the share never breaks
    because of the network).
    """
    source = (source or "").strip()
    if source not in _STALE_AGGREGATOR_SOURCES:
        return source
    url = (url or "").strip()
    if not url:
        return source
    from tools.news_fetcher import publisher_name_from_url
    return publisher_name_from_url(url) or source


def _fetch_more_images(topic: str, existing_norm_urls: Set[str],
                       batch: int = _LOAD_MORE_BATCH
                       ) -> List[Tuple[str, Optional[str]]]:
    """Deeper image-candidate pool for \"load more\" (#91).

    Goes wider than ``_fetch_images_for_story``: 12 topic articles (vs 6)
    and up to 4 images per article page (vs 3), then the web image search
    as a final fallback — every candidate filtered to exclude the
    already-stored normalized URLs, so the batch is genuinely new by URL
    before the merge's content/perceptual dedupe runs. Extraction reuses
    the same article-scoped path as refresh (#86), so site chrome stays
    out here too. Pure fetch — no persistence. Bounded like the refresh
    path; a stuck host raises TimeoutError naming the step.
    """
    found: List[Tuple[str, Optional[str]]] = []
    seen = set(existing_norm_urls)
    articles = _fetch_news_articles(topic, limit=12)
    urls = [getattr(a, "link", "") or "" for a in articles]
    for url, alt in _run_bounded(
            lambda: _grab_article_images(urls, per_page=4),
            90.0, "load-more image fetch"):
        key = normalize_image_url(url)
        if key and key not in seen:
            seen.add(key)
            found.append((url, alt))
            if len(found) >= batch:
                return found
    if len(found) < batch and topic.strip():
        for url in _search_web_images(topic.strip(), limit=10):
            key = normalize_image_url(url)
            if key and key not in seen:
                seen.add(key)
                found.append((url, None))
                if len(found) >= batch:
                    break
    return found


def load_more_images(story_id: str, topic: str = "") -> Tuple[bool, str]:
    """Fetch ONE more batch (up to 5) of genuinely new images (#91).

    The sanctioned way past the #83 fetched-images cap: the cap is
    bypassed by this explicit user request, but dedupe is never bypassed
    — every candidate goes through the full ``_merge_story_images``
    pipeline (alt-text filter, normalized-URL, SHA-256 content and dHash
    perceptual dedupe, #21/#44). New images are appended after the
    existing list; the stored list is never wiped and manual uploads are
    never touched.

    Fail-loud: a missing story, missing topic, or fetch failure raises
    RuntimeError with the honest cause. When the deeper pool yields
    nothing new, this returns ``(False, \"No more images found …\")`` —
    a ``no_change`` outcome, never a faked success. Never touches
    hashtags, news links, or story content.
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — images unchanged.")
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        raise RuntimeError("No topic to search — images unchanged.")
    existing = list(story["meta"].get("image_urls") or [])
    existing_hashes = list(story["meta"].get("image_hashes") or [])
    existing_phashes = list(story["meta"].get("image_phashes") or [])
    existing_norm = {normalize_image_url(u) for u in existing}
    try:
        fresh = _fetch_more_images(topic, existing_norm,
                                   batch=_LOAD_MORE_BATCH)
    except TimeoutError as e:
        return False, (f"Load-more timed out ({e}); "
                       f"kept {len(existing)} existing.")
    # The merge ALWAYS runs so stored duplicates are collapsed and
    # missing hashes backfilled (#57) — and so the batch survives the
    # same dedupe as a refresh. #91: no total-count trim is applied here;
    # the #83 cap is bypassed by this explicit user request.
    merged_urls, merged_hashes, merged_phashes, stats = _merge_story_images(
        existing, existing_hashes, existing_phashes, fresh)
    added = stats["added"]
    if added:
        update_story_fields(story_id, image_urls=merged_urls,
                            image_hashes=merged_hashes,
                            image_phashes=merged_phashes)
        return True, (f"Added {added} more image(s); "
                      f"{len(merged_urls)} total.")
    note = f"No more images found; kept {len(merged_urls)} existing."
    dupes = stats["dup_url"] + stats["dup_content"] + stats["dup_visual"]
    if dupes:
        note += f" ({dupes} already stored.)"
    return False, note


def load_more_news_links(story_id: str, topic: str = "") -> Tuple[bool, str]:
    """Fetch ONE more batch (up to 5) of genuinely new news links (#91).

    The sanctioned way past the #82 5-link target: this explicit user
    request composes with ``_fetch_news_link_candidates`` (#82's reusable
    primitive — query variants, normalized-URL dedupe, fail-loud) and
    asks for one more batch of links that are not already stored,
    appended after the existing ones, which are never wiped and never
    reordered. Fail-loud: a missing story, missing topic, or search
    failure raises RuntimeError with the honest cause; a shortfall
    returns ``(False, "No more news links found")`` — never a faked
    success. Never touches hashtags, images, or story content.
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — news links unchanged.")
    topic = (topic or story["meta"].get("source_topic") or "").strip()
    if not topic:
        raise RuntimeError("No topic to search — news links unchanged.")
    # #143: repair any stored redirect URLs to their final destinations
    # (stories saved before universal resolution).
    try:
        repair_news_link_urls(story_id)
    except Exception:
        pass
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Story not found — news links unchanged.")
    existing = [lk for lk in (story["meta"].get("news_links") or [])
                if isinstance(lk, dict) and lk.get("url")]
    added = _fetch_news_link_candidates(
        topic, count=_LOAD_MORE_BATCH,
        exclude_urls=[lk["url"] for lk in existing])
    if added:
        update_story_fields(story_id, news_links=existing + added)
        return True, (f"Added {len(added)} more news link(s); "
                      f"{len(existing) + len(added)} total.")
    return False, (f"No more news links found; kept {len(existing)} "
                    "existing.")


def _refresh_worker(story_id: str, kind: str, topic: str,
                    ai_engine: Optional[str] = None) -> None:
    """Background worker for one manual refresh kind. Never raises.

    Runs in a daemon thread so tab switches (st.rerun) can't stop it.
    Per-kind locking: "hashtags", "images", "news", "more_images" and
    "more_news" are independent and run concurrently (#54, #80, #91) —
    each kind owns only its own busy flag and outcome, so finishing never
    clears a sibling kind's state (#53). The outcome is recorded honestly (``succeeded`` / ``no_change`` /
    ``failed``) with the real detail in the note — a failure is never
    written as a success, and the toggle-off AI error surfaces verbatim.
    """
    lock = _ENRICH_LOCKS.setdefault((story_id, kind), threading.Lock())
    if not lock.acquire(blocking=False):
        # Another worker owns this kind's refresh state — leave it alone.
        # Writing anything here (even "already running") would clobber the
        # in-flight busy state and flip the UI back to idle while work is
        # still running. The owning worker writes the honest terminal state
        # when it finishes.
        return
    try:
        try:
            if kind == "hashtags":
                changed, note = refresh_hashtags(story_id, topic, ai_engine=ai_engine)
            elif kind == "images":
                changed, note = refresh_images(story_id, topic)
            elif kind == "news":
                changed, note = refresh_news_links(story_id, topic)
            elif kind == "more_images":
                changed, note = load_more_images(story_id, topic)
            elif kind == "more_news":
                changed, note = load_more_news_links(story_id, topic)
            elif kind == "reset":
                changed, note = _do_reset(story_id, topic, ai_engine=ai_engine)
            else:
                changed, note = False, f"Unknown refresh kind: {kind!r}."
            status = "succeeded" if changed else "no_change"
        except Exception as e:
            status = "failed"
            label = {"hashtags": "Hashtag", "images": "Image",
                     "news": "News", "more_images": "Load more images",
                     "more_news": "Load more news",
                     "reset": "Reset"}.get(kind, kind)
            note = f"{label} refresh failed: {e}"
        try:
            _finish_refresh(story_id, kind, status, note or "")
        except Exception:
            traceback.print_exc()
    finally:
        lock.release()


def start_refresh(story_id: str, kind: str,
                  ai_engine: Optional[str] = None) -> Tuple[bool, str]:
    """Kick off a background hashtag/image/news/reset refresh. Never raises.

    ``kind`` is "hashtags", "images", "news", "more_images", "more_news" or
    "reset". ``ai_engine`` (an engine mode string or None) enables
    AI-assisted hashtag suggestions for the hashtags and reset kinds —
    None means the "Enable AI processing" toggle is off, in which case
    the worker fails loudly with a clear message instead of silently
    falling back. The "news" kind re-fetches news links (sources) for the
    story's topic and merges new ones in (never wipes). The "more_images"
    / "more_news" kinds (#91) fetch ONE more batch (up to 5) of genuinely
    new images / news links past the #83/#82 caps — the cap is bypassed
    by this explicit user request, dedupe never is. The "reset" kind
    destructively clears all hashtags, fetched images and news links and
    re-fetches them fresh (manual uploads are never touched). The fetch
    runs in a daemon thread, so changing tabs mid-refresh won't stop it.
    Falls back to the story title when ``source_topic`` is missing so
    older stories can still refresh.

    Concurrency (#54, #80, #91): "hashtags", "images", "news",
    "more_images" and "more_news" are independent and may run at the same
    time — a second kick is refused only for the SAME kind, for the
    SIBLING kind that writes the same field ("images"↔"more_images",
    "news"↔"more_news" — concurrent writers would silently clobber each
    other's appended batch), or when an exclusive kind ("reset", or
    save-time "enrich") is running. "reset" stays exclusive: it refuses
    while ANY kind runs.

    Returns (started, reason): ``reason`` is "" when the refresh started,
    otherwise a human-readable explanation of why it could not start.
    """
    if kind not in ("hashtags", "images", "news", "more_images",
                    "more_news", "reset"):
        return False, f"Unknown refresh kind: {kind!r}."
    try:
        story = load_story(story_id)
        if not story:
            return False, "Story not found."
        busy = refresh_busy_kinds(story["meta"])
        if kind == "reset":
            if busy:
                # The buttons disable while busy, but a double-kick can still
                # race here — refuse instead of starting a second worker that
                # would fight the first over the story's refresh state.
                return False, ("A refresh is already running — reset clears "
                               "hashtags, images and news links, so it can't "
                               "run alongside it. Try again when it's done.")
        elif kind in busy:
            return False, (f"A {kind} refresh is already running — "
                           "try again shortly.")
        elif _SIBLING_KINDS.get(kind) in busy:
            # #91: the sibling writes the same story field — a concurrent
            # run would silently clobber the other's appended batch.
            sibling = _SIBLING_KINDS[kind]
            return False, (f"A {sibling} refresh is already running — "
                           "try again when it's done.")
        elif busy & set(_EXCLUSIVE_KINDS):
            blocker = "reset" if "reset" in busy else "enrichment"
            return False, (f"A {blocker} is already running — "
                           "try again shortly.")
        topic = (story["meta"].get("source_topic")
                 or story["meta"].get("title") or "").strip()
        if not topic:
            return False, "No topic or title to refresh."
        _check_id(story_id)
        if not _set_refresh_busy(story_id, kind):
            return False, "Story not found."
        t = threading.Thread(
            target=_refresh_worker, args=(story_id, kind, topic, ai_engine),
            daemon=True, name=f"refresh-{kind}-{story_id}")
        t.start()
        return True, ""
    except Exception as e:
        reason = f"Could not start refresh: {type(e).__name__}: {e}"
        # Fail loudly AND leave no stuck marker: the story was flagged
        # busy above before the thread failed to start — without a
        # terminal state its buttons (incl. every script-version action,
        # #193) would stay disabled until the next app restart.
        try:
            _finish_refresh(story_id, kind, "failed", reason)
        except Exception:
            traceback.print_exc()
        return False, reason


# ---------------------------------------------------------------------------
# On-device Apple FM warm-up (issue #37)
# ---------------------------------------------------------------------------
# Developer tool: manually trigger the #4 FM availability probe
# (30s -> 30s -> 60s) ahead of time so the first real generation does not
# pay the cold-start delay. Same daemon-thread + terminal-state pattern as
# the refresh flow above: the worker always writes a terminal state, the UI
# auto-polls while busy, and a stale "warming" state is recovered honestly.

# Hard cap for one warm-up run (#122): the worker enforces FM_WARMUP_TIMEOUT_SECONDS
# on the #4 probe (whose internal retry budget is 30+30+60 = 120s), so the
# mailbox always reaches a terminal state within ~60s of kick-off. Anything
# still "warming" past FM_WARMUP_STALE_SECONDS is orphaned (the app died
# mid-run) and is recovered as interrupted — never left stuck.
FM_WARMUP_TIMEOUT_SECONDS = 60.0
FM_WARMUP_STALE_SECONDS = 90.0


def _warmup_state_path() -> Path:
    """Mailbox file for the warm-up worker. Computed from LIBRARY_ROOT so
    tests can redirect it by monkeypatching LIBRARY_ROOT."""
    return LIBRARY_ROOT / "fm_warmup.json"


def _write_fm_warmup_state(state: Dict[str, Any]) -> None:
    """Write the warm-up mailbox atomically (tmp + rename). Never raises
    to the worker: a failed write is printed, and the UI's staleness guard
    recovers honestly on the next read."""
    path = _warmup_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        traceback.print_exc()


def read_fm_warmup_state() -> Dict[str, Any]:
    """Read the warm-up mailbox. Returns {} when idle/never run.

    A "warming" state older than FM_WARMUP_STALE_SECONDS is orphaned (the
    app died mid-run): it is rewritten as a failed/interrupted terminal
    state with an honest note, so the button never stays stuck disabled.
    """
    path = _warmup_state_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("state") == "warming":
        started = data.get("started_at") or 0.0
        try:
            age = time.time() - float(started)
        except (TypeError, ValueError):
            age = FM_WARMUP_STALE_SECONDS + 1.0
        if age > FM_WARMUP_STALE_SECONDS:
            recovered = {
                "state": "failed",
                "message": ("A previous warm-up was interrupted (the app "
                            "restarted while it was running). Nothing was "
                            "changed — try again."),
                "seconds": 0.0,
                "started_at": started,
            }
            _write_fm_warmup_state(recovered)
            return recovered
    return data


def _probe_fm_bounded(dual_engine, timeout_s: float) -> Dict[str, Any]:
    """Run the #4 FM availability probe with a hard timeout (#122).

    The probe itself has a 30s -> 30s -> 60s retry budget and no timeout
    parameter, so it runs in a daemon thread while the caller waits at
    most ``timeout_s``. On timeout the orphaned daemon probe thread is
    abandoned (it dies with the process and never writes the mailbox —
    only the worker below does) and TimeoutError is raised so the worker
    records an honest failed state. Never hangs the caller past the
    timeout. Probe exceptions are re-raised for the worker to record.
    """
    box: Dict[str, Any] = {}

    def _target() -> None:
        try:
            box["status"] = dual_engine.check_status(force=True, check_fm=True)
        except Exception as e:  # noqa: BLE001 -- re-raised below
            box["error"] = e

    t = threading.Thread(target=_target, daemon=True, name="fm-warmup-probe")
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        raise TimeoutError(
            f"warm-up probe timed out after {timeout_s:.0f}s "
            "(the on-device model may still be initializing)")
    if "error" in box:
        raise box["error"]
    return box.get("status") or {}


def _fm_warmup_worker() -> None:
    """Background worker: run the #4 FM availability probe. Never raises.

    Uses ``dual_engine.check_status(force=True)`` — the exact probe — but
    bounded by FM_WARMUP_TIMEOUT_SECONDS (#122), so a hung probe can never
    leave the mailbox "warming" forever. The outcome is recorded honestly:
    "done" only when the probe reports the model available, otherwise
    "failed" with the probe's own message verbatim (same messaging as #4),
    or a timeout message when the probe exceeds its budget.
    """
    started = time.time()
    try:
        from core.dual_engine import dual_engine
        status = _probe_fm_bounded(dual_engine, FM_WARMUP_TIMEOUT_SECONDS)
        fm = (status or {}).get("fm", {}) or {}
        secs = time.time() - started
        if fm.get("available"):
            _write_fm_warmup_state({
                "state": "done",
                "message": fm.get("message") or "Apple Foundation Model ready (On-Device)",
                "seconds": secs,
                "started_at": started,
            })
        else:
            _write_fm_warmup_state({
                "state": "failed",
                "message": fm.get("message") or "Apple Foundation Model unavailable",
                "seconds": secs,
                "started_at": started,
            })
    except Exception as e:
        _write_fm_warmup_state({
            "state": "failed",
            "message": f"Warm-up failed: {type(e).__name__}: {e}",
            "seconds": time.time() - started,
            "started_at": started,
        })


def start_fm_warmup(*, auto: bool = False) -> Tuple[bool, str]:
    """Kick off a background on-device Apple FM warm-up probe. Never raises.

    Returns (started, reason): ``reason`` is "" when the worker started,
    otherwise a human-readable explanation of why it could not start
    (e.g. a warm-up is already running).

    ``auto`` marks a launch-time automatic kick-off (#115/#122): it is
    recorded in the mailbox so the UI can treat it as purely informational
    (no poll loop) instead of user-initiated work.
    """
    try:
        state = read_fm_warmup_state()
        if state.get("state") == "warming":
            # The button disables while busy, but a double-kick can still
            # race here — refuse instead of starting a second worker.
            return False, "A warm-up is already running — try again shortly."
        _write_fm_warmup_state({
            "state": "warming",
            "message": "",
            "seconds": 0.0,
            "started_at": time.time(),
            "auto": bool(auto),
        })
        t = threading.Thread(target=_fm_warmup_worker, daemon=True,
                             name="fm-warmup")
        t.start()
        return True, ""
    except Exception as e:
        return False, f"Could not start warm-up: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Automatic cold-start (#115)
# ---------------------------------------------------------------------------

_auto_cold_start_lock = threading.Lock()
_auto_cold_start_fired = False


def maybe_auto_cold_start() -> None:
    """Kick off the FM warm-up automatically once per process (#115).

    Cold-start init must run in a background thread without disturbing
    anything else: the UI renders immediately and stays interactive while
    the probe warms up the on-device model. This only *fires* the daemon
    thread via :func:`start_fm_warmup` — it never waits for it, never
    touches ``st.session_state`` (not thread-safe), and never raises.

    Safe to call on every render: the per-process flag guarantees at most
    one kick-off, and ``start_fm_warmup`` itself refuses a double-start
    while a warm-up is already in flight. If the kick-off fails, it stays
    silent here — the manual "Cold start" button remains available, and
    the worker itself fails loudly via the mailbox on probe failure.
    """
    global _auto_cold_start_fired
    with _auto_cold_start_lock:
        if _auto_cold_start_fired:
            return
        _auto_cold_start_fired = True
    try:
        start_fm_warmup(auto=True)
    except Exception:
        # Never break the render for a background kick-off failure.
        pass


def _reset_auto_cold_start_for_tests() -> None:
    """Reset the per-process auto cold-start flag. Tests only."""
    global _auto_cold_start_fired
    with _auto_cold_start_lock:
        _auto_cold_start_fired = False


def _do_reset(story_id: str, topic: str,
              ai_engine: Optional[str] = None) -> Tuple[bool, str]:
    """Destructive reset: discard ALL hashtags, fetched images and news
    links, then re-fetch all three rows fresh.

    - Hashtags: every stored tag is discarded; fresh AI discovery runs.
    - Fetched images: ``image_urls`` is discarded and re-extracted fresh.
      Manually uploaded images live in the separate ``uploaded_images``
      field and are NEVER touched.
    - News links: the link verifier re-runs fresh for the topic.

    The screenplay, story content and ``uploaded_images`` are never
    written. The three rows are written in ONE ``update_story_fields``
    call, so a failure partway leaves the story untouched (fail loudly).

    Returns (changed, note). ``changed`` compares the new rows against
    the old ones — identical re-fetch results report ``no_change``.

    Raises RuntimeError when no AI engine is configured (the "Enable AI
    processing" toggle is off): discovering trending hashtags without
    the AI is impossible, so this fails loudly with the same message as
    Update Hashtags instead of silently serving deterministic tags.
    Nothing is changed in that case.
    """
    story = load_story(story_id)
    if not story:
        raise RuntimeError("Reset failed: story not found.")
    if ai_engine is None:
        raise RuntimeError(_AI_DISABLED_MSG)
    meta = story["meta"]
    topic = (topic or meta.get("source_topic") or "").strip()
    if not topic:
        raise RuntimeError("Reset failed: no topic to re-fetch media for.")

    old_tags = [t for t in (meta.get("hashtags") or []) if t]
    old_images = list(meta.get("image_urls") or [])
    old_urls = [lk.get("url") for lk in (meta.get("news_links") or [])
                if isinstance(lk, dict)]

    # 1. Hashtags: discard all, fresh AI discovery.
    new_tags, ai_note = _suggest_hashtags(story, topic, ai_engine)
    new_tags = [t for t in dict.fromkeys(new_tags) if t]

    # 2. Fetched images: discard, fresh article-image extraction.
    #    A TimeoutError propagates: the whole reset fails loudly and
    #    nothing is written. Alt-text filtering and content dedupe apply
    #    to the fresh list (issue #21); a hash-fetch failure raises
    #    ImageDedupeError and likewise fails loudly.
    new_images, new_hashes, new_phashes, _img_stats = _merge_story_images(
        [], [], [], _fetch_images_for_story(story, topic) or [],
        cap=_MAX_FETCHED_IMAGES)

    # 3. News links: re-run the link verifier fresh for the topic.
    #    Best-effort by contract: [] on failure means an empty row, with
    #    the honest cause in the note. Issue #82: targets
    #    NEWS_LINKS_TARGET (5) distinct links via progressively looser
    #    queries.
    try:
        new_links = _fetch_news_link_candidates(
            topic, count=NEWS_LINKS_TARGET)
        news_err = ""
    except RuntimeError as e:
        new_links = []
        news_err = str(e)
    new_urls = [lk["url"] for lk in new_links]

    update_story_fields(
        story_id,
        hashtags=new_tags,
        image_urls=new_images,
        image_hashes=new_hashes,
        image_phashes=new_phashes,
        news_links=new_links,
    )

    changed = (new_tags != old_tags or new_images != old_images
               or new_urls != old_urls)
    parts = [f"Reset re-fetched {len(new_tags)} hashtag(s), "
             f"{len(new_images)} image(s) and {len(new_links)} news link(s)."]
    if not new_tags:
        parts.append("No hashtags found — row cleared.")
    if not new_images:
        parts.append("No images found — fetched row cleared (uploads kept).")
    if _img_stats["trimmed"]:
        parts.append(f"Capped fetched images at {_MAX_FETCHED_IMAGES} "
                     f"({_img_stats['trimmed']} extra not kept; "
                     f"uploads are never capped).")
    if not new_links:
        parts.append(f"News search failed ({news_err}) — row cleared."
                     if news_err else "No news links found — row cleared.")
    if not changed:
        parts.append("Everything already fresh — nothing changed.")
    if ai_note:
        parts.append(ai_note)
    return changed, " ".join(parts)

def _do_enrich(story_id: str, topic: str) -> Tuple[bool, str]:
    """Post-save enrichment body: news links + images + hashtags.

    Deterministic only — save-time enrichment never calls the AI, so a
    story always saves cleanly with AI processing off. Issue #82: the
    news fetch targets ``NEWS_LINKS_TARGET`` (5) distinct links,
    trying progressively looser queries when the topic under-fetches.
    Returns (changed, note); raises loudly on failure.
    """
    try:
        news_links = _fetch_news_link_candidates(
            topic, count=NEWS_LINKS_TARGET)
        news_err = ""
    except RuntimeError as e:
        # Save-time enrichment keeps the image-timeout precedent: a news
        # fetch failure is an honest note, not a lost enrichment — the
        # story is already saved and hashtags/images still land.
        news_links = []
        news_err = str(e)
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
    # reel was built from — the stored links from save time. Define the
    # name before use (issue #62: it was referenced but never defined).
    verified_links = [lk for lk in (meta.get("news_links") or [])
                      if isinstance(lk, dict) and lk.get("url")]
    # Never replace them with topic-search results.
    # Images merge: the story may already carry the Stage-1 curated gallery —
    # keep those and add what enrichment found, deduplicated by normalized
    # URL and content hash (issue #21). A hash-fetch failure raises
    # ImageDedupeError and fails the enrichment loudly.
    merged_imgs, merged_hashes, merged_phashes, _img_stats = _merge_story_images(
        meta.get("image_urls"), meta.get("image_hashes"),
        meta.get("image_phashes"), image_urls, cap=_MAX_FETCHED_IMAGES)
    imgs_added = _img_stats["added"]
    links_added = 0 if verified_links else len(news_links)
    update_story_fields(
        story_id,
        news_links=verified_links or news_links,
        image_urls=merged_imgs,
        image_hashes=merged_hashes,
        image_phashes=merged_phashes,
        hashtags=merged_tags,
    )
    changed = bool(tags_added or imgs_added or links_added)
    bits = []
    if news_err:
        bits.append(f"News search failed ({news_err}); no links added.")
    elif links_added:
        bit = f"Found {links_added} news link(s)."
        if links_added < NEWS_LINKS_TARGET:
            bit += f" Only {links_added} related article(s) found."
        bits.append(bit)
    else:
        bits.append("Kept verified news links." if verified_links
                    else "No related news articles found.")
    bits.append(img_note or (f"Added {imgs_added} image(s)."
                             if imgs_added else "No new images found."))
    if _img_stats["trimmed"]:
        bits.append(f"Capped fetched images at {_MAX_FETCHED_IMAGES} "
                    f"({_img_stats['trimmed']} extra not kept; "
                    f"uploads are never capped).")
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
            # Nothing to enrich: record the honest terminal state (and a
            # pending outcome so the UI can toast it) without touching any
            # other kind's state.
            _finish_refresh(story_id, "enrich", "no_change",
                            "No topic — enrichment skipped.")
            return False, "No topic — enrichment skipped."
        if not _set_refresh_busy(story_id, "enrich"):
            return False, "Story not found."
        t = threading.Thread(
            target=_enrich_worker, args=(story_id, topic.strip(), _do_enrich),
            daemon=True, name=f"enrich-{story_id}")
        _ENRICH_THREADS[story_id] = t
        t.start()
        return True, ""
    except Exception as e:
        reason = f"Could not start enrichment: {type(e).__name__}: {e}"
        # Fail loudly AND leave no stuck marker: the story was flagged
        # busy ("pending") by save_story / _set_refresh_busy above before
        # the thread failed to start — without a terminal state its
        # buttons (incl. every script-version action, #193) would stay
        # disabled until the next app restart.
        try:
            _finish_refresh(story_id, "enrich", "failed", reason)
        except Exception:
            traceback.print_exc()
        return False, reason
