"""Hindi Reel Studio — compact Apple-style master-detail UI."""

import re
import copy
import streamlit as st
import sys
from core.dual_engine import dual_engine
from core.metrics import get_duration_budget
from core.prompt_matrix import build_tailored_instruction
from core.config import load_config, save_config, reset_to_defaults
from tools.news_fetcher import news_fetcher
from workflow import reel_workflow
from agents.dialogue_writer import strip_commenting_and_cta
from core.screenplay_formatter import (
    format_industry_screenplay,
    format_teleprompter_text,
    format_director_prompts,
    derive_scene_detail,
    clean_physical_action,
    get_character_attire,
    get_first_name,
)

ENGINE_OPTIONS = {
    "Local First Then Antigravity": "first_local_then_agy",
    "Antigravity": "agy_only",
    "Codex": "codex_only",
    "Grok Low": "grok_low",
    "Grok Medium": "grok_medium",
    "Grok High": "grok_high",
    "On-device": "fm_only",
}
ENGINE_NAMES_REV = {v: k for k, v in ENGINE_OPTIONS.items()}

# Merged story source: manual topic entry plus every news feed (replaces the
# old separate Source + Category dropdowns, which overlapped in behaviour).
MANUAL_TOPIC_SOURCE = "✏️ Manual Topic"
DEFAULT_STORY_SOURCE = "🇮🇳 India Top Stories & Breaking"
STORY_SOURCES = [
    MANUAL_TOPIC_SOURCE,
    "🔥 India Trending & Viral",
    DEFAULT_STORY_SOURCE,
    "😂 Desi Quirky, Jugaad & Funny India",
    "🏛️ Indian Politics, Elections & Governance",
    "🪔 Indian Culture, Heritage & Festivals",
    "🚀 India Tech, Space (ISRO) & Startups",
    "💻 Technology & AI",
    "🌍 World News",
    "📈 Business & Economy",
]


def sanitize_visual_prompt(text: str) -> str:
    """Ensure no internal model or vendor tokens appear in the public cinematic prompt."""
    if not text:
        return ""
    t = text
    t = re.sub(r"(?:for\s+)?Google\s+(?:Flow\s*(?:/|and|\+)?\s*)?Veo(?:\s*9:16)?\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?:for\s+)?Google\s+Flow\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?:for\s+)?(?:Veo|Sora)\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^Cinematic\s+9:16\s+vertical\s+video\s*(?:for\s+[^:]+)?:\s*", "Cinematic 9:16 vertical shot: ", t, flags=re.IGNORECASE)
    if not t.lower().startswith("cinematic 9:16 vertical"):
        t = f"Cinematic 9:16 vertical shot: {t}"
    return t.strip()


POLITICAL_NAMES_BLACKLIST = {
    "rahul", "modi", "narendra", "kejriwal", "gandhi", "amit shah", "amit",
    "yogi", "adityanath", "sonia", "priyanka", "mamata", "stalin", "pawar",
    "fadnavis", "shinde", "thackeray", "nitish", "lalu", "tejaswi"
}


def sanitize_character_name(name: str) -> str:
    """Ensure characters never use politician names to prevent policy flags."""
    if not name:
        return ""
    t = name
    for pol in POLITICAL_NAMES_BLACKLIST:
        if re.search(rf"\b{pol}\b", t, re.IGNORECASE):
            t = re.sub(rf"\b{pol}\b", "Rohan", t, flags=re.IGNORECASE)
            t = t.replace("राहुल", "रोहन").replace("अमित", "आरव").replace("मोदी", "कबीर")
    return t


def clean_beat_action(text: str) -> str:
    """Strip camera framing and prompt jargon, returning pure physical actor action."""
    return clean_physical_action(text)



