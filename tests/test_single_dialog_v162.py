"""Tests for #130: single shared delete-confirmation dialog.

Streamlit allows only ONE dialog per script run. PR #123 gave each delete
button its own dialog, crashing pages with multiple delete buttons.
The fix: each trigger records its target in ``st.session_state["_pending_delete"]``
and ONE module-level dialog (``_delete_confirm_dialog``) is invoked at most
once per run via ``_maybe_open_delete_dialog()``.
"""

import sys
import types


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeSt:
    """Minimal streamlit stand-in for the #130 shared-dialog logic."""

    def __init__(self, clicks=()):
        self._clicks = set(clicks)
        self.session_state = {}
        self.errors = []
        self.successes = []
        self.reran = False
        self.dialogs = []  # titles of dialogs actually INVOKED (not decorated)
        self.buttons = []  # (label, key) in render order
        self.button_kwargs = []
        self.markup = []
        self.captions = []

    def markdown(self, *a, **k):
        self.markup.append(a[0] if a else "")

    def caption(self, *a, **k):
        self.captions.append(a[0] if a else "")

    def success(self, msg):
        self.successes.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    def rerun(self):
        self.reran = True

    def button(self, label, key=None, on_click=None, **k):
        self.buttons.append((label, key))
        self.button_kwargs.append({"label": label, "key": key, **k})
        if key in self._clicks:
            if on_click is not None:
                on_click()
            return True
        return False

    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [_FakeCtx() for _ in range(n)]

    def dialog(self, title, **k):
        # st.dialog is a decorator at import time; the returned function,
        # when CALLED, records the invocation.
        def _deco(fn):
            def _wrapper(*a, **kw):
                self.dialogs.append(title)
                return fn(*a, **kw)
            return _wrapper
        return _deco


def _ui_with_fake_st(clicks=()):
    """Import library_ui bound to a fake streamlit; restores sys.modules."""
    saved = dict(sys.modules)
    fake = _FakeSt(clicks)
    try:
        fake_mod = types.ModuleType("streamlit")
        for name in ("markdown", "caption", "success", "error", "rerun",
                     "button", "columns", "dialog"):
            setattr(fake_mod, name, getattr(fake, name))
        fake_mod.session_state = fake.session_state
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        # Stub story_library to avoid import-time side effects.
        lib_mod = types.ModuleType("story_library")
        lib_mod.delete_story = lambda sid: True
        lib_mod.delete_all_stories = lambda: 2
        sys.modules["story_library"] = lib_mod
        import library_ui
        return library_ui, fake
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _story_kwargs(**kw):
    d = dict(trigger_label="", trigger_icon=":material/delete:",
             popover_key="lib_delpop_s1", title='Delete "My Story"?',
             message="This can't be undone.",
             on_yes=lambda: None, trigger_help="Delete this story",
             destructive_label="Delete story",
             _pending_delete_kind="story", _pending_delete_story_id="s1")
    d.update(kw)
    return d


def _all_kwargs(**kw):
    d = dict(trigger_label="Delete All", popover_key="lib_delpop_all",
             title="Delete all stories?",
             message="Every saved story will be permanently deleted.",
             on_yes=lambda: None, trigger_help="Delete every saved story",
             destructive_label="Delete all stories",
             _pending_delete_kind="all")
    d.update(kw)
    return d


def test_trigger_sets_pending_delete_and_reruns():
    # #130: tapping a delete trigger records the target — it does NOT open
    # a dialog itself.
    lui, fake = _ui_with_fake_st(clicks=("lib_delpop_s1-trigger",))
    lui._delete_popover(**_story_kwargs())
    _pending = fake.session_state.get(lui._PENDING_DELETE_KEY)
    assert _pending is not None
    assert _pending["kind"] == "story"
    assert _pending["story_id"] == "s1"
    assert _pending["title"] == 'Delete "My Story"?'
    assert _pending["destructive_label"] == "Delete story"
    assert fake.reran is True
    assert fake.dialogs == []  # no dialog invoked by the trigger


def test_no_pending_no_dialog():
    # #130: with no pending delete, the shared dialog is never invoked —
    # pages with N delete buttons render clean.
    lui, fake = _ui_with_fake_st()
    lui._delete_popover(**_story_kwargs())
    lui._delete_popover(**_all_kwargs())
    lui._maybe_open_delete_dialog()
    assert fake.dialogs == []


