"""Tests for issue #105 — "Fine tune script": iterative LLM script refinement.

The LLM is always mocked (``generate_fn``); no network, no model.
"""
import importlib.util
import json
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
