"""Share stories to Telegram via the Bot API.

#159 follow-up: Telegram's ``tg://`` deep link cannot carry a local video
file (a URL is a text string — no attachment parameter exists), so
video + text + news sharing goes through a user-owned Telegram bot
instead. The Streamlit server runs on the user's Mac, so it can read
the story's local video file and POST it to api.telegram.org directly.

Two messages per share (user-approved):
  1. the story video with a caption (title + hashtags) — or the caption
     as a plain text message when the story has no video attached;
  2. the news links, one "site: url" line each.

#179: after the DM share, the same two messages are broadcast to every
group/supergroup the bot is a member of (discovered via getUpdates,
remembered in ~/.cache/telegram_bot_groups.json). The user's own chat id
is skipped (it already got the messages). Every group is attempted; the
summary names any failures loudly — never a silent skip. Prerequisite: the
bot must be added to each group (Telegram only lets bots post where they
are members).

One-time setup (guided in the Share popover):
  1. message @BotFather on Telegram -> /newbot -> copy the token;
  2. open the new bot and tap Start (it needs one message from you);
  3. token source, by precedence (see resolve_token):
     a. DEFAULT: save it as ~/Documents/telegrambot/bot_token.txt —
        the app picks it up automatically;
     b. custom: paste it in the Share popover (stored in app prefs);
  the chat id is discovered automatically from the bot's updates and
  remembered in prefs.

All failures raise TelegramShareError with an actionable message — never
a silent no-op. httpx is imported lazily so this module stays importable
where the dependency is missing; tests inject a fake transport.
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any, Callable, Dict, Optional

API_BASE = "https://api.telegram.org"
MAX_CAPTION_CHARS = 1024  # Telegram media-caption limit
MAX_TEXT_CHARS = 4096  # Telegram text-message limit

# Default bot-token location on the Mac (the Streamlit server runs there,
# so ~ is the user's home). The file holds the raw token, nothing else.
DEFAULT_TOKEN_PATH = Path.home() / "Documents" / "telegrambot" / "bot_token.txt"

# Transport: callable (url, *, data, files, timeout) -> response exposing
# .json() and .status_code. Defaults to httpx (lazy import).
Transport = Callable[..., Any]


class TelegramShareError(RuntimeError):
    """Anything that stops a Telegram share — always actionable, never silent."""


def resolve_token(prefs_token: Optional[str] = None,
                  token_path: Optional[Any] = None) -> str:
    """Return the effective bot token, by precedence.

    1. DEFAULT: ``~/Documents/telegrambot/bot_token.txt`` — read and
       stripped. A missing, unreadable, or blank file is skipped silently
       (it simply isn't the configured source).
    2. The custom token stored in app prefs (set via the Share popover).
    3. Otherwise raise TelegramShareError with setup guidance — never None,
       never a silent no-op.

    ``token_path`` overrides the default file location (for tests).
    """
    path = Path(token_path) if token_path is not None else DEFAULT_TOKEN_PATH
    try:
        file_token = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        file_token = ""
    if file_token:
        return file_token
    custom = (prefs_token or "").strip()
    if custom:
        return custom
    raise TelegramShareError(
        "No Telegram bot token found. Save it as "
        "~/Documents/telegrambot/bot_token.txt, or create a bot with "
        "@BotFather and paste the token in the app's Share popover, then "
        "try again.")


def _httpx_post(url: str, *, data: Optional[dict] = None,
                files: Optional[dict] = None,
                timeout: float = 30) -> Any:
    import httpx
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, data=data, files=files)


def _api(transport: Optional[Transport], token: str, method: str, *,
         data: Optional[dict] = None, files: Optional[dict] = None,
         timeout: float = 30) -> Any:
    """POST one Bot API method; return its ``result`` or raise loudly."""
    token = (token or "").strip()
    if not token:
        raise TelegramShareError(
            "No Telegram bot token configured. Create a bot with @BotFather, "
            "paste the token in the Share popover, then try again.")
    post = transport or _httpx_post
    url = f"{API_BASE}/bot{token}/{method}"
    try:
        resp = post(url, data=data, files=files, timeout=timeout)
    except TelegramShareError:
        raise
    except Exception as e:  # transport-level failure: DNS, TLS, refused…
        raise TelegramShareError(
            f"Couldn't reach the Telegram API ({method}): "
            f"{type(e).__name__}: {e}. Check your internet connection.")
    try:
        payload = resp.json()
    except Exception:
        raise TelegramShareError(
            f"Telegram API returned a non-JSON response for {method} "
            f"(HTTP {getattr(resp, 'status_code', '?')}).")
    if not isinstance(payload, dict) or not payload.get("ok"):
        desc = (payload.get("description")
                if isinstance(payload, dict) else None) or "unknown error"
        raise TelegramShareError(f"Telegram API rejected {method}: {desc}")
    return payload.get("result")


def discover_chat_id(token: str, transport: Optional[Transport] = None) -> int:
    """Return the chat id to post to: the newest chat the bot has heard from.

    In practice this is the user's own chat with the bot (what they see as
    their conversation with it). Raises TelegramShareError — never None —
    when the bot has no updates yet, telling the user exactly what to do.
    """
    result = _api(transport, token, "getUpdates",
                  data={"timeout": 0, "limit": 25}, timeout=25)
    updates = result if isinstance(result, list) else []
    for upd in reversed(updates):
        if not isinstance(upd, dict):
            continue
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") if isinstance(msg, dict) else None
        cid = chat.get("id") if isinstance(chat, dict) else None
        if cid is None:
            continue
        try:
            return int(cid)
        except (TypeError, ValueError):
            continue
    raise TelegramShareError(
        "The bot hasn't heard from you yet — open it in Telegram and tap "
        "Start (or send it any message), then share again.")


# Where the discovered group ids are remembered (JSON list of ints).
# The Streamlit server runs on the user's Mac, so ~ is the user's home.
DEFAULT_GROUPS_PATH = Path.home() / ".cache" / "telegram_bot_groups.json"

_GROUP_CHAT_TYPES = ("group", "supergroup")
_BOT_GONE_STATUSES = ("left", "kicked")


def _load_known_group_ids(groups_path: Path) -> set:
    """Read the persisted group-id set; missing/corrupt starts empty."""
    try:
        raw = groups_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    try:
        data = json.loads(raw)
    except ValueError:
        return set()
    if not isinstance(data, list):
        return set()
    ids = set()
    for value in data:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def discover_group_ids(token: str, transport: Optional[Transport] = None,
                       groups_path: Optional[Any] = None) -> list:
    """Return the ids of every group/supergroup the bot is currently in.

    Harvests ``getUpdates``: any ``message`` whose chat type is ``group``
    or ``supergroup`` counts, and ``my_chat_member`` updates are honored —
    a group the bot was removed from (``left``/``kicked``) drops out.
    Updates are processed oldest-first so a removal always wins over an
    earlier sighting.

    The id set is persisted as JSON (default
    ``~/.cache/telegram_bot_groups.json``) so it survives restarts, and is
    refreshed on every call. A missing or corrupt cache starts empty; a
    cache that can't be written is ignored (the fresh set is still
    returned) — persistence is best-effort, never a hard failure.

    ``groups_path`` overrides the cache location (for tests).
    """
    path = (Path(groups_path) if groups_path is not None
            else DEFAULT_GROUPS_PATH)
    known = _load_known_group_ids(path)
    result = _api(transport, token, "getUpdates",
                  data={"timeout": 0, "limit": 100}, timeout=30)
    updates = result if isinstance(result, list) else []
    for upd in updates:
        if not isinstance(upd, dict):
            continue
        msg = upd.get("message") or {}
        if isinstance(msg, dict):
            chat = msg.get("chat") or {}
            if (isinstance(chat, dict)
                    and chat.get("type") in _GROUP_CHAT_TYPES):
                try:
                    known.add(int(chat.get("id")))
                except (TypeError, ValueError):
                    pass
        mcm = upd.get("my_chat_member") or {}
        if isinstance(mcm, dict):
            chat = mcm.get("chat") or {}
            if (isinstance(chat, dict)
                    and chat.get("type") in _GROUP_CHAT_TYPES):
                try:
                    gid = int(chat.get("id"))
                except (TypeError, ValueError):
                    continue
                status = ((mcm.get("new_chat_member") or {}).get("status")
                          or "")
                if status in _BOT_GONE_STATUSES:
                    known.discard(gid)
                else:
                    known.add(gid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(known)), encoding="utf-8")
    except OSError:
        pass  # cache is best-effort; the fresh set is still returned
    return sorted(known)


def broadcast_story(token: str, group_ids, *, video_path=None,
                    caption: str = "", links_text: str = "",
                    transport: Optional[Transport] = None) -> str:
    """Send the same two share messages to each group id.

    Message 1 is the video with its caption (or the caption as plain text
    when there is no video); message 2 is the news-links text (skipped when
    empty) — the same shape as the DM share.

    Every group is attempted even if some fail; ids are deduped. Returns a
    summary naming the outcome — successes counted, failures listed as
    ``<id>: <reason>`` — so the caller can surface it loudly. Never
    silently skips a failing group. An empty id list is not an error.
    """
    targets = []
    for value in group_ids or []:
        try:
            gid = int(value)
        except (TypeError, ValueError):
            raise TelegramShareError(
                f"Refusing to broadcast: group id {value!r} is not a number.")
        if gid not in targets:
            targets.append(gid)
    if not targets:
        return ("No Telegram groups to broadcast to — add the bot to a "
                "group and share again.")
    failures = []
    delivered = 0
    for gid in targets:
        try:
            if video_path:
                send_video(token, gid, video_path, caption,
                           transport=transport)
            else:
                send_text(token, gid, caption, transport=transport)
            if links_text:
                send_text(token, gid, links_text, transport=transport)
        except TelegramShareError as e:
            failures.append(f"{gid}: {e}")
        except Exception as e:  # never let one group kill the rest silently
            failures.append(f"{gid}: {type(e).__name__}: {e}")
        else:
            delivered += 1
    noun = "group" if delivered == 1 else "groups"
    if failures:
        return (f"Broadcast partially failed — sent to {delivered} {noun}; "
                f"failed in: " + "; ".join(failures))
    return f"Broadcast to {delivered} Telegram {noun}."


def send_video(token: str, chat_id: Any, video_path: Any, caption: str,
               transport: Optional[Transport] = None,
               timeout: float = 120) -> Dict[str, Any]:
    """POST sendVideo: the local video file with a caption. Returns the API result."""
    p = Path(video_path)
    if not p.is_file():
        raise TelegramShareError(f"Video file not found: {p}")
    caption = caption or ""
    if len(caption) > MAX_CAPTION_CHARS:
        raise TelegramShareError(
            f"Video caption is {len(caption)} chars — "
            f"Telegram allows {MAX_CAPTION_CHARS}.")
    ctype = mimetypes.guess_type(p.name)[0] or "video/mp4"
    with p.open("rb") as fh:
        files = {"video": (p.name, fh, ctype)}
        data = {"chat_id": str(chat_id), "caption": caption,
                "supports_streaming": "true"}
        return _api(transport, token, "sendVideo", data=data, files=files,
                    timeout=timeout)


def send_text(token: str, chat_id: Any, text: str,
              transport: Optional[Transport] = None,
              timeout: float = 30) -> Dict[str, Any]:
    """POST sendMessage: a plain text message. Returns the API result."""
    if not (text or "").strip():
        raise TelegramShareError("Refusing to send an empty Telegram message.")
    if len(text) > MAX_TEXT_CHARS:
        raise TelegramShareError(
            f"Message is {len(text)} chars — Telegram allows {MAX_TEXT_CHARS}.")
    return _api(transport, token, "sendMessage",
                data={"chat_id": str(chat_id), "text": text}, timeout=timeout)