def test_pending_opens_single_dialog_with_correct_target():
    # #130: one pending delete → exactly one dialog invocation, rendering
    # the correct title/message/verb for that target.
    lui, fake = _ui_with_fake_st()
    fake.session_state[lui._PENDING_DELETE_KEY] = {
        "kind": "story", "story_id": "s1",
        "title": 'Delete "My Story"?',
        "message": "This can't be undone.",
        "destructive_label": "Delete story",
    }
    lui._maybe_open_delete_dialog()
    assert fake.dialogs == ["Delete"]  # exactly one dialog
    # The specific title is rendered inside the dialog body.
    assert any("My Story" in m for m in fake.markup)
    assert "This can't be undone." in fake.captions
    _labels = [b[0] for b in fake.buttons]
    assert "Cancel" in _labels
    assert "Delete story" in _labels


def test_delete_all_target_renders_its_verb():
    lui, fake = _ui_with_fake_st()
    fake.session_state[lui._PENDING_DELETE_KEY] = {
        "kind": "all", "story_id": "",
        "title": "Delete all stories?",
        "message": "Every saved story will be permanently deleted.",
        "destructive_label": "Delete all stories",
    }
    lui._maybe_open_delete_dialog()
    assert fake.dialogs == ["Delete"]
    _labels = [b[0] for b in fake.buttons]
    assert "Delete all stories" in _labels


def test_cancel_clears_pending_without_deleting():
    # #130: Cancel clears the pending target and reruns — no delete runs.
    lui, fake = _ui_with_fake_st(clicks=("_pending_delete_no",))
    fake.session_state[lui._PENDING_DELETE_KEY] = {
        "kind": "story", "story_id": "s1",
        "title": "Delete?", "message": "M",
        "destructive_label": "Delete story",
    }
    lui._maybe_open_delete_dialog()
    assert fake.dialogs == ["Delete"]
    assert lui._PENDING_DELETE_KEY not in fake.session_state
    assert fake.reran is True
    assert fake.successes == []  # no delete happened


def test_delete_executes_story_action():
    # #130: the destructive button runs the story delete for the pending
    # target's story_id.
    lui, fake = _ui_with_fake_st(clicks=("_pending_delete_yes",))
    fake.session_state[lui._PENDING_DELETE_KEY] = {
        "kind": "story", "story_id": "s1",
        "title": "Delete?", "message": "M",
        "destructive_label": "Delete story",
    }
    # Patch the module-level delete to observe the call.
    deleted = []
    lui._confirm_delete_story = lambda sid: deleted.append(sid)
    lui._maybe_open_delete_dialog()
    assert deleted == ["s1"]
    assert lui._PENDING_DELETE_KEY not in fake.session_state
    assert fake.reran is True


def test_delete_executes_all_action():
    lui, fake = _ui_with_fake_st(clicks=("_pending_delete_yes",))
    fake.session_state[lui._PENDING_DELETE_KEY] = {
        "kind": "all", "story_id": "",
        "title": "Delete all?", "message": "M",
        "destructive_label": "Delete all stories",
    }
    deleted = []
    lui._confirm_delete_all = lambda: deleted.append("all")
    lui._maybe_open_delete_dialog()
    assert deleted == ["all"]


def test_delete_failure_is_loud_and_stays_open():
    # #130: on failure the error is shown loudly and the pending target is
    # kept so the dialog stays open for retry (fail loudly, never silent).
    lui, fake = _ui_with_fake_st(clicks=("_pending_delete_yes",))

    def _boom(sid):
        raise RuntimeError("disk gone")

    lui._confirm_delete_story = _boom
    fake.session_state[lui._PENDING_DELETE_KEY] = {
        "kind": "story", "story_id": "s1",
        "title": "Delete?", "message": "M",
        "destructive_label": "Delete story",
    }
    lui._maybe_open_delete_dialog()
    assert any("disk gone" in e for e in fake.errors)
    # Pending NOT cleared → dialog stays open.
    assert lui._PENDING_DELETE_KEY in fake.session_state


def test_multiple_triggers_one_dialog_per_run():
    # #130 regression: a page with Delete All + story delete (multiple
    # triggers) must invoke the dialog at most once per run.
    lui, fake = _ui_with_fake_st(clicks=("lib_delpop_all-trigger",))
    # Render both triggers (like render_library_page does).
    lui._delete_popover(**_story_kwargs())
    lui._delete_popover(**_all_kwargs())
    # Only the clicked one set pending.
    _pending = fake.session_state.get(lui._PENDING_DELETE_KEY)
    assert _pending["kind"] == "all"
    # Single dialog invocation point.
    lui._maybe_open_delete_dialog()
    assert len(fake.dialogs) == 1
