"""Tests for #215 — Telegram setup moved OUT of the share popover.

HIG §6: popovers are transient and single — don't layer a form over one.
The old ``st.expander("Set up Telegram sharing")`` (bot-token text_input +
Save) lived INSIDE the share popover, so an accidental outside-click
dismissed it and the typed token was lost. The form now lives in
``_render_telegram_setup_section`` (below the story toolbar, outside any
popover); the popover only points at it when no token is configured.

library_ui is loaded under a UNIQUE module name with a recording fake
``streamlit`` so these UI-composition assertions are hermetic and do not
depend on the machine's real ~/Documents/telegrambot/bot_token.txt.
"""
import importlib.util as _ilu
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import story_library as lib  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent


class _RerunRaised(Exception):
    """Raised by the fake st.rerun() — mirrors Streamlit stopping the run."""


class _Ctx:
    """Recording context manager standing in for popover/expander/spinner."""

    def __init__(self, fake, kind, label="", kwargs=None):
        self._fake = fake
        self.kind = kind
        self.label = label
        self.kwargs = dict(kwargs or {})
        self.inner = []  # calls recorded while this context was open

    def __enter__(self):
        self._fake._record(self.kind, self.label, self.kwargs)
        self._fake._stack.append(self)
        return self

    def __exit__(self, *exc):
        self._fake._stack.pop()
        return False


