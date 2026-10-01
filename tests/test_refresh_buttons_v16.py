"""v1.6 (#53/#54) — HIG progress buttons + concurrent refresh kinds.

#53: toolbar refresh buttons never change their label mid-work. While a
kind runs its button keeps its label, shows a CSS spinner (lib-spin-<kind>
marker), stays disabled, and keeps a stable width (use_container_width);
the outcome is reported once via a toast, never by mutating the button.

#54: "hashtags" and "images" are independent — they may run concurrently.
Only the SAME kind re-kick is refused, and "reset"/"enrich" stay exclusive.

Run: python -m pytest tests/test_refresh_buttons_v16.py -q
"""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import story_library as lib  # noqa: E402
from test_library_v15 import (  # noqa: E402
    _make_story,
    _settle_enrichment,
    _ui_with_fake_st,
    libdir,  # noqa: F401  (pytest fixture reuse)
)


# ---------------------------------------------------------------------------
# #54 — concurrency at the library layer
# ---------------------------------------------------------------------------

def _wait_idle(sid, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not lib.refresh_busy_kinds(lib.load_story(sid)["meta"]):
            return True
        time.sleep(0.05)
    return False


def test_hashtags_and_images_run_concurrently(libdir, monkeypatch):
    """#54 core: Update Images starts while Update Hashtags is in flight,
    both run at once, and neither worker's file write clobbers the other's.
    """
    sid = _make_story()
    _settle_enrichment(sid)
    tags_started = threading.Event()
    imgs_started = threading.Event()
    release = threading.Event()

    def _fake_tags(sid_, topic, ai_engine=None):
        tags_started.set()
        assert release.wait(timeout=10)
        lib.update_story_fields(sid_, hashtags=["#A", "#B"])
        return True, "added 2 hashtags"

    def _fake_imgs(sid_, topic):
        imgs_started.set()
        assert release.wait(timeout=10)
        lib.update_story_fields(sid_, image_urls=["http://x/y.jpg"])
        return True, "added 1 image"

    monkeypatch.setattr(lib, "refresh_hashtags", _fake_tags)
    monkeypatch.setattr(lib, "refresh_images", _fake_imgs)

    ok_tags, reason_tags = lib.start_refresh(sid, "hashtags")
    assert ok_tags, reason_tags
    # The #54 assertion: the second kick is NOT refused while the first
    # kind is still running.
    ok_imgs, reason_imgs = lib.start_refresh(sid, "images")
    assert ok_imgs, reason_imgs

    assert tags_started.wait(timeout=10)
    assert imgs_started.wait(timeout=10)
    # Both kinds genuinely in flight at the same moment.
    assert lib.refresh_busy_kinds(lib.load_story(sid)["meta"]) == {
        "hashtags", "images"}

    release.set()
    assert _wait_idle(sid), "workers did not finish"

    meta = lib.load_story(sid)["meta"]
    # Neither worker clobbered the other (per-story write lock).
    assert meta["hashtags"] == ["#A", "#B"]
    assert meta["image_urls"] == ["http://x/y.jpg"]
    assert lib.refresh_busy_kinds(meta) == set()
    outcomes = {json.loads(e)["kind"]: json.loads(e)
                for e in meta["refresh_outcome_pending"]}
    assert outcomes["hashtags"]["status"] == "succeeded"
    assert outcomes["images"]["status"] == "succeeded"


def test_reset_refused_while_hashtags_running(libdir, monkeypatch):
    """#54: Reset is destructive — it stays exclusive while any kind runs."""
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "hashtags")
    ok, reason = lib.start_refresh(sid, "reset")
    assert not ok
    assert "reset clears" in reason
    assert lib.refresh_busy_kinds(lib.load_story(sid)["meta"]) == {"hashtags"}


def test_hashtags_refused_while_reset_running(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "reset")
    ok, reason = lib.start_refresh(sid, "hashtags")
    assert not ok and "already running" in reason
    ok, reason = lib.start_refresh(sid, "images")
    assert not ok and "already running" in reason


def test_same_kind_second_kick_refused(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "images")
    ok, reason = lib.start_refresh(sid, "images")
    assert not ok and "already running" in reason


