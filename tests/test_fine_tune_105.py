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
        emotion="funny",
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


def test_default_generate_uses_dual_engine_with_selected_mode(monkeypatch):
    # core/__init__ needs pydantic (absent in minimal envs), so fake the
    # dual_engine module in sys.modules — the lazy import finds it there.
    import sys
    import types

    seen = {}

    class _FakeEngine:
        def generate(self, prompt="", instructions="", mode="", timeout=None):
            seen["prompt"] = prompt
            seen["instructions"] = instructions
            seen["mode"] = mode
            return "DUAL ENGINE REFINED", "fake"

    fake_de = types.ModuleType("core.dual_engine")
    fake_de.dual_engine = _FakeEngine()
    monkeypatch.setitem(sys.modules, "core.dual_engine", fake_de)
    # #210: the selected engine mode must reach dual_engine.generate —
    # never the hard-coded default.
    out = fine_tune_script("BEAT 1: hello", "make it funnier",
                           engine_mode="codex_only")
    assert out == "DUAL ENGINE REFINED"
    assert "make it funnier" in seen["prompt"]
    assert seen["mode"] == "codex_only"


def test_default_generate_without_mode_fails_loudly():
    # #210: no silent fallback to the default engine on the real path.
    with pytest.raises(FineTuneError, match="AI is disabled"):
        fine_tune_script("BEAT 1: hello", "make it funnier",
                         engine_mode=None)
    with pytest.raises(FineTuneError, match="AI is disabled"):
        fine_tune_script("BEAT 1: hello", "make it funnier")


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
        # Register the real fine_tune module (loaded by path at the top of
        # this file) as BOTH the package attribute and sys.modules entry.
        # A bare ``tools_pkg.fine_tune = None`` attribute suppresses the
        # submodule import and binds None (latent isolation bug: ui.fine_tune
        # was None whenever another test module had stubbed sys.modules).
        tools_pkg.fine_tune = ft
        sys.modules["tools"] = tools_pkg
        sys.modules["tools.fine_tune"] = ft
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _drive_two_phases(ui, st, sid, instruction, refined,
                      llm_side_effect=None, expect_rerun=True):
    """Drive the HIG two-phase flow; returns after phase 2's rerun."""
    btn_key = f"lib_ft_apply_{sid}"
    input_key = f"lib_ft_input_{sid}"
    output_key = f"lib_ft_output_{sid}"

    def fake_llm(current_script, instruction, story_context="",
                 history=(), emotion="", generate_fn=None, engine_mode=None):
        if llm_side_effect is not None:
            raise llm_side_effect
        return refined

    # Phase 1: user typed the instruction and clicked the button.
    st.session_state[input_key] = instruction
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
        if expect_rerun:
            with pytest.raises(_Rerun):
                ui._render_fine_tune_section(sid, story2["meta"],
                                             story2["script"].strip(), False)
        else:
            # Failure path: the error is shown, no rerun.
            ui._render_fine_tune_section(sid, story2["meta"],
                                         story2["script"].strip(), False)
    finally:
        ui.fine_tune.fine_tune_script = _orig_llm
    return output_key


def test_ui_flow_parks_refined_output_without_auto_merge(libdir):
    """#270: with v1 (default) + v2 (latest, not default), a completed
    fine-tune run must park ONLY the LLM output in the right panel —
    no new version, no default change, no auto-merge. The user sees the
    refined script (not the old one) in the output panel."""
    sid = _make_story()
    lib.create_script_version(sid)  # v2: latest, NOT the default
    lib.update_script_version_text(sid, 2, "BEAT 9:\nVIKRAM: \"v2 text\"")

    st = _FakeSt()
    ui = _ui_with_fake_st(st)
    output_key = _drive_two_phases(
        ui, st, sid, "make it funnier", "BEAT 1:\nVIKRAM: \"REFINED\"")
    assert st.errors == []

    # ONLY the LLM output is parked — nothing was merged.
    output = st.session_state.get(output_key)
    assert output is not None
    assert output["refined"] == "BEAT 1:\nVIKRAM: \"REFINED\""
    assert output["instruction"] == "make it funnier"
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [2, 1]  # no new version
    assert default_n == 1  # default untouched
    assert lib.load_story(sid)["script"].startswith("BEAT 1:\nVIKRAM: \"नमस्ते\"")
    assert lib.get_fine_tune_history(sid) == []  # no turn recorded yet


