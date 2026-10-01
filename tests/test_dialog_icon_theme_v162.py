"""Tests for #129: dialog/popover icons follow the theme (light + dark).

Verifies:
- The _copy_button iframe detects Streamlit's theme and applies matching styles.
- Button icons inherit theme color via CSS (no hardcoded icon colors).
- No hardcoded single-theme colors in dialog/popover contexts.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LIB_UI = Path(__file__).resolve().parent.parent / "library_ui.py"
CSS = LIB_UI.read_text(encoding="utf-8")


def _extract_style_blocks(source: str):
    """Return all <style>...</style> contents."""
    return re.findall(r"<style>(.*?)</style>", source, re.DOTALL)


def test_copy_button_detects_theme():
    """_copy_button JS reads data-theme from parent document."""
    src = LIB_UI.read_text(encoding="utf-8")
    # Find the _copy_button function
    m = re.search(r"def _copy_button\(.*?\n(?=def |\Z)", src, re.DOTALL)
    assert m, "_copy_button not found"
    body = m.group(0)
    # Must detect theme from parent
    assert "data-theme" in body, "copy button must read data-theme"
    assert "window.parent.document" in body, "must check parent document theme"
    # Must handle both themes
    assert "'dark'" in body or '"dark"' in body, "must handle dark theme"


def test_copy_button_no_hardcoded_single_theme():
    """_copy_button must not hardcode only light-mode colors in style attr."""
    src = LIB_UI.read_text(encoding="utf-8")
    m = re.search(r"def _copy_button\(.*?\n(?=def |\Z)", src, re.DOTALL)
    body = m.group(0)
    # The button tag's inline style should NOT contain hardcoded colors;
    # colors are applied via JS applyTheme()
    button_tag = re.search(r'<button id="\{btn_id\}" style="([^"]*)"', body)
    assert button_tag, "button tag with style not found"
    style = button_tag.group(1)
    # No hardcoded hex colors or rgba in the static style attribute
    assert not re.search(r"#[0-9a-fA-F]{3,6}", style), \
        f"static style must not hardcode hex colors: {style}"
    assert "rgba(" not in style, \
        f"static style must not hardcode rgba colors: {style}"


def test_button_icon_inherits_theme_color():
    """CSS ensures button/popover icons inherit theme color."""
    styles = _extract_style_blocks(CSS)
    combined = "\n".join(styles)
    # There should be a rule for button icons using inherit/currentColor
    assert "color: inherit" in combined or "currentColor" in combined, \
        "CSS must ensure icons inherit theme color"


def test_no_hardcoded_icon_fill_stroke():
    """No global SVG fill/stroke forcing (breaks Streamlit icons)."""
    styles = _extract_style_blocks(CSS)
    combined = "\n".join(styles)
    # Check for problematic global fill/stroke rules
    # (scoped, intentional ones like the red button are OK)
    lines = combined.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("/*") or stripped.startswith("*"):
            continue
        # Look for fill: or stroke: that aren't part of background/border
        if re.match(r"^\s*(fill|stroke)\s*:", line):
            # This is a global fill/stroke — check if it's scoped to danger
            context = "\n".join(lines[max(0, i-5):i+1])
            assert "lib-danger" in context, \
                f"Global fill/stroke forcing found (not danger-scoped): {line.strip()}"


def test_dialog_uses_native_material_icons():
    """Delete dialog trigger uses native material icon (theme-safe)."""
    src = LIB_UI.read_text(encoding="utf-8")
    # The delete trigger should use _TB_ICON_DELETE
    assert '_TB_ICON_DELETE = ":material/delete:"' in src, \
        "delete icon must be native material icon"


def test_destructive_red_is_intentional():
    """The destructive button red is intentional (Apple HIG), not a theme bug."""
    styles = _extract_style_blocks(CSS)
    combined = "\n".join(styles)
    # The red should be scoped to lib-danger markers
    assert "lib-danger-" in combined, "destructive styling must be danger-scoped"
    assert "#FF3B30" in combined, "macOS system red should be present for destructive"


def test_no_hardcoded_colors_in_dialog_css():
    """Dialog-related CSS should not hardcode non-theme colors (except danger red)."""
    styles = _extract_style_blocks(CSS)
    combined = "\n".join(styles)
    # Find dialog/popover rules (excluding :root theme variable definitions)
    dialog_rules = []
    for rule in re.findall(r"([^{}]*)\{([^{}]*)\}", combined):
        selector, body = rule
        sel_lower = selector.lower()
        # Skip :root and theme variable definitions (these ARE the theme)
        if ":root" in sel_lower or "[data-theme" in sel_lower:
            continue
        if "dialog" in sel_lower or "stPopover" in selector:
            dialog_rules.append(body)
    # Check for hardcoded hex colors that aren't the intentional danger red
    allowed = {"#FF3B30", "#D92D20", "#FFFFFF", "#FFF"}
    for body in dialog_rules:
        hexes = re.findall(r"#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}\b", body)
        for h in hexes:
            assert h.upper() in allowed, \
                f"Hardcoded color {h} in dialog CSS (not danger-scoped)"
