"""Library tab UI (v1.5): macOS-style tab bar + master-detail story browser.

The existing Studio flow is never re-indented or altered: when the Library
tab is selected this module renders the library page and the caller stops
the script (st.stop()) before any Studio code runs.
"""

from __future__ import annotations

import base64 as _base64
import html as _html
import re as _re
import time as _time
from collections.abc import Callable
from functools import lru_cache as _lru_cache
from pathlib import Path as _Path

import streamlit as st

import story_library as lib

TAB_STUDIO = "Studio"
TAB_LIBRARY = "Library"


def _library_ai_engine() -> str | None:
    """Engine mode for Library AI processing, or None when it is disabled.

    Reads the persisted ``library_ai_enabled`` / ``library_ai_engine`` prefs
    (off by default). The AI only ever suggests hashtags — it never alters
    the screenplay, story content, verified links, or images.
    """
    try:
        prefs = lib.load_prefs()
    except Exception:
        return None
    if not prefs.get("library_ai_enabled", False):
        return None
    label = prefs.get("library_ai_engine", lib.DEFAULT_LIBRARY_AI_ENGINE)
    return lib.LIBRARY_ENGINE_OPTIONS.get(label)


# ---------------------------------------------------------------------------
# CSS (separate block — the app's main CSS block is untouched)
# ---------------------------------------------------------------------------

# v1.6.2 (#90): toolbar icon font. "LibToolbarIcons" is a 7-glyph subset
# of Material Symbols Outlined (Apache License 2.0,
# google/material-design-icons), self-hosted as a base64 data URI — no CDN,
# so the app never needs the network for its own chrome. PUA codepoints
# from the official .codepoints file; the subset is reproducible via
# assets/fonts/build_toolbar_icons.sh (see assets/fonts/README.md for the
# license note and the glyph map). Glyphs inherit currentColor, so they
# follow the light/dark theme with no hard-coded color.
_TB_FONT_FAMILY = "LibToolbarIcons"
_TB_ICON_TAG = "\ue9ef"      # Update Hashtags
_TB_ICON_IMAGE = "\ue3f4"    # Update Images
_TB_ICON_NEWS = "\ueb81"     # Update News
_TB_ICON_RESET = "\ue5d5"    # Reset
_TB_ICON_SHARE = "\ue80d"    # Share
_TB_ICON_COPY = "\ue14d"     # Copy
_TB_ICON_DELETE = "\ue92e"   # Delete
_TOOLBAR_FONT_FILE = (
    _Path(__file__).resolve().parent / "assets" / "fonts" / "toolbar-icons.woff2"
)
_tb_font_b64: str | None = None


def _toolbar_icon_font_b64() -> str:
    """Base64 of the bundled toolbar icon font (#90).

    Fail loudly: without the @font-face the toolbar buttons render as
    tofu boxes, so a missing/empty asset raises instead of emitting CSS
    that silently breaks every toolbar icon.
    """
    global _tb_font_b64
    if _tb_font_b64 is None:
        try:
            raw = _TOOLBAR_FONT_FILE.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"toolbar icon font unreadable: {_TOOLBAR_FONT_FILE} ({exc})")
        if not raw:
            raise RuntimeError(
                f"toolbar icon font is empty: {_TOOLBAR_FONT_FILE}")
        _tb_font_b64 = _base64.b64encode(raw).decode("ascii")
    return _tb_font_b64


def _toolbar_font_face_css() -> str:
    """The @font-face <style> block for the toolbar icon font (#90).

    Its own <style> block so the data URI never touches the main CSS
    literal in :func:`inject_library_css`.
    """
    return (
        "<style>\n"
        "@font-face {\n"
        f'    font-family: "{_TB_FONT_FAMILY}";\n'
        f"    src: url(data:font/woff2;base64,{_toolbar_icon_font_b64()})"
        ' format("woff2");\n'
        "    font-weight: 400;\n"
        "    font-style: normal;\n"
        "    font-display: block;\n"
        "}\n"
        "</style>\n"
    )


