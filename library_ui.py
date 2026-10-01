"""Library tab UI (v1.5): macOS-style tab bar + master-detail story browser.

The existing Studio flow is never re-indented or altered: when the Library
tab is selected this module renders the library page and the caller stops
the script (st.stop()) before any Studio code runs.
"""

from __future__ import annotations

import html as _html
import re as _re
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
        display: inline-block;
        background: var(--lib-chip-bg);
        color: var(--lib-chip-text);
        border-radius: 999px;
        padding: 3px 12px;
        margin: 2px 4px 2px 0;
        font-size: 13px;
        font-weight: 600;
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
        margin: 22px 0 8px 0;
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
    lib.start_enrichment(story_id, topic)


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
        lib.start_enrichment(story_id, topic)
        st.success("Saved to Library.")
        st.rerun()


# ---------------------------------------------------------------------------
# Library page: master-detail
# ---------------------------------------------------------------------------

def render_library_page() -> None:
    # macOS HIG: the tab bar already identifies this view — no redundant
    # large title repeating "Library". Deference: content first.
    _inject_story_list_css()
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
        # Delete-all lives in the master section (two-step confirm).
        st.markdown("")
        if not st.session_state.get("lib_confirm_delete_all"):
            if _danger_button("Delete All", key="lib_delete_all_btn", use_container_width=True,
                              help="Delete every saved story"):
                st.session_state["lib_confirm_delete_all"] = True
                st.rerun()
        else:
            if _danger_button("Confirm Delete", key="lib_delete_all_confirm",
                              use_container_width=True, help="Confirm: delete every saved story"):
                n = lib.delete_all_stories()
                st.session_state.pop("lib_confirm_delete_all", None)
                st.session_state.pop("lib_selected_story", None)
                st.session_state.pop("lib_story_radio", None)
                st.success(f"Deleted {n} stor{'y' if n == 1 else 'ies'}.")
                st.rerun()
            if st.button("Cancel", key="lib_delete_all_cancel", use_container_width=True):
                st.session_state.pop("lib_confirm_delete_all", None)
                st.rerun()
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


