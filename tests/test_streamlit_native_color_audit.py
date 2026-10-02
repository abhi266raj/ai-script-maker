"""Streamlit-native color audit — regression tests.

Pins every fix from the full 1.64 native-color sweep (see issue #278):
sub-elements that Streamlit 1.64 paints with its own native colors must
be themed with palette tokens. These are structure/token tests against
the theme CSS in app.py / library_ui.py — they fail loudly if a rule is
removed or regressed to a native color.

Binding spec: docs/COLOR_PALETTE.md (only palette tokens, never
hard-coded colors, never blue, never native red).
"""

import inspect
import re
from pathlib import Path

REPO = Path(inspect.getfile(inspect.currentframe())).resolve().parent.parent
APP_PY = REPO / "app.py"
LIB_UI_PY = REPO / "library_ui.py"


def _css(path: Path) -> str:
    src = path.read_text()
    m = re.search(r"<style>(.*?)</style>", src, re.S)
    assert m, f"no <style> block in {path.name}"
    return m.group(1)


def _lib_css() -> str:
    # library_ui.py injects several <style> blocks; concatenate them.
    src = LIB_UI_PY.read_text()
    blocks = re.findall(r"<style>(.*?)</style>", src, re.S)
    assert blocks, "no <style> blocks in library_ui.py"
    return "\n".join(blocks)


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)




def _rule_has(css: str, selector_frag: str, prop_frag: str) -> bool:
    """True if a rule whose selector contains selector_frag also contains
    prop_frag in its declaration block."""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if selector_frag in m.group(1) and prop_frag in m.group(2):
            return True
    return False


APP_CSS = _css(APP_PY)
LIB_CSS = _lib_css()
APP_CSS_NC = _strip_comments(APP_CSS)
LIB_CSS_NC = _strip_comments(LIB_CSS)


# --- Expander (#278): expanded summary must not paint native bgMix ---

def test_expander_summary_background_transparent():
    assert _rule_has(
        APP_CSS, '[data-testid="stExpander"] summary',
        "background: transparent !important")


def test_expander_summary_hover_uses_hover_token():
    assert _rule_has(
        APP_CSS, '[data-testid="stExpander"] summary:hover',
        "var(--hover)")


def test_expander_summary_focus_ring_is_accent():
    assert _rule_has(
        APP_CSS, '[data-testid="stExpander"] summary:focus-visible',
        "var(--accent)")


def test_expander_details_border_uses_line_token():
    assert _rule_has(
        APP_CSS, '[data-testid="stExpander"] details',
        "var(--line)")


# --- Tooltip: visible surface must be popover/ink, not dark-on-dark ---

def test_tooltip_content_uses_popover():
    assert _rule_has(
        APP_CSS, '[data-testid="stTooltipContent"]',
        "var(--popover)")


def test_tooltip_content_text_is_ink():
    assert _rule_has(
        APP_CSS, '[data-testid="stTooltipContent"]',
        "var(--ink)")


# --- Progress: fill = accent (native is blue), track = sunken ---

def test_progress_fill_is_accent_not_blue():
    assert _rule_has(
        APP_CSS, '[data-testid="stProgressBarTrack"] > div',
        "var(--accent)")
    # and no blue hex anywhere near the progress rules
    assert "#1c83e1" not in APP_CSS.lower()


def test_progress_track_is_sunken():
    assert _rule_has(
        APP_CSS, '[data-testid="stProgressBarTrack"]',
        "var(--sunken)")


# --- Radio: selected ring = accent, never native red ---

def test_radio_selected_ring_is_accent():
    assert _rule_has(APP_CSS, "e1mpz0hj4", "var(--accent)")


def test_radio_unselected_ring_is_line():
    assert _rule_has(APP_CSS, "e1mpz0hj4", "var(--line)")


# --- Toggle: ON = accent, never red; old dead selectors gone ---

def test_toggle_on_is_accent():
    assert _rule_has(APP_CSS, "e15oan337", "var(--accent)")


def test_no_dead_sttoggle_testid_selectors():
    assert '[data-testid="stToggle"]' not in APP_CSS_NC


# --- Checkbox: checked = accent, never red; dead baseweb gone ---