def extract_scene_context(script):
    """Extract slugline, environment, camera setup, and characters for the unified scene."""
    chars = []
    seen = set()
    for sc in script.scenes:
        c_clean = sanitize_character_name(sc.character)
        c_base = c_clean.split("/")[0].split("(")[0].strip()
        if c_base and c_base not in seen:
            seen.add(c_base)
            chars.append(c_clean)
    s1_vis = script.scenes[0].visual_b_roll if script.scenes else ""
    loc = ""
    # Extract specific setting from Scene 1 preamble if present
    m = re.search(r"(?:at|outside|inside|near)\s+([^;.]+?)(?:\s*;\s*|\.\s+)", s1_vis, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        candidate = re.sub(r"^(?:a|an)\s+", "", candidate, flags=re.IGNORECASE)
        if len(candidate) > 10 and not candidate.lower().startswith("shot"):
            loc = candidate[0].upper() + candidate[1:]

    if not loc:
        for lk in ["chai tapri", "tapri", "street", "wall", "college", "court", "station", "shop", "market", "office", "hospital", "सड़क", "दीवार"]:
            if lk in s1_vis.lower():
                loc = f"Vibrant Indian street / public setting ({lk.title()})"
                break
    if not loc:
        loc = "Vibrant Indian street chai tapri and surrounding neighborhood, warm natural sunlight"

    slugline = "EXT. STREET CHAI TAPRI - DAY"
    loc_lower = (loc + " " + s1_vis).lower()
    if "court" in loc_lower:
        slugline = "EXT. HIGH COURT STEPS - DAY"
    elif "office" in loc_lower or "desk" in loc_lower or "corporate" in loc_lower:
        slugline = "INT. CORPORATE TECH OFFICE - DAY"
    elif "hospital" in loc_lower:
        slugline = "INT./EXT. GOVERNMENT HOSPITAL - DAY"
    elif "school" in loc_lower or "college" in loc_lower:
        slugline = "EXT. SCHOOL CAMPUS - DAY"
    elif "market" in loc_lower or "shop" in loc_lower:
        slugline = "EXT. LOCAL INDIAN BAZAAR - DAY"
    elif "village" in loc_lower or "panchayat" in loc_lower or "khet" in loc_lower:
        slugline = "EXT. RURAL VILLAGE CHOPAL - DAY"
    elif "station" in loc_lower or "metro" in loc_lower:
        slugline = "EXT. METRO STATION ENTRY - DAY"

    return {
        "slugline": slugline,
        "location": loc,
        "camera_setup": "Single continuous handheld dynamic 9:16 vertical take; smooth reframing and character pivots without scene cuts.",
        "characters": chars or ["👩 Priya (प्रिया)", "🧑 Rohan (रोहन)"],
    }


def format_professional_screenplay(script, topic_name: str = "", include_overlays: bool = True, include_sfx: bool = True) -> str:
    """Format industry-standard professional screenplay with Scene Detail at top and pure actions in beats."""
    return format_industry_screenplay(script, topic_name, include_overlays=include_overlays, include_sfx=include_sfx)


def format_plain_script(script, include_overlays: bool = True, include_sfx: bool = True) -> str:
    """Format clean plain screenplay ready for immediate copy-pasting."""
    return format_industry_screenplay(script, include_overlays=include_overlays, include_sfx=include_sfx)



st.set_page_config(
    page_title="Hindi Reel Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

app_cfg = load_config()

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@500;600;700&display=swap');

    :root, html, body, .stApp, [data-testid="stAppViewContainer"] {
        color-scheme: light only;
        background-color: #f5f5f7 !important;
        color: #1d1d1f !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial,
                     "Noto Sans Devanagari", sans-serif !important;
    }

    .stDeployButton, [data-testid="stToolbar"], header[data-testid="stHeader"],
    #MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }

    .block-container {
        padding-top: 1.25rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px !important;
    }

    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    label, .stCaption, .stCaption p {
        color: #1d1d1f !important;
    }
    [data-testid="stWidgetLabel"] p {
        color: #3a3a3c !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
    }

    .nav { padding: 4px 2px 18px 2px; }
    .nav-title {
        font-size: 1.35rem; font-weight: 700; color: #1d1d1f !important;
        letter-spacing: -0.03em;
    }
    .nav-sub { font-size: 0.8rem; color: #3a3a3c !important; margin-top: 2px; }

    .ios-section-label {
        font-size: 0.78rem; font-weight: 700; color: #3a3a3c !important;
        text-transform: uppercase; letter-spacing: 0.05em;
        padding: 0 4px 8px 4px;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #ffffff !important;
        border: 1px solid #d2d2d7 !important;
        border-radius: 14px !important;
        box-shadow: none !important;
        padding: 8px 12px 12px 12px !important;
        color: #1d1d1f !important;
    }

    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        border: 1px solid #d2d2d7 !important;
        background: #ffffff !important;
        color: #1d1d1f !important;
        box-shadow: none !important;
        min-height: 40px;
        font-size: 0.88rem !important;
    }
    .stButton > button:hover {
        background: #e8e8ed !important;
        color: #1d1d1f !important;
        border-color: #c7c7cc !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: #0071e3 !important;
        color: #ffffff !important;
        border: 1px solid #0071e3 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #005bb5 !important;
        color: #ffffff !important;
    }

    /* Firefox + Streamlit form controls: force light, high-contrast */
    textarea, input, select,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea,
    [data-baseweb="select"] > div,
    [data-baseweb="select"] span,
    [data-baseweb="base-input"],
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        -moz-appearance: none !important;
        appearance: none !important;
        color-scheme: light !important;
        background-color: #ffffff !important;
        color: #1d1d1f !important;
        caret-color: #1d1d1f !important;
        border: 1px solid #c7c7cc !important;
        border-radius: 10px !important;
    }
    [data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #1d1d1f !important;
    }
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    ul[role="listbox"],
    li[role="option"] {
        background-color: #ffffff !important;
        color: #1d1d1f !important;
    }
    li[role="option"]:hover {
        background-color: #e8e8ed !important;
        color: #1d1d1f !important;
    }

    [data-testid="stExpander"] {
        background: #ffffff !important;
        border: 1px solid #d2d2d7 !important;
        border-radius: 14px !important;
        color: #1d1d1f !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] p,
    [data-testid="stExpander"] span {
        color: #1d1d1f !important;
    }

    [data-testid="stRadio"] label,
    [data-testid="stRadio"] p { color: #1d1d1f !important; }

    code, pre, [data-testid="stCode"] pre {
        background: #f2f2f7 !important;
        color: #1d1d1f !important;
    }

    .phone {
        background: #111111;
        border-radius: 14px;
        padding: 16px;
        border: 1px solid #2c2c2e;
        width: 100%;
        aspect-ratio: 9 / 16;
        min-height: 560px;
        overflow-y: auto;
        color: #f5f5f7;
    }
    .phone-empty {
        color: #d1d1d6 !important; text-align: center; padding: 120px 24px;
        font-size: 0.95rem;
    }
    .script-preview {
        background: #ffffff;
        border: 1px solid #d2d2d7;
        border-radius: 14px;
        padding: 18px 20px;
        color: #1d1d1f;
    }
    .script-format {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: #3a3a3c;
        border-bottom: 1px solid #d2d2d7;
        padding-bottom: 12px;
        margin-bottom: 16px;
    }
    .script-scene { margin-bottom: 18px; }
    .script-time { font-weight: 700; font-size: 0.9rem; color: #0071e3; margin-bottom: 6px; }
    .script-visual { font-size: 0.92rem; line-height: 1.5; margin-bottom: 10px; }
    .script-character { font-size: 0.82rem; font-weight: 700; margin-bottom: 4px; }
    .script-dialogue { font-family: "Noto Sans Devanagari", sans-serif; font-size: 1rem; line-height: 1.6; }
    .phone-title {
        color: #ffffff !important; font-weight: 600; font-size: 0.95rem;
        margin-bottom: 10px; padding: 0 6px;
    }
    .pill {
        display: inline-block; font-size: 0.7rem; font-weight: 600;
        padding: 3px 8px; border-radius: 999px; margin: 0 4px 8px 0;
        background: #3a3a3c; color: #ffffff !important;
    }
    .pill-ok { background: #1c7c3a; color: #ffffff !important; }
    .pill-bad { background: #c41e3a; color: #ffffff !important; }

    .frame-card {
        background: #2c2c2e; border-radius: 16px; padding: 12px 14px; margin-bottom: 10px;
        color: #ffffff;
    }
    .frame-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .frame-title { color: #ffffff !important; font-size: 0.82rem; font-weight: 600; }
    .frame-time { color: #d1d1d6 !important; font-size: 0.72rem; }
    .character-badge {
        display: inline-block; font-size: 0.7rem; font-weight: 600;
        color: #111111 !important; background: #7fd0ff; padding: 2px 8px;
        border-radius: 6px; margin-bottom: 6px;
    }
    .dialogue-text {
        font-family: "Noto Sans Devanagari", sans-serif;
        font-size: 1.02rem; line-height: 1.65; color: #ffffff !important;
        background: #000000; border-radius: 12px; padding: 10px 12px; margin: 6px 0;
    }
    .meta { font-size: 0.78rem; color: #e5e5ea !important; margin-top: 6px; line-height: 1.4; }
    .teleprompter-box {
        background: #2c2c2e; border-radius: 16px; padding: 12px 14px; margin-top: 8px;
    }
    .dialogue-target-badge { font-size: 0.7rem; color: #d1d1d6 !important; font-weight: 600; }
    .hindi-dialogue-text {
        font-family: "Noto Sans Devanagari", sans-serif;
        font-size: 1.05rem; line-height: 1.75; color: #ffffff !important; margin-top: 8px;
    }
    .news-item {
        background: #ffffff;
        border: 1px solid #d2d2d7;
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 8px;
        color: #1d1d1f;
    }
    .news-rank { font-size: 0.72rem; font-weight: 700; color: #0071e3; }
    .news-title { font-size: 0.92rem; font-weight: 600; color: #1d1d1f !important; line-height: 1.35; }
    .news-meta { font-size: 0.72rem; color: #3a3a3c !important; margin-top: 4px; }

    /* — Uniform config-row alignment & polish — */
    .cfg-label {
        font-size: 0.88rem;
        font-weight: 600;
        color: #3a3a3c !important;
        line-height: 40px;
        white-space: nowrap;
        padding: 0;
    }

    /* Uniform widget heights */
    [data-baseweb="select"] > div {
        min-height: 38px !important;
        font-size: 0.88rem !important;
    }

    /* Compact row spacing inside config containers */
    div[data-testid="stVerticalBlockBorderWrapper"] .stSelectbox,
    div[data-testid="stVerticalBlockBorderWrapper"] .stNumberInput,
    div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] {
        margin-bottom: 4px !important;
        margin-top: 0 !important;
    }

    /* Stepper buttons polish */
    [data-testid="stNumberInput"] button {
        min-height: 36px !important;
        min-width: 34px !important;
        border-radius: 7px !important;
        background: #e8e8ed !important;
        border: 1px solid #d2d2d7 !important;
        color: #1d1d1f !important;
        margin: 0 !important;
        font-size: 0.9rem !important;
        transition: background 120ms ease, border-color 120ms ease !important;
    }
    [data-testid="stNumberInput"] button:hover {
        background: #e8e8ed !important;
    }
    [data-testid="stNumberInput"] input {
        text-align: center !important;
        min-height: 36px !important;
        padding: 0 8px !important;
        font-variant-numeric: tabular-nums;
        font-size: 0.88rem !important;
        background: #f5f5f7 !important;
    }

    [data-testid="stNumberInput"] > div {
        min-height: 40px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        background: transparent !important;
        display: block !important;
        position: relative !important;
    }
    [data-testid="stNumberInput"] [data-baseweb="base-input"],
    [data-testid="stNumberInput"] [data-baseweb="input"] {
        width: 100% !important;
        height: 40px !important;
        min-height: 40px !important;
        box-sizing: border-box !important;
        border-radius: 10px !important;
        background: #f5f5f7 !important;
        border: 1px solid #c7c7cc !important;
        box-shadow: none !important;
        padding-left: 36px !important;
        padding-right: 36px !important;
    }
    [data-testid="stNumberInput"] [data-baseweb="base-input"] > div,
    [data-testid="stNumberInput"] [data-baseweb="input"] > div {
        background: #f5f5f7 !important;
        border: 0 !important;
        box-shadow: none !important;
    }
    [data-testid="stNumberInput"] input {
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        height: 38px !important;
        width: 100% !important;
    }
    [data-testid="stNumberInput"] > div > button,
    [data-testid="stNumberInput"] > div button {
        position: absolute !important;
        top: 2px !important;
        z-index: 2 !important;
        height: 36px !important;
    }
    [data-testid="stNumberInput"] > div > button:first-of-type,
    [data-testid="stNumberInput"] > div button:first-of-type {
        left: 1px !important;
    }
    [data-testid="stNumberInput"] > div > button:last-of-type,
    [data-testid="stNumberInput"] > div button:last-of-type {
        right: 1px !important;
    }
    [data-testid="stNumberInput"] button:first-child { margin-left: 0 !important; }
    [data-testid="stNumberInput"] button:last-child { margin-right: 0 !important; }

    /* One shared vertical rhythm for every config row. */
    div[data-testid="stVerticalBlockBorderWrapper"] .stSelectbox,
    div[data-testid="stVerticalBlockBorderWrapper"] .stNumberInput {
        min-height: 42px !important;
        margin: 0 0 4px 0 !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] {
        align-items: center !important;
        min-height: 42px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] > div {
        box-sizing: border-box !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="select"] > div,
    div[data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="base-input"] {
        width: 100% !important;
        min-height: 40px !important;
        height: 40px !important;
        box-sizing: border-box !important;
        border: 1px solid #c7c7cc !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }

    /* Keep every configuration control aligned to one shared row geometry. */
    .config-row {
        min-height: 42px;
        align-items: center;
    }
    [data-testid="stNumberInput"],
    [data-testid="stSelectbox"] {
        width: 100% !important;
    }
    [data-testid="stNumberInput"] > div,
    [data-testid="stSelectbox"] > div {
        min-height: 38px !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "batch_result" not in st.session_state:
    st.session_state.batch_result = None
if "generation_error" not in st.session_state:
    st.session_state.generation_error = None
if "chosen_engine_mode" not in st.session_state:
    st.session_state.chosen_engine_mode = app_cfg.get("default_engine", "first_local_then_agy")
if "chosen_duration" not in st.session_state:
    st.session_state.chosen_duration = app_cfg.get("default_duration", 30)
if "chosen_tone" not in st.session_state:
    st.session_state.chosen_tone = app_cfg.get("default_tone", "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)")
if "chosen_batch_count" not in st.session_state:
    st.session_state.chosen_batch_count = app_cfg.get("batch_count", 1)
if "chosen_max_retries" not in st.session_state:
    st.session_state.chosen_max_retries = app_cfg.get("max_retries", 5)
if "chosen_story_source" not in st.session_state:
    # Merged Source + Category: migrate legacy separate settings once.
    _legacy_cat = app_cfg.get("news_category", "")
    _legacy_mode = app_cfg.get("source_mode", "")
    if _legacy_mode == "✏️ Manual Topic":
        st.session_state.chosen_story_source = MANUAL_TOPIC_SOURCE
    elif _legacy_cat in STORY_SOURCES:
        st.session_state.chosen_story_source = _legacy_cat
    else:
        st.session_state.chosen_story_source = app_cfg.get("story_source", DEFAULT_STORY_SOURCE)
if "selected_script_idx" not in st.session_state:
    st.session_state.selected_script_idx = app_cfg.get("selected_script_index", 0)
if "live_news_articles" not in st.session_state:
    st.session_state.live_news_articles = []
if "selected_headline_title" not in st.session_state:
    st.session_state.selected_headline_title = app_cfg.get("selected_headline", "")
if "active_story_input" not in st.session_state:
    st.session_state.active_story_input = app_cfg.get("selected_headline", "")
if "chosen_angle" not in st.session_state:
    st.session_state.chosen_angle = app_cfg.get("default_angle", "")
if "chosen_character_count" not in st.session_state:
    st.session_state.chosen_character_count = app_cfg.get("character_count", 1)
if "chosen_scene_style" not in st.session_state:
    st.session_state.chosen_scene_style = app_cfg.get("scene_style", "Dialogue")
if "chosen_sample_story" not in st.session_state:
    st.session_state.chosen_sample_story = ""
if "headline_rev" not in st.session_state:
    st.session_state.headline_rev = 0
if "workflow_mode" not in st.session_state:
    st.session_state.workflow_mode = app_cfg.get("workflow_mode", "⚡ Continuous")
if "stepwise_active" not in st.session_state:
    st.session_state.stepwise_active = False
if "stepwise_current_step" not in st.session_state:
    st.session_state.stepwise_current_step = 1
if "stepwise_state" not in st.session_state:
    st.session_state.stepwise_state = None
if "stepwise_step_model" not in st.session_state:
    st.session_state.stepwise_step_model = st.session_state.chosen_engine_mode
if "stepwise_extra_instruction" not in st.session_state:
    st.session_state.stepwise_extra_instruction = ""
if "stepwise_run_requested" not in st.session_state:
    st.session_state.stepwise_run_requested = False
if "stepwise_completed_steps" not in st.session_state:
    st.session_state.stepwise_completed_steps = {}

st.markdown(
    """
    <div class="nav">
        <div>
            <div class="nav-title">Hindi Reel Studio</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col_settings, col_output = st.columns([6, 4], gap="large")

with col_settings:
    @st.fragment
    def settings_panel():
        story_heading, story_refresh = st.columns([8, 1.8])
        with story_heading:
            st.markdown('<div class="ios-section-label">Story &amp; Topic</div>', unsafe_allow_html=True)
        with story_refresh:
            refresh_news = st.button("Refresh", help="Refresh headlines", use_container_width=True, key="refresh_news")
        with st.container(border=True):
            src_lbl, src_dd = st.columns([2.5, 5.5])
            with src_lbl:
                st.markdown('<div class="cfg-label">Source</div>', unsafe_allow_html=True)
            with src_dd:
                _src_idx = STORY_SOURCES.index(st.session_state.chosen_story_source) if st.session_state.chosen_story_source in STORY_SOURCES else STORY_SOURCES.index(DEFAULT_STORY_SOURCE)
                selected_source = st.selectbox(
                    "Story Source",
                    STORY_SOURCES,
                    index=_src_idx,
                    label_visibility="collapsed",
                    key="story_source_dropdown",
                )
                if selected_source != st.session_state.chosen_story_source:
                    st.session_state.chosen_story_source = selected_source
                    save_config("story_source", selected_source)
            is_feed_mode = selected_source != MANUAL_TOPIC_SOURCE
            # The headline fetcher dispatch below keys off this name.
            selected_news_cat = selected_source

            if is_feed_mode and (refresh_news or not st.session_state.live_news_articles or st.session_state.get("loaded_news_cat") != selected_news_cat):
                with st.spinner("Loading headlines…"):
                    if "Funny" in selected_news_cat or "Quirky" in selected_news_cat or "Jugaad" in selected_news_cat:
                            articles = news_fetcher.get_top_funny_viral_india_news(limit=16)
                    elif "Trending" in selected_news_cat or "Viral" in selected_news_cat:
                            articles = news_fetcher.get_india_trending(limit=16)
                    elif "Politics" in selected_news_cat or "Election" in selected_news_cat or "Governance" in selected_news_cat:
                            articles = news_fetcher.get_top_indian_politics_news(limit=16)
                    elif "Culture" in selected_news_cat or "Heritage" in selected_news_cat:
                            articles = news_fetcher.get_top_indian_culture_news(limit=16)
                    elif "Tech" in selected_news_cat or "ISRO" in selected_news_cat:
                            articles = news_fetcher.get_top_india_tech_news(limit=16)
                    elif "Technology" in selected_news_cat or "AI" in selected_news_cat:
                            articles = news_fetcher.get_top_tech_news(limit=16)
                    elif "World" in selected_news_cat:
                            articles = news_fetcher.get_top_world_news(limit=16)
                    elif "Business" in selected_news_cat:
                            articles = news_fetcher.get_top_business_news(limit=16)
                    else:
                            articles = news_fetcher.get_top_india_news(limit=16)
                    st.session_state.live_news_articles = articles
                    st.session_state.loaded_news_cat = selected_news_cat

            if is_feed_mode:
                # Headline dropdown from live feed — persists selection and avoids re-fetching unless refreshed
                arts = st.session_state.live_news_articles[:16]
                if arts:
                    headline_options = [
                        f"{i + 1}. {'[' + getattr(a, 'time_label', '') + '] ' if getattr(a, 'time_label', '') else ''}{getattr(a, 'title', '')[:75]}"
                        for i, a in enumerate(arts)
                    ]
                    saved_headline = st.session_state.get("selected_headline_title") or app_cfg.get("selected_headline", "")
                    active_headline = st.session_state.get("active_story_input", "") or saved_headline
                    hl_idx = 0
                    for i, a in enumerate(arts):
                        if a.title == active_headline or a.title == saved_headline:
                            hl_idx = i
                            break
                    hl_lbl, hl_dd = st.columns([2.5, 5.5])
                    with hl_lbl:
                        st.markdown('<div class="cfg-label">Headline</div>', unsafe_allow_html=True)
                    with hl_dd:
                        picked_hl = st.selectbox("Headline", headline_options, index=hl_idx, label_visibility="collapsed", key="headline_dropdown")
                    if picked_hl:
                        p_idx = int(picked_hl.split(".")[0]) - 1
                        if 0 <= p_idx < len(arts):
                            chosen_art_title = arts[p_idx].title
                            if chosen_art_title != st.session_state.get("selected_headline_title"):
                                st.session_state.selected_headline_title = chosen_art_title
                                st.session_state.active_story_input = chosen_art_title
                                st.session_state.headline_rev = st.session_state.get("headline_rev", 0) + 1
                                save_config("selected_headline", chosen_art_title)
                                st.rerun()
                            elif not st.session_state.get("active_story_input"):
                                st.session_state.active_story_input = chosen_art_title
                else:
                    st.caption("No headlines available for this category yet.")
            elif False:
                # Presets are intentionally hidden in Manual Topic mode.
                topic_presets_list = [
                    ("Custom / Manual Topic", "", ""),
                    ("🪔 Varanasi Dev Deepawali: Sacred Ganga Ghats Lights", "Varanasi Dev Deepawali: Millions of earthen lamps illuminate the sacred Ganga Ghats as worldwide pilgrims celebrate ancient festival of light.", "🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)"),
                    ("🚀 ISRO Gaganyaan Mission: Human Spaceflight Systems", "ISRO tests next-generation crew module and human-rating life support systems for India's historic Gaganyaan space mission.", "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)"),
                    ("🏛️ Ancient Indian Temples: Vedic Acoustic Marvels", "Ancient Indian stone temple architecture and Vedic acoustic engineering certified as architectural marvels by international archaeologists.", "🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)"),
                    ("📱 Digital India & UPI: 16B Monthly Transactions", "India's UPI and digital infrastructure set global record with 16 billion monthly transactions as nations worldwide partner with NPCI.", "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)"),
                    ("🏏 Team India Victory: Historic World Championship", "Team India achieves historic cricket championship victory, sparking nationwide celebrations and global acclaim.", "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)"),
                    ("🌿 Ayurveda & Ancient Wellness: Global Revolution", "Indian Ayurveda and traditional holistic medicine gain unprecedented global scientific validation and adoption.", "🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)"),
                ]
                if st.session_state.live_news_articles:
                    for art in st.session_state.live_news_articles[:8]:
                        topic_presets_list.append((f"📰 {art.title[:75]}…", art.title, "⚡ Urgent Breaking News (ताज़ा खबर)"))

                topic_labels = [p[0] for p in topic_presets_list]
                topic_data_map = {p[0]: (p[1], p[2]) for p in topic_presets_list}

                curr_story = st.session_state.get(
                    "active_story_input",
                    "Varanasi Dev Deepawali: Millions of earthen lamps illuminate the sacred Ganga Ghats as worldwide pilgrims celebrate ancient festival of light.",
                )
                selected_idx = 0
                for i, p in enumerate(topic_presets_list):
                    if p[1] and p[1] == curr_story:
                        selected_idx = i
                        break

                tp_lbl, tp_dd = st.columns([2.5, 5.5])
                with tp_lbl:
                    st.markdown('<div class="cfg-label">Preset</div>', unsafe_allow_html=True)
                with tp_dd:
                    selected_topic = st.selectbox(
                        "Topic Preset",
                        topic_labels,
                        index=selected_idx,
                        label_visibility="collapsed",
                        key="story_topic_dropdown",
                    )
                if "last_selected_topic_choice" not in st.session_state:
                    st.session_state.last_selected_topic_choice = selected_topic
                elif selected_topic != st.session_state.last_selected_topic_choice:
                    st.session_state.last_selected_topic_choice = selected_topic
                    t_story, t_tone = topic_data_map.get(selected_topic, ("", ""))
                    if t_story:
                        st.session_state.active_story_input = t_story
                        if t_tone:
                            st.session_state.chosen_tone = t_tone
                            save_config("default_tone", t_tone)
                        st.rerun()

            # Topic text area — always visible; editable in all modes
            default_story = st.session_state.get(
                "active_story_input",
                "Varanasi Dev Deepawali: Millions of earthen lamps illuminate the sacred Ganga Ghats as worldwide pilgrims celebrate ancient festival of light.",
            )
            topic_key = f"topic_input_{st.session_state.get('headline_rev', 0)}"
            if selected_source == MANUAL_TOPIC_SOURCE:
                news_input = st.text_input(
                    "Title",
                    value=default_story,
                    placeholder="Write your title or news topic…",
                    label_visibility="visible",
                    key=f"manual_{topic_key}",
                )
            else:
                news_input = st.text_area("Topic", value=default_story, height=88, placeholder="Type or edit headline…", label_visibility="collapsed", key=f"area_{topic_key}")
            if news_input != st.session_state.get("active_story_input", ""):
                st.session_state.active_story_input = news_input
                st.session_state.selected_headline_title = news_input
                save_config("selected_headline", news_input)

            with st.expander("📝 Sample Story (Optional Reference)", expanded=bool(st.session_state.get("chosen_sample_story"))):
                if "sample_story_rev" not in st.session_state:
                    st.session_state.sample_story_rev = 0
                sample_story_val = st.text_area(
                    "Sample Story / Reference Script",
                    value=st.session_state.get("chosen_sample_story", ""),
                    height=75,
                    placeholder="Paste reference story or script snippet here. If provided, AI prioritizes it over general instructions...",
                    help="Optional reference story or script snippet. If provided, the AI adapts and prioritizes this sample story. In case of any discrepancy with general instructions, the sample story takes highest precedence!",
                    key=f"sample_story_textarea_{st.session_state.sample_story_rev}",
                )
                if sample_story_val != st.session_state.get("chosen_sample_story", ""):
                    st.session_state.chosen_sample_story = sample_story_val

                c_info, c_clear = st.columns([4, 1.2])
                with c_info:
                    st.caption("Adapts narrative, characters, and tone with highest precedence.")
                with c_clear:
                    if st.button("🗑️ Clear", key="clear_sample_story_btn", help="Clear sample story reference", use_container_width=True):
                        st.session_state.chosen_sample_story = ""
                        st.session_state.sample_story_rev += 1
                        st.session_state.instruction_cfg_sig = None
                        st.rerun()

        # ─── Configuration (below Story & Topic) ───
        top_l, top_r = st.columns([8, 1.2])
        with top_l:
            st.markdown('<div class="ios-section-label" style="margin-top:18px">Configuration</div>', unsafe_allow_html=True)
        with top_r:
            if st.button("Reset", help="Restore defaults", use_container_width=True):
                reset_cfg = reset_to_defaults()
                for key, value in {
                    "chosen_engine_mode": reset_cfg["default_engine"], "chosen_duration": reset_cfg["default_duration"],
                    "chosen_tone": reset_cfg["default_tone"], "chosen_batch_count": reset_cfg["batch_count"],
                    "chosen_max_retries": reset_cfg["max_retries"], "chosen_story_source": DEFAULT_STORY_SOURCE,
                    "selected_headline_title": reset_cfg.get("selected_headline", ""),
                    "selected_script_idx": reset_cfg["selected_script_index"],
                    "chosen_angle": reset_cfg.get("default_angle", "Funny & Relatable"), "chosen_character_count": reset_cfg.get("character_count", 3),
                    "chosen_scene_style": reset_cfg.get("scene_style", "Dialogue"), "chosen_sample_story": "", "batch_result": None,
                }.items():
                    st.session_state[key] = value
                st.session_state.instruction_cfg_sig = None
                st.rerun()

        with st.container(border=True):
            engine_options = {
                "Local First Then Antigravity": "first_local_then_agy",
                "Antigravity": "agy_only",
                "Codex": "codex_only",
                "Grok Low": "grok_low",
                "Grok Medium": "grok_medium",
                "Grok High": "grok_high",
                "On-device": "fm_only",
            }
            def cfg_row(label, widget):
                left, right = st.columns([2.5, 5.5])
                with left:
                    st.markdown(f'<div class="cfg-label">{label}</div>', unsafe_allow_html=True)
                with right:
                    return widget()

            eng_labels = list(engine_options.keys())
            eng_idx = list(engine_options.values()).index(st.session_state.chosen_engine_mode) if st.session_state.chosen_engine_mode in engine_options.values() else 0
            selected_eng_label = cfg_row("Engine", lambda: st.selectbox("Engine", eng_labels, index=eng_idx, label_visibility="collapsed"))
            st.session_state.chosen_engine_mode = engine_options[selected_eng_label]
            save_config("default_engine", st.session_state.chosen_engine_mode)
            target_dur = int(cfg_row("Duration (s)", lambda: st.number_input("Duration", step=5, value=int(st.session_state.chosen_duration), label_visibility="collapsed")))
            st.session_state.chosen_duration = target_dur
            save_config("default_duration", target_dur)
            tone_options = [
                "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)", "🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)",
                "🔥 Viral & High Energy (धमाकेदार)", "😂 Relatable Comedy & Sarcasm (देसी ह्यूमर)",
                "⚡ Urgent Breaking News (ताज़ा खबर)", "💡 Deep Analysis & Curious (गहन पड़ताल)", "🎭 Cinematic Storytelling (भावुक कहानी)",
                "😢 Emotional & Heartbreaking (भावुक / दुखद)",
                "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)",
            ]
            tone_idx = tone_options.index(st.session_state.chosen_tone) if st.session_state.chosen_tone in tone_options else 0
            st.session_state.chosen_tone = cfg_row("Tone", lambda: st.selectbox("Tone", tone_options, index=tone_idx, label_visibility="collapsed"))
            save_config("default_tone", st.session_state.chosen_tone)
            angle_options = ["Funny & Relatable", "Sarcastic & Edgy", "Dramatic Storytelling", "Investigative Deep-Dive", "Inspirational & Uplifting", "Gen-Z Hinglish", "Bollywood Masala", "Tragic & Heartbreaking"]
            angle_idx = angle_options.index(st.session_state.chosen_angle) if st.session_state.chosen_angle in angle_options else 0
            st.session_state.chosen_angle = cfg_row("Angle", lambda: st.selectbox("Angle", angle_options, index=angle_idx, label_visibility="collapsed"))
            save_config("default_angle", st.session_state.chosen_angle)
            st.session_state.chosen_batch_count = int(cfg_row("Scripts", lambda: st.number_input("Scripts", step=1, value=int(st.session_state.chosen_batch_count), label_visibility="collapsed")))
            save_config("batch_count", st.session_state.chosen_batch_count)
            st.session_state.chosen_max_retries = int(cfg_row("Retries", lambda: st.number_input(
                "Retries",
                min_value=1,
                max_value=5,
                step=1,
                value=min(5, max(1, int(st.session_state.chosen_max_retries or 5))),
                label_visibility="collapsed",
                help="Max self-healing retries allowed (1 to 5)",
            )))
            save_config("max_retries", st.session_state.chosen_max_retries)
            st.session_state.chosen_character_count = int(cfg_row("Characters", lambda: st.number_input("Characters", step=1, value=int(st.session_state.chosen_character_count), label_visibility="collapsed")))
            save_config("character_count", st.session_state.chosen_character_count)
            scene_styles = ["Dialogue", "Argument", "Speech", "Narration", "Interview", "Debate", "Monologue", "Lament"]
            style_idx = scene_styles.index(st.session_state.chosen_scene_style) if st.session_state.chosen_scene_style in scene_styles else 0
            st.session_state.chosen_scene_style = cfg_row("Scene style", lambda: st.selectbox("Scene style", scene_styles, index=style_idx, label_visibility="collapsed"))
            save_config("scene_style", st.session_state.chosen_scene_style)


        dur_val = int(st.session_state.chosen_duration)
        budget_val = get_duration_budget(dur_val)
        active_topic_text = st.session_state.get('active_story_input', '').strip() or '[topic]'

        instruction_seed = build_tailored_instruction(
            topic=active_topic_text,
            duration_sec=dur_val,
            tone=st.session_state.chosen_tone,
            angle=st.session_state.chosen_angle,
            scene_style=st.session_state.chosen_scene_style,
            character_count=st.session_state.chosen_character_count,
            batch_count=st.session_state.chosen_batch_count,
            max_retries=st.session_state.chosen_max_retries,
            sample_story=st.session_state.get("chosen_sample_story", ""),
        )

        cfg_sig = (
            dur_val,
            st.session_state.chosen_scene_style,
            st.session_state.chosen_tone,
            st.session_state.chosen_angle,
            st.session_state.chosen_character_count,
            st.session_state.chosen_batch_count,
            st.session_state.chosen_max_retries,
            active_topic_text,
            st.session_state.get("chosen_sample_story", ""),
        )
        if "instruction_rev" not in st.session_state:
            st.session_state.instruction_rev = 0

        if st.session_state.get("instruction_cfg_sig") != cfg_sig:
            st.session_state.instruction_cfg_sig = cfg_sig
            st.session_state.instruction_rev += 1
            st.session_state[f"instruction_text_{st.session_state.instruction_rev}"] = instruction_seed

        inst_hdr_l, inst_hdr_r = st.columns([5.8, 4.2])
        with inst_hdr_l:
            st.markdown('<div class="ios-section-label" style="margin-top:14px; margin-bottom:4px;">Instruction</div>', unsafe_allow_html=True)
        with inst_hdr_r:
            if st.button("🔄 Update Instruction", help="Create or refresh instruction based on current config and selection", use_container_width=True, key="update_inst_btn"):
                st.session_state.instruction_cfg_sig = cfg_sig
                st.session_state.instruction_rev += 1
                st.session_state[f"instruction_text_{st.session_state.instruction_rev}"] = instruction_seed
                st.rerun()

        curr_inst_key = f"instruction_text_{st.session_state.instruction_rev}"
        if curr_inst_key not in st.session_state:
            st.session_state[curr_inst_key] = instruction_seed

        instruction_text = st.text_area(
            "Instruction",
            height=135,
            label_visibility="collapsed",
            help="This master instruction combines tone, angle, scene style, character count, duration budget, retries, and sample story directives. Divided into specialized sub-instructions by Chief Editor.",
            key=curr_inst_key,
        )
        st.markdown('<div class="ios-section-label" style="margin-top:14px; margin-bottom:4px;">Generation Mode</div>', unsafe_allow_html=True)
        with st.container(border=True):
            wf_modes = ["⚡ Continuous", "🪜 Step-Wise"]
            curr_wf = st.session_state.get("workflow_mode") or app_cfg.get("workflow_mode", "⚡ Continuous")
            if curr_wf not in wf_modes:
                curr_wf = "⚡ Continuous"
            sel_wf = st.radio(
                "Generation Mode",
                wf_modes,
                index=wf_modes.index(curr_wf),
                horizontal=True,
                label_visibility="collapsed",
                key="workflow_mode_radio",
            )
            if sel_wf != st.session_state.get("workflow_mode"):
                st.session_state.workflow_mode = sel_wf
                save_config("workflow_mode", sel_wf)
                st.rerun()

        if st.session_state.get("workflow_mode") == "🪜 Step-Wise":
            if not st.session_state.get("stepwise_active"):
                launch_btn = st.button("🪜 Start Step-Wise Generation", type="primary", use_container_width=True, key="launch_stepwise_btn")
                if launch_btn and st.session_state.get("active_story_input", "").strip():
                    st.session_state.stepwise_active = True
                    st.session_state.stepwise_current_step = 1
                    st.session_state.stepwise_state = None
                    st.session_state.stepwise_step_model = st.session_state.chosen_engine_mode
                    st.session_state.stepwise_extra_instruction = ""
                    st.session_state.stepwise_completed_steps = {}
                    st.session_state.stepwise_run_requested = True
                    st.session_state.batch_result = None
                    st.session_state.generation_error = None
                    st.session_state.run_topic = st.session_state.get("active_story_input", "").strip()
                    st.session_state.run_scenario = instruction_text.strip()
                    st.session_state.run_sample_story = st.session_state.get("chosen_sample_story", "").strip()
                    save_config("selected_headline", st.session_state.run_topic)
                    save_config("story_source", st.session_state.chosen_story_source)
                    save_config("max_retries", st.session_state.chosen_max_retries)
                    st.rerun()
            else:
                st.info(f"🪜 Step-Wise Active: Working on Step {st.session_state.get('stepwise_current_step', 1)} of 5")
                c_exit, c_new = st.columns([1, 1])
                with c_exit:
                    if st.button("❌ Exit Step-Wise", use_container_width=True, key="reset_stepwise_btn"):
                        st.session_state.stepwise_active = False
                        st.session_state.stepwise_state = None
                        st.session_state.stepwise_completed_steps = {}
                        st.session_state.stepwise_current_step = 1
                        st.session_state.stepwise_run_requested = False
                        st.rerun()
                with c_new:
                    if st.button("🚀 Restart Step 1", use_container_width=True, key="restart_step1_btn"):
                        st.session_state.stepwise_current_step = 1
                        st.session_state.stepwise_state = None
                        st.session_state.stepwise_completed_steps = {}
                        st.session_state.stepwise_run_requested = True
                        st.session_state.batch_result = None
                        st.session_state.generation_error = None
                        st.rerun()
        else:
            launch_btn = st.button("Generate (Continuous)", type="primary", use_container_width=True, key="launch_continuous_btn")
            if launch_btn and st.session_state.get("active_story_input", "").strip():
                st.session_state.stepwise_active = False
                st.session_state.run_requested = True
                st.session_state.batch_result = None
                st.session_state.generation_error = None
                st.session_state.run_topic = st.session_state.get("active_story_input", "").strip()
                st.session_state.run_scenario = instruction_text.strip()
                st.session_state.run_sample_story = st.session_state.get("chosen_sample_story", "").strip()
                save_config("selected_headline", st.session_state.run_topic)
                save_config("story_source", st.session_state.chosen_story_source)
                save_config("max_retries", st.session_state.chosen_max_retries)
                st.rerun()

    settings_panel()


def _render_step_output(step_num, step_state, key_prefix=""):
    """Render the full finalized output of a completed step (steps 1-4).

    Reused by the main step view and by the previous-steps history, so going
    back (or reviewing history) always shows the complete finalized output.
    """
    if step_num == 1:
        st.markdown("### 🔍 Step 1: Fact Validation & Story Dossier")
        verif = step_state.get("verification")
        if verif:
            c_vf1, c_vf2 = st.columns([1, 1])
            with c_vf1:
                st.markdown(f"**Verification:** {'🟢 Confirmed' if verif.is_verified else '🟡 Warning'} ({verif.confidence_score}% Confidence)")
            with c_vf2:
                st.markdown(f"**Target Format:** {step_state['target_seconds']}s • {step_state['scene_style']}")
            topic_headline = getattr(verif, "headline", None) or step_state.get("news_input", "")
            if topic_headline:
                st.markdown(f"**Headline / Topic:** {topic_headline}")
            if getattr(verif, "verification_summary", None):
                st.caption(f"**Verification Summary:** {verif.verification_summary}")
            if verif.verified_facts:
                st.markdown("**Confirmed Wire Facts:**")
                for f in verif.verified_facts[:4]:
                    st.markdown(f"- {f}")
            if verif.physical_props:
                st.markdown(f"**Physical Props:** {', '.join(verif.physical_props)}")
            if verif.key_locations:
                st.markdown(f"**Key Locations:** {', '.join(verif.key_locations)}")
            if verif.core_conflict_or_irony:
                st.markdown(f"**Core Conflict / Irony:** {verif.core_conflict_or_irony}")

        if step_state.get("sub_instructions"):
            with st.expander("👑 Generated Sub-Instructions for Upcoming Agents"):
                for ag, sub in step_state["sub_instructions"].items():
                    st.markdown(f"**{ag.replace('_', ' ').title()}:**")
                    st.caption(sub)

    elif step_num == 2:
        st.markdown("### 🎭 Step 2: Character & Scene Finalisation")
        chars = step_state.get("finalized_characters", [])
        avail_chars = step_state.get("available_characters", chars)
        scenes = step_state.get("finalized_scenes", [])
        avail_scenes = step_state.get("available_scenes", scenes)

        col_c, col_s = st.columns(2)
        with col_c:
            st.markdown(f"**👥 Characters Generated ({len(avail_chars)} Options - 2X Pool):**")
            for c_idx, ch in enumerate(avail_chars, 1):
                is_primary = "⭐ Primary" if c_idx <= len(chars) else "💡 Alternative"
                st.markdown(f"• **{ch.name}** (`{ch.role_or_job}`) — *{is_primary}*")
                if ch.attire:
                    st.caption(f"👗 Attire: {ch.attire}")
                if ch.emotional_stance:
                    st.caption(f"💥 Stance: {ch.emotional_stance}")
                if ch.relationship_dynamic:
                    st.caption(f"🤝 Dynamic: {ch.relationship_dynamic}")

        with col_s:
            st.markdown(f"**📍 Scene Locations Imagined ({len(avail_scenes)} for this story):**")
            for s_idx, sc in enumerate(avail_scenes, 1):
                is_primary = "⭐ Primary" if s_idx <= len(scenes) else "💡 Alternative"
                st.markdown(f"• **Option {sc.scene_option_number}: {sc.location_name}** — *{is_primary}*")
                if sc.atmosphere:
                    st.caption(f"🌆 Atmosphere: {sc.atmosphere}")
                if sc.lighting_mood:
                    st.caption(f"💡 Lighting: {sc.lighting_mood}")
                if sc.props:
                    st.caption(f"📦 Props: {', '.join(sc.props)}")

    elif step_num == 3:
        st.markdown("### ✍️ Step 3: Spoken Hindi Dialogue & Timing Calibration")
        _used_chars_3 = step_state.get("finalized_characters") or []
        _used_scenes_3 = step_state.get("finalized_scenes") or []
        if _used_chars_3 or _used_scenes_3:
            with st.expander("🎭 Characters & 📍 Scenes from Step 2 driving this dialogue", expanded=False):
                if _used_chars_3:
                    st.markdown("**Characters in use:**")
                    for _ch3 in _used_chars_3:
                        st.markdown(f"• **{_ch3.name}** (`{_ch3.role_or_job}`)")
                if _used_scenes_3:
                    st.markdown("**Scene locations in use:**")
                    for _sc3 in _used_scenes_3:
                        st.markdown(f"• **{_sc3.location_name}**")
        dialogues = step_state.get("script_dialogues", [])
        _timing_rows = []
        for d_idx, d in enumerate(dialogues, 1):
            if d.get("scene_lines"):
                for sl in d["scene_lines"]:
                    _ts = sl.get('timestamp', '')
                    _ts_txt = f" [{_ts}]" if _ts else ""
                    st.markdown(f"**BEAT {sl.get('scene_number', '')}**{_ts_txt} — **{sl.get('character', 'Character')}:** “{sl.get('dialogue', '')}”")
                    if sl.get('action'):
                        st.caption(f"🎬 {sl.get('action')}")
                    if sl.get('sfx'):
                        st.caption(f"🔊 {sl.get('sfx')}")
                    if sl.get('overlay'):
                        st.caption(f"🔖 Overlay: {sl.get('overlay')}")
            else:
                st.markdown(f"“{d.get('narration', '')}”")
            if d.get("retry_notes"):
                for rn in d["retry_notes"]:
                    st.caption(rn)
            # Internal telemetry: kept OUT of the script output, one click away.
            _p_badge = "🟢 In Duration Budget" if not d.get("is_over_budget") else "🔴 Over Budget"
            _timing_rows.append(
                f"Script {d_idx}: {d.get('w_cnt', '?')} spoken words "
                f"(recommended ~{d.get('recommended_words', '?')}w, max {d.get('max_words', '?')}w) • {_p_badge}"
            )
        if any(d.get("is_over_budget") for d in dialogues):
            st.caption("⚠️ A script exceeded the duration word budget — see timing details.")
        if _timing_rows:
            with st.expander("⏱️ Timing telemetry (internal details)", expanded=False):
                for _row in _timing_rows:
                    st.caption(_row)

    elif step_num == 4:
        st.markdown("### 🎬 Step 4: Scene Storyboards & 9:16 Video Prompts")
        _used_chars_4 = step_state.get("finalized_characters") or []
        _used_scenes_4 = step_state.get("finalized_scenes") or []
        if _used_chars_4 or _used_scenes_4:
            with st.expander("🎭 Characters & 📍 Scenes from Step 2 driving this storyboard", expanded=False):
                if _used_chars_4:
                    st.markdown("**Characters in use:**")
                    for _ch4 in _used_chars_4:
                        st.markdown(f"• **{_ch4.name}** (`{_ch4.role_or_job}`)")
                if _used_scenes_4:
                    st.markdown("**Scene locations in use:**")
                    for _sc4 in _used_scenes_4:
                        st.markdown(f"• **{_sc4.location_name}**")
        scripts = step_state.get("scripts", [])
        if scripts:
            s0 = scripts[0]
            v_verif = getattr(s0, "video_verification", None)
            if v_verif:
                st.caption(f"Feasibility Score: {v_verif.feasibility_score}% • Continuity: {v_verif.temporal_consistency}")
            for sc in s0.scenes:
                st.markdown(f"**BEAT {sc.scene_number}** [{sc.timestamp}] — **{sc.character}**")
                st.markdown(f"**🎬 Action:** {clean_beat_action(sc.visual_b_roll)}")
                if sc.on_screen_text:
                    st.caption(f"🔖 Overlay: {sc.on_screen_text}")
                if sc.audio_sfx:
                    st.caption(f"🔊 SFX: {sc.audio_sfx}")
                if sc.video_prompt:
                    st.text_area("Veo 9:16 Cinematic Prompt", value=sc.video_prompt.visual_prompt_ai, height=65, disabled=True, key=f"{key_prefix}step4_vp_view_{sc.scene_number}")


def _render_input_prompts(step_state, key_prefix=""):
    """Show the exact input prompt(s) sent to the AI for a completed step."""
    prompts = step_state.get("input_prompts") or []
    if not prompts:
        return
    with st.expander(f"🔍 View Input Prompt sent to AI ({len(prompts)})", expanded=False):
        for _pi, _p in enumerate(prompts, 1):
            _tmpl = _p.get("template", "")
            _ptxt = _p.get("prompt", "")
            _label = f"📝 Prompt {_pi}: {_tmpl}" if _tmpl else f"📝 Prompt {_pi}"
            with st.expander(_label, expanded=(len(prompts) == 1)):
                _nlines = _ptxt.count("\n") + 1
                _h = max(140, min(560, 40 + _nlines * 15))
                st.text_area(
                    "Input prompt", value=_ptxt, height=_h, disabled=True,
                    key=f"{key_prefix}input_prompt_{_pi}", label_visibility="collapsed",
                )

with col_output:
    st.markdown('<div class="ios-section-label">Preview</div>', unsafe_allow_html=True)

    if st.session_state.get("run_requested"):
        st.session_state.run_requested = False
        with st.status("Generating…", expanded=True) as status_box:
            progress_bar = st.progress(0)
            status_text = st.empty()
            try:
                pipeline = reel_workflow.run_stream(
                    news_input=st.session_state.run_topic,
                    scenario=st.session_state.run_scenario,
                    batch_size=st.session_state.chosen_batch_count,
                    target_seconds=st.session_state.chosen_duration,
                    engine_mode=st.session_state.chosen_engine_mode,
                    max_retries=st.session_state.chosen_max_retries,
                    preferred_angle=st.session_state.chosen_angle,
                    character_count=st.session_state.chosen_character_count,
                    scene_style=st.session_state.chosen_scene_style,
                    preferred_tone=st.session_state.chosen_tone,
                    sample_story=st.session_state.get("run_sample_story", ""),
                )
                for step in pipeline:
                    step_num = step.get("step", 1)
                    total_steps = step.get("total_steps", 5)
                    progress_bar.progress(min(1.0, step_num / total_steps))
                    status_text.caption(f"{step['agent']}")
                    if step.get("completed"):
                        st.session_state.batch_result = step["data"]["batch_result"]
                        st.session_state.generation_error = None
                        st.session_state.selected_script_idx = 0
                        save_config("selected_script_index", 0)
                        progress_bar.progress(1.0)
                        status_box.update(label="Ready", state="complete", expanded=False)
            except Exception as e:
                st.session_state.batch_result = None
                st.session_state.selected_script_idx = 0
                st.session_state.generation_error = {
                    "message": str(e),
                    "engine_mode": st.session_state.get("chosen_engine_mode", ""),
                    "partial_output": getattr(e, "partial_output", "") or "",
                }
                status_box.update(label="Failed", state="error")

    if st.session_state.get("stepwise_active") and st.session_state.get("stepwise_run_requested"):
        st.session_state.stepwise_run_requested = False
        curr_step = st.session_state.get("stepwise_current_step", 1)
        step_model = st.session_state.get("stepwise_step_model", st.session_state.chosen_engine_mode)
        extra_inst = st.session_state.get("stepwise_extra_instruction", "")

        step_titles = {
            1: "Stage 1: Wire Fact Validation",
            2: "Stage 2: Character & Scene Finalisation",
            3: "Stage 3: Dialogue Writing & Calibration",
            4: "Stage 4: Storyboards & AI Video Prompts",
            5: "Stage 5: Quality Gate & Editorial Sign-Off",
        }

        with st.status(f"Executing {step_titles.get(curr_step, f'Step {curr_step}')} with {ENGINE_NAMES_REV.get(step_model, step_model)}…", expanded=True) as s_box:
            try:
                if curr_step == 1:
                    st_res = reel_workflow.run_step_1(
                        news_input=st.session_state.run_topic,
                        scenario=st.session_state.run_scenario,
                        batch_size=st.session_state.chosen_batch_count,
                        target_seconds=st.session_state.chosen_duration,
                        engine_mode=step_model,
                        max_retries=st.session_state.chosen_max_retries,
                        preferred_angle=st.session_state.chosen_angle,
                        character_count=st.session_state.chosen_character_count,
                        scene_style=st.session_state.chosen_scene_style,
                        preferred_tone=st.session_state.chosen_tone,
                        sample_story=st.session_state.get("run_sample_story", ""),
                        extra_instruction=extra_inst,
                    )
                elif curr_step == 2:
                    st_res = reel_workflow.run_step_2(
                        state=st.session_state.stepwise_state,
                        engine_mode=step_model,
                        extra_instruction=extra_inst,
                    )
                elif curr_step == 3:
                    st_res = reel_workflow.run_step_3(
                        state=st.session_state.stepwise_state,
                        engine_mode=step_model,
                        extra_instruction=extra_inst,
                    )
                elif curr_step == 4:
                    st_res = reel_workflow.run_step_4(
                        state=st.session_state.stepwise_state,
                        engine_mode=step_model,
                        extra_instruction=extra_inst,
                    )
                elif curr_step == 5:
                    st_res = reel_workflow.run_step_5(
                        state=st.session_state.stepwise_state,
                        engine_mode=step_model,
                        extra_instruction=extra_inst,
                    )
                    st.session_state.batch_result = st_res["batch_result"]
                    st.session_state.selected_script_idx = 0
                    save_config("selected_script_index", 0)

                st.session_state.stepwise_state = st_res
                st.session_state.setdefault("stepwise_completed_steps", {})[curr_step] = st_res
                st.session_state.stepwise_extra_instruction = ""
                st.session_state.generation_error = None
                s_box.update(label=f"{step_titles.get(curr_step, f'Step {curr_step}')} Ready", state="complete", expanded=False)
                st.rerun()
            except Exception as e:
                st.session_state.stepwise_run_requested = False
                st.session_state.generation_error = {
                    "message": str(e),
                    "engine_mode": step_model,
                    "partial_output": getattr(e, "partial_output", "") or "",
                    "step": curr_step,
                }
                s_box.update(label=f"Step {curr_step} Failed", state="error")

    if st.session_state.get("generation_error"):
        failure = st.session_state.generation_error
        st.error("Script generation failed")
        st.write(f"Selected model: **{ENGINE_NAMES_REV.get(failure['engine_mode'], failure['engine_mode'])}**")
        st.warning(failure["message"])
        if failure.get("partial_output"):
            st.markdown("#### Partial model output")
            st.text_area(
                "Output received before failure",
                value=failure["partial_output"],
                height=180,
                disabled=True,
                label_visibility="collapsed",
            )
        if st.session_state.get("stepwise_active"):
            err_step = failure.get("step", st.session_state.get("stepwise_current_step", 1))
            st.caption(f"Failure occurred during Step {err_step}. You can change the model and retry, or go back to the previous stage.")
            if err_step > 1:
                c_retry, c_back, c_abort = st.columns([1, 1, 1])
            else:
                c_retry, c_abort = st.columns([1, 1])
                c_back = None
            with c_retry:
                if st.button(f"🔄 Retry Step {err_step}", key="retry_stepwise_step", type="primary", use_container_width=True):
                    st.session_state.generation_error = None
                    st.session_state.stepwise_run_requested = True
                    st.rerun()
            if c_back is not None:
                with c_back:
                    if st.button(f"⬅️ Back to Step {err_step - 1}", key="back_stepwise_step", use_container_width=True):
                        st.session_state.generation_error = None
                        st.session_state.stepwise_run_requested = False
                        st.session_state.stepwise_current_step = err_step - 1
                        st.rerun()
            with c_abort:
                if st.button("❌ Exit Step-Wise", key="cancel_stepwise_err", use_container_width=True):
                    st.session_state.generation_error = None
                    st.session_state.stepwise_active = False
                    st.rerun()
        else:
            st.caption("No script was generated. Resolve the model issue and try again.")
            if st.button("Try again", key="retry_failed_generation", use_container_width=True):
                st.session_state.generation_error = None
                st.session_state.batch_result = None
                st.session_state.run_requested = True
                st.rerun()

    step_names = [
        "1. Facts & Wire",
        "2. Character Finalisation",
        "3. Spoken Dialogue",
        "4. Storyboard & Video",
        "5. Integration & Validation",
    ]

    def _stepwise_go_back(target_step: int):
        """Go back to a completed step for fine-tuning (works on success too).
        Restores the state snapshot taken right after that step, drops later
        snapshots, and clears the final result so downstream stages re-run."""
        comp = st.session_state.get("stepwise_completed_steps", {})
        snap = comp.get(target_step)
        if snap is not None:
            st.session_state.stepwise_state = copy.deepcopy(snap)
        for k in [k for k in list(comp.keys()) if k > target_step]:
            comp.pop(k, None)
        st.session_state.batch_result = None
        st.session_state.generation_error = None
        st.session_state.stepwise_run_requested = False
        st.session_state.stepwise_current_step = target_step

    if st.session_state.get("stepwise_active") and not st.session_state.get("batch_result") and not st.session_state.get("generation_error"):
        step_state = st.session_state.get("stepwise_state")
        curr_step = st.session_state.get("stepwise_current_step", 1)

        st.markdown('<div class="ios-section-label">Step-Wise Pipeline Checkpoint</div>', unsafe_allow_html=True)
        cols_step = st.columns(5)
        for idx, (c_st, name) in enumerate(zip(cols_step, step_names), 1):
            with c_st:
                if idx < curr_step:
                    st.markdown(f'<div style="text-align:center; font-size:0.75rem; font-weight:700; color:#34c759; padding:4px 0; border-bottom:3px solid #34c759;">✓ {name}</div>', unsafe_allow_html=True)
                elif idx == curr_step:
                    st.markdown(f'<div style="text-align:center; font-size:0.75rem; font-weight:700; color:#0071e3; padding:4px 0; border-bottom:3px solid #0071e3;">▶ {name}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="text-align:center; font-size:0.75rem; font-weight:500; color:#8e8e93; padding:4px 0; border-bottom:3px solid #d2d2d7;">{name}</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

        if step_state:
            with st.container(border=True):
                _render_step_output(curr_step, step_state, key_prefix="main_")
                _render_input_prompts(step_state, key_prefix="mainp_")

            if curr_step > 1:
                with st.expander(f"📜 View Previous Completed Steps (1 to {curr_step - 1})"):
                    comp_steps = st.session_state.get("stepwise_completed_steps", {})
                    for s_num in range(1, curr_step):
                        past_st = comp_steps.get(s_num)
                        if past_st:
                            with st.expander(f"Step {s_num}: {step_names[s_num - 1]} — full output", expanded=False):
                                _render_step_output(s_num, past_st, key_prefix=f"hist{s_num}_")
                                _render_input_prompts(past_st, key_prefix=f"histp{s_num}_")

            st.markdown('<div class="ios-section-label" style="margin-top:14px;">Next Action &amp; Refinements</div>', unsafe_allow_html=True)
            with st.container(border=True):
                eng_labels = list(ENGINE_OPTIONS.keys())
                curr_model_key = st.session_state.get("stepwise_step_model", st.session_state.chosen_engine_mode)
                eng_idx = list(ENGINE_OPTIONS.values()).index(curr_model_key) if curr_model_key in ENGINE_OPTIONS.values() else 0
                
                c_lbl, c_sel = st.columns([3, 5])
                with c_lbl:
                    st.markdown('<div class="cfg-label">AI Model for Action</div>', unsafe_allow_html=True)
                with c_sel:
                    selected_model_name = st.selectbox(
                        "AI Model for Step",
                        eng_labels,
                        index=eng_idx,
                        label_visibility="collapsed",
                        key=f"step_model_select_{curr_step}",
                        help="Each step could change model in this mode. Select the AI model to execute the next step or re-run this step."
                    )
                chosen_step_engine = ENGINE_OPTIONS[selected_model_name]

                has_extra = st.checkbox(
                    "Provide extra instruction for current or next step",
                    key=f"extra_tick_{curr_step}",
                    help="Tick this box to provide custom instruction or steering prompts for the current step (re-run) or next step."
                )
                extra_text = ""
                apply_target = "next"
                if has_extra:
                    col_t1, col_t2 = st.columns([1, 1])
                    with col_t1:
                        apply_next = st.radio(
                            "Apply instruction to:",
                            ["Next Step ➡️", f"Current Step (Step {curr_step}) 🔄"],
                            horizontal=True,
                            key=f"apply_target_radio_{curr_step}"
                        )
                        apply_target = "next" if "Next" in apply_next else "current"
                    extra_text = st.text_area(
                        "Extra Instruction / Custom Guidance",
                        placeholder=f"Enter guidance for the model (e.g. {'focus on specific facts' if curr_step == 1 else 'make hooks punchier and witty' if curr_step == 2 else 'adjust character dialogue and banter' if curr_step == 3 else 'specify camera movements and locations'})...",
                        key=f"extra_instruction_input_{curr_step}",
                        height=75,
                    )

                if curr_step > 1:
                    c_back, c_proceed, c_rerun = st.columns([1, 1.3, 1])
                    with c_back:
                        if st.button(f"⬅️ Back to Step {curr_step - 1}", use_container_width=True, key=f"back_btn_{curr_step}"):
                            _stepwise_go_back(curr_step - 1)
                            st.rerun()
                else:
                    c_proceed, c_rerun = st.columns([1.3, 1])
                with c_proceed:
                    if curr_step < 4:
                        proceed_label = f"Proceed to Step {curr_step + 1} ➡️"
                    else:
                        proceed_label = "Integrate & Validate (Step 5) 🏁"

                    if st.button(proceed_label, type="primary", use_container_width=True, key=f"proceed_btn_{curr_step}"):
                        st.session_state.stepwise_step_model = chosen_step_engine
                        # If user typed feedback for next step, pass it
                        st.session_state.stepwise_extra_instruction = extra_text.strip() if (has_extra and apply_target == "next" and extra_text.strip()) else ""
                        st.session_state.stepwise_current_step = curr_step + 1
                        st.session_state.stepwise_run_requested = True
                        st.rerun()

                with c_rerun:
                    if st.button(f"🔄 Re-run Step {curr_step}", use_container_width=True, key=f"rerun_step_btn_{curr_step}"):
                        st.session_state.stepwise_step_model = chosen_step_engine
                        # When user clicks Re-run Step with extra instruction, always feed it as correction feedback
                        st.session_state.stepwise_extra_instruction = extra_text.strip() if (has_extra and extra_text.strip()) else ""
                        st.session_state.stepwise_run_requested = True
                        st.rerun()

    if st.session_state.get("batch_result"):
        res = st.session_state.batch_result
        if st.session_state.get("stepwise_active"):
            st.success("🎉 Step-Wise Reel Completed! All 5 stages verified and signed off by Chief Editor.")
            st.caption("Want to fine-tune an earlier stage? Go back — later stages will re-run on the refined output.")
            b_cols = st.columns(4)
            for _bi in range(4):
                with b_cols[_bi]:
                    if st.button(f"⬅️ Step {_bi + 1}", key=f"back_done_{_bi + 1}", use_container_width=True):
                        _stepwise_go_back(_bi + 1)
                        st.rerun()
            with st.expander("🪜 Review Step-by-Step Outputs (Steps 1 to 4)"):
                comp = st.session_state.get("stepwise_completed_steps", {})
                step_names_history = [
                    "1. Facts & Wire",
                    "2. Character Finalisation",
                    "3. Spoken Dialogue",
                    "4. Storyboard & Video",
                ]
                for s_num in [1, 2, 3, 4]:
                    past_st = comp.get(s_num)
                    if past_st:
                        with st.expander(f"Step {s_num}: {step_names_history[s_num - 1]} — full output", expanded=False):
                            _render_step_output(s_num, past_st, key_prefix=f"done{s_num}_")
                            _render_input_prompts(past_st, key_prefix=f"donep{s_num}_")
        if len(res.scripts) > 1:
            sel_id = st.radio(
                "Version",
                range(len(res.scripts)),
                index=min(st.session_state.selected_script_idx, len(res.scripts) - 1),
                format_func=lambda i: f"{i + 1}",
                horizontal=True,
            )
            if sel_id != st.session_state.selected_script_idx:
                st.session_state.selected_script_idx = sel_id
                save_config("selected_script_index", sel_id)

        if not getattr(res, "compliance_passed", True) and getattr(res, "retry_prompt_recommendation", None):
            st.warning(res.retry_prompt_recommendation)
            if st.button("🔄 Retry Generation with Recommended Settings", key="retry_compliance_btn", type="primary", use_container_width=True):
                st.session_state.run_requested = True
                st.rerun()

        if getattr(res, "sample_story", None):
            with st.expander("⭐ Sample Story Reference (Applied with Highest Precedence)"):
                st.info(f"The screenplay was adapted from this sample story with precedence over instructions:\n\n{res.sample_story}")

        curr_script = res.scripts[st.session_state.selected_script_idx]
        d_budget = get_duration_budget(curr_script.target_duration_sec)
        max_w = getattr(curr_script, "max_words", d_budget["max_words"]) or d_budget["max_words"]
        rec_w = getattr(curr_script, "recommended_words", d_budget["recommended_words"]) or d_budget["recommended_words"]
        w_cnt = curr_script.word_count
        pacing_ok = w_cnt <= max_w
        gate_ok = curr_script.video_verification.passed


        st.markdown("### 🎬 Final Screenplay")
        st.caption("Your chosen format — 9:16 vertical reel · SCENE DETAIL · CHARACTERS & CLOTHING · sequential beats.")
        col_c1, col_c2 = st.columns([1, 1])
        with col_c1:
            include_overlays = st.checkbox("Include Text Overlay (Optional)", value=st.session_state.get("include_overlays", True), key="inc_overlays_chk", help="Toggle whether Text Overlay (Optional) lines appear in the screenplay based on user preference.")
        with col_c2:
            include_sfx = st.checkbox("Include Audio/SFX", value=st.session_state.get("include_sfx", True), key="inc_sfx_chk", help="Toggle whether Audio/SFX cues appear in the screenplay.")

        pro_screenplay = format_professional_screenplay(curr_script, st.session_state.get("run_topic", ""), include_overlays=include_overlays, include_sfx=include_sfx)
        plain_script = format_plain_script(curr_script, include_overlays=include_overlays, include_sfx=include_sfx)
        teleprompter_text = format_teleprompter_text(curr_script)
        visual_prompts_text = format_director_prompts(curr_script)

        with st.container(border=True):
            st.markdown(pro_screenplay)

        st.markdown("### 📋 Copy Full Screenplay Content")

        tab_screenplay, tab_teleprompter, tab_plain, tab_visuals = st.tabs([

            "🎬 Full Screenplay (Markdown)",
            "🎙️ Spoken Dialogue Only",
            "📝 Clean Text Script",
            "🎥 Director's Prompts",
        ])
        with tab_screenplay:
            st.caption("Click the copy icon in the top right corner of the box below to copy the complete professional screenplay in Markdown:")
            st.code(pro_screenplay, language="markdown")
        with tab_teleprompter:
            st.caption("Click the copy icon below to copy Devanagari Hindi dialogue only (ready for Voiceover / Teleprompter):")
            st.code(teleprompter_text, language="text")
        with tab_plain:
            st.caption("Click the copy icon below to copy clean plain-text script:")
            st.code(plain_script, language="text")
        with tab_visuals:
            st.caption("Click the copy icon below to copy AI video generation prompts:")
            st.code(visual_prompts_text, language="markdown")

        st.markdown("##### ⚡ Quick Select All & Copy (Full Screenplay Markdown)")
        st.caption("Click inside and press Cmd+A / Ctrl+A, then Cmd+C / Ctrl+C to copy the full screenplay text:")
        st.text_area("Full Screenplay Markdown", value=pro_screenplay, height=260, label_visibility="collapsed")

        d1, d2, d3 = st.columns(3)
        with d1:
            st.download_button("Screenplay (.md)", data=pro_screenplay, file_name=f"screenplay_{curr_script.target_duration_sec}s.md", mime="text/markdown", use_container_width=True)
        with d2:
            st.download_button("Teleprompter (.txt)", data=teleprompter_text, file_name=f"teleprompter_{curr_script.target_duration_sec}s.txt", mime="text/plain", use_container_width=True)
        with d3:
            st.download_button("Full JSON", data=res.model_dump_json(indent=2), file_name=f"reel_{curr_script.target_duration_sec}s.json", mime="application/json", use_container_width=True)

        with st.expander("Analysis"):
            st.caption(f"{res.verification.confidence_score}% · {res.verification.verification_summary}")
            if res.verification.sources:
                for s in res.verification.sources[:3]:
                    st.markdown(f"- [{s.title[:48]}]({s.link})")
            st.caption(f"{w_cnt}/{max_w} words · Visual Feasibility: {curr_script.video_verification.feasibility_score}%")
            if res.audit_report:
                st.caption(f"{res.audit_report.total_failures_detected} issues · {res.audit_report.total_retries_resolved} healed")

        if getattr(res, "sub_instructions", None):
            with st.expander("👑 Master Agent Sub-Instructions"):
                for ag_name, sub_inst in res.sub_instructions.items():
                    st.markdown(f"**{ag_name.replace('_', ' ').title()}**")
                    st.text(sub_inst)
    else:
        st.markdown(
            """
            <div class="phone">
                <div class="phone-empty">No preview</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
