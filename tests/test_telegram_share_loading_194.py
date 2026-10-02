"""Tests for issue #194: the Telegram share button owns its loading state.

The "Share via Telegram" button must show Streamlit's native spinner and
stay disabled for the whole blocking send (HIG §3 — the initiating control
owns its progress, same pattern as _render_kind_button). No detached
st.spinner below the button, no second click mid-send. Send errors surface
loudly via st.error.

Two layers:
  A. Pure state-transition helpers (_tg_share_begin/_tg_share_end/...)
     run on a plain dict — no Streamlit needed.
  B. The _render_share_popover wiring, driven through the real
     click -> busy -> outcome rerun sequence with a fake `st` module.
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import story_library as lib  # noqa: E402

# Same preamble as test_telegram_bot_share.py: load tools/telegram_share.py
# directly by path (no httpx/feedparser/bs4 in the test env), and stub
# streamlit before importing library_ui.
import importlib.util as _ilu  # noqa: E402

_repo_root = Path(__file__).resolve().parent.parent
_tg_spec = _ilu.spec_from_file_location(
    "tools.telegram_share", _repo_root / "tools" / "telegram_share.py")
_tg_mod = _ilu.module_from_spec(_tg_spec)
_tools_pkg = types.ModuleType("tools")
_tools_pkg.__path__ = [str(_repo_root / "tools")]
_tools_pkg.telegram_share = _tg_mod
sys.modules["tools"] = _tools_pkg
sys.modules["tools.telegram_share"] = _tg_mod
_tg_spec.loader.exec_module(_tg_mod)

for _name in ("streamlit", "streamlit.components", "streamlit.components.v1"):
    sys.modules.setdefault(_name, types.ModuleType(_name))

import library_ui  # noqa: E402

STORY = "story-194"
TG_KEY = f"lib_tg_{STORY}"


# ===========================================================================
# A. Pure state-transition helpers (plain dict store, no Streamlit)
# ===========================================================================

def test_begin_on_idle_marks_busy_and_returns_true():
    store = {}
    assert library_ui._tg_share_begin(store, STORY) is True
    assert library_ui._tg_share_is_busy(store, STORY) is True


def test_begin_while_busy_ignores_stale_double_click():
    store = {}
    assert library_ui._tg_share_begin(store, STORY) is True
    # A second click arriving while the send is in flight must NOT re-arm.
    assert library_ui._tg_share_begin(store, STORY) is False
    assert library_ui._tg_share_is_busy(store, STORY) is True


def test_end_clears_busy_and_stashes_success_outcome():
    store = {}
    library_ui._tg_share_begin(store, STORY)
    library_ui._tg_share_end(store, STORY, ok=True, message="sent ok")
    assert library_ui._tg_share_is_busy(store, STORY) is False
    assert library_ui._tg_share_take_outcome(store, STORY) == (True, "sent ok")


def test_end_clears_busy_and_stashes_error_outcome_verbatim():
    store = {}
    library_ui._tg_share_begin(store, STORY)
    msg = "Couldn't share via Telegram: 401 Unauthorized"
    library_ui._tg_share_end(store, STORY, ok=False, message=msg)
    assert library_ui._tg_share_is_busy(store, STORY) is False
    # Fail loudly: the message is preserved verbatim, not truncated.
    assert library_ui._tg_share_take_outcome(store, STORY) == (False, msg)


def test_take_outcome_is_one_shot():
    store = {}
    library_ui._tg_share_begin(store, STORY)
    library_ui._tg_share_end(store, STORY, ok=True, message="sent ok")
    assert library_ui._tg_share_take_outcome(store, STORY) == (True, "sent ok")
    assert library_ui._tg_share_take_outcome(store, STORY) is None


def test_take_outcome_on_idle_is_none():
    assert library_ui._tg_share_take_outcome({}, STORY) is None
    assert library_ui._tg_share_is_busy({}, STORY) is False


def test_state_is_per_story():
    store = {}
    library_ui._tg_share_begin(store, "story-a")
    assert library_ui._tg_share_is_busy(store, "story-a") is True
    assert library_ui._tg_share_is_busy(store, "story-b") is False
    assert library_ui._tg_share_take_outcome(store, "story-b") is None


# ===========================================================================
# B. Wiring: _render_share_popover through click -> busy -> outcome runs
# ===========================================================================

class _Rerun(Exception):
    """Stands in for streamlit's RerunException."""


class _PopoverCtx:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class FakeSt:
    """Minimal streamlit stand-in.

    `click_keys`: button keys returning True exactly once (a scripted
    single click). `sticky_click_keys`: keys returning True on every run
    until removed (models a second click landing while the first send is
    still in flight). Every button() call is recorded with its icon and
    disabled flag so tests can assert the per-run button state.
    """

    def __init__(self):
        self.session_state = {}
        self.click_keys = set()
        self.sticky_click_keys = set()
        self.button_calls = []   # list of dicts: label/key/icon/disabled
        self.errors = []
        self.toasts = []
        self.spinner_calls = []

    # -- widgets ---------------------------------------------------------
    def button(self, label, *, key=None, icon=None, help=None,
               disabled=False, use_container_width=False):
        self.button_calls.append(
            {"label": label, "key": key, "icon": icon, "disabled": disabled})
        if key in self.sticky_click_keys:
            return True
        if key in self.click_keys:
            self.click_keys.discard(key)
            return True
        return False

    def popover(self, *a, **k):
        return _PopoverCtx()

    def divider(self):
        pass

    def caption(self, *a, **k):
        pass

    def rerun(self):
        raise _Rerun()

    # -- feedback ----------------------------------------------------------
    def error(self, msg):
        self.errors.append(msg)

    def toast(self, msg, icon=None):
        self.toasts.append((msg, icon))

    def spinner(self, *a, **k):
        # #194: the detached spinner is gone — the button owns the
        # loading state. Any call here fails the test loudly.
        self.spinner_calls.append((a, k))
        raise AssertionError("st.spinner must not be used for the "
                             "Telegram share (#194)")