def test_enrich_blocks_manual_refresh(libdir):
    """Save-time enrichment is exclusive with manual refreshes."""
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "enrich")
    ok, reason = lib.start_refresh(sid, "hashtags")
    assert not ok and "enrichment" in reason


def test_finish_one_kind_keeps_other_busy(libdir):
    """#53/#54: finishing never clears a sibling kind's busy flag or its
    pending outcome."""
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "hashtags")
    lib._set_refresh_busy(sid, "images")

    lib._finish_refresh(sid, "hashtags", "succeeded", "added 2 hashtags")
    meta = lib.load_story(sid)["meta"]
    assert lib.refresh_busy_kinds(meta) == {"images"}
    assert meta["enrichment_status"] == "running"
    outcomes = [json.loads(e) for e in meta["refresh_outcome_pending"]]
    assert [(o["kind"], o["status"]) for o in outcomes] == [
        ("hashtags", "succeeded")]

    lib._finish_refresh(sid, "images", "no_change", "nothing new")
    meta = lib.load_story(sid)["meta"]
    assert lib.refresh_busy_kinds(meta) == set()
    assert meta["enrichment_status"] == "no_change"
    kinds = [json.loads(e)["kind"] for e in meta["refresh_outcome_pending"]]
    assert kinds == ["hashtags", "images"]


def test_outcome_pending_dedupes_per_kind(libdir):
    sid = _make_story()
    _settle_enrichment(sid)
    lib._set_refresh_busy(sid, "hashtags")
    lib._finish_refresh(sid, "hashtags", "succeeded", "first")
    lib._set_refresh_busy(sid, "hashtags")
    lib._finish_refresh(sid, "hashtags", "failed", "second")
    outcomes = [json.loads(e) for e in
                lib.load_story(sid)["meta"]["refresh_outcome_pending"]]
    # A new run drops the previous run's stale outcome (#53: the toast
    # always reports the latest run).
    assert [(o["kind"], o["status"], o["note"]) for o in outcomes] == [
        ("hashtags", "failed", "second")]


def test_legacy_busy_format_migrates(libdir, monkeypatch):
    """Stories written before the per-kind model map honestly: a known
    legacy kind stays that kind; #54 concurrency applies to it."""
    sid = _make_story()
    lib.update_story_fields(sid, enrichment_status="running",
                            refresh_kind="hashtags")
    meta = lib.load_story(sid)["meta"]
    assert lib.refresh_busy_kinds(meta) == {"hashtags"}
    # Images may run alongside the legacy hashtags refresh (#54) …
    gate = threading.Event()

    def _fake_imgs(sid_, topic):
        assert gate.wait(timeout=10)
        return False, "test done"

    monkeypatch.setattr(lib, "refresh_images", _fake_imgs)
    ok, reason = lib.start_refresh(sid, "images")
    assert ok, reason
    # … but the same kind is still refused.
    ok, reason = lib.start_refresh(sid, "hashtags")
    assert not ok and "already running" in reason
    gate.set()
    deadline = time.time() + 10
    while time.time() < deadline:
        pend = lib.load_story(sid)["meta"].get("refresh_outcome_pending") or []
        if any(json.loads(e)["kind"] == "images" for e in pend):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("images worker did not finish")
    # The legacy hashtags busy state survived the images run (per-kind).
    assert lib.refresh_busy_kinds(lib.load_story(sid)["meta"]) == {"hashtags"}


def test_legacy_unknown_kind_is_exclusive(libdir):
    """A busy legacy state with an unknown/empty kind maps to {"enrich"}
    (exclusive) — the old code blocked everything while busy."""
    sid = _make_story()
    lib.update_story_fields(sid, enrichment_status="pending", refresh_kind="")
    assert lib.refresh_busy_kinds(lib.load_story(sid)["meta"]) == {"enrich"}
    ok, _ = lib.start_refresh(sid, "hashtags")
    assert not ok


