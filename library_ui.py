"""Library tab UI (v1.5): macOS-style tab bar + master-detail story browser.

The existing Studio flow is never re-indented or altered: when the Library
tab is selected this module renders the library page and the caller stops
the script (st.stop()) before any Studio code runs.
"""

from __future__ import annotations

import html as _html
import re as _re
import time as _time
from collections.abc import Callable
from functools import lru_cache as _lru_cache

import streamlit as st

import story_library as lib
import tools.fine_tune as fine_tune

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

# v1.6.2 (#90, #111): toolbar icons. The seven story-detail toolbar
# controls (Update Hashtags / Images / News, Reset, Share, Copy, Delete)
# are icon-only, drawn from Streamlit's NATIVE Material Symbols support
# (``icon=":material/<name>:"``) — no custom font, no @font-face, no data
# URI, no fragile CSS selectors. #111: the bundled woff2 + data-URI
# @font-face never loaded in the browser (tofu boxes), so the custom
# font was removed entirely; Streamlit's own font loading is the
# mechanism that provably works. The spinner is also native:
# ``icon="spinner"`` renders Streamlit's animated spinner icon while a
# refresh runs (#53 HIG: the button that starts work owns its loading
# state). Glyphs follow the light/dark theme via Streamlit's theming —
# no hard-coded colors. Tooltips (``help=``) keep the text labels.
_TB_ICON_TAG = ":material/tag:"              # Update Hashtags
_TB_ICON_IMAGE = ":material/image:"          # Update Images
_TB_ICON_NEWS = ":material/newspaper:"       # Update News
_TB_ICON_RESET = ":material/refresh:"        # Reset
_TB_ICON_SHARE = ":material/share:"          # Share
_TB_ICON_COPY = ":material/content_copy:"    # Copy
_TB_ICON_CHAT = ":material/chat:"            # Send via WhatsApp (#78)
_TB_ICON_SEND = ":material/send:"            # Share via Telegram (#78)
_TB_ICON_DELETE = ":material/delete:"        # Delete
_TB_ICON_UPLOAD = ":material/upload:"        # Upload (#114)
_TB_ICON_EDIT = ":material/edit:"            # Edit title/script (no emoji)
_TB_ICON_TUNE = ":material/tune:"            # Fine tune script (#105)
_TB_ICON_ADD = ":material/add:"              # New script version (#104)
_TB_ICON_DEFAULT = ":material/star:"         # Make default version (#104)
_TB_ICON_SPINNER = "spinner"                 # native animated spinner