def _copy_button(label: str, text: str, key: str) -> None:
    """One-click copy-to-clipboard button (clipboard API with execCommand fallback)."""
    import html as _html
    import json as _json
    import streamlit.components.v1 as components
    payload = _json.dumps(text)
    btn_id = f"libcp-{key}"
    components.html(
        f"""<button id="{btn_id}" style="width:100%;padding:7px 4px;border:1px solid rgba(0,0,0,0.12);
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
        height=50,
    )


def _render_story_detail(story_id: str) -> None:
    story = lib.load_story(story_id)
    if not story:
        st.error("Story not found — it may have been deleted.")
        st.session_state.pop("lib_selected_story", None)
        return
    meta = story["meta"]

    # Detail toolbar (macOS HIG): every primary action lives in ONE top
    # toolbar — Update Hashtags, Update Images, Retry Media — with Delete
    # trailing. The title carries its own inline ✏️ edit icon next to the
    # centered title text. Progress lives inside the initiating button
    # (in-button loader); there are no detached progress messages.
    # Refreshes run in daemon threads, so tab switches never interrupt them.
    _status = meta.get("enrichment_status")
    _refresh_kind = meta.get("refresh_kind", "") if _status in ("pending", "refreshing") else ""
    _busy = bool(_refresh_kind)
    _editing = bool(st.session_state.get(f"lib_edit_title_{story_id}"))
    _confirm_del = bool(st.session_state.get(f"lib_confirm_del_{story_id}"))
    _ai_engine = _library_ai_engine()

    def _kick_refresh(kind: str, label: str) -> None:
        if lib.start_refresh(story_id, kind, ai_engine=_ai_engine):
            st.rerun()
        else:
            st.error(f"Could not start the {label} refresh.")

    def _delete_first_step() -> None:
        if _danger_button("Delete", key=f"lib_del_{story_id}",
                          help="Delete this story"):
            st.session_state[f"lib_confirm_del_{story_id}"] = True
            st.rerun()

    if _confirm_del:
        # Focused delete confirmation: confirm + cancel, nothing else.
        dc1, dc2, _dsp = st.columns([1.8, 1.0, 7.2])
        with dc1:
            if _danger_button("Confirm Delete", key=f"lib_del_confirm_{story_id}",
                              help="Confirm: delete this story"):
                lib.delete_story(story_id)
                st.session_state.pop(f"lib_confirm_del_{story_id}", None)
                st.session_state.pop("lib_selected_story", None)
                st.session_state.pop("lib_story_radio", None)
                st.success("Story deleted.")
                st.rerun()
        with dc2:
            if st.button("Cancel", key=f"lib_del_cancel_{story_id}"):
                st.session_state.pop(f"lib_confirm_del_{story_id}", None)
                st.rerun()
    elif _editing:
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
            _delete_first_step()
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
            _loading = _refresh_kind == "all"
            if st.button("Retrying…" if _loading else "Retry Media",
                         key=f"lib_retry_{story_id}",
                         help="Re-run the hashtag + image fetch for this story",
                         disabled=_busy):
                if lib.retry_enrichment(story_id, ai_engine=_ai_engine):
                    st.rerun()
                else:
                    st.error("Could not start the retry.")
        with tc5:
            _delete_first_step()
    st.markdown('<div class="lib-hairline"></div>', unsafe_allow_html=True)

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

    # Whole script — always through the color-coded renderer so dialogue
    # never falls back to plain markdown.
    script_md = story["script"].strip()
    if script_md:
        st.markdown('<div class="lib-section">Full Script</div>', unsafe_allow_html=True)
        _render_full_script(script_md)
    elif story["dialogue"].strip():
        # Old-format files (saved before the blockquote change): two-box rendering.
        st.markdown(f'<div class="lib-dialogue">{_md_to_html(story["dialogue"])}</div>',
                    unsafe_allow_html=True)

    # Hashtags sit below the story (macOS HIG: centered, quiet chips).
    tags = meta.get("hashtags") or []
    if tags:
        st.markdown('<div class="lib-section">Hashtags</div>', unsafe_allow_html=True)
        st.markdown('<div style="text-align:center">' +
                    "".join(f'<span class="lib-chip">{t}</span>' for t in tags) +
                    '</div>', unsafe_allow_html=True)

    # Copy options: the full final-stage script, pure — nothing added.
    if script_md:
        st.markdown('<div class="lib-section">Copy</div>', unsafe_allow_html=True)
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            _copy_button("Script", _script_plain_text(script_md), f"s-{story_id}")
        with cc2:
            _copy_button("Script + Media", _compose_share_text(meta, script_md, True, False), f"m-{story_id}")
        with cc3:
            _copy_button("Script + Tags", _compose_share_text(meta, script_md, False, True), f"h-{story_id}")
        with cc4:
            _copy_button("All", _compose_share_text(meta, script_md, True, True), f"a-{story_id}")

    # Images + news links at the bottom
    st.markdown('<div class="lib-section">Media &amp; Links</div>', unsafe_allow_html=True)
    img_urls = meta.get("image_urls") or []
    uploaded = meta.get("uploaded_images") or []
    if img_urls:
        st.caption("Auto-fetched from news — remove any to overwrite, edit an address, or upload your own below.")
        for i, url in enumerate(img_urls):
            edit_key = f"lib_editimg_{story_id}_{i}"
            if st.session_state.get(edit_key):
                st.text_input("Image address", value=url,
                              key=f"lib_edimg_url_{story_id}_{i}")
                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("Save", key=f"lib_edimg_save_{story_id}_{i}"):
                        try:
                            new_url = st.session_state.get(
                                f"lib_edimg_url_{story_id}_{i}", "")
                            lib.update_fetched_image_url(story_id, i, new_url)
                        except ValueError as e:
                            st.error(str(e))
                        else:
                            st.session_state.pop(edit_key, None)
                            st.rerun()
                with ec2:
                    if st.button("Cancel", key=f"lib_edimg_cancel_{story_id}_{i}"):
                        st.session_state.pop(edit_key, None)
                        st.rerun()
                continue
            ic1, ic2 = st.columns([5, 1])
            with ic1:
                st.image(url, width=220)
            with ic2:
                if st.button("Edit", key=f"lib_edimg_{story_id}_{i}",
                             help="Edit this image's address"):
                    st.session_state[edit_key] = True
                    st.rerun()
                if st.button("✕", key=f"lib_rmimg_{story_id}_{i}",
                             help="Remove this fetched image"):
                    lib.remove_fetched_image(story_id, url)
                    st.rerun()
    for i, f in enumerate(uploaded):
        p = lib.media_path(story_id, f)
        if not p:
            continue
        uc1, uc2 = st.columns([5, 1])
        with uc1:
            st.image(str(p), width=220)
        with uc2:
            if st.button("✕", key=f"lib_rmup_{story_id}_{i}",
                         help="Remove this uploaded image"):
                lib.remove_uploaded_image(story_id, f)
                st.rerun()
    if not img_urls and not uploaded and meta.get("enrichment_status") != "pending":
        st.caption("No images yet — try ↻ Retry or upload manually below.")
    links = meta.get("news_links") or []
    if links:
        for lk in links:
            title = lk.get("title", "News link")
            url = lk.get("url", "")
            src = lk.get("source", "")
            label = f"{title} ({src})" if src else title
            st.markdown(f"[{label}]({url})" if url else label)
    elif meta.get("enrichment_status") != "pending":
        st.caption("No news links yet.")

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

    # (All primary actions — Edit, Update Hashtags, Update Images, Retry
    # Media, Delete — live in the detail toolbar at the top.)


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
