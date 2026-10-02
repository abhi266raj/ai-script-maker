"""Issue #279 — library auto-save duplicates scripts when browsing.

`maybe_autosave_story` guarded reruns with a single scalar
(`lib_autosaved_for`) that remembered only the LAST save. Browsing
A -> B -> A -> C -> B overwrote the guard on every hop, so the
already-saved A and B were saved AGAIN: 5 library entries for 3
scripts (real Mac evidence, /Users/abhiraj/Documents/HindiReelStudio/stories/,
2026-10-02). This was NOT the #138 generation-duplication bug — the
#138 gates held (3 distinct scripts); only the auto-save guard doubled up.

The fix keeps a SET of completed guard strings
(`lib_autosaved_guards`): each (batch result, script) pair saves at
most once per session, no matter how the user navigates.

Covers: the A->B->A->C->B regression (must FAIL on pristine develop),
repeat-rerun guard preserved, empty-screenplay fail-loud path unchanged,
and the manual "Save to Library" fallback marking the guard so a later
auto-save of the same guard skips.

Run: python -m pytest tests/test_autosave_duplicates_279.py -q
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import library_ui as lui  # noqa: E402


class _FakeSt:
    """Minimal Streamlit stub capturing what the auto-save path touches:
    session_state, error, button, rerun, toast."""

    def __init__(self):
        self.session_state = {}
        self.errors = []
        self.buttons = []           # labels, in render order
        self.button_results = {}
        self.toasts = []            # (msg, icon) tuples
        self.reruns = 0

    def error(self, text, **kw):
        self.errors.append(text)

    def button(self, label, **kw):
        self.buttons.append(label)
        return self.button_results.get(label, False)

    def rerun(self):
        self.reruns += 1

    def toast(self, msg, icon=None):
        self.toasts.append((msg, icon))


class _Script:
    def __init__(self, sid):
        self.id = sid


@pytest.fixture
def ui(monkeypatch, tmp_path):
    """library_ui with `st` stubbed; `_save_current_story` replaced by a
    fake that writes one marker file per script id into tmp_path (the
    "on disk" assertion), and `start_enrichment` neutralized."""
    fake = _FakeSt()
    monkeypatch.setattr(lui, "st", fake)
    saved = []

    def fake_save(batch_result, script, pro_screenplay=""):
        if not (pro_screenplay or "").strip():
            raise ValueError("Cannot save: the final-stage screenplay text is empty.")
        marker = tmp_path / f"story-{script.id}.md"
        marker.write_text(pro_screenplay, encoding="utf-8")
        saved.append(script.id)
        return f"story-id-{script.id}"

    monkeypatch.setattr(lui, "_save_current_story", fake_save)
    monkeypatch.setattr(lui.lib, "start_enrichment",
                        lambda story_id, topic: (True, "ok"))
    return fake, saved, tmp_path


def _view(fake, batch, script, idx, text=None):
    """Simulate the user viewing `script` at selection index `idx`."""
    fake.session_state["selected_script_idx"] = idx
    lui.maybe_autosave_story(batch, script,
                             text if text is not None else f"screenplay-{script.id}")


# ---------------------------------------------------------------------------
# #279 regression: A -> B -> A -> C -> B must save each script exactly once
# ---------------------------------------------------------------------------

def test_browsing_a_b_a_c_b_saves_each_script_once(ui):
    fake, saved, tmp_path = ui
    batch = object()  # one finished batch, like the real session state holds
    a, b, c = _Script("A"), _Script("B"), _Script("C")

    for script, idx in [(a, 0), (b, 1), (a, 0), (c, 2), (b, 1)]:
        _view(fake, batch, script, idx)

    assert saved == ["A", "B", "C"], \
        f"#279: browsing re-saved scripts, save order was {saved}"
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["story-A.md", "story-B.md", "story-C.md"], \
        f"#279: duplicate entries on disk: {files}"


def test_repeat_reruns_of_same_script_save_once(ui):
    """The original rerun guard still holds: same script, same index,
    repeated calls (Streamlit reruns) save exactly once."""
    fake, saved, tmp_path = ui
    batch = object()
    a = _Script("A")
    for _ in range(3):
        _view(fake, batch, a, 0)

    assert saved == ["A"], saved
    assert [p.name for p in tmp_path.iterdir()] == ["story-A.md"]


def test_empty_screenplay_fails_loudly_without_saving(ui):
    """Fail-loud contract unchanged: no silent save, st.error surfaced,
    manual fallback offered, nothing persisted."""
    fake, saved, tmp_path = ui
    batch = object()
    _view(fake, batch, _Script("A"), 0, text="")

    assert saved == [], "nothing may be saved without the final-stage text"
    assert list(tmp_path.iterdir()) == []
    assert any("Auto-save to library failed" in e for e in fake.errors), \
        f"failure must surface loudly, got errors={fake.errors}"
    assert "Save to Library" in fake.buttons, \
        "manual fallback button must be offered on failure"


def test_manual_save_fallback_marks_guard(ui):
    """After a manual save via the fallback, a later auto-save of the
    same guard must skip — the fallback marks the same completed set."""
    fake, saved, tmp_path = ui
    batch = object()
    a = _Script("A")
    fake.session_state["selected_script_idx"] = 0
    guard = f"{id(batch)}:{a.id}:0"

    # Failure path first: empty text -> loud error, fallback offered.
    lui.maybe_autosave_story(batch, a, "")
    assert saved == []

    # User clicks the manual save button with the real final-stage text.
    fake.button_results["Save to Library"] = True
    lui._render_manual_save_fallback(batch, a, guard, "screenplay-A")
    assert saved == ["A"], saved

    # A later auto-save of the same guard must not duplicate it.
    lui.maybe_autosave_story(batch, a, "screenplay-A")
    assert saved == ["A"], f"manual save must mark the guard, got {saved}"