def inject_library_css() -> None:
    st.markdown(
        """
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
    /* #134: news-link chips are NATIVE st.link_button — raw-HTML anchors
       inside st.markdown get neutered by Streamlit's markdown pipeline
       (clicks do nothing), while st.link_button forces a new browser tab
       (the same guarantee the #95 WhatsApp comment relies on). The
       button's <a> is styled as the chip pill so the one-row chip design
       is preserved; the × overlay keeps working via the updated
       :has(.lib-chip, [data-testid="stLinkButton"]) selectors above.
       Scoped to hscroll columns holding a link button — hashtag chips
       (plain .lib-chip spans) are untouched. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has([data-testid="stLinkButton"])
        [data-testid="stLinkButton"] {
        width: fit-content !important;
        max-width: 100% !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has([data-testid="stLinkButton"])
        [data-testid="stLinkButton"] a {
        display: inline-flex !important;
        align-items: center !important;
        box-sizing: border-box !important;
        min-height: var(--lib-chip-h) !important;
        background: var(--lib-chip-bg) !important;
        color: var(--lib-chip-text) !important;
        border: 1px solid var(--lib-chip-border) !important;
        border-radius: 999px !important;
        padding: 3px 44px 3px 12px !important;
        margin: 2px 4px 2px 0 !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
        max-width: 340px !important;
        text-decoration: none !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has([data-testid="stLinkButton"])
        [data-testid="stLinkButton"] a span {
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
        max-width: 100% !important;
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
       (:has(.lib-chip)) — or a news-link button (#134: raw-HTML anchors
       were replaced by native st.link_button, which has no .lib-chip
       span) — with the lib-x-r marker. Image cards have no
       .lib-chip, so their top-right corner × over the image is untouched;
       the ✎ is lib-x-l, also untouched. The extra :has(...) makes
       these selectors strictly more specific than the generic × rules
       above, so they win without touching them. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has(.lib-chip, [data-testid="stLinkButton"]):has([data-marker="lib-x-r"])
        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])
        + div[data-testid="stElementContainer"] {
        top: 50% !important;
        right: 6px !important;
        transform: translateY(-50%) !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has(.lib-chip, [data-testid="stLinkButton"]):has([data-marker="lib-x-r"])
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
        div[data-testid="stColumn"]:has(.lib-chip, [data-testid="stLinkButton"]):has([data-marker="lib-x-r"])
        div[data-testid="stElementContainer"]:has([data-marker="lib-x-r"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button:hover {
        opacity: 1 !important;
        background: rgba(128, 128, 128, 0.22) !important;
        color: var(--lib-chip-text) !important;
        border: none !important;
        box-shadow: none !important;
    }
    /* v1.6.2 (#139): "Send via WhatsApp" is a native st.button whose click
       hands the whatsapp:// deep link to macOS via `open` on the server —
       no custom anchor CSS needed. */
    /* macOS HIG: deference — toolbar rows use a hairline, not a heavy box */
    .lib-hairline {
        border-bottom: 1px solid rgba(128, 128, 128, 0.25);
        margin: 4px 0 12px 0;
    }
    /* v1.6 (#53) HIG progress: the button that starts work owns its loading
       state — its label NEVER changes, it shows a spinner and stays
       disabled while the work runs. (#111: the spinner is Streamlit's
       native ``icon="spinner"`` — no CSS, no markers, no fragile
       selectors. The old marker + ::before circle approach never matched
       the real DOM, so it was removed.) Width stability comes from
       use_container_width on the toolbar buttons (each fills its fixed
       column slot), so no width CSS is needed and nothing shoves its
       neighbours. */
    /* v1.6.2 (#90, #111): toolbar icons are Streamlit native material
       icons (``icon=":material/<name>:"``) — no custom font, no CSS
       needed. The native popover chevron is Streamlit's own and is
       untouched. */
    /* #114: the Upload popover trigger — icon-only (native material
       upload glyph), with a visible theme-safe border so it reads as a
       real button, not a bare glyph. Marker-scoped: the hidden
       [data-marker="lib-upload-btn"] div sits directly before the
       popover's element container inside the Upload row's button column.
       The border uses a neutral translucent gray — theme-safe in light
       and dark mode. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-upload-btn"])
        + div[data-testid="stElementContainer"] [data-testid="stPopoverButton"] {
        border: 1px solid rgba(128, 128, 128, 0.5) !important;
        border-radius: 0.5rem !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-upload-btn"])
        + div[data-testid="stElementContainer"] [data-testid="stPopoverButton"]:hover {
        border-color: currentColor !important;
    }
    /* macOS HIG section header: plain semibold text, no emoji, no boxes */
    .lib-section {
        font-size: 15px;
        font-weight: 600;
        margin: var(--lib-row-space) 0 8px 0;
    }
    /* #107: section titles that share their row with the content
       (Hashtags / News Links). The title rides in the first column of
       the chip row so it always sits on the same line as the chips.
       Margins zeroed — the standalone .lib-section spacing would push
       the row taller than one line.
       #112: the old `align-self: center` on the column never took effect
       reliably (Streamlit's column internals + the hscroll
       `align-items: start` interplay). Robust approach: the title column
       stretches to the row height and centers its content via flex —
       belt (column) and suspenders (inner vertical block). */
    .lib-section-inline {
        margin: 0 !important;
        padding: 0 !important;
        white-space: nowrap;
        line-height: 1.2 !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        > div[data-testid="stColumn"]:has(.lib-section-inline) {
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        > div[data-testid="stColumn"]:has(.lib-section-inline)
        > div[data-testid="stVerticalBlock"] {
        justify-content: center !important;
        gap: 0 !important;
    }
    /* #113: the inline Load more button column — same robust vertical
       centering as the section title above, so the button sits on the
       row's optical center line with the chips/cards. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        > div[data-testid="stColumn"]:has([data-marker="lib-load-more"]) {
        align-self: stretch !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        > div[data-testid="stColumn"]:has([data-marker="lib-load-more"])
        > div[data-testid="stVerticalBlock"] {
        justify-content: center !important;
        gap: 0 !important;
    }
    /* Quiet inline status line (replaces loud banners for background work) */
    .lib-quiet {
        text-align: center;
        font-size: 13px;
        opacity: 0.65;
        margin: 2px 0 10px 0;
    }
    /* macOS HIG: document title left-aligned, multiline, theme-safe (#84
       reverts #60 — the full title text is back as an h2; #120 moves it
       from centered to left-aligned). */
    .lib-doc-title {
        text-align: left;
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
    /* #120: the title edit button is a quiet icon action hugging the
       title — NOT a bordered box. Borderless, transparent, theme-safe
       icon color (inherits, like the other toolbar icons); subtle on
       hover. The marker div sits directly before the button's element
       container, same proven pattern as the chip × buttons. If the
       selector ever misses it degrades to a normal small button. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-title-edit"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: inherit !important;
        opacity: 0.55 !important;
        padding: 6px 8px !important;
        min-height: 0 !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-title-edit"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button:hover:not(:disabled) {
        opacity: 1 !important;
        background: rgba(128, 128, 128, 0.18) !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker="lib-title-edit"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button:disabled {
        opacity: 0.35 !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
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
    /* #129: dialog/popover trigger icons must follow the theme. Streamlit's
       native material icons use currentColor, so ensuring the icon inherits
       the button's text color (which Streamlit themes) is enough — no fill
       or stroke forcing, which would break Streamlit's icon rendering. */
    [data-testid="stButton"] button,
    [data-testid="stPopover"] button {
        color: inherit;
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
    _notify("Story deleted.", icon="✅")


def _confirm_delete_all() -> None:
    """Delete every story; the reported count is always honest."""
    n = lib.delete_all_stories()
    st.session_state.pop("lib_selected_story", None)
    st.session_state.pop("lib_story_radio", None)
    _notify(f"Deleted {n} stor{'y' if n == 1 else 'ies'}.", icon="✅")


# ---------------------------------------------------------------------------
# Single shared delete-confirmation dialog (#130)
# ---------------------------------------------------------------------------
# Streamlit allows only ONE dialog per script run. PR #123 gave each delete
# button its own dialog, crashing pages with multiple delete buttons
# (Delete All + story delete) with StreamlitInvalidLayoutContextError.
#
# Pattern: each delete trigger writes its target into
# ``st.session_state[_PENDING_DELETE_KEY]`` and reruns. ONE module-level
# dialog function (defined once, not per-button) is invoked at most once
# per script run from a single call site at the end of
# ``render_library_page()``. It reads the pending target and renders the
# confirmation for it. No pending target → the dialog is never invoked.

_PENDING_DELETE_KEY = "_pending_delete"


# The dialog decorator is applied defensively: test fakes for streamlit may
# not define ``dialog`` (they only stub what they exercise). In production
# ``st.dialog`` always exists.
try:
    _dialog_decorator = st.dialog("Delete")
except (AttributeError, TypeError):  # pragma: no cover — test fakes only
    _dialog_decorator = None
if not callable(_dialog_decorator):  # pragma: no cover — test fakes only
    def _dialog_decorator(fn):
        return fn


@_dialog_decorator
def _delete_confirm_dialog() -> None:
    """Single shared delete confirmation dialog (#130).

    Reads the pending delete target from session state. Renders nothing
    and returns immediately if there is no pending delete (the caller
    guards this too — belt and suspenders). On "Delete", executes the
    action for the target kind; on failure the error is shown loudly and
    the dialog stays open for retry. On "Cancel" or success, the pending
    target is cleared.
    """
    _pending = st.session_state.get(_PENDING_DELETE_KEY)
    if not isinstance(_pending, dict):
        return
    _kind = _pending.get("kind")
    _title = _pending.get("title", "Delete?")
    _message = _pending.get("message", "This can't be undone.")
    _destructive_label = _pending.get("destructive_label", "Delete")

    st.markdown(f"**{_md_escape(_title)}**")
    st.caption(_message)
    _bc, _bd = st.columns(2)
    with _bc:
        if st.button("Cancel", key="_pending_delete_no",
                     use_container_width=True):
            st.session_state.pop(_PENDING_DELETE_KEY, None)
            st.rerun()
    with _bd:
        if _danger_button(_destructive_label, key="_pending_delete_yes",
                          use_container_width=True):
            try:
                if _kind == "story":
                    _confirm_delete_story(_pending.get("story_id", ""))
                elif _kind == "all":
                    _confirm_delete_all()
                elif _kind == "version":
                    # #104: delete one script version (v1 is protected inside).
                    lib.delete_script_version(_pending.get("story_id", ""),
                                              _pending.get("version", 0))
                else:
                    raise RuntimeError(f"unknown delete target: {_kind!r}")
            except Exception as e:
                # Fail loudly — the dialog stays open with the error.
                st.error(f"Delete failed: {e}")
            else:
                st.session_state.pop(_PENDING_DELETE_KEY, None)
                st.rerun()


def _maybe_open_delete_dialog() -> None:
    """Invoke the shared delete dialog once if a delete is pending (#130).

    Single call site — called once per script run at the end of
    ``render_library_page()``. If no delete is pending, the dialog is
    never invoked, so pages with N delete buttons render clean.
    """
    if st.session_state.get(_PENDING_DELETE_KEY):
        _delete_confirm_dialog()


def _confirm_popover(*, trigger_icon: str = "", trigger_label: str = "",
                     popover_key: str, title: str,
                     message: str, on_yes: Callable[[], None],
                     trigger_help: str = "",
                     use_container_width: bool = False,
                     fail_label: str = "Confirm",
                     destructive_label: str,
                     disabled: bool = False,
                     spin_marker: str = "",
                     as_dialog: bool = False,
                     _pending_delete_kind: str = "",
                     _pending_delete_story_id: str = "") -> None:
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
    contract (#53) the trigger's text label NEVER changes (always empty) —
    while the work runs the trigger shows Streamlit's native animated
    spinner (``icon="spinner"``, #111) instead of its material icon.
    ``spin_marker`` is truthy while the work runs (e.g. "lib-spin-reset");
    the marker divs themselves are gone (#111) — only the truthiness is
    used to pick the spinner icon.

    #90/#111: ``trigger_icon`` is a native Streamlit material icon
    shortcode (see _TB_ICON_*) rendered via ``icon=`` with an empty text
    label — icon-only trigger, tooltip keeps the text label. When only
    ``trigger_label`` is given (e.g. "Delete All") the trigger is a plain
    text button with no icon.

    #119 ``as_dialog``: for destructive actions the trigger must be a
    direct control — no dropdown chevron (Apple HIG). The trigger becomes
    a plain ``st.button`` (icon-only when ``trigger_icon`` is given) and
    the confirmation renders in a native modal dialog instead of a
    popover. The confirmation content — title, message, Cancel +
    solid-red destructive verb, loud error on failure — is identical;
    only the trigger affordance and the container change.
    """
    _go_key = f"{popover_key}-go"
    _err_key = f"{popover_key}-err"
    # Marker first: it must sit directly before the trigger's element
    # container for the #24 collapse rule (the marker's wrapper would
    # otherwise push the trigger one gap lower than its siblings).
    st.markdown(f'<div data-marker="lib-danger-pop-{popover_key}" style="display:none"></div>',
                unsafe_allow_html=True)
    # Consume a previously armed confirmation *before* the popover
    # instantiates, so driving its key here is legal.
    if st.session_state.pop(_go_key, False):
        try:
            on_yes()
        except Exception as e:
            st.session_state[_err_key] = str(e)
            st.session_state[popover_key] = True  # reopen so the error is seen

    def _confirmation_body() -> None:
        # Shared by the popover and dialog (#119) containers: anchor
        # marker, loud error, title, message, then "Cancel" (standard,
        # left) and the destructive verb (red, right) side by side.
        st.markdown('<div data-marker="lib-danger-pop-body" style="display:none"></div>',
                    unsafe_allow_html=True)
        _failure = st.session_state.pop(_err_key, None)
        if _failure:
            st.error(f"{fail_label} failed: {_failure}")
        if not as_dialog:
            # The dialog carries the title as its own header.
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

    if as_dialog:
        # #119/#130: a destructive action is a direct control — no dropdown
        # chevron (Apple HIG). The trigger is a plain button; tapping it
        # records the delete target in session state and reruns. The SINGLE
        # shared dialog (``_delete_confirm_dialog``, #130) is invoked once
        # per script run from ``_maybe_open_delete_dialog()`` — never here —
        # because Streamlit allows only one dialog per run.
        if st.button(trigger_label,
                     icon=trigger_icon or None,
                     key=f"{popover_key}-trigger",
                     help=trigger_help or None,
                     use_container_width=use_container_width,
                     disabled=disabled):
            st.session_state[_PENDING_DELETE_KEY] = {
                "kind": _pending_delete_kind,
                "story_id": _pending_delete_story_id,
                "title": title,
                "message": message,
                "destructive_label": destructive_label,
            }
            st.rerun()
        return

    with st.popover(trigger_label,
                    icon=_TB_ICON_SPINNER if spin_marker else (trigger_icon or None),
                    key=popover_key, on_change="rerun",
                    help=trigger_help or None,
                    use_container_width=use_container_width,
                    disabled=disabled):
        _confirmation_body()


def _delete_popover(*, trigger_label: str, popover_key: str, title: str,
                    message: str, on_yes: Callable[[], None],
                    trigger_help: str = "",
                    use_container_width: bool = False,
                    destructive_label: str,
                    trigger_icon: str = "",
                    _pending_delete_kind: str = "",
                    _pending_delete_story_id: str = "") -> None:
    """Apple-style delete confirmation: neutral trigger, red explicit
    destructive verb + Cancel inside (#58).

    #119: the trigger is a DIRECT button — no popover, no dropdown chevron
    (Apple HIG). Tapping it opens the same confirmation in a native modal
    dialog. Thin wrapper over :func:`_confirm_popover` with the failure
    label set to "Delete" (kept for the existing delete flows and their
    tests). ``trigger_icon`` (#90/#111): a native Streamlit material icon
    shortcode for an icon-only trigger (rendered via ``icon=`` with an
    empty text label); when empty the text ``trigger_label`` is used
    instead.

    #130: the dialog is shared — ``_pending_delete_kind`` ("story"/"all")
    and ``_pending_delete_story_id`` identify the target recorded in
    session state when the trigger is tapped.
    """
    _confirm_popover(
        as_dialog=True,
        trigger_icon=trigger_icon,
        trigger_label=trigger_label,
        popover_key=popover_key,
        title=title,
        message=message,
        on_yes=on_yes,
        trigger_help=trigger_help,
        use_container_width=use_container_width,
        fail_label="Delete",
        destructive_label=destructive_label,
        _pending_delete_kind=_pending_delete_kind,
        _pending_delete_story_id=_pending_delete_story_id,
    )


def _render_kind_button(*, story_id: str, kind: str, label: str,
                       button_key: str, help_text: str, kick_label: str,
                       busy_kinds, ai_engine) -> None:
    """One toolbar refresh button (#53/#54, #71, #80, #90, #111).

    #71/#80/#90/#111: the button is ICON-ONLY — ``label`` is a native
    Streamlit material icon shortcode (see _TB_ICON_*; #111) passed via
    ``icon=`` with an empty text label, and the tooltip (``help_text``)
    carries the "Update Hashtags" / "Update Images" / "Update News"
    label for discoverability and accessibility. Tapping the icon
    triggers the refresh.

    #53 HIG progress: the text label NEVER changes (always empty); while
    ``kind`` runs the button shows Streamlit's native animated spinner
    (``icon="spinner"``) and stays disabled. ``use_container_width``
    keeps the width stable — the button fills its fixed column slot, so
    nothing shoves its neighbours. Each kind disables only while IT
    runs: hashtags, images and news are independent and stay clickable
    while the others run (#54, #80).
    """
    running = kind in busy_kinds
    if st.button("", icon=_TB_ICON_SPINNER if running else label,
                 key=button_key, help=help_text,
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
    button shows Streamlit's native animated spinner (``icon="spinner"``,
    #111) and stays disabled — no second click.
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
    if st.button(label, icon=_TB_ICON_SPINNER if running else None,
                 key=button_key, help=help_text,
                 disabled=running or blocked):
        ok, reason = lib.start_refresh(story_id, kind)
        if ok:
            st.rerun()
        else:
            st.error(f"Could not start: {reason}" if reason
                     else "Could not start.")


def _render_reset_popover(story_id: str, busy_kinds, ai_engine) -> None:
    """Toolbar Reset: destructive confirm popover (red "Reset media" /
    standard "Cancel", #58). #90/#111: the trigger is icon-only (native
    material refresh icon via ``icon=``, tooltip keeps the label).

    #53 HIG progress: the trigger label NEVER changes — while resetting it
    shows Streamlit's native spinner icon (``icon="spinner"``) and stays
    disabled. #54: Reset is destructive and exclusive — the trigger
    also disables while any OTHER kind runs (no spinner then: it is
    blocked, not working). Confirming kicks a "reset" refresh — hashtags,
    fetched images and news links are discarded and re-fetched fresh
    (uploads and the screenplay are never touched).

    ``spin_marker`` is truthy while a reset is running — _confirm_popover
    then shows Streamlit's native spinner icon on the trigger (#111).
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
        trigger_icon=_TB_ICON_RESET,
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
    )


def _notify(msg: str, icon: str | None = None) -> None:
    """#88: the single app-wide pattern for transient status notifications.

    Every transient status goes through ``st.toast`` — Streamlit renders
    it in one fixed position (bottom-right), auto-dismisses it after a few
    seconds, and styles every toast identically. Funneling all transient
    status through this helper guarantees notifications share one style
    and one place. Loud failures are NOT transient: they keep using
    ``st.error``/``st.warning`` so they stay visible until acknowledged.
    """
    st.toast(msg, icon=icon)


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
        _notify(_refresh_toast_text(outcome["kind"], outcome["status"],
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


def _is_openable_article_url(url: str) -> bool:
    """#134: fail-loud gate for news-link chips.

    A news chip must open its article when clicked, so only http(s) URLs
    with a host are rendered as link buttons. Anything else (empty,
    javascript:, redirect wrappers that slipped through, etc.) is
    rejected — the call site surfaces it via st.error instead of
    rendering a dead chip.
    """
    try:
        from urllib.parse import urlparse as _urlparse
        _p = _urlparse(url or "")
        return _p.scheme in ("http", "https") and bool(_p.hostname)
    except Exception:
        return False


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


def _section_title_weight(title: str) -> int:
    """#107: ``st.columns`` weight for a section title sharing its row
    with chips (Hashtags / News Links). Compact — the CSS shrink-wrap
    (``flex: 0 0 auto`` + ``width: fit-content`` on hscroll columns) is
    the primary sizer; this is the proportional fallback so a missed
    selector can only ever produce a proportionally sized column.
    Pure (no Streamlit) so it is unit-testable."""
    return max(len(str(title)), 4) + 2


def _load_more_weight(label: str) -> int:
    """#113: ``st.columns`` weight for the inline Load more button that
    rides as the last column of a section's scroll row. Same
    shrink-wrap-fallback contract as :func:`_section_title_weight`.
    Pure (no Streamlit) so it is unit-testable."""
    return max(len(str(label)), 4) + 2


def _render_news_links_row(story_id: str, links: list, busy_kinds) -> None:
    """#156: the News Links section as ONE reusable component.

    Renders the full row — "News Links" title + link chips + "Load more
    news" — and OWNS its alignment: the hscroll marker, the column
    layout (title weight + per-chip weights + load-more weight), the
    title cell, every chip cell (link button or loud error + × remove
    overlay), and the load-more cell all live inside this function.
    Alignment can no longer drift one call site at a time — any fix
    lands here and applies everywhere.

    Pure refactor of the inline block in ``_render_story_detail``
    (#156): no behavior change. ``links`` are the story's ``news_links``
    dicts (non-empty); callers render the "No news links yet." caption
    themselves when ``links`` is empty.
    """
    st.markdown('<div data-marker="lib-hscroll" style="display:none"></div>',
                unsafe_allow_html=True)
    # #107: "News Links" title and link chips share ONE row — same
    # pattern as Hashtags.
    _labels = [_news_chip_label((_lk.get("title") or "News link"),
                                (_lk.get("source") or ""))
               for _lk in links]
    _lcols = st.columns([_section_title_weight("News Links")]
                        + _chip_col_weights(_labels)
                        + [_load_more_weight("Load more news")],
                        # #162: vertically center title, chips and the
                        # Load more button (columns top-align by default).
                        vertical_alignment="center")
    with _lcols[0]:
        st.markdown('<div class="lib-section lib-section-inline">News Links</div>',
                    unsafe_allow_html=True)
    for _i, (_lc, _lk, _label) in enumerate(zip(_lcols[1:-1], links, _labels)):
        _ltitle = _lk.get("title", "News link") or "News link"
        _lurl = (_lk.get("url") or "").strip()
        with _lc:
            # #134: news links are NATIVE st.link_button, not raw-HTML
            # <a> inside st.markdown — Streamlit's markdown pipeline
            # neuters the anchor (clicks do nothing). st.link_button
            # forces a new browser tab (the same guarantee the #95
            # WhatsApp comment relies on) and is styled as the chip
            # pill by the marker-scoped CSS. Malformed URLs fail
            # loudly instead of rendering a dead chip; the × still
            # removes the bad link.
            if not _is_openable_article_url(_lurl):
                st.error(
                    f"News link \u201c{_ltitle}\u201d has an invalid URL "
                    f"and was not rendered as a link.")
            else:
                st.link_button(
                    _label,
                    _lurl,
                    help=_ltitle,
                    key=f"lib_newslink_{story_id}_{_i}",
                )
            if _overlay_button("lib-x-r", f"lib_xlink_{story_id}_{_i}", "×",
                               help="Remove this news link"):
                try:
                    lib.remove_news_link(story_id, _lurl)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.rerun()
    # #113: inline Load more — last column of the scroll row. The button
    # owns its loading state (spinner + disabled while more_news runs,
    # #91/#53).
    with _lcols[-1]:
        st.markdown('<div data-marker="lib-load-more" style="display:none"></div>',
                    unsafe_allow_html=True)
        _render_load_more_button(
            story_id=story_id, kind="more_news",
            label="Load more news",
            button_key=f"lib_morenews_{story_id}",
            help_text="Fetch up to 5 more news links",
            busy_kinds=busy_kinds)


def _render_title_row(story_id: str, title: str, editing: bool, busy: bool) -> None:
    """#154: the story title as ONE reusable component.

    Renders the title row — big left-aligned h2 + borderless edit icon
    riding in the narrow trailing column (or the borderless text-area
    editor while ``editing``) — and OWNS its alignment: the [11, 1]
    column split, vertical centering, and the edit marker all live
    inside this function.

    Pure refactor of the inline block in ``_render_story_detail``
    (#154): no behavior change.
    """
    if editing:
        st.text_area("", value=title, key=f"lib_title_{story_id}",
                     height=80, label_visibility="collapsed")
    else:
        # #120: [11, 1] — title fills the row left-aligned; the edit
        # icon-button rides in the narrow trailing column, vertically
        # centered, styled borderless via the lib-title-edit marker so it
        # feels part of the title itself.
        _tt1, _tt2 = st.columns([11, 1], vertical_alignment="center")
        with _tt1:
            st.markdown(f"<h2 class='lib-doc-title'>{_html.escape(title)}</h2>",
                        unsafe_allow_html=True)
        with _tt2:
            st.markdown('<div data-marker="lib-title-edit" style="display:none"></div>',
                        unsafe_allow_html=True)
            if st.button("", icon=_TB_ICON_EDIT, key=f"lib_title_edit_{story_id}",
                         help="Edit title", disabled=busy):
                st.session_state[f"lib_edit_title_{story_id}"] = True
                st.rerun()


def _render_hashtags_row(story_id: str, tags: list) -> None:
    """#154: the Hashtags section as ONE reusable component.

    Renders the full row — "Hashtags" title + tag chips, each with a ×
    that removes exactly that tag — and OWNS its alignment: the hscroll
    marker, the column layout (title weight + per-chip weights), the
    title cell, and every chip cell (chip + × remove overlay) all live
    inside this function. Same pattern as ``_render_news_links_row``.

    Pure refactor of the inline block in ``_render_story_detail``
    (#154): no behavior change. ``tags`` are non-empty; callers skip
    the row entirely when there are no tags.
    """
    st.markdown('<div data-marker="lib-hscroll" style="display:none"></div>',
                unsafe_allow_html=True)
    _tcols = st.columns([_section_title_weight("Hashtags")]
                        + _chip_col_weights(tags),
                        # #162: vertically center title and chips
                        # (columns top-align by default).
                        vertical_alignment="center")
    with _tcols[0]:
        st.markdown('<div class="lib-section lib-section-inline">Hashtags</div>',
                    unsafe_allow_html=True)
    for _i, (_tc, _tag) in enumerate(zip(_tcols[1:], tags)):
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


def _render_images_row(story_id: str, img_urls: list, uploaded: list,
                       busy_kinds) -> None:
    """#154: the Images cards row as ONE reusable component.

    Renders the horizontal scroll row — image cards (fetched + uploaded,
    each with ×; fetched cards keep the ✎ address editor) + "Load more
    images" as the last column — and OWNS its alignment: the hscroll
    marker, the per-card columns + load-more weight, every card cell,
    and the load-more cell all live inside this function.

    Pure refactor of the inline block in ``_render_story_detail``
    (#154): no behavior change. Callers render the "Images" title and
    the "No images yet" hint themselves; ``img_urls``/``uploaded`` are
    non-empty here (at least one is).
    """
    st.markdown('<div data-marker="lib-hscroll" style="display:none"></div>',
                unsafe_allow_html=True)
    _cards = [("fetched", i, u) for i, u in enumerate(img_urls)]
    _cards += [("uploaded", i, f) for i, f in enumerate(uploaded)]
    # #113: the Load more button rides as the LAST column of this
    # scroll row — same line as the thumbnails, inside the scroll
    # view — instead of an orphan row below.
    _icols = st.columns([1] * len(_cards)
                        + [_load_more_weight("Load more images")],
                        # #162: vertically center the Load more button
                        # against the thumbnail cards (columns top-align
                        # by default).
                        vertical_alignment="center")
    for _ci, (_icol, (_kind, _ki, _ref)) in enumerate(zip(_icols[:-1], _cards)):
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
    # #113: inline Load more — last column of the scroll row (see
    # above). The button owns its loading state (spinner + disabled
    # while more_images runs, #91/#53).
    with _icols[-1]:
        st.markdown('<div data-marker="lib-load-more" style="display:none"></div>',
                    unsafe_allow_html=True)
        _render_load_more_button(
            story_id=story_id, kind="more_images",
            label="Load more images",
            button_key=f"lib_moreimg_{story_id}",
            help_text="Fetch up to 5 more images",
            busy_kinds=busy_kinds)


def _render_upload_row(story_id: str) -> None:
    """#154: the Upload section as ONE reusable component.

    Renders the full row — "Upload" title + upload popover button
    (Video/Image picker) — and OWNS its alignment: the [11, 1] column
    split, vertical centering, the title cell, and the button cell
    (with its marker) all live inside this function.

    Pure refactor of the inline block in ``_render_story_detail``
    (#154): no behavior change.
    """
    # (Video/Image radio + file uploader). Title and button share one
    # line, vertically centered.
    _u1, _u2 = st.columns([11, 1], vertical_alignment="center")
    with _u1:
        st.markdown('<div class="lib-section lib-section-inline">Upload</div>',
                    unsafe_allow_html=True)
    with _u2:
        st.markdown('<div data-marker="lib-upload-btn" style="display:none"></div>',
                    unsafe_allow_html=True)
        with st.popover("", icon=_TB_ICON_UPLOAD, help="Upload video or image"):
            _render_upload_popover(story_id)


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
    "Warming up…" and stays disabled (no second tap). A *manual* warm-up
    auto-polls until the worker writes its terminal state; an *automatic*
    launch-time warm-up (#122) is purely informational — no poll loop, so
    the page renders once and stays interactive while the probe runs.
    """
    _state = lib.read_fm_warmup_state()
    _label, _disabled = _fm_warmup_button_props(_state)
    if _disabled:
        st.button(_label, key="fm_warmup_btn", disabled=True,
                  help="Warming up the on-device Apple FM model…",
                  use_container_width=True)
        if not (_state or {}).get("auto"):
            # Manual warm-up: the initiating control owns its loading state.
            # Auto-poll while the probe is in flight: the daemon worker
            # cannot trigger st.rerun() itself. Same pattern as the library
            # refresh flow — the loop always terminates because the worker
            # always writes a terminal state within 60s (#122) and stale
            # states are recovered.
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
        _notify(f"Apple FM warmed up in {_secs:.1f}s"
                + (f" — {_msg}" if _msg else ""),
                icon="✅")
    elif _stt == "failed":
        _msg = (_state.get("message") or "unknown error").strip()
        st.error(f"Warm-up failed: {_msg}")
        # Loud failure gets an explicit retry — never a silent stuck state.
        if st.button("Retry warm-up", key="fm_warmup_retry",
                     help="Run the FM warm-up probe again"):
            _ok, _reason = lib.start_fm_warmup()
            if not _ok:
                st.error(f"Could not start warm-up: {_reason}")
            st.rerun()


def render_tab_bar() -> str:
    """Render the macOS-style tab bar. Returns 'studio' or 'library'."""
    # #115: cold-start init runs in a background thread — fire it once per
    # process before anything else so the UI renders immediately and stays
    # interactive while the FM probe warms up. Never blocks, never raises.
    lib.maybe_auto_cold_start()
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
        _notify("Saved to Library.", icon="✅")
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
            _pending_delete_kind="all",
        )
    with detail:
        _render_story_detail(sel)

    # #130: single shared delete dialog — invoked at most once per script
    # run, after all delete triggers have rendered. If no delete is pending,
    # this is a no-op.
    _maybe_open_delete_dialog()


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
    """Share text: title, hashtags, then site-named news link(s).

    #151: format is
        <title>
        #tag1 #tag2

        <site name>: <url>
        <site name>: <url>

    Formatted for pasting straight into a social-media post — title first,
    hashtags space-separated on the next line, then a blank line and one
    "<source>: <url>" line per news link. The site name is the link's
    ``source`` field; when it is missing or empty the URL's domain is
    used instead — the prefix is never blank. URLs are deduped.
    Returns "" when the story has neither title, news links nor hashtags,
    so the caller can say so plainly instead of copying nothing.
    """
    import urllib.parse as _up
    seen_urls: set = set()
    link_lines = []
    for lk in (meta.get("news_links") or []):
        if not isinstance(lk, dict):
            continue
        url = (lk.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        source = (lk.get("source") or "").strip()
        if not source:
            # Fail-loud-friendly: the prefix is never blank; the domain
            # is the best available site name, the raw URL the last resort.
            try:
                source = _up.urlparse(url).netloc or url
            except Exception:
                source = url
        link_lines.append(f"{source}: {url}")
    tags = [t for t in (meta.get("hashtags") or []) if t]
    head = []
    title = (title or "").strip()
    if title:
        head.append(title)
    if tags:
        head.append(" ".join(tags))
    body = "\n".join(head)
    if link_lines:
        links_text = "\n".join(link_lines)
        return f"{body}\n\n{links_text}" if body else links_text
    return body


def _whatsapp_share_url(text: str) -> str:
    """whatsapp:// deep link carrying the EXACT share text (URL-encoded for
    transport only — the text itself is never reformatted).

    #139: this URL is handed to macOS LaunchServices via the ``open``
    command (see ``_open_whatsapp_share``) — the server runs on the user's
    Mac, so the deep link opens the installed WhatsApp Mac app directly
    with the text prefilled. Unlike wa.me links, which always resolve in
    the browser (WhatsApp Web flow) even when the app is installed, the
    native scheme never touches the browser. No connection or connector
    needed.

    Note (#95): this URL must never go through st.link_button, which
    forces a new browser tab and defeats the deep link.
    """
    import urllib.parse as _up
    return "whatsapp://send?text=" + _up.quote(text, safe="")


def _whatsapp_web_share_url(text: str) -> str:
    """wa.me share link carrying the EXACT share text (URL-encoded).

    #144: browser fallback when the native app handoff fails — wa.me
    opens WhatsApp (Web, or the installed app if the browser routes the
    link there) with the text prefilled. The user explicitly requested
    this fallback (#144), reversing the earlier no-fallback rule.
    """
    import urllib.parse as _up
    return "https://wa.me/?text=" + _up.quote(text, safe="")


def _open_whatsapp_share(text: str) -> str:
    """Share via WhatsApp: native app first, browser fallback, loud failure.

    #139/#144: the Streamlit server runs on the user's Mac. First tries
    the installed WhatsApp Mac app: the ``whatsapp://send?text=`` deep
    link is handed to macOS LaunchServices via the ``open`` command,
    which launches WhatsApp with the text prefilled and returns
    immediately; the user picks the chat in the app. This replaced the
    old plain-anchor approach, which depended on the *browser* routing
    the custom URL scheme — unreliable across browsers — and proved
    broken.

    #144: if the app cannot be opened (non-zero exit, timeout, missing
    ``open`` command, no scheme handler — or a non-macOS server where
    the app path can't work), falls back to opening
    ``https://wa.me/?text=`` in the browser. The user explicitly
    requested this browser fallback, reversing the earlier no-fallback
    rule.

    Returns "app" or "browser" naming the path that worked, so the
    caller can confirm honestly. Raises RuntimeError only when BOTH
    paths fail, carrying both failures' details. Never a silent no-op.
    """
    import platform as _platform
    import shutil as _shutil
    import subprocess as _sp
    import webbrowser as _wb

    failures = []

    # Path 1 — native app handoff (macOS only).
    opener = _shutil.which("open") if _platform.system() == "Darwin" else None
    if opener is not None:
        url = _whatsapp_share_url(text)
        try:
            proc = _sp.run(
                [opener, url],
                capture_output=True, text=True, timeout=15,
            )
        except _sp.TimeoutExpired as e:
            failures.append(f"app handoff timed out after 15s: {e}")
        except OSError as e:
            failures.append(f"couldn't launch `open`: {e}")
        else:
            if proc.returncode == 0:
                return "app"
            detail = (proc.stderr or proc.stdout or "").strip()
            failures.append(
                "`open` couldn't hand off to WhatsApp "
                f"(exit {proc.returncode})"
                + (f": {detail}" if detail else
                   ". Is WhatsApp installed and registered for whatsapp:// links?")
            )
    else:
        failures.append(
            "native app handoff needs macOS `open` "
            f"(server runs on {_platform.system()})"
        )

    # Path 2 — browser fallback (#144).
    web_url = _whatsapp_web_share_url(text)
    try:
        if _wb.open(web_url):
            return "browser"
        failures.append("browser launch reported failure opening the wa.me link")
    except Exception as e:
        failures.append(f"browser fallback failed: {type(e).__name__}: {e}")

    raise RuntimeError(
        "Couldn't share via WhatsApp: the app handoff and the browser "
        "fallback both failed (" + "; ".join(failures) + ")."
    )


@_lru_cache(maxsize=1)
def _whatsapp_app_installed() -> bool:
    """Detect the WhatsApp Mac app. The Streamlit server runs locally on the
    user's Mac, so the filesystem is the source of truth. Cached for the
    session — app installs don't change between renders, so this never runs
    per-render. Tests clear the cache via ``cache_clear()``.

    #108: primary detection is Spotlight by bundle ID
    (``net.whatsapp.WhatsApp``) via ``mdfind`` — this finds the app wherever
    it is installed, including the macOS localized folder
    (``/Applications/WhatsApp.localized/WhatsApp.app``), which the old
    hard-coded paths missed. If mdfind is unavailable or fails, we fall back
    to the hard-coded candidate paths (including the .localized variants)
    plus the app's sandbox/group containers (created on first launch) — a
    failed mdfind never reports "not installed"; only the exhaustive
    checks do. #139: the mdfind timeout is short (5s) so a sick Spotlight
    degrades fast instead of hanging the Share popover render.
    """
    import os as _os
    import shutil as _shutil
    import subprocess as _sp

    mdfind = _shutil.which("mdfind")
    if mdfind is not None:
        try:
            out = _sp.run(
                [mdfind,
                 "kMDItemCFBundleIdentifier == 'net.whatsapp.WhatsApp'"],
                capture_output=True, text=True, timeout=5,
            )
        except (OSError, _sp.TimeoutExpired):
            out = None  # mdfind broken here — fall back to path checks.
        if out is not None and out.returncode == 0 and any(
            line.strip() for line in out.stdout.splitlines()
        ):
            return True
        # mdfind ran but found nothing (or failed): fall through to the
        # path-based checks below as a second opinion — Spotlight indexing
        # can lag behind a fresh install.

    candidates = (
        "/Applications/WhatsApp.app",
        "/Applications/WhatsApp.localized/WhatsApp.app",
        _os.path.expanduser("~/Applications/WhatsApp.app"),
        _os.path.expanduser("~/Applications/WhatsApp.localized/WhatsApp.app"),
        # #139: the Mac App Store build creates these sandbox/group
        # containers on first launch — strong positive signals even when
        # Spotlight lags and the .app bundle itself moved elsewhere.
        _os.path.expanduser(
            "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared"),
        _os.path.expanduser("~/Library/Containers/net.whatsapp.WhatsApp"),
    )
    return any(_os.path.isdir(p) for p in candidates)


def _story_video_path(story_id: str, meta: dict) -> Optional[str]:
    """Absolute path of the story's attached video file, or None.

    Shared by WhatsApp (#150) and Telegram (#159) sharing: the metadata
    may reference a video file that is missing from disk, which raises
    RuntimeError loudly instead of sharing without the video.
    """
    video_file = (meta.get("video_file") or "").strip()
    if not video_file:
        return None
    vpath = lib.media_path(story_id, video_file)
    if vpath is None:
        raise RuntimeError(
            f"Story references video '{video_file}' but the file is missing "
            f"from the stories directory."
        )
    return str(vpath.resolve())


def _whatsapp_video_path(story_id: str, meta: dict) -> Optional[str]:
    """Return the absolute path of the story's attached video for WhatsApp sharing.

    #150: WhatsApp's URL scheme (whatsapp://send?text= and wa.me/?text=)
    only carries text — there is no media parameter, so a video file cannot
    be attached via the deep link. The best feasible approach is to include
    the video's file path in the share text and tell the user to attach it
    manually in WhatsApp.

    Returns the absolute video path as a string, or None if no video is
    attached. Raises RuntimeError (fail loudly) if the metadata references
    a video file that is missing from disk.
    """
    return _story_video_path(story_id, meta)


def _telegram_share_parts(meta: dict):
    """(caption, links_text) for the Telegram bot share — pure, testable.

    #159: the share is two messages. The caption (title, then hashtags
    space-separated) rides with the video — or becomes the first text
    message when the story has no video. links_text is one "site: url"
    line per news link (the second message); "" when there are no links.
    The formats mirror _compose_news_tags_text (#151): title → tags →
    links, site name never blank, URLs deduped.
    """
    import urllib.parse as _up
    title = (meta.get("title") or "").strip() or "Untitled Story"
    tags = [t for t in (meta.get("hashtags") or []) if t]
    caption = title + ("\n" + " ".join(tags) if tags else "")
    seen_urls = set()
    link_lines = []
    for lk in (meta.get("news_links") or []):
        if not isinstance(lk, dict):
            continue
        url = (lk.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        source = (lk.get("source") or "").strip()
        if not source:
            try:
                source = _up.urlparse(url).netloc or url
            except Exception:
                source = url
        link_lines.append(f"{source}: {url}")
    return caption, "\n".join(link_lines)


def _share_via_telegram_bot(story_id: str, meta: dict) -> str:
    """Share the story to Telegram via the user's bot. Returns a summary.

    #159: two messages — (1) the video with the caption (title + hashtags),
    or the caption as a plain text message when the story has no video
    attached; (2) the news links. The bot token resolves by precedence —
    ``~/Documents/telegrambot/bot_token.txt`` (default), then the custom
    ``telegram_bot_token`` in prefs; the chat id is discovered once from
    the bot's updates and remembered (``telegram_chat_id``).

    #179: after the DM share, the same two messages are broadcast to every
    group/supergroup the bot is in (the user's own chat id is skipped —
    it already got them). Discovery runs on every share so newly joined
    groups are picked up; a discovery failure must not fail the DM share
    that already went through — it is reported loudly in the summary
    instead.

    Raises TelegramShareError (or RuntimeError for a metadata-referenced
    video file missing from disk) with an actionable message on any
    failure — never a silent no-op.
    """
    from tools import telegram_share as _tg
    prefs = lib.load_prefs()
    token = _tg.resolve_token(prefs.get("telegram_bot_token"))
    chat_id = prefs.get("telegram_chat_id")
    if not chat_id:
        # Raises loudly (including when no token is configured yet).
        chat_id = _tg.discover_chat_id(token)
        lib.save_prefs({"telegram_chat_id": chat_id})
    caption, links_text = _telegram_share_parts(meta)
    video_path = _story_video_path(story_id, meta)  # None, or raises loudly
    sent = []
    if video_path:
        _tg.send_video(token, chat_id, video_path, caption)
        sent.append("video + caption")
    else:
        _tg.send_text(token, chat_id, caption)
        sent.append("caption as text (this story has no video attached)")
    if links_text:
        _tg.send_text(token, chat_id, links_text)
        n_links = len(links_text.splitlines())
        sent.append(f"{n_links} news link{'s' if n_links != 1 else ''}")
    # #179: broadcast the same two messages to every group the bot is in.
    try:
        _group_ids = _tg.discover_group_ids(token)
    except Exception as e:  # auxiliary step — never fail the DM share above
        sent.append(f"group broadcast skipped (couldn't list groups: {e})")
    else:
        _own = str(chat_id)
        _targets = sorted(g for g in set(_group_ids) if str(g) != _own)
        if _targets:
            sent.append(_tg.broadcast_story(
                token, _targets, video_path=video_path, caption=caption,
                links_text=links_text))
        else:
            sent.append("no groups to broadcast to (add the bot to a group)")
    return "Sent to Telegram: " + ", then ".join(sent) + "."


def _render_share_popover(story_id: str, share_text: str, meta: dict) -> None:
    """Share menu (native popover, macOS HIG): sub-actions for the
    story's news-links + hashtags share text.

    #78: redesigned from a plain button stack into a real menu — icon-led
    rows (leading Material icon + label, no button chrome), with a divider
    separating the Copy action from the share destinations. #90/#111: the
    trigger is icon-only (native material share icon via ``icon=`` with an
    empty text label); the tooltip keeps the "Share" label. Streamlit's
    popover natively renders its own chevron, so nothing is baked into the
    label (#46).

    The redundant st.code(share_text) preview is gone (#27) — the dedicated
    Hashtags / News Links sections already show that content, and the text
    stays one click away via "Copy News Link + Hashtags". "Send via WhatsApp"
    hands the share text to the installed WhatsApp Mac app (#28) via a
    server-side ``open`` of the whatsapp:// deep link (#139) — no browser
    tab involved (#95) — with a wa.me browser fallback when the app can't
    be opened (#144).

    #150: if the story has a video attached, the video's file path is
    appended to the WhatsApp share text (the URL scheme cannot carry media,
    so the user attaches it manually in WhatsApp). A missing video file
    fails loudly instead of sending without it.

    #159: "Share via Telegram" sends the story through the user's own
    Telegram bot (Bot API) in two messages — the video with a caption
    (title + hashtags), then the news links. The tg:// deep link cannot
    carry a video file, so the bot route is the one that delivers video.
    The bot token is configured once, right here in the popover; a missing
    token shows setup steps instead of a dead button — never a silent
    no-op.
    """
    with st.popover("", icon=_TB_ICON_SHARE, key=f"lib_sharepop_{story_id}",
                     help="Share this story's news links and hashtags",
                     use_container_width=True):
        if share_text:
            _copy_button("Copy News Link + Hashtags", share_text,
                         f"n-{story_id}", _COPY_ROW_ICON_COPY)
            # #78: the copy action is separated from the share destinations
            # by a divider — the menu reads as two groups, not one stack.
            st.divider()
            if _whatsapp_app_installed():
                # #139/#144: a real button, not an anchor. The click runs
                # _open_whatsapp_share on the server (which runs on the
                # user's Mac): first the whatsapp:// deep link is handed
                # to macOS `open` for the installed app; if the app can't
                # be opened, a wa.me link opens in the browser instead.
                # The old plain-anchor approach depended on the *browser*
                # routing the custom URL scheme, which proved unreliable.
                if st.button(
                    "Send via WhatsApp",
                    icon=_TB_ICON_CHAT,
                    key=f"lib_wa_{story_id}",
                    help="Share via WhatsApp — opens the Mac app when "
                         "installed, otherwise your browser",
                    use_container_width=True,
                ):
                    try:
                        # #150: include the video path if attached. The
                        # URL scheme can't carry media, so the path goes
                        # in the text and the user attaches it manually.
                        # A missing video file fails loudly — we do NOT
                        # send the text without the video.
                        vpath = _whatsapp_video_path(story_id, meta)
                        wa_text = share_text
                        if vpath:
                            wa_text = f"{wa_text}\n\nVideo: {vpath}"
                        _how = _open_whatsapp_share(wa_text)
                    except RuntimeError as e:
                        st.error(f"Couldn't share via WhatsApp: {e}")
                    else:
                        if _how == "app":
                            msg = "WhatsApp opened — pick a chat to send."
                        else:
                            msg = ("Opening WhatsApp in your browser — "
                                   "pick a chat to send.")
                        if vpath:
                            msg += (f" Attach the video manually from:\n"
                                    f"{vpath}")
                        _notify(msg)
            else:
                # Fail loudly: never a dead link. The app may still open
                # via the browser fallback when clicked.
                st.caption("WhatsApp Mac app not installed — "
                           "sharing will open WhatsApp in your browser.")
            # #159: Telegram via the user's bot — video + caption, then
            # news links (two messages). Server-side, like WhatsApp above:
            # the Streamlit server runs on the user's Mac and POSTs the
            # local video file to the Bot API directly. The token resolves
            # by precedence: ~/Documents/telegrambot/bot_token.txt
            # (default), then the custom token in prefs.
            from tools import telegram_share as _tg
            try:
                _tg_token = _tg.resolve_token(
                    lib.load_prefs().get("telegram_bot_token"))
            except _tg.TelegramShareError:
                _tg_token = ""
            if _tg_token:
                if st.button(
                    "Share via Telegram",
                    icon=_TB_ICON_SEND,
                    key=f"lib_tg_{story_id}",
                    help="Send the video + caption, then the news links, "
                         "to Telegram via your bot — also broadcast to "
                         "every group the bot is in",
                    use_container_width=True,
                ):
                    try:
                        with st.spinner("Sharing to Telegram…"):
                            _tg_msg = _share_via_telegram_bot(story_id, meta)
                    except Exception as e:
                        st.error(f"Couldn't share via Telegram: {e}")
                    else:
                        _notify(_tg_msg, icon="✅")
            else:
                # Fail loudly with guided setup — never a dead button.
                with st.expander("Set up Telegram sharing"):
                    st.markdown(
                        "Share the **video + caption + news links** straight "
                        "to Telegram through your own bot (two messages):\n"
                        "1. In Telegram, open **@BotFather** → `/newbot` → "
                        "copy the token.\n"
                        "2. Open your new bot and tap **Start** (send it a "
                        "first message).\n"
                        "3. Save the token as "
                        "`~/Documents/telegrambot/bot_token.txt` (picked up "
                        "automatically), or paste a custom token below.\\n"
                        "4. To broadcast to groups as well, add the bot to "
                        "each group.")
                    _tok_in = st.text_input(
                        "Bot token", type="password",
                        key=f"lib_tg_tok_{story_id}")
                    if st.button("Save Telegram bot",
                                 key=f"lib_tg_tok_save_{story_id}",
                                 use_container_width=True):
                        _tok_in = (_tok_in or "").strip()
                        if not _tok_in:
                            st.error("Paste the bot token from @BotFather first.")
                        else:
                            lib.save_prefs({"telegram_bot_token": _tok_in})
                            _saved = ((lib.load_prefs().get("telegram_bot_token")
                                       or "").strip())
                            if _saved != _tok_in:
                                st.error("Couldn't save the token — the prefs "
                                         "file isn't writable.")
                            else:
                                _notify("Telegram bot saved — you can share now.",
                                        icon="✅")
                                st.rerun()
        else:
            st.caption("No news links or hashtags to share yet.")


def _render_copy_popover(story_id: str, meta: dict, script_md: str) -> None:
    """Copy menu (native popover, macOS HIG): Script / Script + Tags /
    Script + Media — divider — All. The same one-click copy texts as
    before, now presented as menu rows.

    #78 (Claude-approved design): the toolbar's single copy icon opens
    this menu directly (no separate dropdown button); each row carries
    its OWN meaningful leading icon (document / # / image / layers),
    with a divider before "All". #90/#111: the trigger is icon-only
    (native material content_copy icon via ``icon=`` with an empty text
    label); the tooltip keeps the "Copy" label. Each copy row owns its
    loading state ("Copied ✓") via _copy_button — no second click.
    """
    with st.popover("", icon=_TB_ICON_COPY, key=f"lib_copypop_{story_id}",
                     help="Copy the screenplay in different formats",
                     use_container_width=True):
        if script_md:
            _copy_button("Script", _script_plain_text(script_md),
                         f"s-{story_id}", _COPY_ROW_ICON_DOC)
            _copy_button("Script + Tags",
                         _compose_share_text(meta, script_md, False, True),
                         f"h-{story_id}", _COPY_ROW_ICON_HASH)
            _copy_button("Script + Media",
                         _compose_share_text(meta, script_md, True, False),
                         f"m-{story_id}", _COPY_ROW_ICON_IMAGE)
            # The menu reads as two groups: the format rows, then "All".
            st.divider()
            _copy_button("All",
                         _compose_share_text(meta, script_md, True, True),
                         f"a-{story_id}", _COPY_ROW_ICON_LAYERS)
        else:
            st.caption("No script to copy yet.")




# Shared with --lib-act-h in inject_library_css: the copy button renders
# inside an isolated iframe (components.html) so page CSS cannot reach it —
# the value is mirrored here to keep ONE alignment system.
_LIB_ACTION_BTN_H_PX = 38


# #78 (Claude-approved design): the Copy menu rows each carry their OWN
# meaningful leading icon — never the same glyph on every row. All icons
# are inline SVG drawn with currentColor so they follow the theme text
# color; no hardcoded fills (theme-safe, #129).
_COPY_ROW_ICON_DOC = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"'
    ' aria-hidden="true"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12'
    'c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>'
    "</svg>"
)
_COPY_ROW_ICON_HASH = (
    '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">'
    '<text x="12" y="17.5" text-anchor="middle" font-size="15"'
    ' fill="currentColor" font-family="-apple-system,BlinkMacSystemFont,'
    "'SF Pro Text',sans-serif\">#</text></svg>"
)
_COPY_ROW_ICON_IMAGE = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"'
    ' aria-hidden="true"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14'
    'c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>'
    "</svg>"
)
_COPY_ROW_ICON_LAYERS = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"'
    ' aria-hidden="true"><path d="M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63'
    '-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z"/></svg>'
)
_COPY_ROW_ICON_COPY = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"'
    ' aria-hidden="true"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4'
    'H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2-'
    'zm0 16H8V7h11v14z"/></svg>'
)


def _copy_button_html(label: str, text: str, key: str, icon: str) -> str:
    """Pure HTML for the _copy_button menu row (no Streamlit dependency).

    Split out so tests can assert the menu-row markup without importing
    streamlit.components.v1. ``icon`` is the row's leading SVG icon —
    #78 (Claude design): each row carries its own meaningful icon.
    """
    import html as _html
    import json as _json
    payload = _json.dumps(text)
    btn_id = f"libcp-{key}"
    return (
        f"""<button id="{btn_id}" style="width:100%;min-height:{_LIB_ACTION_BTN_H_PX}px;box-sizing:border-box;
        display:flex;align-items:center;gap:10px;padding:7px 10px;margin:0;
        background:transparent;border:none;border-radius:8px;cursor:pointer;
        font-size:13px;text-align:left;
        font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',sans-serif;"
        >{icon}<span id="{btn_id}-lbl">{_html.escape(label)}</span></button>
        <style>#{btn_id}:hover{{background:rgba(0,0,0,0.05);}}
        #{btn_id}[data-dark="1"]:hover{{background:rgba(255,255,255,0.10);}}
        #{btn_id}:focus-visible{{outline:2px solid currentColor;outline-offset:-2px;}}</style>
        <script>
        (function() {{
            const btn = document.getElementById("{btn_id}");
            const lbl = document.getElementById("{btn_id}-lbl");
            function applyTheme() {{
                let dark = false;
                try {{
                    dark = window.parent.document.body.getAttribute('data-theme') === 'dark';
                }} catch (e) {{}}
                btn.setAttribute("data-dark", dark ? "1" : "0");
                btn.style.color = dark ? '#FAF7F0' : '#1d1d1f';
            }}
            applyTheme();
            try {{
                new MutationObserver(applyTheme).observe(
                    window.parent.document.body,
                    {{attributes: true, attributeFilter: ['data-theme']}});
            }} catch (e) {{}}
            btn.addEventListener("click", async () => {{
                const t = {payload};
                try {{ await navigator.clipboard.writeText(t); }}
                catch (e) {{
                    const ta = document.createElement("textarea");
                    ta.value = t; document.body.appendChild(ta); ta.select();
                    try {{ document.execCommand("copy"); }} catch (_e) {{}}
                    ta.remove();
                }}
                const old = lbl.textContent; lbl.textContent = "Copied \\u2713";
                setTimeout(() => {{ lbl.textContent = old; }}, 1500);
            }});
        }})();
        </script>"""
    )


def _copy_button(label: str, text: str, key: str, icon: str) -> None:
    """One-click copy-to-clipboard menu row (clipboard API with execCommand fallback).

    #78 (Claude-approved design): an Apple-HIG menu row — the row's OWN
    leading icon (``icon``) + label, no button chrome, hover highlight.
    #129: theme-aware — detects Streamlit's rendered theme (light/dark)
    from the parent document and applies matching styles. Falls back to
    the light appearance if theme detection fails (e.g. cross-origin).
    Never hardcodes a single-theme color; the icon uses ``currentColor``.

    The click still copies one-click and morphs the row label to
    "Copied ✓" for 1.5s (#30) — the initiating row owns its feedback, no
    second click.
    """
    import streamlit.components.v1 as components
    components.html(
        _copy_button_html(label, text, key, icon),
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


def _reset_file_uploader(key: str) -> None:
    """Reset a file_uploader widget so its file is never processed twice.

    Widget values persist in session state across reruns. Deleting the key
    is the documented reset (allowed even after the widget was instantiated
    this run). Without this, an upload followed by st.rerun() would re-store
    the same file on every subsequent run — an endless rerun loop for video,
    unbounded duplicate images for images (#145).
    """
    if key in st.session_state:
        del st.session_state[key]


def _render_upload_popover(story_id: str) -> None:
    """Body of the Upload popover: Video/Image radio + file uploader.

    On upload the file is stored via lib.store_video_upload /
    lib.store_image_upload, the uploader is reset (see _reset_file_uploader)
    so the file is never stored twice, and the page reruns on success.
    Failures surface via st.error / st.warning; the uploader is still reset
    so a bad file is never silently retried on every later interaction.
    """
    _up_kind = st.radio("Media type", ["Video", "Image"],
                        key=f"lib_upkind_{story_id}")
    if _up_kind == "Video":
        up_vid = st.file_uploader("Upload generated video",
                                  type=["mp4", "mov", "m4v", "webm"],
                                  key=f"lib_video_{story_id}")
        if up_vid is not None:
            _up_ok = False
            try:
                stored = lib.store_video_upload(story_id, up_vid.getvalue(),
                                                up_vid.name)
            except Exception as e:
                st.error(f"Video upload failed: {e}")
            else:
                _up_ok = True
                _notify(f"Video attached: {stored}", icon="✅")
            _reset_file_uploader(f"lib_video_{story_id}")
            if _up_ok:
                st.rerun()
    else:
        # Manual image upload
        up_imgs = st.file_uploader("Upload images manually",
                                   type=["png", "jpg", "jpeg", "webp", "gif"],
                                   accept_multiple_files=True,
                                   key=f"lib_images_{story_id}")
        if up_imgs:
            _up_failed = 0
            for f in up_imgs:
                try:
                    lib.store_image_upload(story_id, f.getvalue(), f.name)
                except Exception as e:
                    _up_failed += 1
                    st.error(f"Image upload failed ({f.name}): {e}")
            _reset_file_uploader(f"lib_images_{story_id}")
            if _up_failed:
                st.warning(f"Attached {len(up_imgs) - _up_failed} of "
                           f"{len(up_imgs)} image(s).")
            else:
                _notify(f"Attached {len(up_imgs)} image(s).", icon="✅")
                st.rerun()


# ---------------------------------------------------------------------------
# #105 — "Fine tune script": iterative LLM refinement of the story's script.
# ---------------------------------------------------------------------------
def _render_fine_tune_section(story_id: str, meta: dict, script_md: str,
                              busy: bool) -> None:
    """Render the "Fine tune script" section under the story's script.

    The user types a natural-language instruction ("make it funnier"); the
    LLM surgically refines the current script and the result replaces it.
    Every turn is recorded in the story's fine-tune history so the
    conversation carries across turns (and #104's versioning can adopt it).

    HIG: the initiating control owns its loading state — the button paints
    "Fine tuning…" with the native spinner and stays disabled until the
    refinement lands on the rerun. LLM errors surface loudly; a failed turn
    never pretends the script changed.
    """
    st.markdown('<div class="lib-section">Fine tune script</div>',
                unsafe_allow_html=True)
    _ft_running = bool(st.session_state.get(f"lib_ft_running_{story_id}"))
    _ft_input_key = f"lib_ft_input_{story_id}"

    try:
        _history = lib.get_fine_tune_history(story_id)
    except Exception as e:
        # Loud, but must not brick the story view over a history read.
        st.error(f"Could not load fine-tune history: {e}")
        _history = []
    if _history and not _ft_running:
        with st.expander(f"Earlier refinements ({len(_history)})",
                         expanded=False):
            for _i, _turn in enumerate(_history, 1):
                st.caption(f"Turn {_i}: {_turn['instruction']}")

    st.text_input(
        "What should change?",
        placeholder="e.g. make it funnier, tighten the hook",
        key=_ft_input_key,
        label_visibility="collapsed",
        disabled=_ft_running or busy,
    )
    if st.button(
        "Fine tuning…" if _ft_running else "Fine tune script",
        icon=_TB_ICON_SPINNER if _ft_running else _TB_ICON_TUNE,
        key=f"lib_ft_apply_{story_id}",
        type="primary",
        disabled=_ft_running or busy,
        help="Ask the AI to refine the script per your instruction",
    ):
        # HIG phase 1: paint the loading state now; the refinement runs
        # on the rerun below (phase 2).
        st.session_state[f"lib_ft_running_{story_id}"] = True
        st.rerun()

    if _ft_running:
        # HIG phase 2: perform the refinement. Errors surface loudly and
        # the input is kept — the turn is never pretended to have landed.
        st.session_state.pop(f"lib_ft_running_{story_id}", None)
        _instruction = (st.session_state.get(_ft_input_key) or "").strip()
        if not _instruction:
            st.error("Describe what to change first — e.g. “make it funnier”.")
            return
        _ctx_parts = []
        _title = (meta.get("title") or "").strip()
        if _title:
            _ctx_parts.append(f"Title: {_title}")
        _topic = (meta.get("source_headline")
                  or meta.get("source_topic") or "").strip()
        if _topic:
            _ctx_parts.append(f"Topic: {_topic}")
        try:
            with st.spinner("Fine-tuning the script…"):
                _refined = fine_tune.fine_tune_script(
                    current_script=script_md,
                    instruction=_instruction,
                    story_context="\n".join(_ctx_parts),
                    history=_history,
                    tone=(meta.get("tone") or "").strip(),
                )
            lib.record_fine_tune_turn(story_id, _instruction, _refined)
        except Exception as e:
            st.error(f"Fine tune failed: {e}")
        else:
            st.session_state.pop(_ft_input_key, None)
            st.rerun()
def _render_script_version_body(story_id: str, version: dict, is_default: bool,
                                busy: bool) -> None:
    """Body of one script-version expander: actions + view/edit (#104).

    Actions are direct icon buttons (repo rule: delete is a direct icon,
    not a dropdown). Delete on v1 is never rendered — the original is
    protected. "Make default" is hidden on the version that already is.
    """
    _n = version["n"]
    _edit_key = f"lib_edit_script_v{_n}_{story_id}"
    _save_key = f"lib_saving_script_v{_n}_{story_id}"
    _text_key = f"lib_script_v{_n}_{story_id}"
    _editing = bool(st.session_state.get(_edit_key))
    _saving = bool(st.session_state.get(_save_key))

    if _saving:
        # HIG save, phase 2: the Save button already painted "Saving…" and
        # disabled on the rerun; now perform the write. Errors surface
        # loudly and edit mode is kept — the save is never pretended.
        st.session_state.pop(_save_key, None)
        _new_text = (st.session_state.get(_text_key) or "").strip()
        if not _new_text:
            st.error("The script can't be saved empty — keep editing or Cancel.")
        else:
            try:
                lib.update_script_version_text(story_id, _n, _new_text)
            except Exception as e:
                st.error(f"Could not save Version {_n}: {e}")
            else:
                st.session_state.pop(_edit_key, None)
                st.rerun()

    # Per-version action row: created date + icon-only controls.
    _ac1, _ac2, _ac3, _ac4 = st.columns([8, 1, 1, 1], vertical_alignment="center")
    with _ac1:
        _created = (version.get("created_at") or "").replace("T", " ")[:16]
        st.caption(f"Created {_created}" if _created else " ")
    with _ac2:
        if st.button("", icon=_TB_ICON_EDIT, key=f"lib_script_vedit_{story_id}_{_n}",
                     help=f"Edit Version {_n}",
                     disabled=busy or _editing or _saving):
            st.session_state[_edit_key] = True
            st.rerun()
    with _ac3:
        if not is_default:
            if st.button("", icon=_TB_ICON_DEFAULT,
                         key=f"lib_script_vdefault_{story_id}_{_n}",
                         help=f"Make Version {_n} the default",
                         disabled=busy or _editing or _saving):
                try:
                    lib.set_default_script_version(story_id, _n)
                except Exception as e:
                    st.error(f"Could not make Version {_n} the default: {e}")
                else:
                    st.rerun()
    with _ac4:
        if _n != 1:
            if st.button("", icon=_TB_ICON_DELETE,
                         key=f"lib_script_vdel_{story_id}_{_n}",
                         help=f"Delete Version {_n}",
                         disabled=busy or _editing or _saving):
                st.session_state[_PENDING_DELETE_KEY] = {
                    "kind": "version",
                    "story_id": story_id,
                    "version": _n,
                    "title": f"Delete Version {_n}?",
                    "message": ("This can't be undone."
                                + (" It is the default — v1 will become the default."
                                   if is_default else "")),
                    "destructive_label": "Delete",
                }
                st.rerun()

    if _editing:
        st.text_area(f"Edit Version {_n}", value=version["text"],
                     key=_text_key, height=400,
                     label_visibility="collapsed", disabled=_saving)
        _vb1, _vb2, _vbs = st.columns([1, 1, 6])
        with _vb1:
            # HIG, phase 1: the initiating control owns the loading state.
            if st.button("Saving…" if _saving else "Save",
                         key=f"lib_script_vsave_{story_id}_{_n}", type="primary",
                         disabled=_saving or busy):
                st.session_state[_save_key] = True
                st.rerun()
        with _vb2:
            if st.button("Cancel", key=f"lib_script_vcancel_{story_id}_{_n}",
                         disabled=_saving):
                st.session_state.pop(_edit_key, None)
                st.rerun()
    else:
        _render_full_script(version["text"])


def _render_script_versions(story_id: str, busy: bool) -> None:
    """Full Script as a collapsible per-version list, latest on top (#104).

    Only the latest version starts expanded. The story's ``## Script``
    section always mirrors the default version, so Copy / Share / export
    keep working unchanged. A corrupt sidecar fails loudly with an error
    instead of a fabricated version list.
    """
    try:
        _versions, _default_n = lib.get_script_versions(story_id)
    except Exception as e:
        st.error(f"Could not load script versions: {e}")
        return
    if not _versions:
        st.caption("No script versions yet.")
        return
    _latest_n = _versions[0]["n"]

    _vh1, _vh2 = st.columns([11, 1], vertical_alignment="center")
    with _vh1:
        st.markdown('<div class="lib-section">Full Script</div>', unsafe_allow_html=True)
    with _vh2:
        if st.button("", icon=_TB_ICON_ADD, key=f"lib_script_newver_{story_id}",
                     help="Create new version", disabled=busy):
            try:
                _new_n = lib.create_script_version(story_id)
            except Exception as e:
                st.error(f"Could not create a new version: {e}")
            else:
                # Open the fresh version in edit mode — it starts as a
                # copy of the default text, ready to modify.
                st.session_state[f"lib_edit_script_v{_new_n}_{story_id}"] = True
                st.rerun()

    for _ver in _versions:
        _n = _ver["n"]
        _label = f"Version {_n}" + (" · Default" if _n == _default_n else "")
        with st.expander(_label, expanded=(_n == _latest_n)):
            _render_script_version_body(story_id, _ver, _n == _default_n, busy)


def _any_script_version_editing(story_id: str) -> bool:
    """True while any script version's manual editor is open (#104).

    Used by #105's fine-tune guard: there must be a stable baseline to
    refine, so fine-tuning hides while a version is being edited.
    """
    try:
        _keys = list(st.session_state.keys())
    except Exception:
        return False
    _suffix = f"_{story_id}"
    return any(
        k.startswith("lib_edit_script_v") and k.endswith(_suffix)
        and st.session_state.get(k)
        for k in _keys
    )


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
    # icon-only, drawn from Streamlit's native material icons (#111);
    # the title carries its own quiet borderless edit icon hugging the
    # left-aligned title text (#120).
    #
    # #53 HIG progress: a refresh button NEVER changes its text label
    # (always empty). While its kind runs the button shows Streamlit's
    # native spinner icon (``icon="spinner"``, #111) and stays disabled.
    # Tooltips keep the "Update Hashtags" / "Update Images" / "Update News"
    # labels (#71, #80). Stable width comes
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
            trigger_label="",
            trigger_icon=_TB_ICON_DELETE,
            popover_key=f"lib_delpop_{story_id}",
            title=f'Delete "{_story_title}"?',
            message="This can't be undone.",
            on_yes=lambda: _confirm_delete_story(story_id),
            trigger_help="Delete this story",
            destructive_label="Delete story",
            use_container_width=True,
            _pending_delete_kind="story",
            _pending_delete_story_id=story_id,
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
            _render_share_popover(story_id, _share_text, meta)
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
            # Icon-only like #71 (native material icon + tooltip); the
            # #53/#54 contract is identical to the hashtag/image buttons —
            # empty text label, native spinner icon while running,
            # disables only while its own kind runs, concurrent with
            # hashtags/images.
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
            _render_share_popover(story_id, _share_text, meta)
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

    # Title at top: big, multiline, LEFT-aligned (#120 — was centered),
    # with a quiet borderless edit icon hugging the title row so it
    # reads as part of the title, not a bolted-on boxed widget.
    # While editing, a borderless editor takes its place (Save/Cancel live
    # in the toolbar above). #84 reverts #60: the full title text is back
    # as an h2 — the #79 `.lib-doc-title a { display:none }` guard keeps
    # Streamlit's heading-anchor 🔗 icon off it. The edit flow and the
    # delete popover's meta.get("title") naming (#58) are untouched; no
    # recency caption is emitted ("Edited … ago" stays removed).
    title = meta.get("title", "Untitled Story") or "Untitled Story"
    # #154: the title row is the reusable _render_title_row component —
    # it owns its own alignment, so layout fixes land there, not here.
    _render_title_row(story_id, title, _editing, _busy)
    # Hashtags: ONE horizontal scroll row. Every tag is a chip with a ×
    # that removes exactly that tag (fail loudly, rerun after).
    # #107: the "Hashtags" title and the chips share ONE row — the title
    # rides in the first column so it always sits on the same line as
    # the chips. Chip rendering (weights, × overlay, clearance) is
    # untouched.
    tags = [t for t in (meta.get("hashtags") or []) if t]
    if tags:
        # #154: the whole row is the reusable _render_hashtags_row
        # component — it owns its own alignment, so layout fixes land
        # there, not here.
        _render_hashtags_row(story_id, tags)

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
        # #154: the cards row is the reusable _render_images_row component —
        # it owns its own alignment, so layout fixes land there, not here.
        _render_images_row(story_id, img_urls, uploaded, _busy_kinds)
    elif not (_busy_kinds & {"images", "more_images", "reset", "enrich"}):
        # #54: only kinds that (re-)fetch images suppress the hint — a
        # concurrent hashtag run leaves it visible.
        st.caption("No images yet — try Reset or upload manually below.")

    # News links: ONE horizontal scroll row. Each verified link is a chip
    # (title + source, opens the article) with a × that removes it.
    # Update Hashtags/Images never touch these — individual removal is
    # manual only (×). Reset re-runs the link verifier fresh for the topic.
    # #156: the whole row is the reusable _render_news_links_row component —
    # it owns its own alignment, so layout fixes land there, not here.
    links = [lk for lk in (meta.get("news_links") or []) if isinstance(lk, dict)]
    if links:
        _render_news_links_row(story_id, links, _busy_kinds)
    elif not (_busy_kinds & {"news", "more_news", "reset", "enrich"}):
        # #54/#80: only kinds that re-fetch links suppress the hint.
        st.caption("No news links yet.")

    # Whole script — versioned (#104): collapsible per-version list, latest
    # on top, latest expanded. The story's ## Script section always mirrors
    # the default version, so Copy / Share / export keep using it unchanged.
    _render_script_versions(story_id, _busy)
    if not story["script"].strip() and story["dialogue"].strip():
        # Old-format files (saved before the blockquote change): two-box rendering.
        st.markdown(f'<div class="lib-dialogue">{_md_to_html(story["dialogue"])}</div>',
                    unsafe_allow_html=True)

    # #105: iterative LLM fine-tuning of the script. Only when a script
    # exists (and not while a version's manual editor is open) — there must
    # be a stable baseline to refine. The refined script replaces the
    # default version's text (#104); the turn history preserves every turn.
    if script_md.strip() and not _any_script_version_editing(story_id):
        _render_fine_tune_section(story_id, meta, script_md, _busy)

    # Video playback — the attached video only. #94: the "Video" section
    # title is gone; the upload affordance is the one-line row below.
    video_file = meta.get("video_file", "")
    vpath = lib.media_path(story_id, video_file) if video_file else None
    if vpath:
        st.video(str(vpath))
    # #94: one-line upload row — "Upload" title on the left, upload
    # button on the right. Clicking the button opens a popover offering
    # a Video / Image selection; the chosen uploader then runs the
    # upload + processing flow (same widget keys, same
    # store_video_upload / store_image_upload paths, same success/error
    # handling, popover body in _render_upload_popover). Uploads stay
    # exempt from the #83 image cap and are never auto-removed.
    # #145: the uploader is reset after every upload so the same file is
    # never stored twice (widget values persist across reruns).
    # #114: the trigger is icon-only (native material upload glyph, no
    # "⬆" text/emoji) with a visible theme-safe border (see CSS marker
    # rule below); the popover body carries the upload affordance
    # (Video/Image radio + file uploader). Title and button share one
    # line, vertically centered.
    # #154: the whole row is the reusable _render_upload_row component —
    # it owns its own alignment, so layout fixes land there, not here.
    _render_upload_row(story_id)

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