def inject_library_css() -> None:
    st.markdown(
        _toolbar_font_face_css()
        + """
<style>
    :root,
    [data-theme="light"] {
        --lib-seg-bg: #E9E2D6;
        --lib-seg-active-bg: #FFFFFF;
        --lib-seg-active-shadow: 0 1px 3px rgba(60, 40, 20, 0.18);
        /* latest macOS: floating glass tab strip */
        --lib-glass-bg: rgba(233, 226, 214, 0.55);
        --lib-glass-border: rgba(255, 255, 255, 0.55);
        --lib-glass-shadow: 0 8px 24px rgba(60, 40, 20, 0.10), 0 1px 3px rgba(60, 40, 20, 0.08);
        --lib-dialogue-bg: #FFF8E7;
        --lib-dialogue-border: #E8B93C;
        --lib-dialogue-text: #5A3E00;
        --lib-script-bg: #EFF4FF;
        --lib-script-border: #6B8DD6;
        --lib-script-text: #1E3A6E;
        /* Chips: warm pill, hairline edge for definition (HIG: flat,
           bordered pills, no shadow). Text contrast ≥ 7:1 both themes. */
        --lib-chip-bg: #F0E7D5;
        --lib-chip-text: #5A4227;
        --lib-chip-border: rgba(90, 66, 39, 0.28);
        /* IDE-style token colors for the full script view */
        --lib-spk: #1D4ED8;
        --lib-said: #047857;
        --lib-key: #0E7490;
    }
    :root[data-theme="dark"],
    html[data-theme="dark"],
    body[data-theme="dark"],
    [data-theme="dark"] {
        --lib-seg-bg: #2E2620;
        --lib-seg-active-bg: #4A3F33;
        --lib-seg-active-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
        /* latest macOS: floating glass tab strip */
        --lib-glass-bg: rgba(46, 38, 32, 0.55);
        --lib-glass-border: rgba(255, 255, 255, 0.14);
        --lib-glass-shadow: 0 8px 24px rgba(0, 0, 0, 0.35), 0 1px 3px rgba(0, 0, 0, 0.4);
        --lib-dialogue-bg: #3A2E14;
        --lib-dialogue-border: #C99A2E;
        --lib-dialogue-text: #F5DFA0;
        --lib-script-bg: #1E2A44;
        --lib-script-border: #5B7BC0;
        --lib-script-text: #C9D9F5;
        /* Chips (dark): lifted warm surface replaces the muddy flat
           fill; hairline edge keeps the pill defined on dark trays. */
        --lib-chip-bg: #4A4034;
        --lib-chip-text: #F2E4C2;
        --lib-chip-border: rgba(242, 228, 194, 0.22);
        /* IDE-style token colors for the full script view */
        --lib-spk: #93C5FD;
        --lib-said: #6EE7B7;
        --lib-key: #67E8F9;
    }
    /* ONE alignment system for the detail action buttons and the three
       horizontal rows (hashtags / images / news links). Theme-neutral
       layout tokens — single source of truth for chip height, card gap,
       × size/position and row spacing. --lib-act-h is mirrored in Python
       as _LIB_ACTION_BTN_H_PX for the copy-button iframe, which cannot
       read page CSS. */
    :root {
        --lib-chip-h: 30px;     /* every chip, every row: one height */
        --lib-chip-gap: 10px;   /* gap between cards in a scroll row */
        --lib-x-size: 22px;     /* × overlay button diameter */
        --lib-act-h: 38px;      /* Share/Copy action button height */
        --lib-row-space: 22px;  /* vertical rhythm between sections */
    }
    /* macOS segmented tab bar — latest macOS: a floating glass tab strip.
       Real DOM (Streamlit 1.64): div[data-testid="stButtonGroup"] >
       div[role="radiogroup"] > button[data-variant="segmented_control"],
       with the active segment marked data-selected="true".
       Labels are plain 13px text (macOS HIG: no emoji in tab titles).
       Centering: the strip is centered via its widget element container
       (div.st-key-lib_view), NOT via .lib-tabbar or margin:auto on the
       widget itself. Two real-DOM reasons, verified against Streamlit 1.64:
       (a) a <div> opened in one st.markdown call and closed in a later one
       is auto-closed by the browser inside its own block, so the widget is
       never actually inside .lib-tabbar; (b) Streamlit 1.64 shrink-wraps
       element containers (width: fit-content), so margin:auto on the inner
       widget has no free space to center in (it computes to 0). */
    /* Center the tab bar: full-width flex row on the widget's own container. */
    div.st-key-lib_view[data-testid="stElementContainer"] {
        width: 100% !important;
        max-width: 100% !important;
        display: flex !important;
        justify-content: center !important;
    }
    /* Hide the "View" widget label Streamlit puts above the strip. */
    [data-testid="stButtonGroup"] > label[data-testid="stWidgetLabel"] {
        display: none !important;
    }
    [data-testid="stButtonGroup"] {
        width: fit-content !important;
        margin: 10px auto 18px auto !important;
    }
    [data-testid="stButtonGroup"] > div[role="radiogroup"] {
        background: var(--lib-glass-bg) !important;
        -webkit-backdrop-filter: blur(18px) saturate(160%);
        backdrop-filter: blur(18px) saturate(160%);
        border: 1px solid var(--lib-glass-border) !important;
        border-radius: 18px !important;
        padding: 4px !important;
        gap: 2px !important;
        box-shadow: var(--lib-glass-shadow) !important;
    }
    [data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 6px 26px !important;
        border: none !important;
        border-radius: 14px !important;
        background: transparent !important;
        box-shadow: none !important;
        color: #6B5F4E !important;
    }
    [data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover {
        background: rgba(60, 40, 20, 0.06) !important;
        color: #3A2E1A !important;
    }
    [data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] {
        background: var(--lib-seg-active-bg) !important;
        color: #2A2118 !important;
        box-shadow: var(--lib-seg-active-shadow) !important;
        font-weight: 600 !important;
    }
    [data-testid="stButtonGroup"] button[data-variant="segmented_control"]:focus-visible {
        outline: 2px solid #E0692A !important;
        outline-offset: 1px !important;
    }
    [data-theme="dark"] [data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
        color: #A89B8B !important;
    }
    [data-theme="dark"] [data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover {
        background: rgba(255, 255, 255, 0.06) !important;
        color: #F5EFE3 !important;
    }
    [data-theme="dark"] [data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] {
        color: #FAF7F0 !important;
    }
    /* Fallback: horizontal radio styled as segmented control
       (scoped to the tab bar's widget container) */
    div.st-key-lib_view [data-testid="stRadio"] > div[role="radiogroup"] {
        flex-direction: row !important;
        gap: 2px !important;
        background: var(--lib-seg-bg) !important;
        border-radius: 12px !important;
        padding: 3px !important;
    }
    div.st-key-lib_view [data-testid="stRadio"] label {
        border-radius: 9px !important;
        padding: 6px 18px !important;
        margin: 0 !important;
    }
    div.st-key-lib_view [data-testid="stRadio"] label:has(input:checked) {
        background: var(--lib-seg-active-bg) !important;
        box-shadow: var(--lib-seg-active-shadow) !important;
    }
    div.st-key-lib_view [data-testid="stRadio"] label > div:first-child { display: none !important; }
    /* Detail view: color-coded sections */
    .lib-dialogue {
        background: var(--lib-dialogue-bg);
        border-left: 4px solid var(--lib-dialogue-border);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0 16px 0;
        color: var(--lib-dialogue-text);
    }
    .lib-script {
        background: var(--lib-script-bg);
        border-left: 4px solid var(--lib-script-border);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0 16px 0;
        color: var(--lib-script-text);
    }
    .lib-script-line { margin: 8px 0; }
    .lib-dialogue-line {
        background: var(--lib-dialogue-bg);
        border-left: 4px solid var(--lib-dialogue-border);
        color: var(--lib-dialogue-text);
        border-radius: 6px;
        padding: 8px 12px;
        margin: 8px 0;
    }
    /* IDE-style syntax colors inside the script view */
    .lib-spk { color: var(--lib-spk); font-weight: 700; }
    .lib-said { color: var(--lib-said); }
    .lib-key { color: var(--lib-key); font-weight: 600; font-style: normal; }
    .lib-chip {
        display: inline-flex;
        align-items: center;
        box-sizing: border-box;  /* border must not grow the 30px pill */
        min-height: var(--lib-chip-h);
        background: var(--lib-chip-bg);
        color: var(--lib-chip-text);
        border: 1px solid var(--lib-chip-border);
        border-radius: 999px;
        padding: 3px 12px;
        margin: 2px 4px 2px 0;
        font-size: 13px;
        font-weight: 600;
    }
    /* Horizontal scroll rows (hashtags / images / news links). Marker-scoped:
       a hidden [data-marker="lib-hscroll"] div sits directly before the
       st.columns() call, so these rules NEVER touch any other horizontal
       block. Real DOM (verified): the marker's stElementContainer is
       immediately followed by div[data-testid="stLayoutWrapper"] >
       div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]
       (Streamlit calls it "stColumn", not "column"). Columns become
       non-wrapping flex items that scroll on overflow.
       The row renders as a quiet tray (translucent neutral = theme-safe),
       giving the stacked sections a layered z-axis read instead of flat. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        gap: var(--lib-chip-gap) !important;
        padding: 10px 10px 12px 10px !important;
        align-items: start !important;
        background: rgba(128, 128, 128, 0.08) !important;
        border-radius: 14px !important;
    }
    /* #56: width: fit-content (not auto) — the column can never exceed
       its content even if the row's layout mode is not flex (e.g. a
       grid, where width:auto would fill the track) or a future
       Streamlit DOM nests differently. flex: 0 0 auto stays the primary
       shrink-wrap on the verified DOM. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 0 0 auto !important;
        width: fit-content !important;
        min-width: 0 !important;
        position: relative !important;
    }
    /* Chips inside scroll rows: single line, never clipped by the ×.
       #51: the × now sits INSIDE the pill as a macOS token-field remove
       glyph (22px target, 6px from the pill's trailing edge), so the
       pill's own padding-right carries the clearance: 44px = 22px
       target + 6px inset + 16px breathing room before the label
       (#68 follow-up: user asked for MORE space for the × — 34px's 6px
       breathing room was too tight).
       #25/#26 no-truncation guarantee now lives here, in the chip —
       the column no longer reserves padding for the × (rule removed).
       #68 ROOT CAUSE: this selector previously used a DESCENDANT
       combinator after the marker container, but the real DOM has the
       marker's stElementContainer as a SIBLING of
       stLayoutWrapper > stHorizontalBlock (see the verified-DOM comment
       above) — so the rule never matched, the pill kept only the base
       12px right padding, and the × (positioned 6px from the column's
       trailing edge, which hugs the pill after #56) landed on top of
       the label. Every other marker-scoped rule uses the adjacent-
       sibling form below; this one must too. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] .lib-chip {
        padding-right: 44px !important;
        white-space: nowrap !important;
        width: fit-content !important;  /* #56: the pill hugs its label —
           never wider than content + padding, even if an ancestor rule
           misbehaves. max-width below still caps long labels. */
        max-width: 340px;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* Links inside news chips inherit the themed chip color (theme-safe).
       #68: same sibling-combinator fix as the pill rule above — the
       descendant form never matched the real DOM. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] .lib-chip a {
        color: inherit !important;
        text-decoration: underline;
    }
    /* Image cards: one uniform size so every card in the row shares a
       baseline. Columns holding an image become fixed 180px cards; the
       image covers a 120px-tall frame (cropped, never distorted) with
       rounded corners. Scoped by :has(stImage) — no Python change needed. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has([data-testid="stImage"]) {
        flex: 0 0 180px !important;
        width: 180px !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has([data-testid="stImage"])
        [data-testid="stImage"] img {
        width: 100% !important;
        height: 120px !important;
        object-fit: cover !important;
        border-radius: 10px !important;
        display: block !important;
    }
    /* #68 FOLLOW-UP (bottom-aligned ×): the lib-x-r/lib-x-l marker divs
       are display:none themselves, but their stElementContainer wrapper
       still occupies one inter-element gap in the column's vertical
       block — the exact #24 / #53 pattern (lib-x- markers were left
       untouched by those fixes). The column becomes taller than the pill,
       so the chip × — top: 50% + translateY(-50%) of the COLUMN — lands
       BELOW the pill's vertical center: bottom-aligned instead of
       vertically centered (user screenshot, dark mode). Collapse the
       wrapper; the `+` sibling selectors above keep matching on DOM
       order regardless of display. Image cards are unaffected: their ×
       is pinned top: 4px of the column, which is still the image's top
       edge once the wrapper collapses. Scoped to the hscroll rows so
       no other marker usage is touched. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stElementContainer"]:has([data-marker^="lib-x-"]) {
        display: none !important;
    }
    /* × / ✎ overlay buttons float OVER their card. Real DOM per item column:
       div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] >
       [content container, marker container (display:none div holding
       data-marker="lib-x-r"/"lib-x-l"), button container]. The button's
       container is the sibling immediately after the marker's container:
       it is lifted out of flow and pinned to the card's top corner, ABOVE
       the content in z-order; the column is the positioned ancestor
       (position:relative set above). Quiet and theme-safe (translucent
       neutral, inherits text color, blurred backdrop + soft shadow so it
       reads over busy images). */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has([data-marker="lib-x-r"])
        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])
        + div[data-testid="stElementContainer"] {
        position: absolute !important;
        top: 4px !important;
        right: 4px !important;
        width: auto !important;
        z-index: 10 !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has([data-marker="lib-x-l"])
        div[data-testid="stElementContainer"]:has([data-marker="lib-x-l"])
        + div[data-testid="stElementContainer"] {
        position: absolute !important;
        top: 4px !important;
        left: 4px !important;
        width: auto !important;
        z-index: 10 !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]
        div[data-testid="stElementContainer"]:has([data-marker^="lib-x-"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button {
        width: var(--lib-x-size) !important;
        height: var(--lib-x-size) !important;
        min-width: var(--lib-x-size) !important;
        min-height: var(--lib-x-size) !important;
        padding: 0 !important;
        border-radius: 999px !important;
        font-size: 13px !important;
        line-height: 1 !important;
        background: rgba(128, 128, 128, 0.35) !important;
        -webkit-backdrop-filter: blur(6px) !important;
        backdrop-filter: blur(6px) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25) !important;
        color: inherit !important;
        border: 1px solid rgba(128, 128, 128, 0.45) !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]
        div[data-testid="stElementContainer"]:has([data-marker^="lib-x-"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button:hover {
        background: rgba(128, 128, 128, 0.55) !important;
        color: inherit !important;
        border-color: rgba(128, 128, 128, 0.7) !important;
    }
    /* v1.6 (#46): the Share/Copy dropdowns moved INTO the single detail
       toolbar row, so the old marker-scoped actions-row rule is gone (dead
       selector). The triggers now share the toolbar's own gap/alignment. */
    /* #51: the chip × becomes a macOS token-field remove glyph, centered
       inside the pill. Chip-scoped: columns holding a chip
       (:has(.lib-chip)) with the lib-x-r marker. Image cards have no
       .lib-chip, so their top-right corner × over the image is untouched;
       the ✎ is lib-x-l, also untouched. The extra :has(.lib-chip) makes
       these selectors strictly more specific than the generic × rules
       above, so they win without touching them. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has(.lib-chip):has([data-marker="lib-x-r"])
        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])
        + div[data-testid="stElementContainer"] {
        top: 50% !important;
        right: 6px !important;
        transform: translateY(-50%) !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has(.lib-chip):has([data-marker="lib-x-r"])
        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button {
        background: transparent !important;
        -webkit-backdrop-filter: none !important;
        backdrop-filter: none !important;
        box-shadow: none !important;
        border: none !important;
        color: var(--lib-chip-text) !important;
        opacity: 0.65 !important;
        font-size: 15px !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has(.lib-chip):has([data-marker="lib-x-r"])
        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button:hover {
        opacity: 1 !important;
        background: rgba(128, 128, 128, 0.22) !important;
        color: var(--lib-chip-text) !important;
        border: none !important;
        box-shadow: none !important;
    }
    /* v1.6 (#27/#28/#30): the WhatsApp link button moved inside the Share
       popover, which renders in a portal outside the marker's subtree, so the
       old marker-scoped 38px height rule no longer applies. The popover's
       link button uses use_container_width and Streamlit's native button
       metrics — no custom height needed. */
    /* v1.6.2 (#95): "Send via WhatsApp" is a plain anchor with NO
       target="_blank" (st.link_button forces a new browser tab, defeating
       the whatsapp:// deep link). Styled to read as a popover button;
       theme-safe via inherit + neutral gray. Vector icons keep their own
       paint — nothing here touches them. */
    a.lib-wa-direct {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        box-sizing: border-box;
        padding: 0.4rem 1rem;
        border: 1px solid rgba(128, 128, 128, 0.45);
        border-radius: 0.5rem;
        color: inherit !important;
        text-decoration: none !important;
        font-size: 1rem;
        line-height: 1.6;
        cursor: pointer;
    }
    a.lib-wa-direct:hover {
        border-color: currentColor;
        color: inherit !important;
        text-decoration: none !important;
    }
    /* macOS HIG: deference — toolbar rows use a hairline, not a heavy box */
    .lib-hairline {
        border-bottom: 1px solid rgba(128, 128, 128, 0.25);
        margin: 4px 0 12px 0;
    }
    /* v1.6 (#53) HIG progress: the button that starts work owns its loading
       state — its label NEVER changes, it shows a spinner and stays
       disabled while the work runs. A hidden marker
       (data-marker="lib-spin-<kind>") is emitted directly before the
       running button's element container; the spinner is painted via
       ::before with currentColor so it follows the light/dark theme
       automatically. Width stability comes from use_container_width on
       the toolbar buttons (each fills its fixed column slot), so no width
       CSS is needed and nothing shoves its neighbours. */
    @keyframes lib-spin {
        to { transform: rotate(360deg); }
    }
    div[data-testid="stElementContainer"]:has([data-marker^="lib-spin-"]) {
        display: none !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-spin-hashtags"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button::before,
    div[data-testid="stElementContainer"]:has([data-marker="lib-spin-images"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button::before,
    div[data-testid="stElementContainer"]:has([data-marker="lib-spin-news"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button::before,
    div[data-testid="stElementContainer"]:has([data-marker="lib-spin-more-images"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button::before,
    div[data-testid="stElementContainer"]:has([data-marker="lib-spin-more-news"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button::before,
    /* #81: the reset spinner selector is the SAME adjacent-sibling shape as
       hashtags/images/news — the lib-spin-reset marker's container
       immediately followed by the popover trigger's container. The old
       3-hop selector routed through the lib-danger-pop- marker, which
       never matched the real DOM, so the spinner silently never painted.
       _render_reset_popover emits lib-spin-reset immediately before the
       popover (see _confirm_popover's spin_marker param). */
    div[data-testid="stElementContainer"]:has([data-marker="lib-spin-reset"])
        + div[data-testid="stElementContainer"] [data-testid="stPopover"] [data-testid="stPopoverButton"]::before {
        content: "";
        display: inline-block;
        width: 13px;
        height: 13px;
        margin-right: 7px;
        vertical-align: -2px;
        border: 2px solid currentColor;
        border: 2px solid color-mix(in srgb, currentColor 25%, transparent);
        border-top-color: currentColor;
        border-radius: 50%;
        animation: lib-spin 0.9s linear infinite;
    }
    /* v1.6.2 (#90): toolbar icon font. The seven story-detail toolbar
       controls (Update Hashtags / Images / News, Reset, Share, Copy,
       Delete) are icon-only — each emits a data-tbicon marker directly
       before its element container, and these rules paint the icon font
       on exactly those controls: plain buttons AND popover triggers
       ([data-testid="stPopoverButton"] carries the label in a <p>, so it
       needs its own line). Scoped: nothing else in the app uses the
       marker, so no other button is touched — never a global rule.
       Glyphs inherit currentColor, so they follow the light/dark theme
       with no hard-coded color. The native popover chevron is Streamlit's
       own SVG and is untouched (never force SVG fill/stroke). */
    div[data-testid="stElementContainer"]:has([data-tbicon]) {
        display: none !important;
    }
    div[data-testid="stElementContainer"]:has([data-tbicon])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button,
    div[data-testid="stElementContainer"]:has([data-tbicon])
        + div[data-testid="stElementContainer"] [data-testid="stPopover"] [data-testid="stPopoverButton"],
    div[data-testid="stElementContainer"]:has([data-tbicon])
        + div[data-testid="stElementContainer"] [data-testid="stPopover"] [data-testid="stPopoverButton"] p {
        font-family: "LibToolbarIcons", "Source Sans Pro", sans-serif !important;
        font-size: 20px !important;
        line-height: 1 !important;
    }
    /* macOS HIG section header: plain semibold text, no emoji, no boxes */
    .lib-section {
        font-size: 15px;
        font-weight: 600;
        margin: var(--lib-row-space) 0 8px 0;
    }
    /* Quiet inline status line (replaces loud banners for background work) */
    .lib-quiet {
        text-align: center;
        font-size: 13px;
        opacity: 0.65;
        margin: 2px 0 10px 0;
    }
    /* macOS HIG: document title centered, multiline, theme-safe (#84
       reverts #60 — the full title text is back as an h2). */
    .lib-doc-title {
        text-align: center;
        font-size: 30px;
        font-weight: 700;
        line-height: 1.25;
        margin: 6px 0 2px 0;
        overflow-wrap: anywhere;
    }
    /* #68 follow-up / #84: the story title never shows Streamlit's
       heading-anchor 🔗 link icon. Streamlit appends that anchor to h1–h6
       rendered through st.markdown — including the raw-HTML
       <h2 class="lib-doc-title"> title restored by #84 (the user's
       screenshot showed the icon on it). The anchor stays hidden. */
    .lib-doc-title a {
        display: none !important;
    }
    .lib-empty {
        text-align: center;
        padding: 48px 16px;
        color: var(--lib-chip-text);
        font-size: 15px;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tab bar
# ---------------------------------------------------------------------------

def _inject_story_list_css() -> None:
    """Library-page-only CSS: the story list renders as a macOS sidebar.

    Only injected on the Library view, where the story radio is the sole
    radio widget — the Studio view never sees these rules.
    """
    st.markdown(
        """
<style>
    /* macOS sidebar: plain rows, accent-tinted rounded selection */
    div[data-testid="stElementContainer"]:has([data-marker="lib-story-list"])
        + div[data-testid="stElementContainer"] [data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 2px !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-story-list"])
        + div[data-testid="stElementContainer"] [data-testid="stRadio"] label {
        border-radius: 8px !important;
        padding: 7px 10px !important;
        margin: 0 !important;
        font-size: 13.5px !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-story-list"])
        + div[data-testid="stElementContainer"] [data-testid="stRadio"] label:has(input:checked) {
        background: rgba(0, 122, 255, 0.15) !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-story-list"])
        + div[data-testid="stElementContainer"] [data-testid="stRadio"] label:has(input:checked) p {
        font-weight: 600 !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-story-list"])
        + div[data-testid="stElementContainer"] [data-testid="stRadio"] label > div:first-child {
        display: none !important;
    }
    /* Sidebar section header */
    .lib-sidebar-label {
        font-size: 12px;
        font-weight: 600;
        opacity: 0.55;
        margin: 2px 0 6px 2px;
    }
    /* v1.6 (#24): the lib-danger-/lib-danger-pop- marker divs are
       display:none themselves, but their stElementContainer wrapper still
       occupies one inter-element gap in Streamlit's vertical block —
       pushing the "Reset"/"Delete" popover triggers (and the red
       destructive button inside the popover) one gap lower than their
       plain-button siblings.
       Collapse the wrapper: CSS `+` sibling combinators and :has() match
       on DOM order regardless of display, so the red-button rule below
       keeps matching. Prefix-scoped: lib-x-/lib-hscroll/
       lib-story-list markers are untouched. */
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"]) {
        display: none !important;
    }
    /* Destructive actions (#87): solid macOS system red fill with white
       text — like Apple's destructive alert buttons. Legible on both
       themes. Graceful — plain button if unmatched. */
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button {
        background-color: #FF3B30 !important;
        color: #FFFFFF !important;
        border-color: #FF3B30 !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button:hover {
        background-color: #D92D20 !important;
        color: #FFFFFF !important;
        border-color: #D92D20 !important;
    }
    /* v1.6 (#58): destructive popover triggers are NEUTRAL — they read as
       plain buttons like their neighbours (see the approved screenshot).
       macOS system red lives ONLY on the explicit destructive button
       inside the popover (the lib-danger- rule above). This deliberately
       reverses the #38 red trigger. */
    /* v1.6 (#38): HIG-anchored destructive popover. Streamlit renders the
       popover body inside a floating overlay portal, so the lib-danger-pop-
       marker sitting before the trigger cannot reach the body with sibling
       combinators. A lib-danger-pop-body marker is therefore emitted as the
       first node *inside* the popover body (see _confirm_popover), and the
       caret below anchors to the body itself. The 45° square inherits the
       body's own background, so it tracks the light/dark theme with no
       hard-coded surface color. Graceful: if the selector ever misses, the
       popover simply renders without the caret. */
    div[data-testid="stPopoverBody"]:has([data-marker="lib-danger-pop-body"])::before {
        content: "" !important;
        position: absolute !important;
        top: -8px !important;
        right: 32px !important;
        width: 14px !important;
        height: 14px !important;
        background: inherit !important;
        transform: rotate(45deg) !important;
        pointer-events: none !important;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def _md_escape(text: str) -> str:
    """Backslash-escape Markdown special characters so user-controlled text
    (e.g. a story title) renders literally inside ``st.markdown``.

    ``st.markdown`` already neutralises raw HTML (``unsafe_allow_html``
    defaults to False), but Markdown *syntax* in the text — ``**``, ``[]()``,
    backticks — would still be interpreted and could break the surrounding
    formatting or inject a link. Every Markdown special is escaped; the
    function is total (None/empty → "") and never raises.
    """
    return _re.sub(r"([\\`*_{}\[\]()#+\-.!|])", r"\\\1", text or "")


def _danger_button(label: str, key: str, **kwargs) -> bool:
    """Mac-style destructive button: solid system-red fill, white text (#87).

    The marker div sits directly before the button so the CSS can target
    exactly this button. If the selector ever misses, it degrades to a
    normal button — never broken.
    """
    st.markdown(f'<div data-marker="lib-danger-{key}" style="display:none"></div>',
                unsafe_allow_html=True)
    return st.button(label, key=key, **kwargs)


def _confirm_delete_story(story_id: str) -> None:
    """Delete one story; raises loudly if the file could not be removed."""
    if not lib.delete_story(story_id):
        raise RuntimeError("the story file could not be removed")
    st.session_state.pop("lib_selected_story", None)
    st.session_state.pop("lib_story_radio", None)
    st.success("Story deleted.")


def _confirm_delete_all() -> None:
    """Delete every story; the reported count is always honest."""
    n = lib.delete_all_stories()
    st.session_state.pop("lib_selected_story", None)
    st.session_state.pop("lib_story_radio", None)
    st.success(f"Deleted {n} stor{'y' if n == 1 else 'ies'}.")


def _confirm_popover(*, trigger_label: str, popover_key: str, title: str,
                     message: str, on_yes: Callable[[], None],
                     trigger_help: str = "",
                     use_container_width: bool = False,
                     fail_label: str = "Confirm",
                     destructive_label: str,
                     disabled: bool = False,
                     spin_marker: str = "",
                     icon_trigger: bool = False) -> None:
    """Apple-style confirmation: native popover, explicit red destructive
    verb, standard Cancel. (#58)

    The trigger is a NEUTRAL button, like its neighbours — macOS system red
    lives only on the destructive action inside the popover (this reverses
    the #38 red trigger, per the approved screenshot). Inside the popover:
    a bold title, a secondary message line, then "Cancel" (standard, left)
    and the destructive verb (red, right) side by side — never a bare
    "Yes"/"No".

    The destructive verb arms a ``<key>-go`` flag via an ``on_click``
    callback and closes the popover; the flag is consumed at the top of
    the next script run — *before* the popover widget instantiates, which
    is the only moment its key may be driven programmatically (doing it
    after raises ``StreamlitWidgetAlreadyInstantiatedError``). ``on_yes``
    must raise on failure: the error is shown loudly inside the reopened
    popover and the popover stays open. "Cancel" only closes the popover.
    The native popover follows the light/dark theme; the only custom color
    is macOS system red, which reads on both themes.

    ``title`` may carry user-controlled text (e.g. a story name): Markdown
    specials are escaped so it renders literally and can never break the
    bold wrapper or inject a link. ``fail_label`` prefixes the loud error
    (e.g. "Delete", "Reset"); ``destructive_label`` is the explicit red
    button verb (e.g. "Delete story", "Reset media"). ``disabled`` disables
    the trigger (e.g. while its work is running). Per the HIG progress
    contract (#53) the trigger label NEVER changes to show progress — a
    separate marker carries the spinner while the work runs. ``spin_marker``
    names that marker's data-marker (e.g. "lib-spin-reset"); when given it
    is emitted IMMEDIATELY before the popover trigger, so the spinner CSS
    is the same adjacent-sibling shape as the hashtag/image/news buttons
    (#81 — the old 3-hop selector through the danger-pop marker never
    matched the real DOM).

    #90: ``icon_trigger`` marks the trigger for the toolbar icon font —
    ``data-tbicon`` rides on the LAST marker emitted before the popover
    trigger (the spin marker when one is given, else the danger-pop
    marker), so the icon-font CSS uses the same adjacent-sibling anchor
    as the spinner CSS. Both markers keep their own ``data-marker``
    untouched — the #24 collapse and #53/#81 spin ``+`` chains keep
    matching — and the caller passes an icon glyph as ``trigger_label``.
    """
    _go_key = f"{popover_key}-go"
    _err_key = f"{popover_key}-err"
    # Marker first: it must sit directly before the popover's element
    # container for the #24 collapse rule (the marker's wrapper would
    # otherwise push the trigger one gap lower than its siblings).
    # #90: data-tbicon rides the LAST marker before the popover trigger
    # (the spin marker when #81 emits one, else the danger-pop marker) —
    # the icon-font CSS anchors on the immediate predecessor, exactly
    # like the spinner CSS.
    _tbicon_here = " data-tbicon" if (icon_trigger and not spin_marker) else ""
    st.markdown(f'<div data-marker="lib-danger-pop-{popover_key}"{_tbicon_here} style="display:none"></div>',
                unsafe_allow_html=True)
    if spin_marker:
        # #81: the spinner marker sits immediately before the popover's
        # element container — the #53 pattern the hashtag/image/news
        # spinners use, and the only shape whose CSS selector matches.
        _tbicon_spin = " data-tbicon" if icon_trigger else ""
        st.markdown(f'<div data-marker="{spin_marker}"{_tbicon_spin} style="display:none"></div>',
                    unsafe_allow_html=True)
    # Consume a previously armed confirmation *before* the popover
    # instantiates, so driving its key here is legal.
    if st.session_state.pop(_go_key, False):
        try:
            on_yes()
        except Exception as e:
            st.session_state[_err_key] = str(e)
            st.session_state[popover_key] = True  # reopen so the error is seen
    with st.popover(trigger_label, key=popover_key, on_change="rerun",
                    help=trigger_help or None,
                    use_container_width=use_container_width,
                    disabled=disabled):
        # v1.6 (#38): anchor marker for the HIG popover caret. The popover
        # body lives in a floating overlay portal, unreachable from the
        # trigger marker, so this marker rides inside the body itself. It is
        # emitted first so the red-button `+` sibling rules (which match on
        # DOM order) never see a button-bearing container after it.
        st.markdown('<div data-marker="lib-danger-pop-body" style="display:none"></div>',
                    unsafe_allow_html=True)
        _failure = st.session_state.pop(_err_key, None)
        if _failure:
            st.error(f"{fail_label} failed: {_failure}")
        st.markdown(f"**{_md_escape(title)}**")
        st.caption(message)
        _bc, _bd = st.columns(2)
        with _bc:
            st.button(
                "Cancel", key=f"{popover_key}-no", use_container_width=True,
                on_click=lambda: st.session_state.update({popover_key: False}),
            )
        with _bd:
            _danger_button(
                destructive_label, key=f"{popover_key}-yes",
                use_container_width=True,
                on_click=lambda: st.session_state.update(
                    {popover_key: False, _go_key: True}),
            )


def _delete_popover(*, trigger_label: str, popover_key: str, title: str,
                    message: str, on_yes: Callable[[], None],
                    trigger_help: str = "",
                    use_container_width: bool = False,
                    destructive_label: str,
                    icon_trigger: bool = False) -> None:
    """Apple-style delete confirmation: neutral trigger, red explicit
    destructive verb + Cancel inside (#58).

    Thin wrapper over :func:`_confirm_popover` with the failure label set
    to "Delete" (kept for the existing delete flows and their tests).
    ``icon_trigger`` (#90) marks the trigger for the toolbar icon font.
    """
    _confirm_popover(
        trigger_label=trigger_label,
        popover_key=popover_key,
        title=title,
        message=message,
        on_yes=on_yes,
        trigger_help=trigger_help,
        use_container_width=use_container_width,
        fail_label="Delete",
        destructive_label=destructive_label,
        icon_trigger=icon_trigger,
    )


def _render_kind_button(*, story_id: str, kind: str, label: str,
                       button_key: str, help_text: str, kick_label: str,
                       busy_kinds, ai_engine) -> None:
    """One toolbar refresh button (#53/#54, #71, #80, #90).

    #71/#80/#90: the button is ICON-ONLY — the label is a single PUA glyph
    from the bundled "LibToolbarIcons" font (see _TB_ICON_*; #90) and the
    tooltip (``help_text``) carries the "Update Hashtags" / "Update Images"
    / "Update News" label for discoverability and accessibility. Tapping
    the icon triggers the refresh.

    The glyph label NEVER changes; while ``kind`` runs the button shows the
    CSS spinner (``lib-spin-<kind>`` marker, painted via ::before in front
    of the glyph) and stays disabled. ``use_container_width`` keeps the
    width stable — the button fills its fixed column slot, so nothing shoves
    its neighbours. Each kind disables only while IT runs: hashtags,
    images and news are independent and stay clickable while the others
    run (#54, #80).

    The ``data-tbicon`` marker rides on the same div as the spin marker
    (when running) so both the spinner ``+`` rule and the icon-font ``+``
    rule keep their required immediate-predecessor DOM order.
    """
    running = kind in busy_kinds
    if running:
        st.markdown(f'<div data-marker="lib-spin-{kind}" data-tbicon style="display:none"></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div data-tbicon style="display:none"></div>',
                    unsafe_allow_html=True)
    if st.button(label, key=button_key, help=help_text,
                 disabled=running, use_container_width=True):
        ok, reason = lib.start_refresh(story_id, kind, ai_engine=ai_engine)
        if ok:
            st.rerun()
        else:
            st.error(f"Could not start the {kick_label} refresh: {reason}" if reason
                     else f"Could not start the {kick_label} refresh.")


def _render_load_more_button(*, story_id: str, kind: str, label: str,
                             button_key: str, help_text: str,
                             busy_kinds) -> None:
    """Section-level "Load more" button (#91).

    #53 HIG progress: the label NEVER changes; while ``kind`` runs the
    button shows the CSS spinner (``lib-spin-<kind>`` marker, painted via
    ::before in front of the label) and stays disabled — no second click.
    The outcome toasts via the existing outcome path. ``kind`` is
    "more_images" or "more_news".

    Disable scope: the button disables while ITS kind runs, and while its
    SIBLING kind runs ("images"↔"more_images", "news"↔"more_news" — the
    sibling writes the same story field, so running together would
    silently clobber the other's appended batch; start_refresh refuses
    the kick too). While the sibling runs the button is merely blocked,
    not working — no spinner then. Other kinds (hashtags, the other
    pair) stay independent.
    """
    running = kind in busy_kinds
    # #91: the sibling kind writes the same story field — blocked (not
    # working) while it runs, so no spinner.
    _sibling = lib._SIBLING_KINDS.get(kind)
    blocked = bool(_sibling and _sibling in busy_kinds)
    # Marker uses hyphens (CSS convention: lib-spin-more-images); the
    # kind name itself keeps underscores for frontmatter/Python.
    _spin_marker = f"lib-spin-{kind.replace('_', '-')}"
    if running:
        st.markdown(f'<div data-marker="{_spin_marker}" style="display:none"></div>',
                    unsafe_allow_html=True)
    if st.button(label, key=button_key, help=help_text,
                 disabled=running or blocked):
        ok, reason = lib.start_refresh(story_id, kind)
        if ok:
            st.rerun()
        else:
            st.error(f"Could not start: {reason}" if reason
                     else "Could not start.")


def _render_reset_popover(story_id: str, busy_kinds, ai_engine) -> None:
    """Toolbar Reset: destructive confirm popover (red "Reset media" /
    standard "Cancel", #58). #90: the trigger is icon-only (refresh glyph
    from the toolbar icon font, tooltip keeps the label).

    #53 HIG progress: the trigger label NEVER changes — while resetting it
    keeps the reset glyph, shows the CSS spinner (``lib-spin-reset`` marker) and
    stays disabled. #54: Reset is destructive and exclusive — the trigger
    also disables while any OTHER kind runs (no spinner then: it is
    blocked, not working). Confirming kicks a "reset" refresh — hashtags,
    fetched images and news links are discarded and re-fetched fresh
    (uploads and the screenplay are never touched).

    The spin marker is emitted INSIDE _confirm_popover immediately before the
    popover trigger (spin_marker param), so the spinner selector is the
    proven marker-then-trigger adjacent-sibling shape (#81).
    """
    resetting = "reset" in busy_kinds
    blocked = bool(set(busy_kinds) - {"reset"})

    def _on_reset_yes() -> None:
        # Raises loudly on failure: the popover shows it and stays open.
        # No st.rerun() here — the destructive click already reruns via the
        # popover's on_change, and the busy state + auto-poll take over.
        ok, reason = lib.start_refresh(story_id, "reset", ai_engine=ai_engine)
        if not ok:
            raise RuntimeError(
                f"Could not start the reset: {reason}" if reason
                else "Could not start the reset.")

    _confirm_popover(
        trigger_label=_TB_ICON_RESET,
        popover_key=f"lib_resetpop_{story_id}",
        title="Reset media rows?",
        message=("Clears all hashtags, fetched images and news links, "
                 "then re-fetches them fresh. Uploads and the screenplay "
                 "are never touched."),
        on_yes=_on_reset_yes,
        trigger_help="Clear and re-fetch hashtags, images and news links",
        fail_label="Reset",
        destructive_label="Reset media",
        use_container_width=True,
        disabled=resetting or blocked,
        spin_marker="lib-spin-reset" if resetting else "",
        icon_trigger=True,
    )


def _refresh_outcome_icon(status: str) -> str:
    """Toast icon for a finished refresh outcome (#53)."""
    return {"succeeded": "✅", "no_change": "ℹ️",
            "failed": "⚠️", "interrupted": "⚠️"}.get(status, "ℹ️")


def _refresh_toast_text(kind: str, status: str, note: str) -> str:
    """One-line toast text for a finished refresh outcome (#53).

    Pure helper (kept pure for unit tests): the kind label, an outcome
    head, and the worker's honest note.
    """
    label = {"hashtags": "Hashtags", "images": "Images", "news": "News",
             "more_images": "More images", "more_news": "More news",
             "reset": "Reset", "enrich": "Enrichment"}.get(kind, kind)
    head = {"succeeded": f"{label} updated",
            "no_change": f"{label}: nothing new",
            "failed": f"{label} failed",
            "interrupted": f"{label} interrupted"}.get(status, label)
    return f"{head} — {note}" if note else head


def _fire_refresh_toasts(story_id: str, meta: dict) -> None:
    """Toast each freshly-finished refresh outcome exactly once (#53).

    Workers append to ``refresh_outcome_pending`` (persisted in the
    story file, one JSON entry per finished kind). The first render that
    sees an entry toasts it and drains it from the file — so the toast
    fires exactly once even across reruns, and entries written while the
    detail page was closed still surface when it opens. Malformed entries
    are reported loudly with st.error and dropped (never toasted).
    """
    pending = meta.get("refresh_outcome_pending") or []
    if not isinstance(pending, list) or not pending:
        return
    for entry in pending:
        outcome = lib.parse_refresh_outcome(entry)
        if outcome is None:
            st.error(f"Could not read a saved refresh outcome "
                     f"({str(entry)[:80]}); dropped.")
            continue
        st.toast(_refresh_toast_text(outcome["kind"], outcome["status"],
                                     outcome["note"]),
                 icon=_refresh_outcome_icon(outcome["status"]))
    lib.update_story_fields(story_id, refresh_outcome_pending=[])
def _overlay_button(marker: str, key: str, label: str, help: str = "") -> bool:
    """Tiny ×/✎ button overlaid at a scroll-card corner (marker-scoped CSS).

    ``marker`` is "lib-x-r" (top-right) or "lib-x-l" (top-left); the marker
    div sits directly before the button so the CSS can pin exactly this
    button's element container absolute over the card (z-index above the
    content). Descendant selectors are used past the column because
    Streamlit nests element containers inside the column's vertical block.
    If the selector ever misses, it degrades to a normal small button —
    never broken.
    """
    st.markdown(f'<div data-marker="{marker}" style="display:none"></div>',
                unsafe_allow_html=True)
    return st.button(label, key=key, help=help)


def _news_chip_label(title: str, source: str) -> str:
    """#26: a news-link chip shows the source website name when known
    (e.g. "The Times of India") instead of the full headline. The
    headline remains available as the link's title tooltip. Empty or
    missing values fall back honestly to "News link", never to an
    empty chip."""
    title = (title or "").strip() or "News link"
    source = (source or "").strip()
    return source if source else title


def _chip_col_weights(labels) -> list:
    """Proportional ``st.columns`` weights for chip rows (#56).

    Chip columns used to be equal-weighted (``st.columns(len(tags))``), so
    every column was as wide as the longest label and short pills floated
    in dead space whenever the CSS shrink-wrap chain missed (the
    ``stLayoutWrapper``-adjacent selectors assume one exact Streamlit DOM,
    and requirements.txt leaves Streamlit unpinned). The CSS shrink-wrap
    (``flex: 0 0 auto`` + ``width: fit-content``) remains the primary
    sizer; these weights are the fallback so a missed selector can only
    ever produce a *proportionally* sized column, never a full-width one.

    Weight tracks the rendered pill width: label length plus ~7 chars for
    the pill's fixed horizontal padding (12px left + 44px × clearance ≈
    56px at ~7.5px/char). The floor keeps degenerate labels tappable.
    Pure (no Streamlit) so it is unit-testable.
    """
    return [max(len(str(_l)), 4) + 7 for _l in labels]


def _fm_warmup_button_props(state: dict) -> tuple:
    """Pure helper: (label, disabled) for the warm-up button given the
    mailbox state. Kept pure so the HIG loading/disabled contract is
    unit-testable without a Streamlit runtime."""
    if (state or {}).get("state") == "warming":
        return "Warming up…", True
    return "Cold start", False


def _render_fm_warmup_button() -> None:
    """Developer warm-up control (issue #37): subtle, compact, sits next to
    the Studio/Library tab bar. Tapping it kicks off the #4 FM probe in a
    daemon thread so the first real generation skips the cold-start delay.

    HIG: the button owns its progress — while warming it paints
    "Warming up…" and stays disabled (no second tap), and the page
    auto-polls until the worker writes its terminal state.
    """
    _state = lib.read_fm_warmup_state()
    _label, _disabled = _fm_warmup_button_props(_state)
    if _disabled:
        st.button(_label, key="fm_warmup_btn", disabled=True,
                  help="Warming up the on-device Apple FM model…",
                  use_container_width=True)
        # Auto-poll while the probe is in flight: the daemon worker cannot
        # trigger st.rerun() itself. Same pattern as the library refresh
        # flow — the loop always terminates because the worker always
        # writes a terminal state and stale states are recovered.
        _time.sleep(1.0)
        st.rerun()
        return
    if st.button(_label, key="fm_warmup_btn", disabled=False,
                 help=("Developer: warm up the on-device Apple FM model now "
                       "so the first generation doesn't pay the cold-start "
                       "delay. Runs the FM availability probe (up to ~2 min "
                       "on first run)."),
                 use_container_width=True):
        _ok, _reason = lib.start_fm_warmup()
        if not _ok:
            st.error(f"Could not start warm-up: {_reason}")
        st.rerun()


def _render_fm_warmup_result() -> None:
    """Honest terminal result under the tab bar: success carries the real
    timing, failure carries the probe's own message verbatim (#4
    messaging) — never a fake 'ready' state."""
    _state = lib.read_fm_warmup_state()
    _stt = (_state or {}).get("state")
    if _stt == "done":
        _secs = _state.get("seconds") or 0.0
        _msg = (_state.get("message") or "").strip()
        st.success(f"Apple FM warmed up in {_secs:.1f}s"
                   + (f" — {_msg}" if _msg else ""))
    elif _stt == "failed":
        _msg = (_state.get("message") or "unknown error").strip()
        st.error(f"Warm-up failed: {_msg}")


def render_tab_bar() -> str:
    """Render the macOS-style tab bar. Returns 'studio' or 'library'."""
    inject_library_css()
    # Developer warm-up (issue #37) rides in a compact trailing column so
    # the normal author flow keeps its centered tab strip untouched.
    _tab_col, _warm_col = st.columns([6.0, 1.0], vertical_alignment="center")
    with _tab_col:
        seg = getattr(st, "segmented_control", None)
        if seg is not None:
            choice = seg(
                "View",
                options=[TAB_STUDIO, TAB_LIBRARY],
                default=TAB_STUDIO,
                key="lib_view",
                label_visibility="collapsed",
            )
        else:  # older Streamlit: horizontal radio dressed as a segmented control
            choice = st.radio(
                "View",
                options=[TAB_STUDIO, TAB_LIBRARY],
                index=0 if st.session_state.get("lib_view", TAB_STUDIO) == TAB_STUDIO else 1,
                key="lib_view",
                label_visibility="collapsed",
                horizontal=True,
            )
    with _warm_col:
        _render_fm_warmup_button()
    _render_fm_warmup_result()
    return "library" if choice == TAB_LIBRARY else "studio"


# ---------------------------------------------------------------------------
# Auto-save hook (called from the Studio final-output view)
# ---------------------------------------------------------------------------

def _script_markdown(script) -> str:
    """Full script as Markdown: hook, narration, per-scene blocks, CTA.

    Dialogue lines are blockquotes (``> **Speaker:** line``) so the detail
    view can highlight them in a distinct color inside the whole script.
    """
    lines: list[str] = []
    hook = (getattr(script, "hook_hindi", "") or "").strip()
    if hook:
        lines.append(f"**Hook:** {hook}\n")
    narration = (getattr(script, "narration_hindi", "") or "").strip()
    if narration:
        lines.append(f"**Narration:** {narration}\n")
    for sc in getattr(script, "scenes", None) or []:
        n = getattr(sc, "scene_number", "?")
        parts: list[str] = [f"**Scene {n}**"]
        for label, attr in (
            ("Visual", "visual_b_roll"),
            ("Location", "scene_location"),
            ("Atmosphere", "scene_atmosphere"),
            ("Lighting", "scene_lighting"),
            ("On-screen text", "on_screen_text"),
            ("SFX", "audio_sfx"),
        ):
            val = (getattr(sc, attr, "") or "").strip()
            if val:
                parts.append(f"{label}: {val}")
        props = getattr(sc, "scene_props", "") or []
        if props:
            parts.append("Props: " + ", ".join(props))
        lines.append(" — ".join(parts))
        dialogue = (getattr(sc, "dialogue", "") or "").strip()
        if dialogue:
            speaker = (getattr(sc, "character", "") or "").strip() or f"Scene {n}"
            lines.append(f"> **{speaker}:** {dialogue}")
        lines.append("")
    cta = (getattr(script, "call_to_action", "") or "").strip()
    if cta:
        lines.append(f"**CTA:** {cta}")
    return "\n".join(lines).strip()


def maybe_autosave_story(batch_result, script, pro_screenplay: str = "") -> None:
    """Auto-save the finished story once (guarded against Streamlit reruns).

    ``pro_screenplay`` is the exact final-stage screenplay text already shown
    in the Studio (overlay/SFX toggles applied). It is stored verbatim —
    never regenerated, never a CTA added. On failure: surfaces the error
    with a manual "Save to library" fallback.
    """
    res_id = id(batch_result)
    script_id = getattr(script, "id", "?")
    sel_idx = st.session_state.get("selected_script_idx", 0)
    guard = f"{res_id}:{script_id}:{sel_idx}"
    if st.session_state.get("lib_autosaved_for") == guard:
        return
    if st.session_state.get("lib_save_failed_for") == guard:
        _render_manual_save_fallback(batch_result, script, guard, pro_screenplay)
        return
    if not (pro_screenplay or "").strip():
        # Fail loudly: saving anything but the exact final-stage text would
        # silently misrepresent the story.
        st.session_state["lib_save_failed_for"] = guard
        st.error("Auto-save to library failed: the final-stage screenplay text was not provided.")
        _render_manual_save_fallback(batch_result, script, guard, pro_screenplay)
        return
    try:
        story_id = _save_current_story(batch_result, script, pro_screenplay)
    except Exception as e:  # fail loudly, offer manual fallback
        st.session_state["lib_save_failed_for"] = guard
        st.error(f"Auto-save to library failed: {e}")
        _render_manual_save_fallback(batch_result, script, guard, pro_screenplay)
        return
    st.session_state["lib_autosaved_for"] = guard
    st.session_state.pop("lib_save_failed_for", None)
    topic = st.session_state.get("run_topic", "") or ""
    _ok, _why = lib.start_enrichment(story_id, topic)


def _verified_news_links(batch_result) -> list:
    """Stage-1 verified sources — the exact articles the story was built from.

    If the user verified one specific story link in Stage 1.4, it goes
    first. Saved as the story's news links so they always point at the same
    story; the background enrichment keeps them and never overwrites them.
    """
    links: list = []
    chosen = st.session_state.get("s1_verified_story_link") or {}
    if chosen.get("url"):
        links.append({"title": chosen.get("title", "") or "",
                      "url": chosen["url"],
                      "source": chosen.get("source", "") or ""})
    verif = getattr(batch_result, "verification", None)
    for s in (getattr(verif, "sources", None) or []):
        if isinstance(s, dict):
            title = s.get("title", "") or ""
            url = s.get("link", "") or s.get("url", "") or ""
            source = s.get("source", "") or ""
        else:
            title = getattr(s, "title", "") or ""
            url = getattr(s, "link", "") or getattr(s, "url", "") or ""
            source = getattr(s, "source", "") or ""
        if url and all(l["url"] != url for l in links):
            links.append({"title": title, "url": url, "source": source})
    return links


def _derive_local_hashtags(title: str, topic: str, headline: str) -> list:
    """Instant, network-free hashtag candidates from the story's own words.

    Guarantees at least one story-specific tag so a story is never saved
    hashtag-less — even trending-news stories get possible hashtags.
    """
    tags: list = []
    for text in (headline, title, topic):
        t = lib._camel_tag(lib._keyword_list(text or ""))
        if t and t not in tags:
            tags.append(t)
        if len(tags) >= 3:
            break
    if not tags:
        words = _re.findall(r"[A-Za-z]{3,}", f"{title} {topic}")
        if words:
            tags.append("#" + "".join(w.capitalize() for w in words[:3]))
        else:
            tags.append("#HindiReelStudio")
    return tags


def _save_current_story(batch_result, script, pro_screenplay: str) -> str:
    """Persist the story. ``pro_screenplay`` is stored verbatim — it is the
    exact final-stage text the Studio displayed (toggles already applied)."""
    if not (pro_screenplay or "").strip():
        raise ValueError("Cannot save: the final-stage screenplay text is empty.")
    hashtag = st.session_state.get("active_hashtag", "") or ""
    hashtags = [hashtag] if hashtag else []
    tone = st.session_state.get("chosen_tone", "") or ""
    topic = st.session_state.get("run_topic", "") or ""
    headline = st.session_state.get("selected_headline_title", "") or ""
    # The story title is the news headline it was built from.
    title = headline or topic or getattr(script, "title", "") or "Untitled Story"
    if not hashtags:
        # Never save hashtag-less: derive story-specific tags locally
        # (instant, no network) — the background enrichment adds trending
        # ones on top. Trending-news stories always get possible hashtags.
        hashtags = _derive_local_hashtags(title, topic, headline)
    return lib.save_story(
        title=title,
        tone=tone,
        hashtags=hashtags,
        dialogue_md="",
        script_md=pro_screenplay.strip(),
        source_topic=topic,
        source_headline=headline,
        news_links=_verified_news_links(batch_result),
        image_urls=st.session_state.get("s1_kept_images") or [],
    )


def _render_manual_save_fallback(batch_result, script, guard: str, pro_screenplay: str = "") -> None:
    if st.button("Save to Library", key="lib_manual_save_btn", type="primary"):
        try:
            story_id = _save_current_story(batch_result, script, pro_screenplay)
        except Exception as e:
            st.error(f"Save to library failed: {e}")
            return
        st.session_state["lib_autosaved_for"] = guard
        st.session_state.pop("lib_save_failed_for", None)
        topic = st.session_state.get("run_topic", "") or ""
        _ok, _why = lib.start_enrichment(story_id, topic)
        st.success("Saved to Library.")
        st.rerun()


# ---------------------------------------------------------------------------
# Library page: master-detail
# ---------------------------------------------------------------------------

def render_library_page() -> None:
    # macOS HIG: the tab bar already identifies this view — no redundant
    # large title repeating "Library". Deference: content first.
    _inject_story_list_css()
    # Once per process: clear refresh states orphaned by a dead worker so
    # buttons can never stay stuck on a previous run's "Updating…".
    lib.recover_orphaned_refreshes()
    stories = lib.list_stories()

    if not stories:
        st.markdown('<div class="lib-empty">No saved stories yet.<br>'
                    'Generate a reel in the Studio tab — '
                    'it auto-saves here on completion.</div>',
                    unsafe_allow_html=True)
        return

    # Header row: story count leading; AI processing controls trailing
    # (macOS HIG: view controls live in the header, trailing side).
    _prefs = lib.load_prefs()
    _ai_on = bool(_prefs.get("library_ai_enabled", False))
    _engine_labels = list(lib.LIBRARY_ENGINE_OPTIONS.keys())
    _engine_label = _prefs.get("library_ai_engine", lib.DEFAULT_LIBRARY_AI_ENGINE)
    if _engine_label not in _engine_labels:
        _engine_label = lib.DEFAULT_LIBRARY_AI_ENGINE
    hh1, hh2, hh3 = st.columns([4.4, 2.6, 3.0], vertical_alignment="center")
    with hh1:
        st.markdown(f'<div class="lib-sidebar-label">Stories · {len(stories)}</div>',
                    unsafe_allow_html=True)
    with hh2:
        _new_ai = st.toggle(
            "Enable AI processing", value=_ai_on, key="lib_ai_toggle",
            help="When on, hashtag refreshes use the selected AI engine for "
                 "content-aware suggestions. AI never changes your script, "
                 "verified links, or images.")
        if _new_ai != _ai_on:
            lib.save_prefs({"library_ai_enabled": _new_ai})
            _ai_on = _new_ai  # use the fresh value for the rest of this run
    with hh3:
        _new_engine = st.selectbox(
            "AI engine", options=_engine_labels,
            index=_engine_labels.index(_engine_label),
            disabled=not _ai_on, key="lib_ai_engine",
            label_visibility="collapsed",
            help="Engine used for AI hashtag suggestions. Disabled while "
                 "AI processing is off.")
        if _new_engine != _engine_label:
            lib.save_prefs({"library_ai_engine": _new_engine})
    st.markdown('<div class="lib-hairline"></div>', unsafe_allow_html=True)

    master, detail = st.columns([1, 3])
    with master:
        # macOS sidebar: the story list is a single-select list with an
        # accent-tinted selected row (like Mail/Finder). Newest first, so
        # the latest story is selected on entry.
        ids = [s.get("id", "") for s in stories]
        titles = {s.get("id", ""): (s.get("title", "Untitled") or "Untitled")[:38]
                  for s in stories}
        if st.session_state.get("lib_story_radio") not in ids:
            # Reset a stale selection (e.g. after a delete) before the
            # widget is created so it falls back to the first row.
            st.session_state.pop("lib_story_radio", None)
        st.markdown('<div data-marker="lib-story-list" style="display:none"></div>',
                    unsafe_allow_html=True)
        sel = st.radio(
            "Stories",
            options=ids,
            format_func=lambda sid: titles.get(sid, "?"),
            index=0,
            key="lib_story_radio",
            label_visibility="collapsed",
        )
        st.session_state["lib_selected_story"] = sel
        # Delete-all lives in the master section (popover confirm).
        st.markdown("")
        _delete_popover(
            trigger_label="Delete All",
            popover_key="lib_delpop_all",
            title="Delete all stories?",
            message="Every saved story will be permanently deleted. This can't be undone.",
            on_yes=_confirm_delete_all,
            trigger_help="Delete every saved story",
            use_container_width=True,
            destructive_label="Delete all stories",
        )
    with detail:
        _render_story_detail(sel)


def _render_full_script(script_md: str) -> None:
    """Render the saved full script as styled HTML.

    Handles the final-stage industry screenplay (plain text: [Format
    Requirement] header, SCENE DETAIL / CHARACTERS & CLOTHING sections,
    ``SPEAKER: "dialogue"`` lines) and the older Markdown reconstruction
    (``> **Speaker:** line`` blockquotes). Spoken dialogue gets the amber
    highlight with IDE-style syntax colors — speaker like a keyword,
    spoken words like a string.
    """
    import html as _html
    import re as _re

    _SPEAKER_RE = _re.compile(r'^([A-Z][A-Z0-9 .\'-]{1,40}):\s*"(.*)"\s*$')
    _SECTION_RE = _re.compile(r"^([A-Z][A-Z &/()\-]{2,}):$")
    _LABEL_RE = _re.compile(r"^([A-Za-z][A-Za-z &/()\-]{1,40}):")

    def _inline(text: str) -> str:
        s = _html.escape(text.strip())
        s = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = _re.sub(r"\*([^*]+?):\*", r'<span class="lib-key">\1:</span>', s)
        return s

    def _dialogue_div(speaker: str, said: str) -> str:
        said_html = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _html.escape(said.strip()))
        return (f'<div class="lib-dialogue-line"><span class="lib-spk">{_html.escape(speaker.strip())}:</span> '
                f'<span class="lib-said">{said_html}</span></div>')

    chunks: list[str] = []
    pending: list[str] = []

    def _flush_pending() -> None:
        if pending:
            chunks.append('<div class="lib-script-line">' + "<br>".join(pending) + "</div>")
            pending.clear()

    for para in script_md.split("\n\n"):
        for raw in para.split("\n"):
            line = raw.strip()
            if not line:
                continue
            if line.startswith("[Format Requirement:"):
                _flush_pending()
                chunks.append(
                    f'<div class="lib-script-line" style="opacity:0.75;font-style:italic;">'
                    f'{_html.escape(line)}</div>')
                continue
            if line.startswith(">"):
                _flush_pending()
                # Older reconstruction format: "> **Speaker:** line"
                m = _re.match(r"\*\*(.+?):\*\*\s*(.*)", line.lstrip(">").strip(), _re.DOTALL)
                if m:
                    chunks.append(_dialogue_div(m.group(1), m.group(2)))
                else:
                    chunks.append(f'<div class="lib-dialogue-line"><span class="lib-said">'
                                  f'{_inline(line.lstrip(">").strip())}</span></div>')
                continue
            m = _SPEAKER_RE.match(line)
            if m:
                _flush_pending()
                chunks.append(_dialogue_div(m.group(1), m.group(2)))
                continue
            m = _SECTION_RE.match(line)
            if m:
                _flush_pending()
                chunks.append(f'<div class="lib-script-line"><span class="lib-key"><b>'
                              f'{_html.escape(line)}</b></span></div>')
                continue
            m = _LABEL_RE.match(line)
            if m:
                pending.append(f'<span class="lib-key">{_html.escape(m.group(1))}:</span> '
                               + _inline(line[m.end():].strip()))
            else:
                pending.append(_inline(line))
        _flush_pending()
    st.markdown("".join(chunks) or "<p>—</p>", unsafe_allow_html=True)


def _script_plain_text(md: str) -> str:
    """Full-script Markdown → clean plain text for copying."""
    import re as _re
    s = _re.sub(r"\*\*(.+?)\*\*", r"\1", md)
    s = _re.sub(r"\*([^*]+?):\*", r"\1:", s)
    s = _re.sub(r"^>\s?", "", s, flags=_re.M)
    return s.strip()


def _compose_share_text(meta: dict, script_md: str, with_media: bool, with_tags: bool) -> str:
    """Compose the copy text: the full final-stage script plus optional
    media links and hashtags. News article links are never added."""
    parts = [_script_plain_text(script_md)]
    if with_media:
        media = list(meta.get("image_urls") or []) + list(meta.get("uploaded_images") or [])
        media = [u for u in dict.fromkeys(media) if u]
        if media:
            parts.append("Media:\n" + "\n".join(f"- {u}" for u in media))
    if with_tags:
        tags = meta.get("hashtags") or []
        if tags:
            parts.append(" ".join(tags))
    return "\n\n".join(p for p in parts if p).strip()


def _compose_news_tags_text(meta: dict, title: str = "") -> str:
    """Share text: title, then hashtags, then verified news link(s).

    Formatted for pasting straight into a social-media post — title first,
    hashtags space-separated on the next line, then one link per line.
    Returns "" when the story has neither title, news links nor hashtags,
    so the caller can say so plainly instead of copying nothing.
    """
    links = [
        (lk.get("url") or "").strip()
        for lk in (meta.get("news_links") or [])
        if isinstance(lk, dict)
    ]
    links = [u for u in dict.fromkeys(links) if u]
    tags = [t for t in (meta.get("hashtags") or []) if t]
    parts = []
    title = (title or "").strip()
    if title:
        parts.append(title)
    if tags:
        parts.append(" ".join(tags))
    if links:
        parts.append("\n".join(links))
    return "\n\n".join(parts)


def _whatsapp_share_url(text: str) -> str:
    """whatsapp:// deep link carrying the EXACT share text (URL-encoded for
    transport only — the text itself is never reformatted). macOS routes the
    whatsapp:// scheme to the installed WhatsApp Mac app, opening it directly
    with the text prefilled — unlike wa.me links, which always resolve in the
    browser (WhatsApp Web flow) even when the app is installed. No connection
    or connector needed.

    Note (#95): this URL must be rendered as a plain anchor WITHOUT
    target="_blank". st.link_button forces a new browser tab, which defeats
    the deep link — the browser opens a blank tab before macOS can route the
    scheme to the app.
    """
    import urllib.parse as _up
    return "whatsapp://send?text=" + _up.quote(text, safe="")


@_lru_cache(maxsize=1)
def _whatsapp_app_installed() -> bool:
    """Detect the WhatsApp Mac app. The Streamlit server runs locally on the
    user's Mac, so the filesystem is the source of truth. Cached for the
    session — app installs don't change between renders, so this never runs
    per-render. Tests clear the cache via ``cache_clear()``.
    """
    import os as _os
    candidates = (
        "/Applications/WhatsApp.app",
        _os.path.expanduser("~/Applications/WhatsApp.app"),
    )
    return any(_os.path.isdir(p) for p in candidates)


def _render_share_popover(story_id: str, share_text: str) -> None:
    """Share dropdown (native popover, macOS HIG): sub-actions for the
    story's news-links + hashtags share text.

    #90: the trigger is icon-only (share glyph from the toolbar icon
    font); the tooltip keeps the "Share" label. Streamlit's popover
    natively renders its own chevron, so nothing is baked into the label
    (#46).

    The redundant st.code(share_text) preview is gone (#27) — the dedicated
    Hashtags / News Links sections already show that content, and the text
    stays one click away via "Copy News Link + Hashtags". "Send via WhatsApp"
    deep-links straight into the installed WhatsApp Mac app (#28), with no
    browser tab involved (#95).
    """
    # data-tbicon marker: must sit directly before the popover's element
    # container for the icon-font `+` rule (same pattern as #24).
    st.markdown('<div data-tbicon style="display:none"></div>',
                unsafe_allow_html=True)
    with st.popover(_TB_ICON_SHARE, key=f"lib_sharepop_{story_id}",
                     help="Share this story's news links and hashtags",
                     use_container_width=True):
        if share_text:
            _copy_button("Copy News Link + Hashtags", share_text,
                         f"n-{story_id}")
            if _whatsapp_app_installed():
                # #95: plain anchor, NO target="_blank". st.link_button forces
                # a new browser tab, which defeats the whatsapp:// deep link —
                # macOS must receive the scheme directly to open the app.
                url = _whatsapp_share_url(share_text)
                st.markdown(
                    f'<a class="lib-wa-direct"'
                    f' href="{_html.escape(url, quote=True)}"'
                    f' title="Open the installed WhatsApp Mac app with this'
                    f' text prefilled">Send via WhatsApp</a>',
                    unsafe_allow_html=True,
                )
            else:
                # Fail loudly: never a dead link, never a silent browser
                # fallback (wa.me) — the user asked for direct app handoff.
                st.caption("WhatsApp Mac app not installed — "
                           "install it to send via WhatsApp.")
        else:
            st.caption("No news links or hashtags to share yet.")


def _render_copy_popover(story_id: str, meta: dict, script_md: str) -> None:
    """Copy dropdown (native popover, macOS HIG): Script / Script + Tags /
    Script + Media / All — the same one-click copy texts as before, now
    revealed as sub-actions.

    #90: the trigger is icon-only (copy glyph from the toolbar icon font);
    the tooltip keeps the "Copy" label. Streamlit's native chevron is the
    only indicator (#46). Each copy button owns its loading state
    ("Copied ✓") via _copy_button — no second click.
    """
    # data-tbicon marker: must sit directly before the popover's element
    # container for the icon-font `+` rule (same pattern as #24).
    st.markdown('<div data-tbicon style="display:none"></div>',
                unsafe_allow_html=True)
    with st.popover(_TB_ICON_COPY, key=f"lib_copypop_{story_id}",
                     help="Copy the screenplay in different formats",
                     use_container_width=True):
        if script_md:
            _copy_button("Script", _script_plain_text(script_md),
                         f"s-{story_id}")
            _copy_button("Script + Tags",
                         _compose_share_text(meta, script_md, False, True),
                         f"h-{story_id}")
            _copy_button("Script + Media",
                         _compose_share_text(meta, script_md, True, False),
                         f"m-{story_id}")
            _copy_button("All",
                         _compose_share_text(meta, script_md, True, True),
                         f"a-{story_id}")
        else:
            st.caption("No script to copy yet.")




# Shared with --lib-act-h in inject_library_css: the copy button renders
# inside an isolated iframe (components.html) so page CSS cannot reach it —
# the value is mirrored here to keep ONE alignment system.
_LIB_ACTION_BTN_H_PX = 38


def _copy_button(label: str, text: str, key: str) -> None:
    """One-click copy-to-clipboard button (clipboard API with execCommand fallback)."""
    import html as _html
    import json as _json
    import streamlit.components.v1 as components
    payload = _json.dumps(text)
    btn_id = f"libcp-{key}"
    components.html(
        f"""<button id="{btn_id}" style="width:100%;min-height:{_LIB_ACTION_BTN_H_PX}px;box-sizing:border-box;padding:7px 4px;border:1px solid rgba(0,0,0,0.12);
        border-radius:8px;background:rgba(255,255,255,0.72);color:#1d1d1f;cursor:pointer;font-size:13px;
        font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',sans-serif;">{_html.escape(label)}</button>
        <script>
        document.getElementById("{btn_id}").addEventListener("click", async () => {{
            const t = {payload};
            try {{ await navigator.clipboard.writeText(t); }}
            catch (e) {{
                const ta = document.createElement("textarea");
                ta.value = t; document.body.appendChild(ta); ta.select();
                try {{ document.execCommand("copy"); }} catch (_e) {{}}
                ta.remove();
            }}
            const b = document.getElementById("{btn_id}");
            const old = b.textContent; b.textContent = "Copied \\u2713";
            setTimeout(() => {{ b.textContent = old; }}, 1500);
        }});
        </script>""",
        height=_LIB_ACTION_BTN_H_PX,
    )


# v1.6 (#38, #46, #53, #80) / v1.6.2 (#90): story-detail toolbar column
# weights. Streamlit ellipsizes ("…") any button/popover label wider than
# its column, so every action column is weighted to fit its label — #53:
# labels never change mid-work. #90: ALL seven controls are icon-only
# (icon-font glyphs for hashtags/images/news, Reset, Share, Copy, Delete),
# so the static labels are the longest state. Share / Copy are short native-
# popover labels. #71: hashtags/images became icon-only buttons, so their
# columns shrank to icon width and the freed weight moved to the spacer —
# the row stays full-width with no dead space in the action area and Delete
# stays visually trailing. #80: the news button is icon-only too (same 0.9
# slot); the spacer gives up 0.9 to keep the total unchanged (10.0) so the
# overall layout is preserved and the #24 baseline alignment is untouched.
_DETAIL_TOOLBAR_WEIGHTS = [0.9, 0.9, 0.9, 1.4, 1.1, 1.1, 2.0, 1.7]
_TITLE_EDIT_TOOLBAR_WEIGHTS = [1.0, 1.1, 1.1, 1.1, 4.2, 1.5]

def _render_story_detail(story_id: str) -> None:
    story = lib.load_story(story_id)
    if not story:
        st.error("Story not found — it may have been deleted.")
        st.session_state.pop("lib_selected_story", None)
        return
    meta = story["meta"]
    script_md = story["script"].strip()
    _share_text = _compose_news_tags_text(
        meta, meta.get("title", "Untitled Story") or "Untitled Story")

    # Detail toolbar (macOS HIG): every primary action lives in ONE top
    # toolbar — hashtag/image/news refresh icons (#71, #80, #90), Reset,
    # Share, Copy — with Delete trailing (#46). #90: all seven are
    # icon-only, drawn from the single "LibToolbarIcons" icon font; the
    # title carries its own inline ✏️ edit icon next to the centered
    # title text.
    #
    # #53 HIG progress: a refresh button NEVER changes its label. While
    # its kind runs the button keeps its glyph label, shows a CSS spinner
    # (the lib-spin-<kind> marker, painted via ::before in front of the
    # glyph) and stays disabled. Tooltips keep the "Update Hashtags" /
    # "Update Images" / "Update News" labels (#71, #80). Stable width comes
    # from use_container_width — each button fills its fixed column slot,
    # so nothing shoves its neighbours. Refreshes run in daemon threads,
    # so tab switches never interrupt them.
    #
    # #54/#80 concurrency: "hashtags", "images" and "news" are independent
    # — each button disables only while ITS kind runs. Reset is
    # destructive and exclusive: its trigger disables while ANY kind runs.
    _busy_kinds = lib.refresh_busy_kinds(meta)
    _busy = bool(_busy_kinds)
    _editing = bool(st.session_state.get(f"lib_edit_title_{story_id}"))
    _ai_engine = _library_ai_engine()

    def _story_delete_popover() -> None:
        # #58: the confirmation names the story, quoted — the title is
        # user-editable, so _confirm_popover escapes Markdown specials.
        _story_title = meta.get("title", "Untitled Story") or "Untitled Story"
        _delete_popover(
            trigger_label=_TB_ICON_DELETE,
            popover_key=f"lib_delpop_{story_id}",
            title=f'Delete "{_story_title}"?',
            message="This can't be undone.",
            on_yes=lambda: _confirm_delete_story(story_id),
            trigger_help="Delete this story",
            destructive_label="Delete story",
            use_container_width=True,
            icon_trigger=True,
        )

    if _editing:
        # Title edit mode: Save/Cancel lead, Share/Copy stay available,
        # Delete stays trailing.
        ec1, ec2, ec3, ec4, _esp, ec5 = st.columns(_TITLE_EDIT_TOOLBAR_WEIGHTS)
        with ec1:
            if st.button("Save", key=f"lib_title_save_{story_id}", type="primary"):
                _new = (st.session_state.get(f"lib_title_{story_id}") or "").strip()
                if _new:
                    lib.update_story_fields(story_id, title=_new)
                st.session_state.pop(f"lib_edit_title_{story_id}", None)
                st.rerun()
        with ec2:
            if st.button("Cancel", key=f"lib_title_cancel_{story_id}"):
                st.session_state.pop(f"lib_edit_title_{story_id}", None)
                st.rerun()
        with ec3:
            _render_share_popover(story_id, _share_text)
        with ec4:
            _render_copy_popover(story_id, meta, script_md)
        with ec5:
            _story_delete_popover()
    else:
        tc1, tc2, tc3, tc4, tc5, tc6, _tsp, tc7 = st.columns(_DETAIL_TOOLBAR_WEIGHTS)
        with tc1:
            _render_kind_button(
                story_id=story_id, kind="hashtags", label=_TB_ICON_TAG,
                button_key=f"lib_tags_{story_id}", kick_label="hashtag",
                help_text="Update Hashtags",
                busy_kinds=_busy_kinds, ai_engine=_ai_engine)
        with tc2:
            _render_kind_button(
                story_id=story_id, kind="images", label=_TB_ICON_IMAGE,
                button_key=f"lib_imgs_{story_id}", kick_label="image",
                help_text="Update Images",
                busy_kinds=_busy_kinds, ai_engine=_ai_engine)
        with tc3:
            # #80: re-fetch news links (sources) for the story's topic.
            # Icon-only like #71 (glyph + tooltip); the #53/#54 contract
            # is identical to the hashtag/image buttons — stable glyph
            # label, lib-spin-news spinner while running, disables only
            # while its own kind runs, concurrent with hashtags/images.
            _render_kind_button(
                story_id=story_id, kind="news", label=_TB_ICON_NEWS,
                button_key=f"lib_news_{story_id}", kick_label="news",
                help_text="Update News",
                busy_kinds=_busy_kinds, ai_engine=_ai_engine)
        with tc4:
            # Reset is destructive: it confirms via the same native popover
            # pattern as Delete (red explicit verb / standard Cancel, #58).
            # #53: the trigger label never changes; #54: it stays disabled
            # while any kind runs (exclusive).
            _render_reset_popover(story_id, _busy_kinds, _ai_engine)
        with tc5:
            _render_share_popover(story_id, _share_text)
        with tc6:
            _render_copy_popover(story_id, meta, script_md)
        with tc7:
            _story_delete_popover()
    # #53: toast each freshly-finished refresh outcome exactly once, then
    # drain it. The file (not session state) is the drain record, so a
    # toast never fires twice and outcomes that finished while this page
    # was closed still surface when it opens.
    _fire_refresh_toasts(story_id, meta)
    st.markdown('<div class="lib-hairline"></div>', unsafe_allow_html=True)

    # Title at top: big, multiline, centered, with a small inline edit icon.
    # While editing, a borderless editor takes its place (Save/Cancel live
    # in the toolbar above). #84 reverts #60: the full title text is back
    # as an h2 — the #79 `.lib-doc-title a { display:none }` guard keeps
    # Streamlit's heading-anchor 🔗 icon off it. The ✏️ edit flow and the
    # delete popover's meta.get("title") naming (#58) are untouched; no
    # recency caption is emitted ("Edited … ago" stays removed).
    title = meta.get("title", "Untitled Story") or "Untitled Story"
    if _editing:
        st.text_area("", value=title, key=f"lib_title_{story_id}",
                     height=80, label_visibility="collapsed")
    else:
        _tt1, _tt2, _tt3 = st.columns([1, 8, 1], vertical_alignment="center")
        with _tt2:
            st.markdown(f"<h2 class='lib-doc-title'>{_html.escape(title)}</h2>",
                        unsafe_allow_html=True)
        with _tt3:
            if st.button("✏️", key=f"lib_title_edit_{story_id}",
                         help="Edit title", disabled=_busy):
                st.session_state[f"lib_edit_title_{story_id}"] = True
                st.rerun()
    # Hashtags: ONE horizontal scroll row. Every tag is a chip with a ×
    # that removes exactly that tag (fail loudly, rerun after).
    tags = [t for t in (meta.get("hashtags") or []) if t]
    if tags:
        st.markdown('<div class="lib-section">Hashtags</div>', unsafe_allow_html=True)
        st.markdown('<div data-marker="lib-hscroll" style="display:none"></div>',
                    unsafe_allow_html=True)
        _tcols = st.columns(_chip_col_weights(tags))
        for _i, (_tc, _tag) in enumerate(zip(_tcols, tags)):
            with _tc:
                st.markdown(f'<span class="lib-chip">{_html.escape(_tag)}</span>',
                            unsafe_allow_html=True)
                if _overlay_button("lib-x-r", f"lib_xtag_{story_id}_{_i}", "×",
                                   help=f"Remove {_tag}"):
                    try:
                        lib.remove_hashtag(story_id, _tag)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.rerun()

    # Images: ONE horizontal scroll row of cards (fetched + uploaded). Each
    # card shows the image with a × at its top; fetched cards keep a discreet
    # ✎ at the top-left for the address editor.
    img_urls = [u for u in (meta.get("image_urls") or []) if u]
    uploaded = [f for f in (meta.get("uploaded_images") or [])
                if lib.media_path(story_id, f)]
    _edit_idx = next(
        (i for i in range(len(img_urls))
         if st.session_state.get(f"lib_editimg_{story_id}_{i}")), None)
    if _edit_idx is not None:
        st.markdown('<div class="lib-section">Edit image address</div>',
                    unsafe_allow_html=True)
        st.text_input("Image address", value=img_urls[_edit_idx],
                      key=f"lib_edimg_url_{story_id}_{_edit_idx}")
        _eb1, _eb2, _ebs = st.columns([1, 1, 6])
        with _eb1:
            if st.button("Save", key=f"lib_edimg_save_{story_id}_{_edit_idx}"):
                try:
                    lib.update_fetched_image_url(
                        story_id, _edit_idx,
                        st.session_state.get(f"lib_edimg_url_{story_id}_{_edit_idx}", ""))
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.session_state.pop(f"lib_editimg_{story_id}_{_edit_idx}", None)
                    st.rerun()
        with _eb2:
            if st.button("Cancel", key=f"lib_edimg_cancel_{story_id}_{_edit_idx}"):
                st.session_state.pop(f"lib_editimg_{story_id}_{_edit_idx}", None)
                st.rerun()
    if img_urls or uploaded:
        st.markdown('<div class="lib-section">Images</div>', unsafe_allow_html=True)
        st.markdown('<div data-marker="lib-hscroll" style="display:none"></div>',
                    unsafe_allow_html=True)
        _cards = [("fetched", i, u) for i, u in enumerate(img_urls)]
        _cards += [("uploaded", i, f) for i, f in enumerate(uploaded)]
        _icols = st.columns(len(_cards))
        for _ci, (_icol, (_kind, _ki, _ref)) in enumerate(zip(_icols, _cards)):
            with _icol:
                if _kind == "fetched":
                    st.image(_ref, width=200)
                    if _overlay_button("lib-x-l", f"lib_xedit_{story_id}_{_ci}", "✎",
                                       help="Edit this image's address"):
                        st.session_state[f"lib_editimg_{story_id}_{_ki}"] = True
                        st.rerun()
                    if _overlay_button("lib-x-r", f"lib_ximg_{story_id}_{_ci}", "×",
                                       help="Remove this fetched image"):
                        if lib.remove_fetched_image(story_id, _ref):
                            st.rerun()
                        else:
                            st.error("Could not remove the image — "
                                     "the story may have been deleted.")
                else:
                    st.image(str(lib.media_path(story_id, _ref)), width=200)
                    if _overlay_button("lib-x-r", f"lib_xup_{story_id}_{_ci}", "×",
                                       help="Remove this uploaded image"):
                        if lib.remove_uploaded_image(story_id, _ref):
                            st.rerun()
                        else:
                            st.error("Could not remove the image — "
                                     "the story may have been deleted.")
        # #91: explicit "load more" — one more batch (up to 5) of genuinely
        # new images past the #83 cap. The button owns its loading state
        # (spinner + disabled while more_images runs).
        _render_load_more_button(
            story_id=story_id, kind="more_images",
            label="Load more images",
            button_key=f"lib_moreimg_{story_id}",
            help_text="Fetch up to 5 more images",
            busy_kinds=_busy_kinds)
    elif not (_busy_kinds & {"images", "more_images", "reset", "enrich"}):
        # #54: only kinds that (re-)fetch images suppress the hint — a
        # concurrent hashtag run leaves it visible.
        st.caption("No images yet — try Reset or upload manually below.")

    # News links: ONE horizontal scroll row. Each verified link is a chip
    # (title + source, opens the article) with a × that removes it.
    # Update Hashtags/Images never touch these — individual removal is
    # manual only (×). Reset re-runs the link verifier fresh for the topic.
    links = [lk for lk in (meta.get("news_links") or []) if isinstance(lk, dict)]
    if links:
        st.markdown('<div class="lib-section">News Links</div>', unsafe_allow_html=True)
        st.markdown('<div data-marker="lib-hscroll" style="display:none"></div>',
                    unsafe_allow_html=True)
        _labels = [_news_chip_label((_lk.get("title") or "News link"),
                                       (_lk.get("source") or ""))
                   for _lk in links]
        _lcols = st.columns(_chip_col_weights(_labels))
        for _i, (_lc, _lk, _label) in enumerate(zip(_lcols, links, _labels)):
            _ltitle = _lk.get("title", "News link") or "News link"
            _lurl = (_lk.get("url") or "").strip()
            with _lc:
                st.markdown(
                    f'<span class="lib-chip"><a href="{_html.escape(_lurl, quote=True)}" '
                    f'target="_blank" rel="noopener" '
                    f'title="{_html.escape(_ltitle, quote=True)}">{_html.escape(_label)}</a></span>',
                    unsafe_allow_html=True)
                if _overlay_button("lib-x-r", f"lib_xlink_{story_id}_{_i}", "×",
                                   help="Remove this news link"):
                    try:
                        lib.remove_news_link(story_id, _lurl)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.rerun()
        # #91: explicit "load more" — one more batch (up to 5) of genuinely
        # new news links past the #82 cap. The button owns its loading
        # state (spinner + disabled while more_news runs).
        _render_load_more_button(
            story_id=story_id, kind="more_news",
            label="Load more news",
            button_key=f"lib_morenews_{story_id}",
            help_text="Fetch up to 5 more news links",
            busy_kinds=_busy_kinds)
    elif not (_busy_kinds & {"news", "more_news", "reset", "enrich"}):
        # #54/#80: only kinds that re-fetch links suppress the hint.
        st.caption("No news links yet.")

    # Whole script — always through the color-coded renderer so dialogue
    # never falls back to plain markdown. The ✏️ edit control mirrors the
    # title's inline edit: it swaps the renderer for a text area and
    # persists through lib.update_story_script, which fails loudly.
    _script_editing = bool(st.session_state.get(f"lib_edit_script_{story_id}"))
    _script_saving = bool(st.session_state.get(f"lib_saving_script_{story_id}"))
    if _script_saving:
        # HIG save, phase 2: the Save button already painted "Saving…"
        # and disabled on the rerun; now perform the write. Errors
        # surface loudly and edit mode is kept — the save is never
        # pretended to have landed.
        st.session_state.pop(f"lib_saving_script_{story_id}", None)
        _new_script = (st.session_state.get(f"lib_script_{story_id}") or "").strip()
        if not _new_script:
            st.error("The script can't be saved empty — keep editing or Cancel.")
        else:
            try:
                lib.update_story_script(story_id, _new_script)
            except Exception as e:
                st.error(f"Could not save the script: {e}")
            else:
                st.session_state.pop(f"lib_edit_script_{story_id}", None)
                st.rerun()
    if script_md or _script_editing:
        _sh1, _sh2 = st.columns([11, 1], vertical_alignment="center")
        with _sh1:
            st.markdown('<div class="lib-section">Full Script</div>', unsafe_allow_html=True)
        with _sh2:
            if st.button("✏️", key=f"lib_script_edit_{story_id}",
                         help="Edit script",
                         disabled=_busy or _script_editing or _script_saving):
                st.session_state[f"lib_edit_script_{story_id}"] = True
                st.rerun()
        if _script_editing:
            st.text_area("Edit script", value=script_md,
                         key=f"lib_script_{story_id}", height=400,
                         label_visibility="collapsed", disabled=_script_saving)
            _sb1, _sb2, _sbs = st.columns([1, 1, 6])
            with _sb1:
                # HIG, phase 1: the initiating control owns the loading
                # state — it paints "Saving…" and stays disabled until
                # the write lands on the rerun above.
                if st.button("Saving…" if _script_saving else "Save",
                             key=f"lib_script_save_{story_id}", type="primary",
                             disabled=_script_saving or _busy):
                    st.session_state[f"lib_saving_script_{story_id}"] = True
                    st.rerun()
            with _sb2:
                if st.button("Cancel", key=f"lib_script_cancel_{story_id}",
                             disabled=_script_saving):
                    st.session_state.pop(f"lib_edit_script_{story_id}", None)
                    st.rerun()
        else:
            _render_full_script(script_md)
    elif story["dialogue"].strip():
        # Old-format files (saved before the blockquote change): two-box rendering.
        st.markdown(f'<div class="lib-dialogue">{_md_to_html(story["dialogue"])}</div>',
                    unsafe_allow_html=True)

    # Video upload + playback
    st.markdown('<div class="lib-section">Video</div>', unsafe_allow_html=True)
    video_file = meta.get("video_file", "")
    vpath = lib.media_path(story_id, video_file) if video_file else None
    if vpath:
        st.video(str(vpath))
    # Uploads: secondary actions must not dominate the layout (#66). Both
    # file uploaders live inside a single collapsed expander — one quiet
    # footer-level row. Streamlit's own size/format caption stays
    # discoverable inside the expander; upload handling behavior is
    # unchanged.
    with st.expander("⬆ Upload media", expanded=False):
        up_vid = st.file_uploader("Upload generated video", type=["mp4", "mov", "m4v", "webm"],
                                  key=f"lib_video_{story_id}")
        if up_vid is not None:
            try:
                stored = lib.store_video_upload(story_id, up_vid.getvalue(), up_vid.name)
                st.success(f"Video attached: {stored}")
                st.rerun()
            except Exception as e:
                st.error(f"Video upload failed: {e}")

        # Manual image upload
        up_imgs = st.file_uploader("Upload images manually", type=["png", "jpg", "jpeg", "webp", "gif"],
                                   accept_multiple_files=True, key=f"lib_images_{story_id}")
        if up_imgs:
            for f in up_imgs:
                try:
                    lib.store_image_upload(story_id, f.getvalue(), f.name)
                except Exception as e:
                    st.error(f"Image upload failed ({f.name}): {e}")
            st.success(f"Attached {len(up_imgs)} image(s).")
            st.rerun()

    # (Refresh actions live in the detail toolbar at the top; Share/Copy
    # actions sit in the Actions row just below it.)

    # Auto-poll while a refresh is in flight. The daemon worker thread
    # cannot trigger st.rerun() itself, so without this the page would
    # never repaint on completion — and the loader painted by the kickoff
    # rerun could miss its window entirely. While busy, re-render on a
    # short cadence; the moment the worker writes its terminal state the
    # page settles to the idle buttons and _fire_refresh_toasts reports
    # the honest outcome. Fully automatic — no "click to check status"
    # hunting. The loop always terminates: workers always write a
    # terminal state, and startup recovery clears anything a dead process
    # left behind.
    if _busy:
        _time.sleep(1.0)
        st.rerun()


def _md_to_html(md: str) -> str:
    """Tiny markdown subset → HTML for the colored section boxes (no raw HTML passthrough)."""
    import html as _html
    import re as _re
    out: list[str] = []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        s = _html.escape(s)
        s = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        out.append(f"<p style='margin: 4px 0;'>{s}</p>")
    return "".join(out) or "<p>—</p>"