def test_recover_orphaned_clears_new_format(libdir, monkeypatch):
    """Startup recovery understands the per-kind list: each orphaned kind
    is cleared and gets an "interrupted" pending outcome (the #53 toast
    channel — the "Last refresh" caption is gone)."""
    monkeypatch.setattr(lib, "_RECOVERY_DONE", False)
    sid = _make_story()
    lib.update_story_fields(sid, refresh_busy=["images"],
                            enrichment_status="running", refresh_kind="")
    assert lib.recover_orphaned_refreshes() == 1
    meta = lib.load_story(sid)["meta"]
    assert lib.refresh_busy_kinds(meta) == set()
    assert meta["enrichment_status"] == "interrupted"
    outcomes = [json.loads(e) for e in meta["refresh_outcome_pending"]]
    assert len(outcomes) == 1
    assert outcomes[0]["kind"] == "images"
    assert outcomes[0]["status"] == "interrupted"
    assert "interrupted" in outcomes[0]["note"]


def test_parse_refresh_outcome():
    good = json.dumps({"kind": "hashtags", "status": "succeeded",
                       "note": "added 2"})
    assert lib.parse_refresh_outcome(good) == {
        "kind": "hashtags", "status": "succeeded", "note": "added 2"}
    assert lib.parse_refresh_outcome("garbage") is None
    assert lib.parse_refresh_outcome(None) is None
    assert lib.parse_refresh_outcome(json.dumps({"kind": "bogus",
                                                 "status": "succeeded"})) is None
    assert lib.parse_refresh_outcome(json.dumps({"kind": "images"})) is None


# ---------------------------------------------------------------------------
# #53 — HIG progress buttons at the UI layer
# ---------------------------------------------------------------------------

def _kind_button_kwargs(lui, **kw):
    d = dict(story_id="sid1", kind="hashtags", label=lui._TB_ICON_TAG,
             button_key="lib_tags_sid1", kick_label="hashtag",
             help_text="Update Hashtags",
             busy_kinds=set(), ai_engine=None)
    d.update(kw)
    return d


def test_kind_button_label_stable_while_running():
    """#53/#71/#90: while hashtags runs the icon button still reads the tag
    glyph (never "Updating Hashtags…"), is disabled, keeps full width, and
    the spin marker is emitted for the CSS spinner. The tooltip keeps the
    "Update Hashtags" label for discoverability."""
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(**_kind_button_kwargs(lui, busy_kinds={"hashtags"}))
    assert fake.buttons == [(lui._TB_ICON_TAG, "lib_tags_sid1")]
    kw = fake.button_kwargs[0]
    assert kw["disabled"] is True
    assert kw["use_container_width"] is True
    assert kw["help"] == "Update Hashtags"
    assert 'data-marker="lib-spin-hashtags"' in "".join(fake.markup)


def test_kind_button_idle_state():
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(**_kind_button_kwargs(lui))
    assert fake.buttons == [(lui._TB_ICON_TAG, "lib_tags_sid1")]
    assert fake.button_kwargs[0]["disabled"] is False
    assert fake.button_kwargs[0]["help"] == "Update Hashtags"
    assert "lib-spin-hashtags" not in "".join(fake.markup)


def test_kind_button_independent_while_sibling_runs():
    """#54: the images icon button stays enabled while hashtags runs."""
    lui, fake = _ui_with_fake_st()
    lui._render_kind_button(**_kind_button_kwargs(lui,
        kind="images", label=lui._TB_ICON_IMAGE, button_key="lib_imgs_sid1",
        kick_label="image", help_text="Update Images",
        busy_kinds={"hashtags"}))
    assert fake.buttons == [(lui._TB_ICON_IMAGE, "lib_imgs_sid1")]
    assert fake.button_kwargs[0]["disabled"] is False
    assert fake.button_kwargs[0]["help"] == "Update Images"
    assert "lib-spin-images" not in "".join(fake.markup)


def test_kind_button_click_kicks_refresh(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_tags_sid1",))
    calls = []
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (
                            calls.append((sid, kind, ai_engine)) or (True, "")))
    lui._render_kind_button(**_kind_button_kwargs(lui))
    assert calls == [("sid1", "hashtags", None)]
    assert fake.reran is True
    assert fake.errors == []


