"""Tests for issue #105 — "Fine tune script": iterative LLM script refinement.

The LLM is always mocked (``generate_fn``); no network, no model.
"""
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

import story_library as lib


def _load_fine_tune():
    # Load tools/fine_tune.py directly by path: importing the ``tools``
    # package pulls ``tools/__init__`` → news_fetcher → feedparser, which is
    # not installed in minimal test envs (pre-existing collection failure).
    # fine_tune.py itself is stdlib-only (dual_engine is lazily imported).
    path = Path(__file__).resolve().parent.parent / "tools" / "fine_tune.py"
    spec = importlib.util.spec_from_file_location("fine_tune_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ft = _load_fine_tune()
FineTuneError = ft.FineTuneError
fine_tune_script = ft.fine_tune_script


# ---------------------------------------------------------------------------
# LLM plumbing (mocked)
# ---------------------------------------------------------------------------

def _fake_llm(captured, response="REFINED SCRIPT"):
    def _gen(prompt, instructions):
        captured.append({"prompt": prompt, "instructions": instructions})
        return response
    return _gen


def test_instruction_script_and_context_reach_prompt():
    captured = []
    out = fine_tune_script(
        "BEAT 1: hello",
        "make it funnier",
        story_context="Title: Test",
        tone="funny",
        generate_fn=_fake_llm(captured),
    )
    assert out == "REFINED SCRIPT"
    prompt = captured[0]["prompt"]
    assert "make it funnier" in prompt
    assert "BEAT 1: hello" in prompt
    assert "Title: Test" in prompt
    assert "funny" in captured[0]["instructions"]


def test_history_carried_across_turns():
    captured = []
    history = [
        {"instruction": "tighten the hook", "script": "BEAT 1: tight"},
        {"instruction": "add a joke", "script": "BEAT 1: tight + joke"},
    ]
    fine_tune_script("BEAT 1: tight + joke", "make it shorter",
                     history=history, generate_fn=_fake_llm(captured))
    prompt = captured[0]["prompt"]
    assert "tighten the hook" in prompt
    assert "add a joke" in prompt
    assert "BEAT 1: tight + joke" in prompt  # prior script visible


def test_blank_instruction_raises_loudly():
    with pytest.raises(FineTuneError):
        fine_tune_script("BEAT 1: hello", "   ",
                         generate_fn=_fake_llm([]))


def test_blank_script_raises_loudly():
    with pytest.raises(FineTuneError):
        fine_tune_script("   ", "make it funnier",
                         generate_fn=_fake_llm([]))


def test_blank_llm_output_raises_no_silent_fallback():
    with pytest.raises(FineTuneError):
        fine_tune_script("BEAT 1: hello", "make it funnier",
                         generate_fn=_fake_llm([], response="   "))


def test_llm_error_propagates_as_fine_tune_error():
    def _boom(prompt, instructions):
        raise RuntimeError("model exploded")
    with pytest.raises(FineTuneError, match="model exploded"):
        fine_tune_script("BEAT 1: hello", "make it funnier", generate_fn=_boom)


def test_default_generate_uses_dual_engine(monkeypatch):
    # core/__init__ needs pydantic (absent in minimal envs), so fake the
    # dual_engine module in sys.modules — the lazy import finds it there.
    import sys
    import types

    seen = {}

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            seen["prompt"] = prompt
            seen["instructions"] = instructions
            return "DUAL ENGINE REFINED", "fake"

    fake_de = types.ModuleType("core.dual_engine")
    fake_de.dual_engine = _FakeEngine()
    monkeypatch.setitem(sys.modules, "core.dual_engine", fake_de)
    out = fine_tune_script("BEAT 1: hello", "make it funnier")
    assert out == "DUAL ENGINE REFINED"
    assert "make it funnier" in seen["prompt"]


# ---------------------------------------------------------------------------
# story_library history persistence
# ---------------------------------------------------------------------------

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


def test_record_replaces_script_and_appends_history(libdir):
    sid = _make_story()
    lib.record_fine_tune_turn(sid, "make it funnier",
                              "BEAT 1:\nVIKRAM: \"ज़्यादा मज़ेदार नमस्ते\"")
    story = lib.load_story(sid)
    assert "ज़्यादा मज़ेदार" in story["script"]
    history = lib.get_fine_tune_history(sid)
    assert len(history) == 1
    assert history[0]["instruction"] == "make it funnier"
    assert "ज़्यादा मज़ेदार" in history[0]["script"]
    # #191: the refined script lands as a NEW version — latest on top and
    # the default — so the versions list displays it immediately instead
    # of hiding it in a collapsed expander.
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [2, 1]
    assert default_n == 2
    assert "ज़्यादा मज़ेदार" in versions[0]["text"]
    assert "नमस्ते" in versions[1]["text"]  # pre-turn text recoverable


def test_history_round_trips_tricky_content(libdir):
    # Quotes, commas, newlines, Devanagari must survive the frontmatter.
    sid = _make_story()
    tricky = ("BEAT 1:\nVIKRAM: \"सुनो, \"ख़बर\" बड़ी है, समझो\" — comma, test\n"
              "BEAT 2:\nRAJESH: \"हाँ, बिल्कुल!\"")
    lib.record_fine_tune_turn(sid, 'use "quotes", commas, and\nnewlines', tricky)
    history = lib.get_fine_tune_history(sid)
    assert history[0]["script"] == tricky
    assert history[0]["instruction"] == 'use "quotes", commas, and\nnewlines'
    # And the stored script keeps its line breaks too.
    assert lib.load_story(sid)["script"] == tricky


def test_history_capped_at_max_turns(libdir):
    sid = _make_story()
    total = lib._FINE_TUNE_HISTORY_MAX_TURNS + 2
    for i in range(total):
        lib.record_fine_tune_turn(sid, f"instruction {i}", f"script {i}")
    history = lib.get_fine_tune_history(sid)
    assert len(history) == lib._FINE_TUNE_HISTORY_MAX_TURNS
    assert history[-1]["instruction"] == f"instruction {total - 1}"
    assert history[0]["instruction"] == "instruction 2"  # oldest dropped


def test_record_blank_instruction_raises(libdir):
    sid = _make_story()
    with pytest.raises(ValueError):
        lib.record_fine_tune_turn(sid, "  ", "script")
    assert lib.get_fine_tune_history(sid) == []


def test_record_blank_script_raises(libdir):
    sid = _make_story()
    with pytest.raises(ValueError):
        lib.record_fine_tune_turn(sid, "do it", "  ")
    assert lib.get_fine_tune_history(sid) == []


def test_record_missing_story_raises(libdir):
    with pytest.raises(FileNotFoundError):
        lib.record_fine_tune_turn("no-such-id", "do it", "script")
    with pytest.raises(FileNotFoundError):
        lib.get_fine_tune_history("no-such-id")


def test_get_history_skips_corrupt_entries(libdir):
    sid = _make_story()
    lib.record_fine_tune_turn(sid, "good turn", "good script")
    # Inject garbage directly into frontmatter.
    lib.update_story_fields(
        sid, **{lib._FINE_TUNE_HISTORY_KEY: [
            "not json at all",
            json.dumps({"instruction": "only instruction"}),
            json.dumps({"instruction": "good turn", "script": "good script"}),
        ]})
    history = lib.get_fine_tune_history(sid)
    assert history == [{"instruction": "good turn", "script": "good script"}]


# ---------------------------------------------------------------------------
# UI flow (#191): the two-phase HIG run must surface the refined script
# ---------------------------------------------------------------------------

class _Rerun(Exception):
    """Stands in for Streamlit's rerun — restarts the render function."""


class _FakeSt:
    """Minimal fake streamlit with faithful rerun/session-state semantics:
    widget values persist in session_state under their key (disabled or
    not); button() returns True once per click(); rerun() restarts."""

    def __init__(self):
        self.session_state = {}
        self.errors = []
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
    def spinner(self, *a, **k):
        yield

    def text_input(self, label, placeholder="", key=None,
                   label_visibility="visible", disabled=False):
        return self.session_state.get(key, "")

    def button(self, label, icon=None, key=None, type=None,
               disabled=False, help=None):
        if disabled:
            return False
        if self._clicks.get(key, 0) > 0:
            self._clicks[key] -= 1
            return True
        return False

    def rerun(self):
        raise _Rerun()


def _ui_with_fake_st(st):
    """Import library_ui bound to the fake streamlit; restores sys.modules.

    library_ui does ``import tools.fine_tune`` at module top, and importing
    the ``tools`` package pulls in news_fetcher (feedparser, not installed
    here) — so the ``tools`` package is stubbed with fine_tune.py loaded
    directly by path (same trick as _load_fine_tune above)."""
    import types as _types
    saved = dict(sys.modules)
    try:
        fake_mod = _types.ModuleType("streamlit")
        for _name in ("markdown", "caption", "error", "expander", "spinner",
                      "text_input", "button", "rerun"):
            setattr(fake_mod, _name, getattr(st, _name))
        fake_mod.session_state = st.session_state
        sys.modules["streamlit"] = fake_mod
        tools_pkg = _types.ModuleType("tools")
        tools_pkg.__path__ = [str(Path(__file__).resolve().parent.parent
                                  / "tools")]
        tools_pkg.fine_tune = sys.modules.get("fine_tune_mod")
        sys.modules["tools"] = tools_pkg
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def test_ui_flow_surfaces_refined_script_when_latest_is_not_default(libdir):
    """#191: with v1 (default) + v2 (latest, not default), a completed
    fine-tune run must leave the refined script as the latest version —
    which is what the versions list expands — not hidden in a collapsed
    default expander showing old text."""
    sid = _make_story()
    lib.create_script_version(sid)  # v2: latest, NOT the default
    lib.update_script_version_text(sid, 2, "BEAT 9:\nVIKRAM: \"v2 text\"")

    st = _FakeSt()
    ui = _ui_with_fake_st(st)
    btn_key = f"lib_ft_apply_{sid}"
    input_key = f"lib_ft_input_{sid}"

    def fake_llm(current_script, instruction, story_context="",
                 history=(), tone="", generate_fn=None):
        assert current_script.strip() == "BEAT 1:\nVIKRAM: \"नमस्ते\""
        assert instruction == "make it funnier"
        return "BEAT 1:\nVIKRAM: \"REFINED\""

    # Phase 1: user typed the instruction and clicked the button.
    st.session_state[input_key] = "make it funnier"
    st.click(btn_key)
    story = lib.load_story(sid)
    with pytest.raises(_Rerun):
        ui._render_fine_tune_section(sid, story["meta"],
                                     story["script"].strip(), False)
    assert st.session_state.get(f"lib_ft_running_{sid}") is True

    # Phase 2: the rerun performs the refinement (button not clicked).
    _orig_llm = ui.fine_tune.fine_tune_script
    ui.fine_tune.fine_tune_script = fake_llm
    try:
        story2 = lib.load_story(sid)
        with pytest.raises(_Rerun):
            ui._render_fine_tune_section(sid, story2["meta"],
                                         story2["script"].strip(), False)
    finally:
        ui.fine_tune.fine_tune_script = _orig_llm
    assert st.errors == []

    # The refined script is the latest version AND the default — the
    # versions list expands the latest, so the user sees it immediately.
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [3, 2, 1]
    assert default_n == 3
    assert versions[0]["text"] == "BEAT 1:\nVIKRAM: \"REFINED\""
    assert lib.load_story(sid)["script"] == "BEAT 1:\nVIKRAM: \"REFINED\""
