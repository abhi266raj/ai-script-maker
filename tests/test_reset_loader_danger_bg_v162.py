"""v1.6.2 (#81, #87) — reset loader re-anchored + solid-red destructive buttons.

#81: the Reset trigger showed no spinner while a reset ran — the old
3-hop selector routed through the lib-danger-pop- marker and never
matched the real DOM, so the spinner silently never painted. The
lib-spin-reset marker is now emitted immediately before the popover
trigger (the #53 adjacent-sibling shape the hashtag/image/news spinners
use), and the selector is the same 2-hop shape.

#87: the destructive confirmation buttons ("Delete story",
"Delete all stories", "Reset media") are solid macOS system red
(#FF3B30) with white text — like Apple's destructive alert buttons —
instead of red text + red border. Hover darkens the fill.

Run: python -m pytest tests/test_reset_loader_danger_bg_v162.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import _ui_with_fake_st  # noqa: E402


def _capture_library_css(lui, monkeypatch):
    """Capture the <style> HTML emitted by inject_library_css (holds the
    lib-spin-reset spinner rule)."""
    chunks = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: chunks.append(a[0] if a else ""))
    lui.inject_library_css()
    return "\n".join(chunks)


def _capture_story_list_css(lui, monkeypatch):
    """Capture the <style> HTML emitted by _inject_story_list_css (holds the
    danger-button rules)."""
    chunks = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: chunks.append(a[0] if a else ""))
    lui._inject_story_list_css()
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# #81 — lib-spin-reset immediately before the popover trigger
# ---------------------------------------------------------------------------

def test_reset_spin_marker_immediately_before_popover_while_resetting(monkeypatch):
    """#81: while resetting, lib-spin-reset must be emitted immediately
    before the popover trigger — its container is the immediate predecessor
    of the popover's container, the shape the spinner selector needs."""
    lui, fake = _ui_with_fake_st()
    seq = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: seq.append(("md", a[0] if a else "")))
    orig_popover = lui.st.popover

    def rec_popover(label, **k):
        seq.append(("popover", label))
        return orig_popover(label, **k)

    monkeypatch.setattr(lui.st, "popover", rec_popover)
    lui._render_reset_popover("sid1", {"reset"}, ai_engine=None)
    kinds = [s[0] for s in seq]
    spin_at = next(i for i, s in enumerate(seq)
                   if s[0] == "md" and 'data-marker="lib-spin-reset"' in s[1])
    # The event right after the spin marker is the popover trigger itself.
    # (#90: the trigger is icon-only — the reset glyph, tooltip keeps
    # the "Reset" label.)
    assert kinds[spin_at + 1] == "popover"
    assert seq[spin_at + 1][1] == lui._TB_ICON_RESET
    # The danger-pop marker still precedes the spin marker (its #24 collapse
    # contract is unchanged).
    danger_at = next(i for i, s in enumerate(seq)
                     if s[0] == "md" and "lib-danger-pop-lib_resetpop_sid1" in s[1])
    assert danger_at < spin_at
    assert fake.popover_kwargs["disabled"] is True


def test_reset_spin_marker_absent_when_idle_or_blocked():
    """#81: no spinner when Reset is idle, and none when it is merely
    blocked by another running kind (disabled then, not working)."""
    lui, fake = _ui_with_fake_st()
    lui._render_reset_popover("sid1", set(), ai_engine=None)
    assert "lib-spin-reset" not in "".join(fake.markup)
    assert fake.popover_kwargs["disabled"] is False

    lui2, fake2 = _ui_with_fake_st()
    lui2._render_reset_popover("sid1", {"hashtags"}, ai_engine=None)
    assert "lib-spin-reset" not in "".join(fake2.markup)
    # Blocked: the trigger disables, but there is no spinner — it is not
    # the control doing the work.
    assert fake2.popover_kwargs["disabled"] is True


def test_reset_spinner_css_is_two_hop_shape(monkeypatch):
    """#81: the reset spinner selector must be the same adjacent-sibling
    shape as the working hashtag/image/news spinners — marker container
    immediately followed by the trigger container. The old 3-hop form
    (via the lib-danger-pop- marker) must be gone: it never matched."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    two_hop = (r'div\[data-testid="stElementContainer"\]:has\(\[data-marker='
               r'"lib-spin-reset"\]\)\s*\+\s*div\[data-testid="stElementContainer"\]'
               r'\s*\[data-testid="stPopover"\]\s*\[data-testid="stPopoverButton"\]::before')
    assert re.search(two_hop, clean), "reset spinner selector lost its 2-hop shape"
    between = re.search(r'\[data-marker="lib-spin-reset"\]\)(.*?)::before',
                        clean, re.S)
    assert between, "reset spinner rule missing entirely"
    assert "lib-danger-pop-" not in between.group(1), \
        "the 3-hop middle selector is back"


def test_delete_popover_emits_no_spin_marker():
    """#81: spin_marker defaults to empty — the delete flows are untouched."""
    lui, fake = _ui_with_fake_st()
    lui._delete_popover(
        trigger_label="Delete", popover_key="dp1", title="Delete?",
        message="gone", on_yes=lambda: None, destructive_label="Delete story")
    assert "lib-spin-reset" not in "".join(fake.markup)
    assert "lib-spin-" not in "".join(fake.markup)


# ---------------------------------------------------------------------------
# #87 — solid red destructive buttons
# ---------------------------------------------------------------------------

def test_danger_button_solid_red_background(monkeypatch):
    """#87: the destructive button rule paints a solid system-red fill
    with white text — not red text + red border."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_story_list_css(lui, monkeypatch)
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    base = re.search(
        r'\[data-marker\^="lib-danger-"\]\)\s*\+\s*div\[data-testid="stElementContainer"\]'
        r'\s*\[data-testid="stButton"\]\s*button\s*\{([^}]*)\}', clean)
    assert base, "danger-button rule missing"
    decls = base.group(1)
    assert "background-color: #FF3B30 !important;" in decls
    assert "color: #FFFFFF !important;" in decls
    assert "border-color: #FF3B30 !important;" in decls
    # No red-text-only leftover: the fill carries the red now (match the
    # standalone `color` declaration, not `background-color`/`border-color`).
    assert not re.search(r"(?<![a-z-])color: #FF3B30", decls)


def test_danger_button_hover_darkens(monkeypatch):
    """#87: hover darkens the fill; the text stays white."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_story_list_css(lui, monkeypatch)
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    hover = re.search(
        r'\[data-marker\^="lib-danger-"\]\)\s*\+\s*div\[data-testid="stElementContainer"\]'
        r'\s*\[data-testid="stButton"\]\s*button:hover\s*\{([^}]*)\}', clean)
    assert hover, "danger-button :hover rule missing"
    decls = hover.group(1)
    assert "background-color: #D92D20 !important;" in decls
    assert "color: #FFFFFF !important;" in decls
    assert "border-color: #D92D20 !important;" in decls


def test_danger_button_rule_stays_marker_scoped(monkeypatch):
    """#87: the solid-red rule keeps its marker scoping — if the selector
    ever misses, the button degrades to a plain button, never broken."""
    lui, _fake = _ui_with_fake_st()
    css = _capture_story_list_css(lui, monkeypatch)
    scoped = ('div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"])\n'
              '        + div[data-testid="stElementContainer"] [data-testid="stButton"] button')
    assert scoped in css
    assert scoped + ":hover" in css
