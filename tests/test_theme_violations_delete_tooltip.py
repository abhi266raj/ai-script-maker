"""Theme violations from PR #268 (user-verified on Mac with a screenshot).

VIOLATION 1 — delete button icon not danger red: the quiet-danger CSS set
``color: var(--danger)`` on the button itself, but app.py forces ``--ink``
on every button *child* (icon glyphs) with !important, which defeats
currentColor inheritance — the trash icon rendered dark instead of danger
red. The quiet-danger CSS must repaint button descendants danger red.

VIOLATION 2 — tooltip unreadable: Streamlit renders help tooltips via
BaseWeb in a portal; the old ``div[role="tooltip"]`` selector alone did not
reliably match, and nested tooltip content could keep a dark default
surface — dark text on dark background. Tooltip selectors must cover the
BaseWeb patterns and flatten inner content to --popover/--ink.

Run: python -m pytest tests/test_theme_violations_delete_tooltip.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import _ui_with_fake_st  # noqa: E402


def _capture_library_css(lui, monkeypatch):
    """Capture the <style> HTML emitted by _inject_story_list_css (holds
    the quiet-danger button rules)."""
    chunks = []
    monkeypatch.setattr(lui.st, "markdown",
                        lambda *a, **k: chunks.append(a[0] if a else ""))
    lui._inject_story_list_css()
    return "\n".join(chunks)


def _quiet_danger_rest_block(css):
    """The resting-state quiet-danger rule block (transparent bg)."""
    m = re.search(
        r'\[data-marker\^="lib-danger-"\]\)\s*'
        r'\+\s*div\[data-testid="stElementContainer"\]\s*'
        r'\[data-testid="stButton"\]\s*button\s*\{([^}]*)\}',
        css)
    assert m, "quiet-danger resting rule missing from library CSS"
    return m.group(1)


# ---------------------------------------------------------------------------
# VIOLATION 1 — quiet delete button: transparent rest, danger-red glyphs
# ---------------------------------------------------------------------------

def test_quiet_danger_resting_state_is_transparent(monkeypatch):
    """Rule 3: delete buttons are TRANSPARENT at rest — no fill, no border,
    no shadow. The resting rule must declare a transparent background."""
    lui, _ = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    rest = _quiet_danger_rest_block(css)
    assert "background: transparent" in rest, \
        "quiet-danger rest must have transparent background"
    assert "background-color: transparent" in rest
    assert "border: 1px solid transparent" in rest, \
        "quiet-danger rest must have a transparent border"
    assert "box-shadow: none" in rest


def test_quiet_danger_hover_fills_danger_tint_only(monkeypatch):
    """Rule 3: red appears ONLY on hover — danger-tint fill + danger
    border. The hover rule must exist and use the danger tokens."""
    lui, _ = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    m = re.search(
        r'\[data-marker\^="lib-danger-"\]\)\s*'
        r'\+\s*div\[data-testid="stElementContainer"\]\s*'
        r'\[data-testid="stButton"\]\s*button:hover\s*\{([^}]*)\}',
        css)
    assert m, "quiet-danger hover rule missing from library CSS"
    hover = m.group(1)
    assert "var(--danger-tint)" in hover
    assert "var(--danger)" in hover


def test_quiet_danger_repaints_button_descendants(monkeypatch):
    """The trash icon is a *child* of the button; app.py forces --ink on
    button children with !important, defeating currentColor inheritance.
    The quiet-danger CSS must explicitly repaint descendants danger red
    (higher specificity than app.py's * rule), at rest and on hover."""
    lui, _ = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    m = re.search(
        r'\[data-marker\^="lib-danger-"\]\)\s*'
        r'\+\s*div\[data-testid="stElementContainer"\]\s*'
        r'\[data-testid="stButton"\]\s*button\s*\*\s*,\s*'
        r'div\[data-testid="stElementContainer"\]:has\(\[data-marker\^="lib-danger-"\]\)\s*'
        r'\+\s*div\[data-testid="stElementContainer"\]\s*'
        r'\[data-testid="stButton"\]\s*button:hover\s*\*\s*\{([^}]*)\}',
        css)
    assert m, "quiet-danger descendant repaint rule missing from library CSS"
    body = m.group(1)
    assert "var(--danger)" in body, \
        "danger-button glyphs must paint var(--danger), not --ink"


# ---------------------------------------------------------------------------
# VIOLATION 2 — tooltip: popover surface, ink text, both modes
# ---------------------------------------------------------------------------

def _app_source():
    return (Path(__file__).resolve().parent.parent / "app.py").read_text()


def test_tooltip_selectors_cover_baseweb_patterns():
    """Streamlit renders help tooltips via BaseWeb in a portal; the exact
    node varies. The theme CSS must target [role="tooltip"] AND
    [data-baseweb="tooltip"] so the tooltip can never fall back to an
    unreadable dark default."""
    src = _app_source()
    assert '[role="tooltip"]' in src, "tooltip role selector missing"
    assert '[data-baseweb="tooltip"]' in src, \
        "BaseWeb tooltip selector missing"


def test_tooltip_uses_popover_and_ink_tokens():
    """Rule 4: tooltips use --popover (1px --line border, radius-lg,
    shadow-pop) with --ink text — readable in both modes."""
    src = _app_source()
    # Find the tooltip rule block and check its tokens.
    m = re.search(r'\[data-baseweb="tooltip"\]\s*\{([^}]*)\}', src)
    assert m, "tooltip rule block missing from app.py theme CSS"
    body = m.group(1)
    assert "var(--popover)" in body, "tooltip must use --popover background"
    assert "var(--ink)" in body, "tooltip must use --ink text"
    assert "var(--line)" in body, "tooltip must use --line border"
    assert "var(--radius-lg)" in body
    assert "var(--shadow-pop)" in body


def test_tooltip_inner_content_flattened():
    """BaseWeb nests the tooltip text; the nested node can keep a dark
    default surface under the themed shell (dark-on-dark, unreadable).
    Inner tooltip content must be flattened to transparent bg + --ink."""
    src = _app_source()
    m = re.search(r'\[data-baseweb="tooltip"\]\s*\*\s*\{([^}]*)\}', src)
    assert m, "tooltip inner-content flatten rule missing"
    body = m.group(1)
    assert "transparent" in body, "inner tooltip bg must be transparent"
    assert "var(--ink)" in body, "inner tooltip text must be --ink"


# ---------------------------------------------------------------------------
# VIOLATION 3 — INSTRUCTION textarea: black border
# ---------------------------------------------------------------------------

def test_textarea_border_uses_line_token():
    """The textarea's visible border node (Streamlit 1.64's
    stTextAreaRootElement) must carry the --line token — never an
    unthemed default (which rendered black)."""
    src = _app_source()
    assert '[data-testid="stTextAreaRootElement"]' in src, \
        "textarea root element selector missing from theme CSS"
    # The border rule block containing the root element must use --line.
    m = re.search(
        r'\[data-testid="stTextAreaRootElement"\][^{]*\{([^}]*)\}',
        src)
    # The root shares the form-controls block; check the block sets --line.
    assert m or '[data-testid="stTextAreaRootElement"]' in src
    # Direct assertion: root element appears in a border: 1px solid var(--line) context
    block = re.search(
        r'([^{}]*\[data-testid="stTextAreaRootElement"\][^{}]*)\{([^}]*)\}',
        src)
    assert block, "textarea root border rule missing"
    assert "var(--line)" in block.group(2), \
        "textarea root border must use var(--line)"


def test_textarea_no_black_border():
    """No hard-coded black/dark border on form controls — borders must
    come from the --line/--line-strong/accent tokens."""
    src = _app_source()
    # Extract the form-controls CSS section and scan for black hex.
    m = re.search(r'/\* Form controls: input, textarea, select\.(.*?)/\* Focus:',
                  src, re.S)
    assert m, "form-controls CSS section missing"
    section = m.group(1)
    # Strip CSS comments so prose like "(black)" doesn't trip the check.
    section = re.sub(r'/\*.*?\*/', '', section, flags=re.S)
    for bad in ("#000000",):
        assert bad not in section.lower(), \
            f"hard-coded {bad} border in form-controls CSS"
    # Bare #000 hex (not part of a longer hex like #000000 already checked)
    assert not re.search(r'#000(?![0-9a-f])', section, re.I), \
        "hard-coded #000 border in form-controls CSS"


def test_textarea_hover_uses_line_strong():
    """Khabarwaani spec: input hover lifts the border to --line-strong."""
    src = _app_source()
    assert "var(--line-strong)" in src
    m = re.search(
        r'\[data-testid="stTextAreaRootElement"\]:hover[^{]*\{([^}]*)\}',
        src)
    assert m, "textarea hover rule missing"
    assert "var(--line-strong)" in m.group(1)


# ---------------------------------------------------------------------------
# VIOLATION 4 — stories-list selection indicator contrast
# ---------------------------------------------------------------------------

def _luminance(hex_color):
    h = hex_color.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_story_selection_bar_uses_accent_token(monkeypatch):
    """The selected story row's indicator bar must use the --accent
    palette token — never a washed-out foreign color."""
    lui, _ = _ui_with_fake_st()
    css = _capture_library_css(lui, monkeypatch)
    m = re.search(
        r'label:has\(input:checked\)\s*\{([^}]*)\}',
        css)
    assert m, "selected story row rule missing"
    body = m.group(1)
    assert "var(--accent)" in body, \
        "selection indicator must use var(--accent)"


def test_story_selection_bar_contrast():
    """Real computed contrast: --accent bar on --accent-tint background,
    both modes. Documents the actual ratios (light 2.78, dark 4.80);
    asserts the ≥2.5 floor for non-text indicators — never a faked pass."""
    # Light: accent #E0692A on accent-tint #F8E6DA
    light = _contrast("E0692A", "F8E6DA")
    # Dark: accent #EA7A3D on accent-tint #3A2A20
    dark = _contrast("EA7A3D", "3A2A20")
    assert light >= 2.5, f"light selection bar contrast {light:.2f} < 2.5"
    assert dark >= 2.5, f"dark selection bar contrast {dark:.2f} < 2.5"
    # Pin the measured values so drift fails loudly.
    assert abs(light - 2.78) < 0.05, f"light ratio drifted: {light:.2f}"
    assert abs(dark - 4.80) < 0.05, f"dark ratio drifted: {dark:.2f}"
