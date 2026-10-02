"""#291 full-UUID4 story IDs + #264 icon-only Refresh button.

#291: ``new_story_id()`` must return ``uuid.uuid4().hex`` (32 lowercase hex
chars). Existing timestamp-prefixed IDs stay valid (no migration), and
``list_stories()`` sorts on ``created_at``, not filename.
#264: the source-page Refresh button is icon-only (no text label) while
keeping its hover help tag.
"""
import ast
import re
import sys
import uuid as _uuid
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


def _save(title):
    return lib.save_story(
        title=title, tone="funny", hashtags=[], dialogue_md="",
        script_md="a line", source_topic="t", source_headline="h")


# ---------------------------------------------------------------------------
# #291 — full UUID4 story IDs
# ---------------------------------------------------------------------------

def test_new_story_id_is_full_uuid4_hex():
    sid = lib.new_story_id()
    assert re.fullmatch(r"[0-9a-f]{32}", sid), \
        f"new story id must be full UUID4 hex, got {sid!r}"
    assert _uuid.UUID(sid).version == 4


def test_new_story_ids_are_unique():
    ids = {lib.new_story_id() for _ in range(2000)}
    assert len(ids) == 2000


def test_legacy_timestamp_ids_remain_valid():
    # No migration: IDs minted before #291 must keep working.
    old = "20261002-113022-a1b2c3"
    assert lib._check_id(old) == old
    assert lib.story_path(old).name == f"{old}.md"


def test_list_stories_sorts_on_created_at_not_filename(libdir):
    # Filenames (UUIDs) carry no time order; created_at decides recency.
    s1, s2, s3 = _save("A"), _save("B"), _save("C")
    lib.update_story_fields(s1, created_at="2026-10-02T12:00:01")
    lib.update_story_fields(s2, created_at="2026-10-02T10:00:01")
    lib.update_story_fields(s3, created_at="2026-10-02T11:00:01")
    assert [m["id"] for m in lib.list_stories()] == [s1, s3, s2]


# ---------------------------------------------------------------------------
# #264 — Refresh button is icon-only
# ---------------------------------------------------------------------------

def _refresh_news_call():
    src = (Path(__file__).resolve().parent.parent / "app.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "button"):
            keys = {k.arg: k.value for k in node.keywords}
            key = keys.get("key")
            if isinstance(key, ast.Constant) and key.value == "refresh_news":
                label = node.args[0].value if node.args else None
                icon = keys.get("icon")
                helpv = keys.get("help")
                return (
                    label,
                    icon.value if isinstance(icon, ast.Constant) else None,
                    helpv.value if isinstance(helpv, ast.Constant) else None,
                )
    raise AssertionError("refresh_news button not found in app.py")


def test_refresh_button_is_icon_only():
    label, icon, helpv = _refresh_news_call()
    assert label == "", \
        f"Refresh button must have no text label (icon-only rule), got {label!r}"
    assert icon == ":material/refresh:"
    assert helpv and helpv.strip(), \
        "icon-only button must keep its hover help tag"
