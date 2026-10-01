"""Library tab UI (v1.5): macOS-style tab bar + master-detail story browser.

The existing Studio flow is never re-indented or altered: when the Library
tab is selected this module renders the library page and the caller stops
the script (st.stop()) before any Studio code runs.
"""

from __future__ import annotations

import streamlit as st

import story_library as lib
from core.screenplay_formatter import format_industry_screenplay

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


def _verified_news_links(batch_result) -> list:
    """Stage-1 verified sources — the exact articles the story was built from.

    Saved as the story's news links so they always point at the same story;
    the background enrichment keeps them and never overwrites them.
    """
    links: list = []
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


def _full_script_markdown(script) -> str:
    """The complete final-stage screenplay, via the app's own formatter.

    This is the same clean plain screenplay the Studio offers for
    copy-pasting — [Format Requirement] header, SCENE DETAIL, CHARACTERS &
    CLOTHING, all beats. Nothing is added or dropped by the library.
    Falls back to the field-by-field reconstruction only if the industry
    formatter refuses (its fail-loud contract); the save itself must not
    break.
    """
    try:
        # Mirrors app.format_plain_script: the clean plain screenplay ready
        # for copy-pasting (imported from core to avoid an app↔library cycle).
        return format_industry_screenplay(
            script, include_overlays=True, include_sfx=True).strip()
    except Exception:
        return _script_markdown(script)


def _save_current_story(batch_result, script) -> str:
    hashtag = st.session_state.get("active_hashtag", "") or ""
    hashtags = [hashtag] if hashtag else []
    tone = st.session_state.get("chosen_tone", "") or ""
    topic = st.session_state.get("run_topic", "") or ""
    headline = st.session_state.get("selected_headline_title", "") or ""
    # The story title is the news headline it was built from.
    title = headline or topic or getattr(script, "title", "") or "Untitled Story"
    return lib.save_story(
        title=title,
        tone=tone,
        hashtags=hashtags,
        dialogue_md="",
        script_md=_full_script_markdown(script),
        source_topic=topic,
        source_headline=headline,
        news_links=_verified_news_links(batch_result),
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

    master, detail = st.columns([1, 3])
    with master:
        st.caption(f"**Stories** · {len(stories)}")
        for s in stories:
            sid = s.get("id", "")
            title = (s.get("title", "Untitled") or "Untitled")[:42]
            created = (s.get("created_at", "") or "")[:10]
            badge = " ⏳" if s.get("enrichment_status") == "pending" else ""
            label = f"📄 {title}{badge}\n\n{created}"
            if st.button(label, key=f"lib_story_{sid}", use_container_width=True):
                st.session_state["lib_selected_story"] = sid
                st.rerun()
    with detail:
        if not selected or not any(s.get("id") == selected for s in stories):
            st.info("👈 Select a story to view it.")
            return
        _render_story_detail(selected)


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
        f"""<button id="{btn_id}" style="width:100%;padding:8px 4px;border:1px solid #bbb;border-radius:8px;
        background:#f5f5f5;color:#222;cursor:pointer;font-size:13px;">{_html.escape(label)}</button>
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

    # Title at top — editable; saves on change
    new_title = st.text_input("Title", value=meta.get("title", "Untitled Story"),
                              key=f"lib_title_{story_id}")
    if new_title.strip() and new_title.strip() != meta.get("title", ""):
        lib.update_story_fields(story_id, title=new_title.strip())
        st.rerun()
    created = (meta.get("created_at", "") or "").replace("T", " ")
    st.caption(f"Created {created}" + (f" · Tone: {meta.get('tone')}" if meta.get("tone") else ""))

    # Hashtags
    tags = meta.get("hashtags") or []
    if tags:
        st.markdown("".join(f'<span class="lib-chip">{t}</span>' for t in tags), unsafe_allow_html=True)

    # Enrichment / refresh state
    _status = meta.get("enrichment_status")
    if _status == "pending":
        st.info("⏳ Fetching images & news links in the background…")
    elif _status == "refreshing":
        st.info("🔄 Refreshing in the background — feel free to switch tabs, it won't stop.")
    _note = (meta.get("refresh_note") or "").strip()
    if _note:
        st.caption(f"🔄 Last refresh: {_note}")

    # Whole script — always through the color-coded renderer so dialogue
    # never falls back to plain markdown.
    script_md = story["script"].strip()
    if script_md:
        st.markdown("### 🎬 Full Script")
        _render_full_script(script_md)
    elif story["dialogue"].strip():
        # Old-format files (saved before the blockquote change): two-box rendering.
        st.markdown(f'<div class="lib-dialogue">{_md_to_html(story["dialogue"])}</div>',
                    unsafe_allow_html=True)

    # Copy options: the full final-stage script, pure — nothing added.
    if script_md:
        st.markdown("### 📋 Copy")
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            _copy_button("📋 Script", _script_plain_text(script_md), f"s-{story_id}")
        with cc2:
            _copy_button("🖼️ + Media", _compose_share_text(meta, script_md, True, False), f"m-{story_id}")
        with cc3:
            _copy_button("#️⃣ + Tags", _compose_share_text(meta, script_md, False, True), f"h-{story_id}")
        with cc4:
            _copy_button("📦 All", _compose_share_text(meta, script_md, True, True), f"a-{story_id}")

    # Images + news links at the bottom
    st.markdown("### 🖼️ Media & Links")
    img_urls = meta.get("image_urls") or []
    uploaded = meta.get("uploaded_images") or []
    if img_urls:
        st.caption("Auto-fetched from news — remove any to overwrite, or upload your own below.")
        for i, url in enumerate(img_urls):
            ic1, ic2 = st.columns([5, 1])
            with ic1:
                st.image(url, width=220)
            with ic2:
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

    # Refresh / retry controls (all background — safe to switch tabs mid-fetch)
    r1, r2, r3 = st.columns(3)
    with r1:
        if st.button("#️⃣ Update hashtags", key=f"lib_tags_{story_id}",
                     help="Find trending hashtags for this story's topic and add them"):
            if lib.start_refresh(story_id, "hashtags"):
                st.toast("Looking for trending hashtags in the background…")
                st.rerun()
            else:
                st.error("Could not start the hashtag refresh.")
    with r2:
        if st.button("🖼️ Update images", key=f"lib_imgs_{story_id}",
                     help="Re-fetch news images for this story's topic"):
            if lib.start_refresh(story_id, "images"):
                st.toast("Fetching images in the background…")
                st.rerun()
            else:
                st.error("Could not start the image refresh.")
    with r3:
        if st.button("↻ Retry media fetch", key=f"lib_retry_{story_id}",
                     help="Re-run the hashtag + image fetch for this story"):
            if lib.retry_enrichment(story_id):
                st.toast("Retrying media fetch…")
                st.rerun()
            else:
                st.error("Could not start the retry.")

    # Delete + back
    d1, d2 = st.columns(2)
    with d1:
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
    with d2:
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