def test_kind_button_kick_failure_is_loud(monkeypatch):
    lui, fake = _ui_with_fake_st(clicks=("lib_tags_sid1",))
    monkeypatch.setattr(lui.lib, "start_refresh",
                        lambda sid, kind, ai_engine=None: (False, "boom"))
    lui._render_kind_button(**_kind_button_kwargs(lui))
    assert fake.errors == ["Could not start the hashtag refresh: boom"]
    assert fake.reran is False


def test_reset_popover_emits_spin_marker_while_resetting():
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", {"reset"}, ai_engine=None)
    assert 'data-marker="lib-spin-reset"' in "".join(fake.markup)
    assert fake.popover_kwargs["label"] == lui._TB_ICON_RESET
    assert fake.popover_kwargs["disabled"] is True


def _story_with_outcome(libdir, entries):
    sid = _make_story()
    lib.update_story_fields(
        sid, refresh_outcome_pending=[json.dumps(e) for e in entries])
    return sid


def test_fire_refresh_toasts_fires_once(libdir):
    """#53: each finished outcome toasts exactly once, then drains."""
    lui, fake = _ui_with_fake_st()
    sid = _story_with_outcome(libdir, [
        {"kind": "hashtags", "status": "succeeded", "note": "added 3 tags"}])
    meta = lib.load_story(sid)["meta"]

    lui._fire_refresh_toasts(sid, meta)
    assert fake.toasts == [("Hashtags updated — added 3 tags", "✅")]

    # Drained from the file: a second render toasts nothing.
    meta = lib.load_story(sid)["meta"]
    assert meta.get("refresh_outcome_pending") == []
    lui._fire_refresh_toasts(sid, meta)
    assert fake.toasts == [("Hashtags updated — added 3 tags", "✅")]


def test_fire_refresh_toasts_all_statuses(libdir):
    lui, fake = _ui_with_fake_st()
    sid = _story_with_outcome(libdir, [
        {"kind": "images", "status": "no_change", "note": "nothing new"},
        {"kind": "reset", "status": "failed", "note": "network down"},
        {"kind": "enrich", "status": "interrupted", "note": "restarted"},
    ])
    lui._fire_refresh_toasts(sid, lib.load_story(sid)["meta"])
    assert fake.toasts == [
        ("Images: nothing new — nothing new", "ℹ️"),
        ("Reset failed — network down", "⚠️"),
        ("Enrichment interrupted — restarted", "⚠️"),
    ]


def test_fire_refresh_toasts_malformed_drops_loudly(libdir):
    lui, fake = _ui_with_fake_st()
    sid = _story_with_outcome(libdir, [{"kind": "hashtags",
                                       "status": "succeeded", "note": "ok"}])
    lib.update_story_fields(
        sid, refresh_outcome_pending=["garbage",
                                      json.dumps({"kind": "images",
                                                  "status": "succeeded",
                                                  "note": "fresh"})])
    lui._fire_refresh_toasts(sid, lib.load_story(sid)["meta"])
    assert len(fake.errors) == 1
    assert "dropped" in fake.errors[0]
    # The malformed entry is dropped; the good one still toasts.
    assert fake.toasts == [("Images updated — fresh", "✅")]
    assert lib.load_story(sid)["meta"].get("refresh_outcome_pending") == []


def test_fire_refresh_toasts_no_pending_is_quiet(libdir):
    lui, fake = _ui_with_fake_st()
    sid = _make_story()
    lui._fire_refresh_toasts(sid, lib.load_story(sid)["meta"])
    assert fake.toasts == []
    assert fake.errors == []


def test_refresh_toast_texts():
    lui, _fake = _ui_with_fake_st()
    assert lui._refresh_toast_text("hashtags", "succeeded", "added 2") == \
        "Hashtags updated — added 2"
    assert lui._refresh_toast_text("images", "no_change", "") == \
        "Images: nothing new"
    assert lui._refresh_toast_text("reset", "failed", "boom") == \
        "Reset failed — boom"
    assert lui._refresh_toast_text("enrich", "interrupted", "restarted") == \
        "Enrichment interrupted — restarted"
