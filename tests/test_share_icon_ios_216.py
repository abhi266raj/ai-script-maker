"""#216 — Share icon uses the iOS share metaphor, not Android.

Apple HIG §5 ("Icons & symbols", plus §2's standard-icons guidance):
familiar actions get familiar platform icons — share on macOS is the
iOS-style square-with-up-arrow (SF Symbols ``square.and.arrow.up``),
not Android's three-node ``share`` glyph. Streamlit's native Material
Symbols support provides the same metaphor as ``:material/ios_share:``.

Run: python -m pytest tests/test_share_icon_ios_216.py -q
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_library_v15 import _ui_with_fake_st  # noqa: E402


def test_share_constant_uses_ios_share_glyph():
    lui, _ = _ui_with_fake_st()
    assert lui._TB_ICON_SHARE == ":material/ios_share:", \
        f"share icon regressed to: {lui._TB_ICON_SHARE!r}"


def test_share_constant_is_not_android_share_glyph():
    lui, _ = _ui_with_fake_st()
    assert lui._TB_ICON_SHARE != ":material/share:"


def test_no_material_share_shortcode_remains_in_codebase():
    """Same bug class as #216: no ``:material/share:`` (Android metaphor)
    anywhere in shipped or test Python. The iOS glyph is ``ios_share``."""
    root = Path(__file__).resolve().parent.parent
    bad = []
    for py in sorted(root.rglob("*.py")):
        if py.name == "test_share_icon_ios_216.py":
            continue  # this file names the old shortcode intentionally
        try:
            text = py.read_text()
        except OSError:
            continue
        for m in re.finditer(r":material/share:", text):
            bad.append(f"{py.relative_to(root)}: line {text.count(chr(10), 0, m.start()) + 1}")
    assert not bad, "Android share glyph still present:\n" + "\n".join(bad)


def test_share_glyph_name_is_valid_material_symbols_identifier():
    """``ios_share`` is a real Material Symbols icon name (Google Fonts);
    the shortcode shape must survive exactly as passed to Streamlit."""
    lui, _ = _ui_with_fake_st()
    icon = lui._TB_ICON_SHARE
    assert icon.startswith(":material/") and icon.endswith(":")
    assert icon == ":material/ios_share:"
