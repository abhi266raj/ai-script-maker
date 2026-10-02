"""Warning severity (issue #217).

A vibe<->format mismatch is a WARNING, not an error — but app.py rendered it
as a red ``st.error`` banner with a warning emoji: wrong severity (a warning
dressed as an error).

Covers:
- source-level guard: no ``st.error(`` call site in app.py renders warning
  content (the ``_vibe_reason`` text, or any line carrying the ⚠️ emoji);
- source-level guard: no ``st.warning(`` call site embeds a redundant ⚠️
  emoji — ``st.warning`` already carries the caution treatment (HIG §6:
  "Use the caution symbol sparingly"), and the no-emoji house rule applies;
- the vibe<->format mismatch renders via ``st.warning(_vibe_reason)``;
- behaviour: ``check_vibe_format_compatible`` still classifies the
  contradictory combos as incompatible (warning text intact, no ⚠️ added)
  and compatible combos as fine.

Run: python -m pytest tests/test_warning_severity_217.py -q
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.constants import (  # noqa: E402
    VIBE_COMEDY,
    VIBE_EMOTIONAL,
    FORMAT_DIALOGUE,
    FORMAT_LAMENT,
)


def _app_src():
    return (Path(__file__).resolve().parent.parent
            / "app.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source-level guards: warning severity, no redundant caution emoji
# ---------------------------------------------------------------------------

def test_vibe_warning_never_rendered_as_error():
    """#217: the vibe<->format warning must not go through st.error."""
    src = _app_src()
    assert "st.error(_vibe_reason)" not in src
    assert 'st.error(f"{_vibe_reason}' not in src
    for i, line in enumerate(src.splitlines(), start=1):
        if "st.error(" in line:
            assert "⚠️" not in line, (
                f"app.py:{i}: warning content rendered via st.error — "
                "warnings must use st.warning"
            )
            assert "_vibe_reason" not in line, (
                f"app.py:{i}: _vibe_reason (a warning) rendered via st.error"
            )


def test_vibe_mismatch_renders_st_warning():
    """#217: the mismatch warning renders via st.warning (not st.error).

    The banner keeps the sanctioned :material/warning: icon per the merged
    #199 icon-only convention — no emoji.
    """
    src = _app_src()
    warning_lines = [line for line in src.splitlines()
                     if "st.warning(" in line and "_vibe_reason" in line]
    assert warning_lines, (
        "the vibe<->format mismatch must render via st.warning(_vibe_reason …)"
    )
    assert all("⚠️" not in line for line in warning_lines)


def test_no_redundant_warning_emoji_on_st_warning():
    """#217: st.warning already carries the caution treatment (HIG §6) —
    embedding ⚠️ in the call is redundant and breaks the no-emoji rule."""
    src = _app_src()
    for i, line in enumerate(src.splitlines(), start=1):
        if "st.warning(" in line:
            assert "⚠️" not in line, (
                f"app.py:{i}: redundant ⚠️ on st.warning — "
                "st.warning already carries the caution treatment"
            )


# ---------------------------------------------------------------------------
# Behaviour: check_vibe_format_compatible (real app module, fake streamlit)
# ---------------------------------------------------------------------------

class _Stop(Exception):
    pass


class _State(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


class _Noop:
    def __call__(self, *a, **k):
        return _Noop()

    def __getattr__(self, n):
        return _Noop()

    def __getitem__(self, k):
        return _Noop()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False


def _app_with_fake_st():
    """Import app.py bound to a fake streamlit; restores sys.modules."""
    saved = dict(sys.modules)
    state = _State()

    def _make_fake(name):
        mod = types.ModuleType(name)
        mod.session_state = state

        def _ga(n):
            if n == "session_state":
                return state
            if n == "stop":
                def _stop(*a, **k):
                    raise _Stop()
                return _stop
            if n in ("columns", "tabs"):
                def _mk(*a, **k):
                    spec = a[0] if a else 2
                    cnt = (len(spec) if isinstance(spec, (list, tuple))
                           else int(spec))
                    return [_Noop() for _ in range(cnt)]
                return _mk
            return _Noop()

        mod.__getattr__ = _ga
        return mod

    try:
        for sub in ("streamlit", "streamlit.components",
                    "streamlit.components.v1"):
            sys.modules[sub] = _make_fake(sub)
        for mod_name in ("app", "library_ui", "story_library"):
            sys.modules.pop(mod_name, None)
        import app
        return app, state
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def test_clashing_combo_reports_warning_text():
    """Sorrow + Comedy is incompatible: (False, non-empty reason).

    The reason text itself must not carry a ⚠️ prefix — the banner
    (st.warning) already provides the caution treatment (#217).
    """
    app, state = _app_with_fake_st()
    state["chosen_tone"] = VIBE_COMEDY
    state["chosen_scene_style"] = FORMAT_LAMENT
    ok, reason = app.check_vibe_format_compatible()
    assert ok is False
    assert reason, "incompatible combo must explain why"
    assert "⚠️" not in reason


def test_compatible_combo_passes():
    app, state = _app_with_fake_st()
    state["chosen_tone"] = VIBE_COMEDY
    state["chosen_scene_style"] = FORMAT_DIALOGUE
    assert app.check_vibe_format_compatible() == (True, "")


def test_sorrow_with_emotional_vibe_passes():
    app, state = _app_with_fake_st()
    state["chosen_tone"] = VIBE_EMOTIONAL
    state["chosen_scene_style"] = FORMAT_LAMENT
    assert app.check_vibe_format_compatible() == (True, "")