def test_checkbox_checked_is_accent():
    assert _rule_has(APP_CSS, "e15oan335", "var(--accent)")


def test_no_dead_baseweb_checkbox_selectors():
    assert '[data-baseweb="checkbox"]' not in APP_CSS_NC


# --- Tabs: selected = accent; dead baseweb tab selectors gone ---

def test_tab_selected_text_is_accent():
    assert _rule_has(
        APP_CSS, '[data-testid="stTabs"] [role="tablist"] button[data-selected]',
        "var(--accent)")


def test_tab_selection_indicator_is_accent():
    assert _rule_has(
        APP_CSS, "react-aria-SelectionIndicator",
        "var(--accent)")


def test_no_dead_baseweb_tab_selectors():
    assert '[data-baseweb="tab' not in APP_CSS_NC


# --- Caption: live testid, ink-2, full opacity (old .stCaption dead) ---

def test_caption_uses_live_testid_with_ink2():
    assert _rule_has(
        APP_CSS, '[data-testid="stCaptionContainer"]',
        "var(--ink-2)")


def test_caption_full_opacity():
    assert _rule_has(
        APP_CSS, '[data-testid="stCaptionContainer"]',
        "opacity: 1 !important")


# --- Markdown: links = ink (never blue); blockquote = line; tables = line ---

def test_markdown_links_are_ink_not_blue():
    assert _rule_has(
        APP_CSS, '[data-testid="stMarkdownContainer"] a',
        "var(--ink)")


def test_blockquote_border_is_line():
    assert _rule_has(
        APP_CSS, '[data-testid="stMarkdownContainer"] blockquote',
        "var(--line)")


# --- Text input / textarea roots: sunken + line, accent focus ---

def test_text_input_root_is_sunken_with_line_border():
    assert _rule_has(
        APP_CSS, '[data-testid="stTextInputRootElement"]',
        "var(--sunken)")
    assert _rule_has(
        APP_CSS, '[data-testid="stTextInputRootElement"]',
        "var(--line)")


def test_text_area_root_is_sunken_with_line_border():
    assert _rule_has(
        APP_CSS, '[data-testid="stTextAreaRootElement"]',
        "var(--sunken)")


def test_text_input_root_focus_is_accent():
    assert _rule_has(
        APP_CSS, '[data-testid="stTextInputRootElement"]:focus-within',
        "var(--accent)")


# --- Link button: accent focus ring, native red glow killed ---

def test_link_button_focus_ring_is_accent():
    assert _rule_has(
        APP_CSS, '[data-testid="stLinkButton"] a:focus-visible',
        "var(--accent)")


# --- Dialog: body text ink; toast: no brightness filter ---

def test_dialog_body_text_is_ink():
    assert _rule_has(
        APP_CSS, '[data-testid="stDialog"] div[class*="ee2kfji5"]',
        "var(--ink)")


def test_toast_brightness_filter_killed():
    assert _rule_has(
        APP_CSS, '[data-testid="stToast"]',
        "filter: none !important")


# --- Disabled buttons: ink-3 labels (not white-on-sunken) ---

def test_disabled_button_descendants_are_ink3():
    assert _rule_has(
        APP_CSS, 'button[data-testid="stBaseButton-primary"]:disabled *',
        "var(--ink-3)")


# --- Danger buttons: glyphs repainted danger red (app * rule defeats it) ---

def test_danger_button_glyphs_are_danger_red():
    # The button element itself was always --danger; the bug was the
    # glyphs (label span, svg), defeated by app.py's * rule. Pin the
    # descendant override.
    found = False
    for m in re.finditer(r"([^{}]+)\{([^{}]+)\}", _strip_comments(LIB_CSS)):
        sel, decl = m.group(1), m.group(2)
        if "lib-danger-" in sel and sel.strip().endswith("*") \
                and "var(--danger)" in decl:
            found = True
    assert found, "no lib-danger- * descendant override to --danger"


# --- File uploader chips ---

def test_file_chip_uses_card():
    assert _rule_has(
        APP_CSS, '[data-testid="stFileChip"]',
        "var(--card)")


def test_file_chip_name_is_ink():
    assert _rule_has(
        APP_CSS, '[data-testid="stFileChipName"]',
        "var(--ink)")
