"""Regression tests for issue #292: white circle artifact (toggle/radio with
unpainted track).

The theme's toggle/radio/checkbox selectors historically depended on
Emotion-generated class hashes (e15oan337/338, e1mpz0hj4/5, e15oan335),
which are build-fragile: if the hashes change, the selectors go dead and
a control can render as an orphaned white circle. These tests verify that
every circular control also has a STRUCTURAL fallback selector (verified
against the 1.64.0 bundle's component tree) that does not depend on hashes.

Structural facts (from the 1.64.0 frontend bundle):
- st.toggle renders inside [data-testid="stCheckbox"]; its <input> carries
  role="switch"; the track div directly contains the leaf thumb div.
- st.radio options carry [data-testid="stRadioOption"]; the outer circle
  div directly contains the leaf inner-dot div.
- st.checkbox (non-toggle) box directly contains the check svg.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_CSS = (REPO / "app.py").read_text(encoding="utf-8")
# Strip CSS comments so hash mentions in prose don't pollute selector checks.
APP_CSS = re.sub(r"/\*.*?\*/", "", APP_CSS, flags=re.DOTALL)


def _selectors_for(pattern: str):
    """Return all CSS selectors whose rule block contains the given declaration pattern."""
    # crude CSS parse: split on '}' and check each rule
    out = []
    for chunk in APP_CSS.split("}"):
        if "{" not in chunk:
            continue
        sel, _, body = chunk.rpartition("{")
        if re.search(pattern, body):
            out.append(sel.strip())
    return out


def test_toggle_track_has_structural_fallback():
    """The toggle track must be themeable without the e15oan337 hash."""
    sels = _selectors_for(r"background-color:\s*var\(--line-strong\)")
    structural = [s for s in sels
                  if 'input[role="switch"]' in s and "e15oan" not in s]
    assert structural, (
        "No structural (hash-free) selector themes the toggle track. "
        "Expected a [role=\"switch\"]-scoped selector."
    )


def test_toggle_track_on_state_has_structural_fallback():
    """The selected toggle track must be themeable without hashes."""
    sels = _selectors_for(r"background-color:\s*var\(--accent\)")
    structural = [s for s in sels
                  if 'input[role="switch"]' in s
                  and "data-selected" in s
                  and "e15oan" not in s]
    assert structural, (
        "No structural selector themes the ON toggle track."
    )


def test_toggle_thumb_has_structural_fallback():
    """The toggle thumb must be themeable without the e15oan338 hash."""
    # thumb off = --ink, thumb on = --on-accent, both scoped by switch role
    sels_ink = _selectors_for(r"background-color:\s*var\(--ink\)")
    sels_on = _selectors_for(r"background-color:\s*var\(--on-accent\)")
    struct_ink = [s for s in sels_ink
                  if 'input[role="switch"]' in s and "e15oan" not in s]
    struct_on = [s for s in sels_on
                 if 'input[role="switch"]' in s and "e15oan" not in s]
    assert struct_ink, "No structural selector themes the toggle thumb (off)."
    assert struct_on, "No structural selector themes the toggle thumb (on)."


def test_radio_outer_has_structural_fallback():
    """The radio outer circle must be themeable without the e1mpz0hj4 hash."""
    sels = _selectors_for(r"background-color:\s*var\(--line\)")
    structural = [s for s in sels
                  if "stRadioOption" in s and "e1mpz0hj" not in s]
    assert structural, (
        "No structural (hash-free) selector themes the unselected radio circle."
    )


def test_radio_inner_dot_has_structural_fallback():
    """The radio inner dot must be themeable without the e1mpz0hj5 hash."""
    sels = _selectors_for(r"background-color:\s*var\(--paper\)")
    structural = [s for s in sels
                  if "stRadioOption" in s and "e1mpz0hj" not in s]
    assert structural, (
        "No structural selector themes the radio inner dot."
    )


def test_checkbox_box_has_structural_fallback():
    """The checkbox box must be themeable without the e15oan335 hash."""
    sels = _selectors_for(r"background-color:\s*var\(--sunken\)")
    structural = [s for s in sels
                  if "stCheckbox" in s and "e15oan" not in s
                  # :not(:has(input[role="switch"])) scopes AWAY from toggles
                  and (":not(:has(input[role=\"switch\"]))" in s
                       or "role=\"switch\"" not in s)]
    assert structural, (
        "No structural selector themes the checkbox box."
    )


def test_structural_selectors_use_parent_child_not_hashes():
    """Structural fallbacks must key on parent>child structure, never hashes."""
    sels = _selectors_for(r"background-color:\s*var\(--(line-strong|accent|line|paper|sunken|ink|on-accent)\)")
    structural = [s for s in sels
                  if (":has(" in s and ("stCheckbox" in s or "stRadio" in s))]
    assert structural, "Expected :has()-based structural selectors."
    for s in structural:
        assert "e15oan" not in s and "e1mpz0hj" not in s, (
            f"Structural selector leaked an emotion hash: {s[:80]}"
        )


def test_no_white_circular_control_possible():
    """Every circular control family has both hash AND structural theming.

    If the hashes ever change, the structural rules still paint the
    control — a white orphaned circle cannot survive.
    """
    families = {
        "toggle track": ('input[role="switch"]', "e15oan337"),
        "radio outer": ("stRadioOption", "e1mpz0hj4"),
    }
    for name, (struct_hook, hash_hook) in families.items():
        has_hash = hash_hook in APP_CSS
        has_struct = struct_hook in APP_CSS and ":has(" in APP_CSS
        assert has_hash and has_struct, (
            f"{name}: need both hash ({has_hash}) and structural ({has_struct}) coverage"
        )
