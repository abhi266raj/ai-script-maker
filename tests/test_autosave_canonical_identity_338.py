"""Issue #338 — autosave dedup must use the script's canonical identity.

``_screenplay_content_hash`` hashed the FORMATTED screenplay, which varies
with the overlay/SFX checkbox toggles even for a byte-identical script.
Two runs of the same topic then hash differently and the same story saves
twice (Mac evidence: current develop @399771f, identical scripts, same
topic — the #138 persisted-hash dedup missed).

Fix: ``_canonical_script_hash`` covers authored content only
(angle/hook/narration/beats); run metadata and presentation toggles
cannot change it. Old formatted-text records are still honored (and
upgraded to canonical on sight) so stories saved by earlier builds never
re-save after upgrade.

Run: python -m pytest tests/test_autosave_canonical_identity_338.py -q
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


class _Scene:
    def __init__(self, n, character, dialogue):
        self.scene_number = n
        self.character = character
        self.dialogue = dialogue
        self.timestamp = "0:00 - 0:03"
        self.visual_b_roll = "Action"
        self.on_screen_text = "overlay text"
        self.audio_sfx = "sfx cue"


class _Script:
    def __init__(self, sid, dialogue, **meta):
        self.id = sid
        self.angle = "angle one"
        self.hook_hindi = "hook line"
        self.narration_hindi = "narration line"
        self.scenes = [_Scene(1, "RAM", dialogue)]
        # Run-specific metadata: must NEVER affect the identity.
        self.retry_count = meta.get("retry_count", 0)
        self.engine_used = meta.get("engine_used", "Local FM")
        self.self_healing_notes = meta.get("self_healing_notes", [])


class _Batch:
    pass


@pytest.fixture
def ui(monkeypatch, tmp_path):
    """library_ui with `st` stubbed, prefs redirected to tmp_path,
    `_save_current_story` replaced by a counting fake."""
    fake = _FakeSt()
    monkeypatch.setattr(lui, "st", fake)
    _prefs_dir = tmp_path / "prefsdir"
    _prefs_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(lib, "PREFS_PATH", _prefs_dir / "prefs.json")
    saved = []

    def fake_save(batch_result, script, pro_screenplay=""):
        if not (pro_screenplay or "").strip():
            raise ValueError("Cannot save: the final-stage screenplay text is empty.")
        saved.append((script.id, pro_screenplay))
        return f"story-id-{script.id}-{len(saved)}"

    monkeypatch.setattr(lui, "_save_current_story", fake_save)
    monkeypatch.setattr(lui.lib, "start_enrichment",
                        lambda story_id, topic: (True, "ok"))
    return fake, saved, tmp_path


def _view(fake, batch, script, idx, text):
    fake.session_state["selected_script_idx"] = idx
    lui.maybe_autosave_story(batch, script, text)


def test_identical_script_new_run_different_toggles_saves_once(ui):
    """#338 core: same canonical script, fresh batch object (new run),
    formatted text differs only by overlay-toggle lines -> exactly one
    save. Run metadata differences must not matter either."""
    fake, saved, _ = ui
    batch1, batch2 = _Batch(), _Batch()
    s1 = _Script(1, "same dialogue")
    s2 = _Script(1, "same dialogue", retry_count=2,
                 engine_used="grok_medium",
                 self_healing_notes=["healed on attempt 2/3"])
    text_overlays_on = "SCREENPLAY\nBeat 1: same dialogue\n[Overlay: overlay text]\n[SFX: sfx cue]"
    text_overlays_off = "SCREENPLAY\nBeat 1: same dialogue"

    _view(fake, batch1, s1, 0, text_overlays_on)
    assert len(saved) == 1
    # New run, toggles flipped, metadata differs -> must skip.
    _view(fake, batch2, s2, 0, text_overlays_off)
    assert len(saved) == 1
    # Canonical hash recorded; a third view with yet another formatting
    # variant still skips.
    _view(fake, batch2, s2, 0, text_overlays_on + "\n")
    assert len(saved) == 1


def test_backward_compat_formatted_hash_upgrades_to_canonical(ui):
    """Stories saved by pre-#338 builds recorded the formatted-text hash.
    Viewing the same script with different toggles must skip (old record
    honored) AND upgrade the record to canonical."""
    fake, saved, _ = ui
    batch = _Batch()
    script = _Script(1, "same dialogue")
    old_text = "SCREENPLAY\nBeat 1: same dialogue\n[Overlay: overlay text]"
    # Simulate the pre-#338 record.
    lui._record_autosaved_content_hash(lui._screenplay_content_hash(old_text))

    # Same formatted text the old build saved -> skip, upgrade the record.
    _view(fake, batch, script, 0, old_text)
    assert saved == []
    assert lui._canonical_script_hash(script) in lui._autosaved_content_hashes()
    # Toggles flipped afterwards -> still skips via the canonical record.
    _view(fake, _Batch(), _Script(1, "same dialogue"), 0,
          "SCREENPLAY\nBeat 1: same dialogue")
    assert saved == []


def test_distinct_scripts_still_save_twice(ui):
    """Different dialogue -> different canonical hash -> two saves."""
    fake, saved, _ = ui
    # NOTE: batches must stay alive (named vars, like the real
    # st.session_state.batch_result) — a _Batch() temporary would be
    # freed and its id() address reused, colliding the guard.
    batch1, batch2 = _Batch(), _Batch()
    _view(fake, batch1, _Script(1, "first dialogue"), 0, "text one")
    _view(fake, batch2, _Script(1, "second dialogue"), 0, "text two")
    assert len(saved) == 2


def test_canonical_hash_ignores_batch_position_and_title(ui):
    """`ReelScript.id` is the batch position (1, 2, ...) — identical
    content at a different position must still dedupe."""
    fake, saved, _ = ui
    batch1, batch2 = _Batch(), _Batch()
    _view(fake, batch1, _Script(1, "same dialogue"), 0, "text a")
    _view(fake, batch2, _Script(2, "same dialogue"), 1, "text b")
    assert len(saved) == 1


# ---------------------------------------------------------------------------
# dedup_id: hash(script identity + title), verified while saving
# ---------------------------------------------------------------------------

def test_dedup_id_recorded_and_skips_resave(ui):
    """First save records the content id; a new run with the same script
    skips via the content id even if the formatted text differs. The
    title plays no part in the identity."""
    fake, saved, _ = ui
    fake.session_state["run_topic"] = "Same Topic"
    batch1, batch2 = _Batch(), _Batch()
    s1 = _Script(1, "same dialogue")
    s2 = _Script(1, "same dialogue")

    _view(fake, batch1, s1, 0, "formatted one")
    assert len(saved) == 1
    cid = lui._canonical_script_hash(s1)
    assert cid in lui._autosaved_content_hashes()

    _view(fake, batch2, s2, 0, "formatted two — toggles flipped")
    assert len(saved) == 1


def test_identity_ignores_title():
    """Same script, different titles -> SAME identity. The title is
    presentation; only content hash + script id form the dedup base."""
    s = _Script(1, "same dialogue")
    assert (lui._canonical_script_hash(s)
            == lui._canonical_script_hash(_Script(2, "same dialogue")))


# ---------------------------------------------------------------------------
# Load-time verification + removal
# ---------------------------------------------------------------------------

def _meta(sid, title, dedup_id="", created="2026-10-02T10:00:00"):
    return {"id": sid, "title": title, "dedup_id": dedup_id,
            "created_at": created}


def test_group_duplicate_stories_by_dedup_id():
    items = [
        (_meta("a", "X · v1", dedup_id="D"), "body"),
        (_meta("b", "X · v1", dedup_id="D"), "body"),
        (_meta("c", "Y · v1", dedup_id="E"), "other"),
    ]
    groups = lui._group_duplicate_stories(items)
    assert len(groups) == 1
    assert sorted(m["id"] for m in groups[0]) == ["a", "b"]


def test_group_duplicate_stories_fallback_old_stories():
    """Stories saved before dedup_id existed group by normalized body
    only — the title plays no part (titles can be edited)."""
    items = [
        (_meta("a", "X · v1"), "same body"),
        (_meta("b", "X · v1"), "same body"),   # two runs, same title
        (_meta("c", "Y · v9"), "same body"),   # title differs entirely
        (_meta("d", "X · v1"), "different body"),
        (_meta("e", "X · v1"), "   "),          # hollow: never grouped
        (_meta("f", "X · v1"), ""),
    ]
    groups = lui._group_duplicate_stories(items)
    assert len(groups) == 1
    assert sorted(m["id"] for m in groups[0]) == ["a", "b", "c"]


def test_remove_duplicate_stories_on_load_keeps_oldest(ui, monkeypatch):
    """End-to-end sweep: dupes removed via lib.delete_story (oldest
    kept), once per session."""
    fake, _saved, _tmp = ui
    metas = [
        _meta("old", "X · v1", created="2026-10-02T10:00:00"),
        _meta("new", "X · v1", created="2026-10-02T11:00:00"),
        _meta("solo", "Y · v1", created="2026-10-02T12:00:00"),
    ]
    bodies = {"old": "same body", "new": "same body", "solo": "other body"}
    deleted = []
    monkeypatch.setattr(lui.lib, "load_story",
                        lambda sid: {"script": bodies[sid]})
    monkeypatch.setattr(lui.lib, "delete_story",
                        lambda sid: deleted.append(sid) or True)

    assert lui._remove_duplicate_stories_on_load(metas) == 1
    assert deleted == ["new"]
    # Once per session — second call is a no-op.
    assert lui._remove_duplicate_stories_on_load(metas) == 0
    assert deleted == ["new"]