def test_ui_flow_add_to_current_script_adopts_refined_output(libdir):
    """#270: clicking "Add to current script" saves the parked refined
    output as a new version (latest on top) and makes it the default —
    the left panel then shows the new script, and the output clears."""
    sid = _make_story()
    lib.create_script_version(sid)  # v2: latest, NOT the default
    lib.update_script_version_text(sid, 2, "BEAT 9:\nVIKRAM: \"v2 text\"")

    st = _FakeSt()
    ui = _ui_with_fake_st(st)
    output_key = _drive_two_phases(
        ui, st, sid, "make it funnier", "BEAT 1:\nVIKRAM: \"REFINED\"")
    assert st.errors == []

    # The user clicks "Add to current script".
    st.click(f"lib_ft_add_{sid}")
    story = lib.load_story(sid)
    with pytest.raises(_Rerun):
        ui._render_fine_tune_section(sid, story["meta"],
                                     story["script"].strip(), False)
    assert st.errors == []

    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [3, 2, 1]
    assert default_n == 3
    assert versions[0]["text"] == "BEAT 1:\nVIKRAM: \"REFINED\""
    assert lib.load_story(sid)["script"] == "BEAT 1:\nVIKRAM: \"REFINED\""
    # The output panel is consumed; the turn is recorded in history.
    assert st.session_state.get(output_key) is None
    history = lib.get_fine_tune_history(sid)
    assert len(history) == 1
    assert history[0]["instruction"] == "make it funnier"


def test_enter_in_instruction_input_does_not_start_fine_tune(libdir):
    """#270: pressing Enter in the instruction input only reruns (the
    widget value persists) — without the button click, no refinement
    starts and the LLM is never called."""
    sid = _make_story()
    st = _FakeSt()
    ui = _ui_with_fake_st(st)

    called = []

    def fake_llm(*a, **k):
        called.append(True)
        return "REFINED"

    _orig_llm = ui.fine_tune.fine_tune_script
    ui.fine_tune.fine_tune_script = fake_llm
    try:
        # Enter in the input: value set, render runs, button NOT clicked.
        st.session_state[f"lib_ft_input_{sid}"] = "make it funnier"
        story = lib.load_story(sid)
        ui._render_fine_tune_section(sid, story["meta"],
                                     story["script"].strip(), False)
    finally:
        ui.fine_tune.fine_tune_script = _orig_llm

    assert called == []
    assert st.session_state.get(f"lib_ft_running_{sid}") is None
    assert st.session_state.get(f"lib_ft_output_{sid}") is None
    assert st.errors == []


def test_fine_tune_llm_failure_is_loud_and_leaves_nothing(libdir):
    """#270: an LLM failure surfaces loudly; no output is parked and no
    version is created — the old script is never presented as a result."""
    sid = _make_story()
    st = _FakeSt()
    ui = _ui_with_fake_st(st)
    _drive_two_phases(ui, st, sid, "make it funnier", "REFINED",
                      llm_side_effect=Exception("model exploded"),
                      expect_rerun=False)

    assert len(st.errors) == 1
    assert "Fine tune failed" in st.errors[0]
    assert st.session_state.get(f"lib_ft_output_{sid}") is None
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [1]
    assert default_n == 1
    assert lib.get_fine_tune_history(sid) == []