class _FakeSt:
    """Minimal recording stand-in for the streamlit module."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.calls = []        # (kind, label, kwargs) for every st call
        self._stack = []       # open _Ctx frames
        self.session_state = {}
        self.text_values = {}  # text_input key -> typed value
        self.clicks = {}       # button key -> clicked?
        self.reruns = 0
        self.errors = []

    # -- internal ------------------------------------------------------
    def _record(self, kind, label="", kwargs=None):
        entry = (kind, label, dict(kwargs or {}))
        self.calls.append(entry)
        for ctx in self._stack:
            ctx.inner.append(entry)

    # -- containers ----------------------------------------------------
    def popover(self, label="", **kw):
        return _Ctx(self, "popover", label, kw)

    def expander(self, label="", **kw):
        return _Ctx(self, "expander", label, kw)

    def spinner(self, text="", **kw):
        return _Ctx(self, "spinner", text, kw)

    # -- widgets -------------------------------------------------------
    def text_input(self, label="", value="", type=None, key=None, **kw):
        self._record("text_input", label, {"key": key, "type": type})
        return self.text_values.get(key, "")

    def button(self, label="", key=None, **kw):
        self._record("button", label, {"key": key})
        return bool(self.clicks.get(key, False))

    # -- display -------------------------------------------------------
    def markdown(self, body="", **kw):
        self._record("markdown", body, kw)

    def caption(self, body="", **kw):
        self._record("caption", body, kw)

    def error(self, body="", **kw):
        self._record("error", body, kw)
        self.errors.append(body)

    def warning(self, body="", **kw):
        self._record("warning", body, kw)

    def info(self, body="", **kw):
        self._record("info", body, kw)

    def success(self, body="", **kw):
        self._record("success", body, kw)

    def toast(self, msg="", **kw):
        self._record("toast", msg, kw)

    def divider(self, **kw):
        self._record("divider", "", kw)

    def rerun(self, **kw):
        self.reruns += 1
        self._record("rerun", "", kw)
        raise _RerunRaised()


def _install_fake_streamlit():
    fake = _FakeSt()
    st_mod = types.ModuleType("streamlit")
    for name in dir(fake):
        if not name.startswith("_"):
            setattr(st_mod, name, getattr(fake, name))
    comp_pkg = types.ModuleType("streamlit.components")
    comp_v1 = types.ModuleType("streamlit.components.v1")

    def _html(*a, **kw):
        fake._record("components.html", "", kw)

    comp_v1.html = _html
    comp_pkg.v1 = comp_v1
    st_mod.components = comp_pkg
    # Deliberate overwrite (not setdefault): these tests own the fake.
    sys.modules["streamlit"] = st_mod
    sys.modules["streamlit.components"] = comp_pkg
    sys.modules["streamlit.components.v1"] = comp_v1
    return fake, st_mod


_fake, _st_mod = _install_fake_streamlit()
_spec = _ilu.spec_from_file_location(
    "library_ui_215", _REPO / "library_ui.py")
lui = _ilu.module_from_spec(_spec)
sys.modules["library_ui_215"] = lui
_spec.loader.exec_module(lui)


@pytest.fixture(autouse=True)
def _fresh_fake():
    _fake.reset()
    yield
    _fake.reset()


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


def _no_token(monkeypatch):
    monkeypatch.setattr(lui, "_telegram_bot_token", lambda: "")


def _with_token(monkeypatch):
    monkeypatch.setattr(lui, "_telegram_bot_token", lambda: "TOK123")


def _expanders_in_popover(sid, monkeypatch, share_text="t"):
    """Render the share popover; return (popover_ctx, all_calls)."""
    _no_token(monkeypatch)
    monkeypatch.setattr(lui, "_whatsapp_app_installed", lambda: False)
    ctxs = []
    orig_popover = _st_mod.popover

    def _spy_popover(label="", **kw):
        ctx = orig_popover(label, **kw)
        ctxs.append(ctx)
        return ctx

    monkeypatch.setattr(_st_mod, "popover", _spy_popover)
    lui._render_share_popover(sid, share_text, {})
    assert ctxs, "expected the share popover to render"
    return ctxs[0], list(_fake.calls)


# ---------------------------------------------------------------------------
# #215 core: no form inside the popover
# ---------------------------------------------------------------------------

def test_popover_has_no_setup_expander_when_token_missing(monkeypatch):
    popover, _ = _expanders_in_popover("s1", monkeypatch)
    kinds = [k for k, _l, _kw in popover.inner]
    assert "expander" not in kinds, (
        "the setup form must not live inside the transient share popover")
    assert not [c for c in popover.inner
                if c[0] == "text_input" and c[2].get("key", "").startswith("lib_tg_tok_")], (
        "no bot-token field may render inside the popover")


def test_popover_points_at_setup_section_when_token_missing(monkeypatch):
    popover, _ = _expanders_in_popover("s1", monkeypatch)
    captions = [label for k, label, _kw in popover.inner if k == "caption"]
    assert any("Set up Telegram sharing" in c for c in captions), (
        "popover must guide the user to the out-of-popover setup section")


def test_popover_shows_share_button_when_token_configured(monkeypatch):
    _with_token(monkeypatch)
    monkeypatch.setattr(lui, "_whatsapp_app_installed", lambda: False)
    lui._render_share_popover("s1", "share text", {})
    buttons = [(label, kw.get("key")) for k, label, kw in _fake.calls
               if k == "button"]
    assert any(key == "lib_tg_s1" for _label, key in buttons), (
        "Share via Telegram button must still render from the popover")
    assert "expander" not in [k for k, _l, _kw in _fake.calls]


# ---------------------------------------------------------------------------
# The setup section itself (outside any popover)
# ---------------------------------------------------------------------------

def test_setup_section_renders_expander_with_token_field(monkeypatch):
    _no_token(monkeypatch)
    lui._render_telegram_setup_section("s7")
    expanders = [c for c in _fake.calls if c[0] == "expander"]
    assert len(expanders) == 1
    assert expanders[0][1] == "Set up Telegram sharing"
    inputs = [(label, kw.get("key")) for k, label, kw in _fake.calls
              if k == "text_input"]
    assert ("Bot token", "lib_tg_tok_s7") in inputs
    buttons = [kw.get("key") for k, _l, kw in _fake.calls if k == "button"]
    assert "lib_tg_tok_save_s7" in buttons


def test_setup_section_hidden_when_token_configured(monkeypatch):
    _with_token(monkeypatch)
    lui._render_telegram_setup_section("s7")
    assert "expander" not in [k for k, _l, _kw in _fake.calls]
    assert "text_input" not in [k for k, _l, _kw in _fake.calls]


def test_setup_section_not_nested_in_popover(monkeypatch):
    # The expander's context must never be entered inside a popover frame.
    _no_token(monkeypatch)
    lui._render_telegram_setup_section("s7")
    assert "popover" not in [k for k, _l, _kw in _fake.calls]


# ---------------------------------------------------------------------------
# Save logic preserved verbatim (fail-loudly)
# ---------------------------------------------------------------------------

def test_save_token_persists_and_verifies(libdir, monkeypatch):
    _no_token(monkeypatch)
    _fake.text_values["lib_tg_tok_s7"] = "  tok-abc-123  "
    _fake.clicks["lib_tg_tok_save_s7"] = True
    with pytest.raises(_RerunRaised):
        lui._render_telegram_setup_section("s7")
    assert _fake.errors == []
    assert lib.load_prefs().get("telegram_bot_token") == "tok-abc-123"
    assert _fake.reruns == 1


def test_save_empty_token_errors_loudly(libdir, monkeypatch):
    _no_token(monkeypatch)
    _fake.text_values["lib_tg_tok_s7"] = "   "
    _fake.clicks["lib_tg_tok_save_s7"] = True
    lui._render_telegram_setup_section("s7")  # no rerun expected
    assert _fake.reruns == 0
    assert any("Paste the bot token from @BotFather first." in e
               for e in _fake.errors)
    assert "telegram_bot_token" not in lib.load_prefs()


def test_save_unwritable_prefs_errors_loudly(libdir, monkeypatch):
    # save_prefs silently failing => read-back mismatch => loud error.
    _no_token(monkeypatch)
    monkeypatch.setattr(lib, "save_prefs", lambda updates: None)
    _fake.text_values["lib_tg_tok_s7"] = "tok-xyz"
    _fake.clicks["lib_tg_tok_save_s7"] = True
    lui._render_telegram_setup_section("s7")
    assert _fake.reruns == 0
    assert any("isn't writable" in e for e in _fake.errors)


# ---------------------------------------------------------------------------
# _telegram_bot_token helper
# ---------------------------------------------------------------------------

def _tg_module():
    """Resolve tools.telegram_share exactly the way _telegram_bot_token does
    (fresh ``from tools import telegram_share`` at call time), so the
    monkeypatch lands on the right module object regardless of which test
    module imported first."""
    import importlib
    return importlib.import_module("tools.telegram_share")


def test_telegram_bot_token_helper_returns_resolved_token(monkeypatch):
    tg = _tg_module()
    monkeypatch.setattr(tg, "resolve_token", lambda prefs_token: "FILETOK")
    assert lui._telegram_bot_token() == "FILETOK"


def test_telegram_bot_token_helper_empty_when_unconfigured(monkeypatch):
    tg = _tg_module()

    def _raise(prefs_token):
        raise tg.TelegramShareError("no token")

    monkeypatch.setattr(tg, "resolve_token", _raise)
    assert lui._telegram_bot_token() == ""
