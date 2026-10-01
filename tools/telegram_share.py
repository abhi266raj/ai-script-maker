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

One-time setup (guided in the Share popover):
  1. message @BotFather on Telegram -> /newbot -> copy the token;
  2. open the new bot and tap Start (it needs one message from you);
  3. paste the token in the app — the chat id is discovered automatically
     from the bot's updates and remembered in prefs.

All failures raise TelegramShareError with an actionable message — never
a silent no-op. httpx is imported lazily so this module stays importable
where the dependency is missing; tests inject a fake transport.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Callable, Dict, Optional

API_BASE = "https://api.telegram.org"
MAX_CAPTION_CHARS = 1024  # Telegram media-caption limit
MAX_TEXT_CHARS = 4096  # Telegram text-message limit

# Transport: callable (url, *, data, files, timeout) -> response exposing
# .json() and .status_code. Defaults to httpx (lazy import).
Transport = Callable[..., Any]


class TelegramShareError(RuntimeError):
    """Anything that stops a Telegram share — always actionable, never silent."""


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
