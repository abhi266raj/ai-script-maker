"""Library tab UI (v1.5): macOS-style tab bar + master-detail story browser.

The existing Studio flow is never re-indented or altered: when the Library
tab is selected this module renders the library page and the caller stops
the script (st.stop()) before any Studio code runs.
"""

from __future__ import annotations

import streamlit as st

import story_library as lib

TAB_STUDIO = "🎬 Studio"
TAB_LIBRARY = "📚 Library"


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
        --lib-dialogue-bg: #FFF8E7;
        --lib-dialogue-border: #E8B93C;
        --lib-dialogue-text: #5A3E00;
        --lib-script-bg: #EFF4FF;
        --lib-script-border: #6B8DD6;
        --lib-script-text: #1E3A6E;
        --lib-chip-bg: #F0E9DB;
        --lib-chip-text: #6B5433;
    }
    :root[data-theme="dark"],
    html[data-theme="dark"],
    body[data-theme="dark"],
    [data-theme="dark"] {
        --lib-seg-bg: #2E2620;
        --lib-seg-active-bg: #4A3F33;
        --lib-seg-active-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
        --lib-dialogue-bg: #3A2E14;
        --lib-dialogue-border: #C99A2E;
        --lib-dialogue-text: #F5DFA0;
        --lib-script-bg: #1E2A44;
        --lib-script-border: #5B7BC0;
        --lib-script-text: #C9D9F5;
        --lib-chip-bg: #3A3129;
        --lib-chip-text: #D8C49A;
    }
    /* macOS segmented tab bar — centers the control like a native tab strip */
    .lib-tabbar { display: flex; justify-content: center; margin: 6px 0 14px 0; }
    .lib-tabbar [data-testid="stSegmentedControl"] { width: auto; }
    .lib-tabbar [data-testid="stSegmentedControl"] > div {
        background: var(--lib-seg-bg) !important;
        border-radius: 12px !important;
        padding: 3px !important;
    }
    .lib-tabbar [data-testid="stSegmentedControl"] button[aria-pressed="true"] {
        background: var(--lib-seg-active-bg) !important;
        box-shadow: var(--lib-seg-active-shadow) !important;
        border-radius: 9px !important;
    }
    /* Fallback: horizontal radio styled as segmented control (scoped to tabbar) */
    .lib-tabbar [data-testid="stRadio"] > div[role="radiogroup"] {
        flex-direction: row !important;
        gap: 2px !important;
        background: var(--lib-seg-bg) !important;
        border-radius: 12px !important;
        padding: 3px !important;
    }
    .lib-tabbar [data-testid="stRadio"] label {
        border-radius: 9px !important;
        padding: 6px 18px !important;
        margin: 0 !important;
    }
    .lib-tabbar [data-testid="stRadio"] label:has(input:checked) {
        background: var(--lib-seg-active-bg) !important;
        box-shadow: var(--lib-seg-active-shadow) !important;
    }
    .lib-tabbar [data-testid="stRadio"] label > div:first-child { display: none !important; }
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
    .lib-story-card {
        border: 1px solid var(--lib-chip-bg);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 8px;
        cursor: pointer;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tab bar
# ---------------------------------------------------------------------------

def render_tab_bar() -> str:
    """Render the macOS-style tab bar. Returns 'studio' or 'library'."""
    inject_library_css()
    st.markdown('<div class="lib-tabbar">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)
    return "library" if choice == TAB_LIBRARY else "studio"


# ---------------------------------------------------------------------------
# Auto-save hook (called from the Studio final-output view)
# ---------------------------------------------------------------------------

def _dialogue_markdown(script) -> str:
    lines: list[str] = []
    if getattr(script, "hook_hindi", ""):
        lines.append(f"**Hook:** {script.hook_hindi}")
    for sc in getattr(script, "scenes", []) or []:
        speaker = getattr(sc, "character", "") or f"Scene {getattr(sc, 'scene_number', '?')}"
        dialogue = (getattr(sc, "dialogue", "") or "").strip()
        if dialogue:
            lines.append(f"**{speaker}:** {dialogue}")
    if getattr(script, "call_to_action", ""):
        lines.append(f"**CTA:** {script.call_to_action}")
    return "\n\n".join(lines)


def _script_markdown(script) -> str:
    lines: list[str] = []
    if getattr(script, "narration_hindi", ""):
        lines.append(f"**Narration:** {script.narration_hindi}")
    for sc in getattr(script, "scenes", []) or []:
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
    return "\n\n".join(lines)


def maybe_autosave_story(batch_result, script) -> None:
    """Auto-save the finished story once (guarded against Streamlit reruns).

    On failure: surfaces the error with a manual "Save to library" fallback.
    """
    res_id = id(batch_result)
    script_id = getattr(script, "id", "?")
    sel_idx = st.session_state.get("selected_script_idx", 0)
    guard = f"{res_id}:{script_id}:{sel_idx}"
    if st.session_state.get("lib_autosaved_for") == guard:
        return
    if st.session_state.get("lib_save_failed_for") == guard:
        _render_manual_save_fallback(batch_result, script, guard)
        return
    try:
        story_id = _save_current_story(batch_result, script)
    except Exception as e:  # fail loudly, offer manual fallback
        st.session_state["lib_save_failed_for"] = guard
        st.error(f"Auto-save to library failed: {e}")
        _render_manual_save_fallback(batch_result, script, guard)
        return
    st.session_state["lib_autosaved_for"] = guard
    st.session_state.pop("lib_save_failed_for", None)
    topic = st.session_state.get("run_topic", "") or ""
    lib.start_enrichment(story_id, topic)
    st.toast("💾 Saved to Library — fetching images & news links…", icon="📚")


def _save_current_story(batch_result, script) -> str:
    hashtag = st.session_state.get("active_hashtag", "") or ""
    hashtags = [hashtag] if hashtag else []
    tone = st.session_state.get("chosen_tone", "") or ""
    topic = st.session_state.get("run_topic", "") or ""
    headline = st.session_state.get("selected_headline_title", "") or ""
    return lib.save_story(
        title=getattr(script, "title", "") or topic or "Untitled Story",
        tone=tone,
        hashtags=hashtags,
        dialogue_md=_dialogue_markdown(script),
        script_md=_script_markdown(script),
        source_topic=topic,
        source_headline=headline,
    )


def _render_manual_save_fallback(batch_result, script, guard: str) -> None:
    if st.button("💾 Save to library", key="lib_manual_save_btn", type="primary"):
        try:
            story_id = _save_current_story(batch_result, script)
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
    st.markdown("## 📚 Story Library")
    stories = lib.list_stories()
    selected = st.session_state.get("lib_selected_story")

    # Delete-all (two-step confirm), only when there are stories.
    if stories:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.caption(f"{len(stories)} saved stor{'y' if len(stories) == 1 else 'ies'} · stored in ~/Documents/HindiReelStudio")
        with c2:
            if not st.session_state.get("lib_confirm_delete_all"):
                if st.button("🗑️ Delete all", key="lib_delete_all_btn"):
                    st.session_state["lib_confirm_delete_all"] = True
                    st.rerun()
            else:
                if st.button("⚠️ Confirm delete ALL?", key="lib_delete_all_confirm", type="primary"):
                    n = lib.delete_all_stories()
                    st.session_state.pop("lib_confirm_delete_all", None)
                    st.session_state.pop("lib_selected_story", None)
                    st.success(f"Deleted {n} stor{'y' if n == 1 else 'ies'}.")
                    st.rerun()
                if st.button("Cancel", key="lib_delete_all_cancel"):
                    st.session_state.pop("lib_confirm_delete_all", None)
                    st.rerun()

    if not stories:
        st.info("No saved stories yet. Generate a reel in the Studio tab — it auto-saves here on completion.")
        return

    master, detail = st.columns([2, 3])
    with master:
        st.markdown("### Stories")
        for s in stories:
            sid = s.get("id", "")
            title = s.get("title", "Untitled")
            created = (s.get("created_at", "") or "")[:10]
            tags = " ".join(f"`{t}`" for t in (s.get("hashtags") or [])[:3])
            status = s.get("enrichment_status", "")
            badge = " ⏳" if status == "pending" else ""
            label = f"📄 {title}{badge}\n\n{created} {tags}"
            if st.button(label, key=f"lib_story_{sid}", use_container_width=True):
                st.session_state["lib_selected_story"] = sid
                st.rerun()
    with detail:
        if not selected or not any(s.get("id") == selected for s in stories):
            st.info("👈 Select a story to view it.")
            return
        _render_story_detail(selected)


def _render_story_detail(story_id: str) -> None:
    story = lib.load_story(story_id)
    if not story:
        st.error("Story not found — it may have been deleted.")
        st.session_state.pop("lib_selected_story", None)
        return
    meta = story["meta"]

    # Title at top
    st.markdown(f"# {meta.get('title', 'Untitled Story')}")
    created = (meta.get("created_at", "") or "").replace("T", " ")
    st.caption(f"Created {created}" + (f" · Tone: {meta.get('tone')}" if meta.get("tone") else ""))

    # Hashtags
    tags = meta.get("hashtags") or []
    if tags:
        st.markdown("".join(f'<span class="lib-chip">{t}</span>' for t in tags), unsafe_allow_html=True)

    # Enrichment pending state
    if meta.get("enrichment_status") == "pending":
        st.info("⏳ Fetching images & news links in the background…")

    # Dialogue (color 1) vs Script (color 2)
    if story["dialogue"].strip():
        st.markdown("### 🗣️ Dialogue")
        st.markdown(f'<div class="lib-dialogue">{_md_to_html(story["dialogue"])}</div>', unsafe_allow_html=True)
    if story["script"].strip():
        st.markdown("### 🎬 Script / Scenes")
        st.markdown(f'<div class="lib-script">{_md_to_html(story["script"])}</div>', unsafe_allow_html=True)

    # Images + news links at the bottom
    st.markdown("### 🖼️ Media & Links")
    img_urls = meta.get("image_urls") or []
    uploaded = meta.get("uploaded_images") or []
    local_imgs = [lib.media_path(story_id, f) for f in uploaded]
    local_imgs = [p for p in local_imgs if p]
    if img_urls:
        st.image(img_urls, width=220)
    for p in local_imgs:
        st.image(str(p), width=220)
    if not img_urls and not local_imgs and meta.get("enrichment_status") != "pending":
        st.caption("No images yet.")
    links = meta.get("news_links") or []
    if links:
        for lk in links:
            title = lk.get("title", "News link")
            url = lk.get("url", "")
            src = lk.get("source", "")
            label = f"{title} ({src})" if src else title
            st.markdown(f"🔗 [{label}]({url})" if url else f"🔗 {label}")
    elif meta.get("enrichment_status") != "pending":
        st.caption("No news links yet.")

    # Video upload + playback
    st.markdown("### 🎥 Video")
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

    # Retry enrichment + delete
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("↻ Retry media fetch", key=f"lib_retry_{story_id}",
                     help="Re-run the hashtag + image fetch for this story"):
            if lib.retry_enrichment(story_id):
                st.toast("Retrying media fetch…")
                st.rerun()
            else:
                st.error("Could not start the retry.")
    with b2:
        if not st.session_state.get(f"lib_confirm_del_{story_id}"):
            if st.button("🗑️ Delete story", key=f"lib_del_{story_id}"):
                st.session_state[f"lib_confirm_del_{story_id}"] = True
                st.rerun()
        else:
            if st.button("⚠️ Confirm delete?", key=f"lib_del_confirm_{story_id}", type="primary"):
                lib.delete_story(story_id)
                st.session_state.pop(f"lib_confirm_del_{story_id}", None)
                st.session_state.pop("lib_selected_story", None)
                st.success("Story deleted.")
                st.rerun()
    with b3:
        if st.button("← Back to list", key=f"lib_back_{story_id}"):
            st.session_state.pop("lib_selected_story", None)
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