@pytest.fixture
def fx(monkeypatch):
    """Fake st wired in as library_ui.st, with WhatsApp skipped and a
    fake token configured so the Telegram branch renders."""
    fake = FakeSt()
    monkeypatch.setattr(library_ui, "st", fake)
    monkeypatch.setattr(library_ui, "_copy_button", lambda *a, **k: None)
    monkeypatch.setattr(library_ui, "_whatsapp_app_installed", lambda: False)
    monkeypatch.setattr(lib, "load_prefs",
                        lambda: {"telegram_bot_token": "fake-token"})
    monkeypatch.setattr(_tg_mod, "resolve_token", lambda *a, **k: "fake-token")
    return fake


def _run_popover(fx, monkeypatch, send_impl, clicks=(), sticky_clicks=()):
    """Drive _render_share_popover through Streamlit-style reruns.

    `send_impl(story_id, meta)` replaces _share_via_telegram_bot.
    Returns (runs, send_calls); `runs` is e.g. ["rerun", "rerun",
    "settled"]. Per-run button/error/toast state is left on `fx` from
    the final (settled) run.
    """
    send_calls = []

    def _send(story_id, meta):
        send_calls.append(story_id)
        return send_impl(story_id, meta)

    monkeypatch.setattr(library_ui, "_share_via_telegram_bot", _send)
    fx.click_keys = set(clicks)
    fx.sticky_click_keys = set(sticky_clicks)
    runs = []
    for _ in range(6):  # click run, busy run, outcome run — then idle
        fx.button_calls = []
        fx.errors = []
        fx.toasts = []
        try:
            library_ui._render_share_popover(STORY, "share text", {})
        except _Rerun:
            runs.append("rerun")
            continue
        runs.append("settled")
        break
    else:
        pytest.fail("popover kept rerunning — busy flag never cleared")
    return runs, send_calls


def _tg_button_calls(fx):
    return [c for c in fx.button_calls if c["key"] == TG_KEY]


def test_click_shows_spinner_disabled_button_then_success_toast(fx,
                                                                monkeypatch):
    def fake_send(story_id, meta):
        # The send runs while the button already renders spinner+disabled.
        calls = _tg_button_calls(fx)
        assert calls, "Telegram button must render during the busy run"
        assert calls[-1]["icon"] == "spinner"
        assert calls[-1]["disabled"] is True
        return "Sent to Telegram: video + caption."

    runs, send_calls = _run_popover(fx, monkeypatch, fake_send,
                                    clicks=(TG_KEY,))

    assert send_calls == [STORY]           # exactly one send — no double-send
    assert runs == ["rerun", "rerun", "settled"]
    assert fx.spinner_calls == []          # no detached spinner anywhere
    # Outcome run: button back to idle, success toasted once.
    idle = _tg_button_calls(fx)[-1]
    assert idle["icon"] == ":material/send:"
    assert idle["disabled"] is False
    assert fx.toasts == [("Sent to Telegram: video + caption.", "✅")]
    assert fx.errors == []


def test_stale_double_click_while_busy_sends_only_once(fx, monkeypatch):
    def fake_send(story_id, meta):
        # Once the disabled+spinner button has rendered, the frontend
        # can't produce more clicks — drop the sticky click now.
        fx.sticky_click_keys.discard(TG_KEY)
        return "Sent to Telegram: video + caption."

    # The user double-clicks: the second click lands while the first send
    # is still in flight (busy run). begin() must refuse it — one send.
    runs, send_calls = _run_popover(fx, monkeypatch, fake_send,
                                    sticky_clicks=(TG_KEY,))
    assert send_calls == [STORY]
    assert runs == ["rerun", "rerun", "settled"]
    assert fx.toasts == [("Sent to Telegram: video + caption.", "✅")]


def test_send_error_surfaces_loudly_and_button_recovers(fx, monkeypatch):
    def fake_send(story_id, meta):
        raise RuntimeError("401 Unauthorized")

    runs, send_calls = _run_popover(fx, monkeypatch, fake_send,
                                    clicks=(TG_KEY,))

    assert send_calls == [STORY]
    assert runs == ["rerun", "rerun", "settled"]
    # Fail loudly: the exact error is shown and nothing is swallowed.
    assert fx.errors == ["Couldn't share via Telegram: 401 Unauthorized"]
    assert fx.toasts == []
    # The button is usable again after the failure — never stuck disabled.
    idle = _tg_button_calls(fx)[-1]
    assert idle["disabled"] is False
    assert idle["icon"] == ":material/send:"
    assert library_ui._tg_share_is_busy(fx.session_state, STORY) is False
