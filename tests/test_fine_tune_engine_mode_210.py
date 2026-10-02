"""Regression tests for issue #210 — fine-tune must use the selected AI engine.

Before the fix, ``_default_generate`` called ``dual_engine.generate()``
without a mode, so fine-tune always ran on ``first_local_then_agy`` no
matter which engine the user selected in the toolbar. The selected mode is
now threaded ``fine_tune_script(...)`` → ``_default_generate`` →
``dual_engine.generate(mode=...)``; a disabled AI ("None") fails loudly.
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _load_fine_tune():
    # Same isolation trick as test_fine_tune_105.py: load tools/fine_tune.py
    # directly by path (importing the ``tools`` package pulls feedparser,
    # absent in minimal envs).
    path = Path(__file__).resolve().parent.parent / "tools" / "fine_tune.py"
    spec = importlib.util.spec_from_file_location("fine_tune_mod_210", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ft = _load_fine_tune()
FineTuneError = ft.FineTuneError
fine_tune_script = ft.fine_tune_script


def _fake_dual_engine(monkeypatch):
    """Fake ``core.dual_engine`` capturing the mode it was called with."""
    seen = {}

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            seen["mode"] = mode
            return "REFINED", "fake-engine"

    fake_de = types.ModuleType("core.dual_engine")
    fake_de.dual_engine = _FakeEngine()
    monkeypatch.setitem(sys.modules, "core.dual_engine", fake_de)
    return seen


@pytest.mark.parametrize("mode", [
    "first_local_then_agy", "fm_only", "agy_only",
    "codex_only", "grok_low", "grok_medium", "grok_high",
])
def test_selected_engine_mode_reaches_dual_engine(monkeypatch, mode):
    """#210: every selectable engine mode must arrive at dual_engine."""
    seen = _fake_dual_engine(monkeypatch)
    out = fine_tune_script("BEAT 1: hello", "make it funnier",
                           engine_mode=mode)
    assert out == "REFINED"
    assert seen["mode"] == mode


def test_no_mode_means_no_silent_default(monkeypatch):
    """#210: omitting the mode on the real path must NOT silently fall
    back to the default engine — it fails loudly."""
    _fake_dual_engine(monkeypatch)
    with pytest.raises(FineTuneError, match="AI is disabled"):
        fine_tune_script("BEAT 1: hello", "make it funnier")


def test_disabled_ai_fails_loudly(monkeypatch):
    """#210: toolbar \"None\" selection (engine_mode=None) fails loudly —
    no silent fallback, no silent no-op."""
    _fake_dual_engine(monkeypatch)
    with pytest.raises(FineTuneError, match="AI is disabled"):
        fine_tune_script("BEAT 1: hello", "make it funnier",
                         engine_mode=None)
    with pytest.raises(FineTuneError, match="AI is disabled"):
        fine_tune_script("BEAT 1: hello", "make it funnier",
                         engine_mode="")


def test_injected_generate_fn_needs_no_mode():
    """The test-injection path is unaffected by the mode requirement."""
    out = fine_tune_script(
        "BEAT 1: hello", "make it funnier",
        generate_fn=lambda prompt, instructions: "INJECTED")
    assert out == "INJECTED"


def test_ui_call_site_threads_toolbar_engine():
    """#210: the library UI's fine-tune call must pass the toolbar's
    selected engine (``_library_ai_engine()``) — this is where the
    selection was dropped before the fix."""
    src = (Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text(encoding="utf-8")
    assert "engine_mode=_library_ai_engine()" in src, (
        "fine-tune call site must thread the toolbar engine selection")
