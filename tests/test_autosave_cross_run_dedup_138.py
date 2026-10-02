"""Issue #138 (save phase) — cross-run autosave dedup.

Root cause (side-chat deep-dive, verified): `maybe_autosave_story`'s guard
is session-ephemeral (`st.session_state`) and `id()`-based. Every NEW
generation run mints a new batch_result object -> all guards fresh -> the
landing version (v1) autosaves AGAIN. Same topic + same first angle ->
near-identical script 1 -> the Library accumulates same-content stories
with indistinguishable titles. #147's gates only check within one batch;
#279 only fixed the in-session case.

Fix: persist screenplay content-hashes in prefs.json (not session state);
skip the autosave when the hash already exists; suffix autosave titles
with `· v{n}` so one batch's stories are distinguishable.

Run: python -m pytest tests/test_autosave_cross_run_dedup_138.py -q
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import library_ui as lui  # noqa: E402
import story_library as lib  # noqa: E402


class _FakeSt:
    """Minimal Streamlit stub for the auto-save path."""

    def __init__(self):
        self.session_state = {}
        self.errors = []
        self.button_results = {}

    def error(self, text, **kw):
        self.errors.append(text)

    def button(self, label, **kw):
        return self.button_results.get(label, False)

    def rerun(self):
        pass

    def toast(self, msg, icon=None):
        pass


class _Script:
    def __init__(self, sid, content=""):
        self.id = sid
        # #338: autosave identity is canonical content now — distinct stub
        # scripts need distinct content, not just distinct ids.
        self.angle = f"angle-{sid}-{content}"
        self.hook_hindi = f"hook-{sid}-{content}"
        self.narration_hindi = f"narration-{sid}-{content}"
        self.scenes = []


@pytest.fixture
def ui(monkeypatch, tmp_path):
    """library_ui with `st` stubbed, prefs redirected to tmp_path,
    `_save_current_story` replaced by a marker-file fake."""
    fake = _FakeSt()
    monkeypatch.setattr(lui, "st", fake)
    _prefs_dir = tmp_path / "prefsdir"
    _prefs_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(lib, "PREFS_PATH", _prefs_dir / "prefs.json")
    saved = []

    def fake_save(batch_result, script, pro_screenplay=""):
        if not (pro_screenplay or "").strip():
            raise ValueError("Cannot save: the final-stage screenplay text is empty.")
        marker = tmp_path / f"story-{script.id}-{len(saved)}.md"
        marker.write_text(pro_screenplay, encoding="utf-8")
        saved.append(script.id)
        return f"story-id-{script.id}-{len(saved)}"

    monkeypatch.setattr(lui, "_save_current_story", fake_save)
    monkeypatch.setattr(lui.lib, "start_enrichment",
                        lambda story_id, topic: (True, "ok"))
    return fake, saved, tmp_path


def _view(fake, batch, script, idx, text):
    fake.session_state["selected_script_idx"] = idx
    lui.maybe_autosave_story(batch, script, pro_screenplay=text)


# ---------------------------------------------------------------------------
# Hash identity
# ---------------------------------------------------------------------------

def test_content_hash_stable_across_runs():
    h1 = lui._screenplay_content_hash("Hello  World\nNew line")
    h2 = lui._screenplay_content_hash("hello world new line")
    assert h1 == h2
    assert lui._screenplay_content_hash("something else") != h1
    assert len(h1) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# Cross-run dedup: the core #138 save-phase regression
# ---------------------------------------------------------------------------

def test_second_run_same_screenplay_skips_save(ui):
    """Two generation runs, same topic -> same v1 screenplay text.
    Run 2 must NOT save again. FAILS on pristine develop (id-based guard
    is fresh for the new batch object -> saves a duplicate)."""
    fake, saved, _tmp = ui
    text = "FINAL SCREENPLAY V1 — same topic, same angle"
    script = _Script("s1")

    # Run 1: fresh session, batch object A.
    _view(fake, object(), script, 0, text)
    assert saved == ["s1"]

    # Run 2: brand-new session (fresh guards) + new batch object.
    fake2 = _FakeSt()
    import library_ui as lui2  # same module
    old_st = lui2.st
    lui2.st = fake2
    try:
        fake2.session_state["selected_script_idx"] = 0
        lui2.maybe_autosave_story(object(), script, pro_screenplay=text)
    finally:
        lui2.st = old_st
    assert saved == ["s1"], "second run re-saved the identical screenplay"


def test_different_screenplay_still_saves(ui):
    fake, saved, _tmp = ui
    _view(fake, object(), _Script("s1", "dialogue one"), 0, "screenplay one")
    fake.session_state.clear()  # new run
    _view(fake, object(), _Script("s1", "dialogue two"), 0, "screenplay two — different")
    assert saved == ["s1", "s1"]


def test_hash_persisted_in_prefs(ui):
    fake, saved, tmp_path = ui
    script = _Script("s1", "some dialogue")
    _view(fake, object(), script, 0, "persist me")
    prefs_path = tmp_path / "prefsdir" / "prefs.json"
    assert prefs_path.exists()
    import json
    data = json.loads(prefs_path.read_text(encoding="utf-8"))
    hashes = data.get("autosaved_screenplay_hashes")
    # #338: both the canonical script hash and the dedup id are recorded.
    assert isinstance(hashes, list) and len(hashes) == 2
    assert lui._canonical_script_hash(script) in hashes
    assert lui._story_dedup_id(script, lui._build_autosave_title(script)) in hashes


# ---------------------------------------------------------------------------
# Distinguishable titles
# ---------------------------------------------------------------------------

def test_title_suffix_via_real_save(monkeypatch, tmp_path):
    """Direct test of the real `_save_current_story` title logic."""
    fake = _FakeSt()
    monkeypatch.setattr(lui, "st", fake)
    monkeypatch.setattr(lib, "PREFS_PATH", tmp_path / "prefs.json")
    captured = {}

    def fake_lib_save(**kw):
        captured.update(kw)
        return "story-id-x"

    monkeypatch.setattr(lib, "save_story", fake_lib_save)
    fake.session_state["selected_headline_title"] = "Big News Today"
    fake.session_state["selected_script_idx"] = 2
    # Bypass module-level monkeypatching by calling the undecorated func.
    lui._save_current_story(object(), _Script("s9"), "screenplay text")
    assert captured["title"] == "Big News Today · v3"
