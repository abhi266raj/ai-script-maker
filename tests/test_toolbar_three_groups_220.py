"""#220 — the detail toolbar is grouped into at most three visually
separated groups (macOS HIG §1: "Don't overcrowd toolbars — aim for a max
of three item groups").

The icon-only controls render as three groups — refresh ×3 (hashtags,
images, news) | share+copy+upload+engine | destructive (reset + delete)
— with a hairline vertical separator column between groups. The
separators use a theme-adaptive neutral gray (HIG §4: no hard-coded
colors) and the shared --lib-act-h height token so they match the
toolbar buttons.

Run: python -m pytest tests/test_toolbar_three_groups_220.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import (  # noqa: E402
    _ui_with_fake_st,
    _capture_library_css,
)
from test_one_row_toolbar_v16 import (  # noqa: E402
    _ui_with_recording_st,
    _story,
)


def _tb_sep_rule(css):
    m = re.search(r"\.lib-tb-sep\s*\{([^}]*)\}", css)
    assert m, ".lib-tb-sep rule missing from injected CSS"
    return m.group(1)


# ---------------------------------------------------------------------------
# #220 — column spec encodes exactly three groups with separators
# ---------------------------------------------------------------------------

def test_toolbar_spec_has_three_groups_with_separators():
    lui, _fake = _ui_with_fake_st()
    w = lui._DETAIL_TOOLBAR_WEIGHTS
    assert len(w) == 12
    sep = lui._TB_SEP_W
    # Separator slots sit exactly between the groups: after refresh ×3
    # (index 3) and after share+copy+upload+engine (index 8).
    assert w[3] == sep and w[8] == sep
    assert all(s <= 0.2 for s in (w[3], w[8])), "separator slots must be thin"
    # Every other slot is a real action or the spacer — no second
    # separator hiding anywhere.
    non_sep = [x for i, x in enumerate(w) if i not in (3, 8)]
    assert all(x >= 0.8 for x in non_sep)
    # Group 1: refresh ×3 (hashtags, images, news icon columns).
    assert w[0] >= 0.8 and w[1] >= 0.8 and w[2] >= 0.8
    # Group 2: share+copy+upload popover triggers + AI engine dropdown.
    assert w[4] >= 1.0 and w[5] >= 1.0 and w[6] >= 1.0 and w[7] >= 1.5
    # Group 3: destructive — reset moved next to delete, both trailing
    # after the spacer.
    assert w[10] >= 1.3 and w[11] >= 1.5
    assert w[9] > 1.0  # spacer pushes the destructive group trailing


def test_toolbar_renders_exactly_two_separators(monkeypatch):
    lui, fake = _ui_with_recording_st()
    _story(monkeypatch, lui)
    lui._render_story_detail("sid1")
    seps = [m for m in fake.markup if 'class="lib-tb-sep"' in m]
    assert len(seps) == 2  # one between each pair of groups
    assert all('aria-hidden="true"' in m for m in seps)


# ---------------------------------------------------------------------------
# #220 / HIG §4 — the separator is theme-adaptive: no hard-coded colors,
# no theme branch; height follows the shared action-button token.
# ---------------------------------------------------------------------------

def test_separator_css_is_theme_adaptive(monkeypatch):
    lui, _fake = _ui_with_fake_st()
    rule = _tb_sep_rule(_capture_library_css(lui, monkeypatch))
    # Neutral translucent gray — reads in light and dark mode, no
    # hard-coded hex color and no theme-branching media query.
    assert "rgba(128, 128, 128" in rule
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", rule), \
        f"hard-coded hex color in separator: {rule!r}"
    assert "prefers-color-scheme" not in rule
    # Height matches the toolbar buttons via the shared token (the same
    # --lib-act-h mirrored in Python as _LIB_ACTION_BTN_H_PX).
    assert "var(--lib-act-h)" in rule
    # Hairline, centered in its thin column.
    assert "width: 1px" in rule
    assert "margin: 0 auto" in rule
