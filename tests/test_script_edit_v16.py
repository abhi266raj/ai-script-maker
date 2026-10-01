"""Tests for issue #31 (v1.6): editing the saved screenplay text.

Covers lib.update_story_script: edit round-trip persistence, preservation
of title/dialogue/frontmatter, and fail-loud behavior (missing story,
blank script, invalid id).

Run: python -m pytest tests/test_script_edit_v16.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import story_library as lib  # noqa: E402


@pytest.fixture
def libdir(tmp_path, monkeypatch):
    root = tmp_path / "HindiReelStudio"
    monkeypatch.setattr(lib, "LIBRARY_ROOT", root)
    monkeypatch.setattr(lib, "STORIES_DIR", root / "stories")
    monkeypatch.setattr(lib, "PREFS_PATH", root / "prefs.json")
    return root


def _make_story(**kw):
    kw.setdefault("title", "Dog Showdown Reel")
    kw.setdefault("tone", "funny")
    kw.setdefault("hashtags", ["#DogShowdown"])
    kw.setdefault("dialogue_md", "> **AARAV:** chubby dogs vote")
    kw.setdefault("script_md", "AARAV: chubby dogs voting contest in the park")
    kw.setdefault("source_topic", "chubby dogs voting contest")
    kw.setdefault("source_headline", "Chubby dogs battle in voting contest")
    return lib.save_story(**kw)


def test_update_script_round_trip(libdir):
    sid = _make_story()
    lib.update_story_script(sid, "AARAV: edited script text\n\nVIKRAM: second line")
    story = lib.load_story(sid)
    assert story["script"] == "AARAV: edited script text\n\nVIKRAM: second line"


def test_update_script_preserves_everything_else(libdir):
    sid = _make_story()
    before = lib.load_story(sid)
    lib.update_story_script(sid, "AARAV: brand new script")
    after = lib.load_story(sid)
    assert after["meta"]["title"] == before["meta"]["title"]
    assert after["meta"]["hashtags"] == before["meta"]["hashtags"]
    assert after["meta"]["tone"] == before["meta"]["tone"]
    assert after["meta"]["source_topic"] == before["meta"]["source_topic"]
    assert after["dialogue"] == before["dialogue"]
    assert after["script"] == "AARAV: brand new script"


def test_update_script_missing_story_raises(libdir):
    # Fail loud: no silent no-op when the story is gone.
    with pytest.raises(FileNotFoundError):
        lib.update_story_script("deadbeef-1234", "AARAV: hello")


def test_update_script_rejects_blank(libdir):
    sid = _make_story()
    for blank in ("", "   ", "\n\n"):
        with pytest.raises(ValueError):
            lib.update_story_script(sid, blank)
    # The failed attempts left the original script untouched.
    assert lib.load_story(sid)["script"] == \
        "AARAV: chubby dogs voting contest in the park"


def test_update_script_invalid_id_raises(libdir):
    with pytest.raises(ValueError):
        lib.update_story_script("../../etc/passwd", "AARAV: hello")


def test_update_script_survives_second_edit(libdir):
    sid = _make_story()
    lib.update_story_script(sid, "first edit")
    lib.update_story_script(sid, "second edit")
    assert lib.load_story(sid)["script"] == "second edit"
