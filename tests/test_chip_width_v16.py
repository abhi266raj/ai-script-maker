"""v1.6 (#56) — chip pills must hug their labels; no dead space before the ×.

Bug: hashtag/news-link pills rendered ~60-80px wider than their labels,
with dead space between the label text and the ×, and the × sat low
instead of vertically centered. Root cause: chip columns were
equal-weighted (``st.columns(len(tags))``) and the only thing sizing them
was a fragile CSS shrink-wrap chain (``flex: 0 0 auto`` + ``width: auto``)
behind long ``:has()`` selectors that assume one exact Streamlit DOM —
requirements.txt leaves Streamlit unpinned, so any DOM drift silently
degrades to full-width columns.

Fix (defense in depth):
1. Python: proportional ``st.columns`` weights from label lengths
   (``_chip_col_weights``) — a missed selector can now only ever yield a
   *proportionally* sized column, never a full-width one.
2. CSS: ``width: fit-content !important`` on the chip and on chip
   columns — hard caps that hold even if the row is not a flex
   container (``width: auto`` would fill a grid track).
3. #51 × centering (``top: 50%`` + ``translateY(-50%)``) untouched and
   still winning the cascade; #25/#26 44px clearance (#68 follow-up:
   user asked for more × breathing room), #45 colors kept.

Run: python -m pytest tests/test_chip_width_v16.py -q
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_lui():
    """Import library_ui with a capturing streamlit stub.

    Returns (module, css_chunks). Restores sys.modules afterwards.
    """
    saved = dict(sys.modules)
    chunks = []
    try:
        fake_mod = types.ModuleType("streamlit")
        fake_mod.markdown = lambda *a, **k: chunks.append(a[0] if a else "")
        # Any other streamlit attribute access returns a no-op callable.
        fake_mod.__getattr__ = lambda name: (lambda *a, **k: None)
        sys.modules["streamlit"] = fake_mod
        sys.modules.pop("library_ui", None)
        import library_ui as lui
        lui.inject_library_css()
        return lui, "\n".join(chunks)
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _block(css, selector_tail):
    """Return the declaration block of the first rule whose selector text
    contains selector_tail."""
    idx = css.find(selector_tail)
    assert idx != -1, f"rule containing {selector_tail!r} missing"
    brace = css.find("{", idx)
    return css[brace + 1:css.find("}", brace)]


# ---------------------------------------------------------------------------
# CSS: hard fit-content caps (#56)
# ---------------------------------------------------------------------------

def test_chip_column_width_is_fit_content_not_auto():
    _, css = _load_lui()
    block = _block(
        css,
        '+ div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]'
        ' > div[data-testid="stColumn"] {')
    assert "flex: 0 0 auto !important;" in block
    assert "width: fit-content !important;" in block
    assert "width: auto !important;" not in block, \
        "plain width:auto would fill a grid track; fit-content is the cap"


def test_chip_pill_width_is_fit_content():
    _, css = _load_lui()
    block = _block(css, '[data-testid="stHorizontalBlock"] .lib-chip {')
    assert "width: fit-content !important;" in block
    assert "max-width: 340px;" in block, \
        "long labels still capped (ellipsis)"


def test_image_cards_keep_fixed_180px_width():
    # The image-card column rule is more specific (:has(stImage)) and later,
    # so it must still beat the generic fit-content column rule.
    _, css = _load_lui()
    block = _block(css, 'div[data-testid="stColumn"]:has([data-testid="stImage"]) {')
    assert "width: 180px !important;" in block
    assert "flex: 0 0 180px !important;" in block


# ---------------------------------------------------------------------------
# CSS: #25/#26, #45, #51 guarantees preserved
# ---------------------------------------------------------------------------

def test_chip_clearance_44px_preserved():
    _, css = _load_lui()
    block = _block(css, '[data-testid="stHorizontalBlock"] .lib-chip {')
    # #68 follow-up: user asked for MORE space for the × — 44px
    # (22px target + 6px inset + 16px breathing room).
    assert "padding-right: 44px !important;" in block, \
        "#25/#26: label must never slide under the ×"
    assert "white-space: nowrap !important;" in block


def test_chip_x_centering_preserved():
    _, css = _load_lui()
    anchor = ('div[data-testid="stColumn"]:has(.lib-chip, [data-testid="stLinkButton"]):has([data-marker="lib-x-r"])')
    block = _block(css, anchor)
    for needle in ("top: 50% !important;",
                   "transform: translateY(-50%) !important;",
                   "right: 6px !important;"):
        assert needle in block, f"#51 centering lost: {needle}"


def test_chip_x_token_field_look_preserved():
    _, css = _load_lui()
    anchor = ('div[data-testid="stColumn"]:has(.lib-chip, [data-testid="stLinkButton"]):has([data-marker="lib-x-r"])')
    idx = css.find(anchor)
    btn_block = _block(css[idx:], '[data-testid="stButton"] button {')
    assert "background: transparent !important;" in btn_block
    assert "opacity: 0.65 !important;" in btn_block
    hover_block = _block(css[idx:], '[data-testid="stButton"] button:hover {')
    assert "opacity: 1 !important;" in hover_block
    assert "background: rgba(128, 128, 128, 0.22) !important;" in hover_block


def test_chip_theme_colors_preserved():
    _, css = _load_lui()
    assert "--lib-chip-bg: #F0E7D5;" in css, "#45 light chip fill"
    assert "--lib-chip-bg: #4A4034;" in css, "#45 dark chip fill"


# ---------------------------------------------------------------------------
# Python: proportional column weights (#56)
# ---------------------------------------------------------------------------

def test_chip_col_weights_proportional_to_label_length():
    lui, _ = _load_lui()
    short = lui._chip_col_weights(["#NiftyFall"])
    long_ = lui._chip_col_weights(["#IndianStockMarket"])
    assert long_[0] > short[0], "longer label must get a wider column"


def test_chip_col_weights_include_padding_allowance():
    lui, _ = _load_lui()
    # 6-char label + ~7 chars for the pill's fixed 56px horizontal padding
    # (#68 follow-up: clearance grew 34px → 44px for more × breathing room).
    assert lui._chip_col_weights(["#abcde"]) == [13]


def test_chip_col_weights_floor_keeps_tiny_labels_tappable():
    lui, _ = _load_lui()
    assert lui._chip_col_weights(["#a"]) == [11]
    assert lui._chip_col_weights([]) == []


def test_chip_col_weights_monotonic():
    lui, _ = _load_lui()
    labels = ["#a", "#abcd", "#abcdefgh", "#abcdefghijklmnop"]
    weights = lui._chip_col_weights(labels)
    assert weights == sorted(weights), f"not monotonic: {weights}"
    assert len(weights) == len(labels)


def test_hashtag_row_uses_proportional_weights():
    src = Path(__file__).resolve().parent.parent.joinpath(
        "library_ui.py").read_text()
    # #107: the title rides in the first column; chips keep proportional
    # weights (never equal-weighted).
    assert '_tcols = st.columns([_section_title_weight("Hashtags")]' in src
    assert "_chip_col_weights(tags)" in src
    assert "_tcols = st.columns(len(tags))" not in src


def test_newslink_row_uses_proportional_weights():
    src = Path(__file__).resolve().parent.parent.joinpath(
        "library_ui.py").read_text()
    # #107: the title rides in the first column; chips keep proportional
    # weights (never equal-weighted).
    assert '_lcols = st.columns([_section_title_weight("News Links")]' in src
    assert "_chip_col_weights(_labels)" in src
    assert "_lcols = st.columns(len(links))" not in src


def test_image_row_keeps_equal_columns():
    # Image cards are uniform 180px — equal weights stay correct there.
    src = Path(__file__).resolve().parent.parent.joinpath(
        "library_ui.py").read_text()
    assert "_icols = st.columns(len(_cards))" in src
