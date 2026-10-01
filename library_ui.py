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
        --lib-chip-bg: #F0E9DB;
        --lib-chip-text: #6B5433;
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
        --lib-chip-bg: #3A3129;
        --lib-chip-text: #D8C49A;
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
        min-height: var(--lib-chip-h);
        background: var(--lib-chip-bg);
        color: var(--lib-chip-text);
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
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
        position: relative !important;
    }
    /* Chips inside scroll rows: single line, never clipped by the ×.
       #25/#26: the × clearance lives in the CHIP COLUMN's own padding
       (rule below), not in the chip — the × overlay (22px at right:4px
       of the column) floats in padding space, 4px clear of the chip
       edge, so tag text can never slide underneath it regardless of
       chip width. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        [data-testid="stHorizontalBlock"] .lib-chip {
        padding-right: 12px !important;
        white-space: nowrap !important;
        max-width: 340px;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* #25/#26: chip columns reserve the × clearance in the column's own
       padding. Scoped to columns holding a chip (:has(.lib-chip)) —
       image cards keep their inset × over the image corner. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
        div[data-testid="stColumn"]:has(.lib-chip) {
        padding-right: 30px !important;
    }
    /* Links inside news chips inherit the themed chip color (theme-safe). */
    div[data-testid="stElementContainer"]:has([data-marker="lib-hscroll"])
        [data-testid="stHorizontalBlock"] .lib-chip a {
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
    /* Detail action buttons (Share/Copy) share the same system: one
       button height (--lib-act-h), one gap, top-aligned in their columns.
       Marker-scoped: a hidden [data-marker="lib-actions"] div sits
       directly before the actions st.columns() call. The copy buttons
       render inside an iframe (components.html) and get their height from
       _LIB_ACTION_BTN_H_PX in Python — same value, same system. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-actions"])
        + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] {
        gap: var(--lib-chip-gap) !important;
        align-items: start !important;
    }
    /* v1.5.4: the sibling after the marker is stLayoutWrapper (not
       stElementContainer), and the anchor is nested inside the link
       button (descendant, not direct child) — with the real selectors the
       WhatsApp link button shares the 38px action height with the copy
       buttons. */
    div[data-testid="stElementContainer"]:has([data-marker="lib-actions"])
        + div[data-testid="stLayoutWrapper"] [data-testid="stLinkButton"] a {
        min-height: var(--lib-act-h) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    /* macOS HIG: deference — toolbar rows use a hairline, not a heavy box */
    .lib-hairline {
        border-bottom: 1px solid rgba(128, 128, 128, 0.25);
        margin: 4px 0 12px 0;
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
    /* macOS HIG: document title centered, empty states centered */
    .lib-doc-title {
        text-align: center;
        font-size: 30px;
        font-weight: 700;
        line-height: 1.25;
        margin: 6px 0 2px 0;
        overflow-wrap: anywhere;
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
       pushing the "Reset"/"Delete" popover triggers (and the red "Yes"
       inside the popover) one gap lower than their plain-button siblings.
       Collapse the wrapper: CSS `+` sibling combinators and :has() match
       on DOM order regardless of display, so the red-trigger/red-button
       rules below keep matching. Prefix-scoped: lib-x-/lib-actions/
       lib-hscroll/lib-story-list markers are untouched. */
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"]) {
        display: none !important;
    }
    /* Destructive actions: macOS system red text (graceful — plain button if unmatched) */
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button {
        color: #FF3B30 !important;
        border-color: rgba(255, 59, 48, 0.35) !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-"])
        + div[data-testid="stElementContainer"] [data-testid="stButton"] button:hover {
        color: #FF3B30 !important;
        border-color: rgba(255, 59, 48, 0.6) !important;
    }
    /* Destructive popover trigger: same macOS system red on the native
       popover button (graceful — plain button if the selector ever misses).
       #FF3B30 reads on both light and dark themes; no theme overrides. */
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-pop-"])
        + div[data-testid="stElementContainer"] [data-testid="stPopover"] [data-testid="stPopoverButton"] {
        color: #FF3B30 !important;
        border-color: rgba(255, 59, 48, 0.35) !important;
    }
    div[data-testid="stElementContainer"]:has([data-marker^="lib-danger-pop-"])
        + div[data-testid="stElementContainer"] [data-testid="stPopover"] [data-testid="stPopoverButton"]:hover {
        color: #FF3B30 !important;
        border-color: rgba(255, 59, 48, 0.6) !important;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def _danger_button(label: str, key: str, **kwargs) -> bool:
    """Mac-style destructive button: red text via a marker-scoped rule.

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
                     disabled: bool = False) -> None:
    """Apple-style confirmation: native popover, red Yes, normal No.

    The trigger is a red destructive button (marker-scoped CSS, graceful if
    the selector misses). Inside the popover: a bold title, a secondary
    message line, then "Yes" (red, destructive) and "No" (standard) side by
    side.

    "Yes" arms a ``<key>-go`` flag via an ``on_click`` callback and closes
    the popover; the flag is consumed at the top of the next script run —
    *before* the popover widget instantiates, which is the only moment its
    key may be driven programmatically (doing it after raises
    ``StreamlitWidgetAlreadyInstantiatedError``). ``on_yes`` must raise on
    failure: the error is shown loudly inside the reopened popover and the
    popover stays open. "No" only closes the popover. The native popover
    follows the light/dark theme; the only custom color is macOS system red,
    which reads on both themes.

    ``fail_label`` prefixes the loud error (e.g. "Delete", "Reset").
    ``disabled`` disables the trigger (e.g. while its work is running) —
    the trigger label can then carry the loading state ("Resetting…").
    """
    _go_key = f"{popover_key}-go"
    _err_key = f"{popover_key}-err"
    # Marker first: it must sit directly before the popover's element
    # container for the red-trigger CSS sibling selector to hit.
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
    with st.popover(trigger_label, key=popover_key, on_change="rerun",
                    help=trigger_help or None,
                    use_container_width=use_container_width,
                    disabled=disabled):
        _failure = st.session_state.pop(_err_key, None)
        if _failure:
            st.error(f"{fail_label} failed: {_failure}")
        st.markdown(f"**{title}**")
        st.caption(message)
        _by, _bn = st.columns(2)
        with _by:
            _danger_button(
                "Yes", key=f"{popover_key}-yes", use_container_width=True,
                on_click=lambda: st.session_state.update(
                    {popover_key: False, _go_key: True}),
            )
        with _bn:
            st.button(
                "No", key=f"{popover_key}-no", use_container_width=True,
                on_click=lambda: st.session_state.update({popover_key: False}),
            )


def _delete_popover(*, trigger_label: str, popover_key: str, title: str,
                    message: str, on_yes: Callable[[], None],
                    trigger_help: str = "",
                    use_container_width: bool = False) -> None:
    """Apple-style delete confirmation: native popover, red Yes, normal No.

    Thin wrapper over :func:`_confirm_popover` with the failure label set
    to "Delete" (kept for the existing delete flows and their tests).
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
    )


def _render_reset_popover(story_id: str, busy: bool, refresh_kind: str,
                          ai_engine) -> None:
    """Toolbar Reset: destructive confirm popover (red Yes / normal No).

    The trigger owns its loading state ("Resetting…") and stays disabled
    while any refresh is busy. Confirming kicks a "reset" refresh —
    hashtags, fetched images and news links are discarded and re-fetched
    fresh (uploads and the screenplay are never touched).
    """
    resetting = refresh_kind == "reset"

    def _on_reset_yes() -> None:
        # Raises loudly on failure: the popover shows it and stays open.
        # No st.rerun() here — the Yes click already reruns via the
        # popover's on_change, and the busy state + auto-poll take over.
        ok, reason = lib.start_refresh(story_id, "reset", ai_engine=ai_engine)
        if not ok:
            raise RuntimeError(
                f"Could not start the reset: {reason}" if reason
                else "Could not start the reset.")

    _confirm_popover(
        trigger_label="Resetting…" if resetting else "Reset",
        popover_key=f"lib_resetpop_{story_id}",
        title="Reset media rows?",
        message=("Clears all hashtags, fetched images and news links, "
                 "then re-fetches them fresh. Uploads and the screenplay "
                 "are never touched."),
        on_yes=_on_reset_yes,
        trigger_help="Clear and re-fetch hashtags, images and news links",
        fail_label="Reset",
        disabled=busy,
    )
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


def render_tab_bar() -> str:
    """Render the macOS-style tab bar. Returns 'studio' or 'library'."""
    inject_library_css()
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


def _compose_news_tags_text(meta: dict) -> str:
    """Share text: verified news link(s), one per line, then hashtags space-separated.

    Formatted for pasting straight into a social-media post — links first,
    hashtags after. Returns "" when the story has neither news links nor
    hashtags, so the caller can say so plainly instead of copying nothing.
    """
    links = [
        (lk.get("url") or "").strip()
        for lk in (meta.get("news_links") or [])
        if isinstance(lk, dict)
    ]
    links = [u for u in dict.fromkeys(links) if u]
    tags = [t for t in (meta.get("hashtags") or []) if t]
    parts = []
    if links:
        parts.append("\n".join(links))
    if tags:
        parts.append(" ".join(tags))
    return "\n\n".join(parts)


def _whatsapp_share_url(text: str) -> str:
    """wa.me share link carrying the EXACT share text (URL-encoded for
    transport only — the text itself is never reformatted). Opens
    WhatsApp with the text prefilled; no connection or connector needed.
    """
    import urllib.parse as _up
    return "https://wa.me/?text=" + _up.quote(text, safe="")


def _render_share_column(story_id: str, share_text: str) -> None:
    """Share column: "Copy News Link + Hashtags" and "Send via WhatsApp"
    side by side, then the share-text preview.

    The WhatsApp button is a native ``st.link_button`` (theme-safe) to a
    wa.me deep link carrying the EXACT share text — no reformatting, no
    WhatsApp connection needed.
    """
    st.markdown('<div class="lib-quiet" style="text-align:left;margin:0 0 4px 0">Share</div>',
                unsafe_allow_html=True)
    if share_text:
        _sh1, _sh2 = st.columns(2)
        with _sh1:
            _copy_button("Copy News Link + Hashtags", share_text, f"n-{story_id}")
        with _sh2:
            st.link_button(
                "Send via WhatsApp",
                _whatsapp_share_url(share_text),
                help="Open WhatsApp with this text prefilled",
                use_container_width=True,
            )
        st.code(share_text)
    else:
        st.caption("No news links or hashtags to share yet.")


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


def _render_story_detail(story_id: str) -> None:
    story = lib.load_story(story_id)
    if not story:
        st.error("Story not found — it may have been deleted.")
        st.session_state.pop("lib_selected_story", None)
        return
    meta = story["meta"]

    # Detail toolbar (macOS HIG): every primary action lives in ONE top
    # toolbar — Update Hashtags, Update Images, Reset — with Delete
    # trailing. The title carries its own inline ✏️ edit icon next to the
    # centered title text. Progress lives inside the initiating button
    # (in-button loader); there are no detached progress messages.
    # Refreshes run in daemon threads, so tab switches never interrupt them.
    _status = meta.get("enrichment_status")
    _refresh_kind = meta.get("refresh_kind", "") if _status in lib.BUSY_STATES else ""
    _busy = bool(_refresh_kind)
    _editing = bool(st.session_state.get(f"lib_edit_title_{story_id}"))
    _ai_engine = _library_ai_engine()

    def _kick_refresh(kind: str, label: str) -> None:
        ok, reason = lib.start_refresh(story_id, kind, ai_engine=_ai_engine)
        if ok:
            st.rerun()
        else:
            st.error(f"Could not start the {label} refresh: {reason}" if reason
                     else f"Could not start the {label} refresh.")

    def _story_delete_popover() -> None:
        _delete_popover(
            trigger_label="Delete",
            popover_key=f"lib_delpop_{story_id}",
            title="Delete this story?",
            message="This can't be undone.",
            on_yes=lambda: _confirm_delete_story(story_id),
            trigger_help="Delete this story",
        )

    if _editing:
        # Title edit mode: Save/Cancel lead, Delete stays trailing.
        ec1, ec2, _esp, ec3 = st.columns([1.0, 1.0, 7.0, 1.0])
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
            _story_delete_popover()
    else:
        tc2, tc3, tc4, _tsp, tc5 = st.columns([1.7, 1.6, 1.3, 4.4, 1.0])
        with tc2:
            _loading = _refresh_kind == "hashtags"
            if st.button("Updating Hashtags…" if _loading else "Update Hashtags",
                         key=f"lib_tags_{story_id}",
                         help="Find hashtags for this story's topic and add them",
                         disabled=_busy):
                _kick_refresh("hashtags", "hashtag")
        with tc3:
            _loading = _refresh_kind == "images"
            if st.button("Updating Images…" if _loading else "Update Images",
                         key=f"lib_imgs_{story_id}",
                         help="Re-fetch news images for this story's topic",
                         disabled=_busy):
                _kick_refresh("images", "image")
        with tc4:
            # Reset is destructive: it confirms via the same native popover
            # pattern as Delete (red Yes / normal No). The trigger owns its
            # loading state ("Resetting…") and stays disabled while busy.
            _render_reset_popover(story_id, _busy, _refresh_kind, _ai_engine)
        with tc5:
            _story_delete_popover()
    st.markdown('<div class="lib-hairline"></div>', unsafe_allow_html=True)
    script_md = story["script"].strip()

    # Actions at top (compact): Share + Copy live here so the user can grab
    # anything without scrolling past the script. Copied texts are identical
    # to before — only the position changed.
    st.markdown('<div class="lib-section">Actions</div>', unsafe_allow_html=True)
    _share_text = _compose_news_tags_text(meta)
    st.markdown('<div data-marker="lib-actions" style="display:none"></div>',
                unsafe_allow_html=True)
    _aa1, _aa2 = st.columns([3, 2])
    with _aa1:
        _render_share_column(story_id, _share_text)
    with _aa2:
        st.markdown('<div class="lib-quiet" style="text-align:left;margin:0 0 4px 0">Copy</div>',
                    unsafe_allow_html=True)
        if script_md:
            _ac1, _ac2 = st.columns(2)
            with _ac1:
                _copy_button("Script", _script_plain_text(script_md), f"s-{story_id}")
                _copy_button("Script + Tags",
                             _compose_share_text(meta, script_md, False, True),
                             f"h-{story_id}")
            with _ac2:
                _copy_button("Script + Media",
                             _compose_share_text(meta, script_md, True, False),
                             f"m-{story_id}")
                _copy_button("All", _compose_share_text(meta, script_md, True, True),
                             f"a-{story_id}")
        else:
            st.caption("No script to copy yet.")

    # Title at top: big, multiline, centered, with a small inline edit icon.
    # While editing, a borderless editor takes its place (Save/Cancel live
    # in the toolbar above).
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
    created = (meta.get("created_at", "") or "").replace("T", " ")
    _sub = f"Created {created}" + (f" · Tone: {meta.get('tone')}" if meta.get("tone") else "")
    st.markdown(f"<div style='text-align:center' class='stCaption'>{_html.escape(_sub)}</div>",
                unsafe_allow_html=True)

    # Refresh outcome — quiet inline status, never a loud banner and never a
    # detached progress message (progress lives in the toolbar button itself).
    _note = (meta.get("refresh_note") or "").strip()
    if _note:
        st.caption(f"Last refresh: {_note}")

    # Hashtags: ONE horizontal scroll row. Every tag is a chip with a ×
    # that removes exactly that tag (fail loudly, rerun after).
    tags = [t for t in (meta.get("hashtags") or []) if t]
    if tags:
        st.markdown('<div class="lib-section">Hashtags</div>', unsafe_allow_html=True)
        st.markdown('<div data-marker="lib-hscroll" style="display:none"></div>',
                    unsafe_allow_html=True)
        _tcols = st.columns(len(tags))
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
    elif meta.get("enrichment_status") not in lib.BUSY_STATES:
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
        _lcols = st.columns(len(links))
        for _i, (_lc, _lk) in enumerate(zip(_lcols, links)):
            _ltitle = _lk.get("title", "News link") or "News link"
            _lsrc = _lk.get("source", "") or ""
            _lurl = (_lk.get("url") or "").strip()
            _label = _news_chip_label(_ltitle, _lsrc)
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
    elif meta.get("enrichment_status") not in lib.BUSY_STATES:
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
    # page settles to the idle buttons plus the honest result note. Fully
    # automatic — no "click to check status" hunting. The loop always
    # terminates: workers always write a terminal state, and startup
    # recovery clears anything a dead process left behind.
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
