"""v1.6.3 (#303) — Hashtags / News Links two-panel card redesign.

Replaces the old single-row chip layouts (#283, #274) with two separate
cards side by side — Hashtags left, News Links right. Contract:

1. Panel header = title + Load more + Force fetch only (icon-only, no
   text labels, no emoji, no collapse chevron).
2. Load more = REAL network fetch: icon swaps to the native animated
   spinner while fetching, then appends the newly fetched results.
3. Force fetch = re-pulls the full set, with spinner state.
4. Fixed 3-row list height with internal scroll — loading more never
   resizes the panel.
5. Rows are read-only: no inline edit, no reorder — only the × remove.
6. No Add tag / Add news buttons anywhere in the panels.
7. News rows open the true article URL (not just domains).
8. Headlines locked to a single line with ellipsis.
9. Footer shows ONLY "Showing X of Y".

Backend: new "more_hashtags" refresh kind (sibling of "hashtags").

Run: python -m pytest tests/test_taglink_panels_303.py -q
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_library as lib  # noqa: E402
from test_library_v15 import libdir  # noqa: F401  (pytest fixture reuse)
from test_library_v15 import _settle_enrichment  # noqa: F401,E402
from test_one_row_toolbar_v16 import (  # noqa: E402
    _story,
    _ui_with_recording_st,
)


_TAGS = ["#Alpha", "#Beta", "#Gamma", "#Delta"]
_LINKS = [
    {"title": "Alpha headline", "source": "Alpha",
     "url": "https://a.example/story-1"},
    {"title": "Beta headline", "source": "Beta",
     "url": "https://b.example/story-2"},
]


def _css():
    src = (Path(__file__).resolve().parent.parent
           / "library_ui.py").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", src, flags=re.S)


# ---------------------------------------------------------------------------
# backend: the more_hashtags refresh kind
# ---------------------------------------------------------------------------

def _story_with_tags(monkeypatch, tags):
    sid = lib.save_story(title="T", tone="", hashtags=list(tags),
                         dialogue_md="", script_md="x",
                         source_topic="test topic")
    _settle_enrichment(sid)
    return sid


def test_more_hashtags_is_a_known_refresh_kind():
    assert "more_hashtags" in lib._REFRESH_KINDS


def test_more_hashtags_sibling_of_hashtags():
    assert lib._SIBLING_KINDS["hashtags"] == "more_hashtags"
    assert lib._SIBLING_KINDS["more_hashtags"] == "hashtags"


def test_start_refresh_accepts_more_hashtags(libdir, monkeypatch):
    sid = _story_with_tags(monkeypatch, ["#Old"])
    # Neuter the worker thread: the kick must still be accepted and mark
    # the kind busy (the neutered worker never finishes, so busy stays
    # set deterministically — no thread race).
    monkeypatch.setattr(lib, "_refresh_worker", lambda *a, **k: None)
    ok, reason = lib.start_refresh(sid, "more_hashtags", ai_engine="Dummy")
    assert ok, f"more_hashtags must start; got {reason!r}"
    try:
        assert "more_hashtags" in lib.refresh_busy_kinds(
            lib.load_story(sid)["meta"])
        ok2, _ = lib.start_refresh(sid, "more_hashtags", ai_engine="Dummy")
        assert not ok2, "second kick while busy must be refused, not stacked"
    finally:
        lib._finish_refresh(sid, "more_hashtags", "succeeded", "test done")


def test_start_refresh_refuses_sibling_while_hashtags_runs(libdir,
                                                           monkeypatch):
    sid = _story_with_tags(monkeypatch, ["#Old"])
    assert lib._set_refresh_busy(sid, "hashtags") is True
    try:
        ok, reason = lib.start_refresh(sid, "more_hashtags",
                                       ai_engine="Dummy")
        assert not ok, "sibling kinds must not run together"
        assert "already running" in reason and "hashtags" in reason, (
            f"sibling refusal must name the running kind; saw {reason!r}")
    finally:
        lib._finish_refresh(sid, "hashtags", "succeeded", "test done")


def test_load_more_hashtags_appends_new_only(libdir, monkeypatch):
    sid = _story_with_tags(monkeypatch, ["#Old", "#Keep"])
    monkeypatch.setattr(
        lib, "_suggest_hashtags",
        lambda story, topic, eng: (["#Old", "#Fresh1", "#Fresh2"], "n"))
    changed, note = lib.load_more_hashtags(sid, "test topic", "Dummy")
    assert changed is True
    story = lib.load_story(sid)
    assert story["meta"]["hashtags"] == [
        "#Old", "#Keep", "#Fresh1", "#Fresh2"], (
        "existing tags never wiped/reordered; only genuinely new appended")
    assert "2" in note


def test_load_more_hashtags_no_new_is_honest(libdir, monkeypatch):
    sid = _story_with_tags(monkeypatch, ["#Old"])
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, eng: (["#Old"], "n"))
    changed, note = lib.load_more_hashtags(sid, "test topic", "Dummy")
    assert changed is False
    assert "No new hashtags" in note
    assert lib.load_story(sid)["meta"]["hashtags"] == ["#Old"]


def test_load_more_hashtags_fails_loudly(libdir):
    with pytest.raises(RuntimeError):
        lib.load_more_hashtags("no-such-story", "t", "Dummy")
    sid = lib.save_story(title="T", tone="", hashtags=[], dialogue_md="",
                         script_md="x", source_topic="test topic")
    with pytest.raises(RuntimeError):
        lib.load_more_hashtags(sid, "test topic", None)


def test_refresh_worker_routes_more_hashtags(libdir, monkeypatch):
    """The daemon worker dispatches the new kind (fail-loud on error)."""
    sid = _story_with_tags(monkeypatch, ["#Old"])
    monkeypatch.setattr(lib, "_suggest_hashtags",
                        lambda story, topic, eng: (["#W1"], "n"))
    lib._refresh_worker(sid, "more_hashtags", "test topic", "Dummy")
    story = lib.load_story(sid)
    assert story["meta"]["hashtags"] == ["#Old", "#W1"]
    # terminal state written, busy cleared
    assert "more_hashtags" not in lib.refresh_busy_kinds(story["meta"])


# ---------------------------------------------------------------------------
# old single-row layout is gone
# ---------------------------------------------------------------------------

def test_old_row_components_removed():
    lui, _ = _ui_with_recording_st()
    for name in ("_render_hashtags_row", "_render_news_links_row",
                 "_news_chip_label", "_chip_col_weights",
                 "_section_title_weight"):
        assert not hasattr(lui, name), (
            f"{name} must be gone with the old row layout")


def test_old_toolbar_refresh_buttons_removed(libdir, monkeypatch):
    """The hashtag/news refresh buttons moved into the panel headers —
    only the Images refresh keeps a toolbar slot."""
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, hashtags=_TAGS, news_links=_LINKS)
    lui._render_story_detail("sid1")

    keys = [b[1] for b in fake.buttons]
    assert "lib_tags_sid1" not in keys, "toolbar hashtag button must be gone"
    assert "lib_news_sid1" not in keys, "toolbar news button must be gone"
    assert "lib_imgs_sid1" in keys, "toolbar images button stays"


# ---------------------------------------------------------------------------
# panel section contract
# ---------------------------------------------------------------------------

def _render_section(libdir, monkeypatch, tags=_TAGS, links=_LINKS):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui, hashtags=list(tags),
           news_links=[dict(l) for l in links])
    lui._render_story_detail("sid1")
    return lui, fake


def test_two_panels_side_by_side(libdir, monkeypatch):
    lui, fake = _render_section(libdir, monkeypatch)

    assert 2 in fake.column_specs, (
        f"panels must sit in a 2-column layout; saw {fake.column_specs}")
    titles = [m for m in fake.markup if "lib-panel-title" in m]
    assert len(titles) == 2, f"two panel titles expected; saw {titles}"
    assert "Hashtags" in titles[0] and "News Links" in titles[1], (
        "Hashtags left, News Links right")


def test_section_uses_divider(libdir, monkeypatch):
    _, fake = _render_section(libdir, monkeypatch)
    assert fake.dividers != [], "panels section must use st.divider()"


def test_no_add_buttons_anywhere(libdir, monkeypatch):
    _, fake = _render_section(libdir, monkeypatch)
    for label, key in fake.buttons:
        text = f"{label} {(key or '')}".lower()
        assert "add tag" not in text and "add news" not in text, (
            f"no Add buttons allowed in the panels; saw {(label, key)}")


def test_rows_are_read_only(libdir, monkeypatch):
    """No inline edit affordances inside the panels — × is the only
    row control."""
    lui, fake = _ui_with_recording_st()
    lui._render_tag_link_panels(
        story_id="sid1", tags=_TAGS, links=_LINKS, busy_kinds=set(),
        ai_engine="Dummy")

    edit_buttons = [b for b in fake.buttons if b[0] == "✎"]
    assert not edit_buttons, f"no inline edit in panels; saw {fake.buttons}"
    text_inputs = [m for m in fake.markup if "<input" in m]
    assert not text_inputs, "no editable inputs in panel rows"


def test_footer_format_both_panels(libdir, monkeypatch):
    """Each panel footer reads ONLY 'Showing X of Y' — no other text."""
    lui, fake = _ui_with_recording_st()
    lui._render_tag_link_panels(
        story_id="sid1", tags=_TAGS, links=_LINKS, busy_kinds=set(),
        ai_engine="Dummy")

    assert fake.captions == ["Showing 4 of 4", "Showing 2 of 2"], (
        f"footers must read only 'Showing X of Y'; saw {fake.captions}")


def test_css_single_line_ellipsis_rules():
    clean = _css()
    assert ".lib-panel-row" in clean
    # rows + news headline anchors: single line, ellipsis, never wrap
    assert clean.count("text-overflow: ellipsis") >= 2
    assert "white-space: nowrap" in clean


def test_css_no_hardcoded_colors_in_panel_rules():
    """Panel CSS uses tokens/currentColor/inherit — never literals."""
    clean = _css()
    idx = clean.find(".lib-panel-title")
    assert idx != -1
    block = clean[idx:clean.find("}", idx)]
    assert "#" not in block and "rgb" not in block, (
        f"panel title CSS must not hard-code colors; saw {block!r}")


def test_hashtags_load_more_kicks_real_fetch(libdir, monkeypatch):
    """Tapping Load more in the hashtags panel starts a real
    more_hashtags refresh (not a reveal of pre-loaded items)."""
    lui, fake = _ui_with_recording_st(clicks=("lib_panel_moretags_sid1",))
    _story(monkeypatch, lui, hashtags=_TAGS, news_links=[])
    started = []

    def fake_start(sid, kind, ai_engine=None):
        started.append((sid, kind, ai_engine))
        return True, ""

    monkeypatch.setattr(lui.lib, "start_refresh", fake_start)
    lui._render_story_detail("sid1")

    assert any(s[1] == "more_hashtags" for s in started), (
        f"Load more must kick a more_hashtags refresh; saw {started}")


def test_news_load_more_kicks_real_fetch(libdir, monkeypatch):
    lui, fake = _ui_with_recording_st(clicks=("lib_panel_morenews_sid1",))
    _story(monkeypatch, lui, hashtags=[], news_links=_LINKS)
    started = []
    monkeypatch.setattr(
        lui.lib, "start_refresh",
        lambda sid, kind, ai_engine=None: (started.append(kind), (True, ""))[1])
    lui._render_story_detail("sid1")

    assert "more_news" in started, (
        f"Load more must kick a more_news refresh; saw {started}")