def test_add_to_current_script_failure_is_loud_and_keeps_output(libdir):
    """#270: if adopting the refined output fails, the error is loud and
    the output panel is kept (not silently dropped)."""
    sid = _make_story()
    st = _FakeSt()
    ui = _ui_with_fake_st(st)
    output_key = _drive_two_phases(
        ui, st, sid, "make it funnier", "BEAT 1:\nVIKRAM: \"REFINED\"")
    assert st.errors == []

    _orig_record = lib.record_fine_tune_turn
    def _boom(*a, **k):
        raise OSError("disk exploded")
    monkeypatch_record = _orig_record
    lib.record_fine_tune_turn = _boom
    try:
        st.click(f"lib_ft_add_{sid}")
        story = lib.load_story(sid)
        ui._render_fine_tune_section(sid, story["meta"],
                                     story["script"].strip(), False)
    finally:
        lib.record_fine_tune_turn = monkeypatch_record

    assert len(st.errors) == 1
    assert "Could not add the refined script" in st.errors[0]
    # Output retained for retry; versions untouched.
    assert st.session_state.get(output_key)["refined"] == \
        "BEAT 1:\nVIKRAM: \"REFINED\""
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [1]
    assert default_n == 1


# ---------------------------------------------------------------------------
# Layout (#270): fine-tune panel sits side-by-side (right) with the script
# ---------------------------------------------------------------------------

class _ColumnCtx:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def _fake_st_with_columns():
    st = _FakeSt()
    st.column_calls = []

    def columns(spec, vertical_alignment=None):
        st.column_calls.append((spec, vertical_alignment))
        n = spec if isinstance(spec, int) else len(spec)
        return [_ColumnCtx() for _ in range(n)]

    st.columns = columns
    return st


def _ui_with_columns(st):
    import types as _types
    saved = dict(sys.modules)
    try:
        fake_mod = _types.ModuleType("streamlit")
        for _name in ("markdown", "caption", "error", "expander", "spinner",
                      "text_input", "button", "rerun", "columns"):
            setattr(fake_mod, _name, getattr(st, _name))
        fake_mod.session_state = st.session_state
        sys.modules["streamlit"] = fake_mod
        tools_pkg = _types.ModuleType("tools")
        tools_pkg.__path__ = [str(Path(__file__).resolve().parent.parent
                                  / "tools")]
        # Same registration as _ui_with_fake_st: real module as attribute
        # AND sys.modules entry (never a None attribute).
        tools_pkg.fine_tune = ft
        sys.modules["tools"] = tools_pkg
        sys.modules["tools.fine_tune"] = ft
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def test_script_and_fine_tune_render_side_by_side(libdir):
    """#270: with a script present, the versions list and the fine-tune
    panel render in two side-by-side columns (script left, panel right)."""
    sid = _make_story()
    st = _fake_st_with_columns()
    ui = _ui_with_columns(st)

    rendered = []
    ui._render_script_versions = lambda *a, **k: rendered.append("versions")
    ui._render_fine_tune_section = lambda *a, **k: rendered.append("fine_tune")

    story = lib.load_story(sid)
    ui._render_script_and_fine_tune(sid, story["meta"],
                                    story["script"].strip(), set(), False)

    assert st.column_calls == [(2, "top")]
    assert rendered == ["versions", "fine_tune"]


def test_no_script_renders_versions_full_width(libdir):
    """#270: without a script there is no fine-tune baseline — the
    versions list renders full-width with no columns."""
    sid = _make_story()
    st = _fake_st_with_columns()
    ui = _ui_with_columns(st)

    rendered = []
    ui._render_script_versions = lambda *a, **k: rendered.append("versions")
    ui._render_fine_tune_section = lambda *a, **k: rendered.append("fine_tune")

    story = lib.load_story(sid)
    ui._render_script_and_fine_tune(sid, story["meta"], "   ", set(), False)

    assert st.column_calls == []
    assert rendered == ["versions"]
