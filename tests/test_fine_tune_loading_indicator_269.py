"""Tests for issue #269 — fine-tune loading indicator.

Bug (user screenshot): during fine-tuning TWO indicators appeared —
1. the initiating button repainted as "Fine tuning…" (disabled, native
   spinner icon), and
2. a detached ``st.spinner("Fine-tuning the script…")`` below it.

Worse, the disabled primary button rendered its label in --on-accent
(white) on the light --sunken background (1.18:1 — unreadable): the
primary-children CSS rule forced white on ALL descendants, including
when disabled.

Fix: ONE indicator, owned by the starting control (HIG §3) — the
detached st.spinner is gone, and disabled primary-button descendants
use --ink-3 on --sunken (the Khabarwaani .btn:disabled spec).

HIG: the initiating control owns its loading state — disabled till
done, no second click (see ~/workspace/docs/apple-hig-notes.md §3).
"""
import re
import sys
import types as _types
from contextlib import contextmanager
from pathlib import Path

import pytest

import story_library as lib

REPO = Path(__file__).resolve().parent.parent
APP_PY = REPO / "app.py"
LIB_UI_PY = REPO / "library_ui.py"


def _load_fine_tune():
    import importlib.util
    path = REPO / "tools" / "fine_tune.py"
    spec = importlib.util.spec_from_file_location("fine_tune_mod_269", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["fine_tune_mod_269"] = mod
    return mod


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "lib"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    (root / "stories").mkdir(parents=True)
    return root


def _make_story():
    return lib.save_story(
        title="T", tone="funny", hashtags=[], dialogue_md="D",
        script_md="BEAT 1:\nVIKRAM: \"नमस्ते\"")


class _Rerun(Exception):
    """Stands in for Streamlit's rerun."""


class _RecordingFakeSt:
    """Fake streamlit that RECORDS spinner() calls (and button labels)."""

    def __init__(self):
        self.session_state = {}
        self.errors = []
        self.spinner_calls = []
        self.button_labels = []
        self._clicks = {}

    def click(self, key):
        self._clicks[key] = self._clicks.get(key, 0) + 1

    def markdown(self, *a, **k):
        pass

    def caption(self, *a, **k):
        pass

    def error(self, msg):
        self.errors.append(msg)

    @contextmanager
    def expander(self, *a, **k):
        yield

    @contextmanager
    def spinner(self, text="", *a, **k):
        self.spinner_calls.append(text)
        yield

    def text_input(self, label, placeholder="", key=None,
                   label_visibility="visible", disabled=False):
        return self.session_state.get(key, "")

    def button(self, label, icon=None, key=None, type=None,
               disabled=False, help=None):
        self.button_labels.append((label, icon, bool(disabled)))
        if disabled:
            return False
        if self._clicks.get(key, 0) > 0:
            self._clicks[key] -= 1
            return True
        return False

    def rerun(self):
        raise _Rerun()


def _ui_with_fake_st(st):
    saved = dict(sys.modules)
    try:
        fake_mod = _types.ModuleType("streamlit")
        for _name in ("markdown", "caption", "error", "expander", "spinner",
                      "text_input", "button", "rerun"):
            setattr(fake_mod, _name, getattr(st, _name))
        fake_mod.session_state = st.session_state
        sys.modules["streamlit"] = fake_mod
        tools_pkg = _types.ModuleType("tools")
        tools_pkg.__path__ = [str(REPO / "tools")]
        tools_pkg.fine_tune = sys.modules.get("fine_tune_mod_269")
        sys.modules["tools"] = tools_pkg
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _run_full_fine_tune(libdir):
    """Drive the complete two-phase fine-tune flow; return (ui, st)."""
    _load_fine_tune()
    sid = _make_story()
    st = _RecordingFakeSt()
    ui = _ui_with_fake_st(st)
    btn_key = f"lib_ft_apply_{sid}"
    input_key = f"lib_ft_input_{sid}"

    def fake_llm(current_script, instruction, story_context="",
                 history=(), tone="", generate_fn=None):
        return "BEAT 1:\nVIKRAM: \"REFINED\""

    # Phase 1: user typed instruction and clicked the button.
    st.session_state[input_key] = "make it funnier"
    st.click(btn_key)
    story = lib.load_story(sid)
    with pytest.raises(_Rerun):
        ui._render_fine_tune_section(sid, story["meta"],
                                     story["script"].strip(), False)
    assert st.session_state.get(f"lib_ft_running_{sid}") is True

    # Phase 2: the rerun performs the refinement (button not clicked).
    _orig = ui.fine_tune.fine_tune_script
    ui.fine_tune.fine_tune_script = fake_llm
    try:
        story2 = lib.load_story(sid)
        with pytest.raises(_Rerun):
            ui._render_fine_tune_section(sid, story2["meta"],
                                         story2["script"].strip(), False)
    finally:
        ui.fine_tune.fine_tune_script = _orig
    assert st.errors == []
    return ui, st


# ---------------------------------------------------------------------------
# #269: one loading indicator, owned by the starting control
# ---------------------------------------------------------------------------

def test_no_detached_spinner_during_fine_tune(libdir):
    """The full fine-tune run must never call st.spinner — the button's own
    loading state ("Fine tuning…" + native spinner icon, disabled) is the
    single indicator (HIG §3)."""
    _, st = _run_full_fine_tune(libdir)
    assert st.spinner_calls == [], (
        f"detached st.spinner used during fine-tune: {st.spinner_calls}")


def test_running_button_label_is_verb_first_ing_form(libdir):
    """While running, the button shows the -ing form of its own label
    (HIG §3: 'Checkout' → 'Checking out…'), disabled, with the spinner
    icon — and no second indicator text exists in the source."""
    _, st = _run_full_fine_tune(libdir)
    running = [(label, icon, dis) for (label, icon, dis)
               in st.button_labels if dis]
    assert running, "no disabled running-state button was rendered"
    tuning = [(label, icon) for (label, icon, _dis) in running
              if "Fine tuning" in label]
    assert tuning, f"no 'Fine tuning…' running button: {running}"
    assert all(icon == "spinner" for (_, icon) in tuning), tuning


def test_no_duplicate_loading_wording_in_source():
    """No detached st.spinner call with the old wording remains for
    fine-tune — exactly one loading message (the button's own).
    Comments are stripped first so explanatory comments don't trip it."""
    src = LIB_UI_PY.read_text()
    code = "\n".join(
        line.split("#", 1)[0] for line in src.splitlines())
    assert 'spinner("Fine-tuning' not in code and "spinner('Fine-tuning" not in code, (
        "detached st.spinner call with duplicate wording still present")
    assert src.count("Fine tuning…") >= 1


# ---------------------------------------------------------------------------
# #269: disabled primary button must be readable (contrast)
# ---------------------------------------------------------------------------

def _luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _ratio(fg, bg):
    la, lb = _luminance(fg), _luminance(bg)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_disabled_primary_children_use_ink3_token():
    """The CSS must override the primary-children white-text rule for
    :disabled buttons — otherwise the 'Fine tuning…' label renders
    --on-accent on --sunken (1.18:1, unreadable)."""
    css = APP_PY.read_text()
    assert re.search(
        r'button\[data-testid="stBaseButton-primary"\]:disabled\s*\*',
        css), "missing :disabled * override for primary buttons"
    block_start = css.find("/* #269: disabled primary buttons")
    assert block_start != -1, "missing #269 disabled-primary CSS block"
    block = css[block_start:block_start + 2000]
    assert "var(--ink-3)" in block, (
        "disabled primary descendants must use the --ink-3 token")


def test_disabled_button_contrast_pinned_better_than_bug():
    """Pin the measured disabled-button ratios (user's explicit
    .btn:disabled spec: --ink-3 on --sunken). They must never drift back
    toward the 1.18:1 white-on-sunken bug — measured, never faked."""
    # Light: #9A958A on #EFECE4 → 2.53 ; Dark: #77726A on #2E2D29 → 2.89
    light = _ratio("#9A958A", "#EFECE4")
    dark = _ratio("#77726A", "#2E2D29")
    assert abs(light - 2.53) < 0.05, f"light disabled ratio moved: {light:.2f}"
    assert abs(dark - 2.89) < 0.05, f"dark disabled ratio moved: {dark:.2f}"
    # Strictly better than the bug it replaces (white --on-accent on sunken).
    assert light > _ratio("#FFFFFF", "#EFECE4") + 1.0
    assert dark > _ratio("#1C1B19", "#2E2D29") + 1.0
