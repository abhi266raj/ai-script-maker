"""Tests for script versioning (#104): multiple versions per story, latest on
top, exactly one default, v1 protected, default mirrored into ## Script.

Run: python -m pytest tests/test_script_versioning.py -q
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


def _make_story(script="AARAV: original script text here"):
    return lib.save_story(
        title="Versioning Reel",
        tone="funny",
        hashtags=["#Test"],
        dialogue_md="",
        script_md=script,
        source_topic="t",
        source_headline="h",
    )


def _versions_path(sid):
    return lib.stories_dir() / f"{sid}.versions.json"


# --- migration -------------------------------------------------------------

def test_migration_seeds_v1_from_legacy_script(libdir):
    sid = _make_story()
    assert not _versions_path(sid).exists()
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [1]
    assert default_n == 1
    assert versions[0]["text"] == "AARAV: original script text here"
    # Migration persisted the sidecar.
    assert _versions_path(sid).exists()


def test_migration_preserves_multiline_script(libdir):
    sid = _make_story(script="LINE ONE\nLINE TWO\n\nLINE THREE")
    versions, _ = lib.get_script_versions(sid)
    assert versions[0]["text"] == "LINE ONE\nLINE TWO\n\nLINE THREE"


# --- creation & ordering ---------------------------------------------------

def test_create_versions_latest_first(libdir):
    sid = _make_story()
    n2 = lib.create_script_version(sid)
    n3 = lib.create_script_version(sid)
    assert (n2, n3) == (2, 3)
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [3, 2, 1]
    # New versions are seeded from the default text, and the default is untouched.
    assert default_n == 1
    assert versions[0]["text"] == "AARAV: original script text here"
    # Numbering never reuses deleted numbers.
    lib.delete_script_version(sid, 3)
    assert lib.create_script_version(sid) == 4


# --- default ---------------------------------------------------------------

def test_single_default_and_md_mirror(libdir):
    sid = _make_story()
    lib.create_script_version(sid)
    lib.update_script_version_text(sid, 2, "AARAV: second take")
    lib.set_default_script_version(sid, 2)
    versions, default_n = lib.get_script_versions(sid)
    assert default_n == 2
    assert sum(1 for _ in [default_n]) == 1  # exactly one default recorded
    # The .md ## Script section mirrors the default → Copy/Share/export unchanged.
    assert lib.load_story(sid)["script"] == "AARAV: second take"
    # Switching back restores v1's text.
    lib.set_default_script_version(sid, 1)
    _, default_n = lib.get_script_versions(sid)
    assert default_n == 1
    assert lib.load_story(sid)["script"] == "AARAV: original script text here"


def test_set_default_unknown_version_raises(libdir):
    sid = _make_story()
    with pytest.raises(ValueError):
        lib.set_default_script_version(sid, 99)


# --- editing ---------------------------------------------------------------

def test_edit_default_updates_md_script(libdir):
    sid = _make_story()
    lib.update_script_version_text(sid, 1, "AARAV: edited original")
    assert lib.load_story(sid)["script"] == "AARAV: edited original"
    versions, _ = lib.get_script_versions(sid)
    assert versions[0]["text"] == "AARAV: edited original"


def test_edit_nondefault_keeps_md_on_default(libdir):
    sid = _make_story()
    lib.create_script_version(sid)
    lib.set_default_script_version(sid, 2)
    lib.update_script_version_text(sid, 1, "AARAV: v1 reworked")
    # .md still shows the default (v2), not the edited v1.
    assert lib.load_story(sid)["script"] == "AARAV: original script text here"
    versions, _ = lib.get_script_versions(sid)
    by_n = {v["n"]: v["text"] for v in versions}
    assert by_n[1] == "AARAV: v1 reworked"


def test_edit_blank_text_rejected(libdir):
    sid = _make_story()
    with pytest.raises(ValueError):
        lib.update_script_version_text(sid, 1, "   ")


def test_edit_unknown_version_raises(libdir):
    sid = _make_story()
    with pytest.raises(ValueError):
        lib.update_script_version_text(sid, 42, "nope")


# --- deletion --------------------------------------------------------------

def test_delete_nondefault_version(libdir):
    sid = _make_story()
    lib.create_script_version(sid)
    lib.create_script_version(sid)
    lib.delete_script_version(sid, 2)
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [3, 1]
    assert default_n == 1


def test_delete_v1_protected(libdir):
    sid = _make_story()
    lib.create_script_version(sid)
    with pytest.raises(ValueError, match="v1"):
        lib.delete_script_version(sid, 1)
    versions, _ = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [2, 1]


def test_delete_default_falls_back_to_v1(libdir):
    sid = _make_story()
    lib.create_script_version(sid)
    lib.update_script_version_text(sid, 2, "AARAV: second take")
    lib.set_default_script_version(sid, 2)
    lib.delete_script_version(sid, 2)
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [1]
    assert default_n == 1
    assert lib.load_story(sid)["script"] == "AARAV: original script text here"


def test_delete_unknown_version_raises(libdir):
    sid = _make_story()
    with pytest.raises(ValueError):
        lib.delete_script_version(sid, 7)


# --- corruption & edge cases ------------------------------------------------

def test_corrupt_sidecar_raises_loudly(libdir):
    sid = _make_story()
    lib.get_script_versions(sid)  # migrate first
    _versions_path(sid).write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Corrupt script versions"):
        lib.get_script_versions(sid)


def test_structurally_bad_sidecar_raises_loudly(libdir):
    sid = _make_story()
    lib.get_script_versions(sid)
    _versions_path(sid).write_text(
        json.dumps({"default": 5, "versions": [{"n": 1, "text": "x"}]}),
        encoding="utf-8")
    with pytest.raises(ValueError, match="Corrupt script versions"):
        lib.get_script_versions(sid)


def test_unknown_story_raises(libdir):
    with pytest.raises(FileNotFoundError):
        lib.get_script_versions("no-such-story-123")


def test_delete_story_removes_sidecar(libdir):
    sid = _make_story()
    lib.get_script_versions(sid)
    assert _versions_path(sid).exists()
    lib.delete_story(sid)
    assert not _versions_path(sid).exists()


# --- #105 × #104 integration ------------------------------------------------

def test_fine_tune_turn_creates_new_default_version(libdir):
    # #191: a fine-tune turn saves the refined script as a NEW version —
    # latest on top and the default — so the versions list displays it
    # immediately (it expands the latest). The old in-place overwrite of
    # the default version's text hid the result inside a collapsed
    # "Version N · Default" expander whenever the latest version wasn't
    # the default, while the expanded latest version still showed old text.
    sid = _make_story()
    lib.create_script_version(sid)  # v2, latest, NOT the default
    lib.record_fine_tune_turn(sid, "make it funnier", "AARAV: much funnier now")
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [3, 2, 1]  # latest on top
    assert default_n == 3
    by_n = {v["n"]: v["text"] for v in versions}
    assert by_n[3] == "AARAV: much funnier now"
    assert by_n[1] == "AARAV: original script text here"  # untouched
    assert by_n[2] == "AARAV: original script text here"  # untouched
    # The ## Script mirror (what Copy / Share / export use) follows the
    # new default.
    assert lib.load_story(sid)["script"] == "AARAV: much funnier now"
    # The history turn is still recorded.
    history = lib.get_fine_tune_history(sid)
    assert len(history) == 1
    assert history[0]["script"] == "AARAV: much funnier now"


def test_fine_tune_turn_when_latest_is_default(libdir):
    # Single-version story: the turn still creates a new version (v2)
    # holding the refined text; the pre-turn text stays recoverable as v1.
    sid = _make_story()
    lib.record_fine_tune_turn(sid, "tighten it", "AARAV: tightened")
    versions, default_n = lib.get_script_versions(sid)
    assert [v["n"] for v in versions] == [2, 1]
    assert default_n == 2
    by_n = {v["n"]: v["text"] for v in versions}
    assert by_n[2] == "AARAV: tightened"
    assert by_n[1] == "AARAV: original script text here"
    assert lib.load_story(sid)["script"] == "AARAV: tightened"


# --- persistence round-trip -------------------------------------------------

def test_versions_survive_reload(libdir):
    sid = _make_story()
    lib.create_script_version(sid)
    lib.update_script_version_text(sid, 2, "AARAV: take two\nsecond line")
    lib.set_default_script_version(sid, 2)
    # Fresh read straight from disk (simulates a new process).
    raw = json.loads(_versions_path(sid).read_text(encoding="utf-8"))
    assert raw["default"] == 2
    assert [v["n"] for v in raw["versions"]] == [1, 2]
    versions, default_n = lib.get_script_versions(sid)
    assert default_n == 2
    by_n = {v["n"]: v["text"] for v in versions}
    assert by_n[2] == "AARAV: take two\nsecond line"
    assert lib.load_story(sid)["script"] == "AARAV: take two\nsecond line"
