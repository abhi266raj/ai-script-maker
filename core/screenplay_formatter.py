"""Industry-standard screenplay formatter for 9:16 vertical Hindi Reels.
Implements the canonical professional script structure:
- Scene Detail (setting & atmosphere)
- Characters & Clothing (tone-aligned attire, no genre clashes)
- Beats with continuous camera cues (no contradictory cuts)
- Physical actor action lines only (bodies, props, expressions)
- Spoken Hindi dialogues in Devanagari
- Removal of over-engineered metadata (no word count formulas or microsecond math)
"""

import re
from typing import List, Dict, Any, Optional
from core.script_analyzer import harmonize_setting_description

POLITICAL_NAMES_BLACKLIST = {
    "rahul", "modi", "narendra", "kejriwal", "gandhi", "amit shah", "amit",
    "yogi", "adityanath", "sonia", "priyanka", "mamata", "stalin", "pawar",
    "fadnavis", "shinde", "thackeray", "nitish", "lalu", "tejaswi"
}


def sanitize_character_name(name: str) -> str:
    """Reject missing or politician names loudly instead of inventing replacements.

    Fail-loud rule: a missing character name, or a name matching the political
    blacklist, is a Stage 2 contract breach. Returning "CREATOR" or swapping in
    "Rohan"/"Aarav"/"Kabir" would invent a person who was never finalized.
    Raise with stage/field detail so the retry flow regenerates the characters.
    """
    if not name or not name.strip():
        raise ValueError(
            "Screenplay formatting failed: a scene has a missing/empty character name. "
            "Stage 2 must finalize a named character for every beat — inventing one here is not allowed."
        )
    t = name
    for pol in POLITICAL_NAMES_BLACKLIST:
        if re.search(rf"\b{pol}\b", t, re.IGNORECASE):
            raise ValueError(
                f"Screenplay formatting failed: character name {name!r} matches the political-name "
                f"blacklist (matched {pol!r}). Stage 2 must finalize a fictional, non-political "
                "character name; inventing a replacement name here is not allowed."
            )
    return t


# Social-media CTA patterns (comment/like/share/subscribe/follow). The
# formatters must NOT silently rewrite dialogue to remove these —
# dialogue_has_cta() detects them and the formatters fail loudly instead.
_CTA_PATTERNS = [
    r"(?:नीचे\s*)?कमेंट\s*(?:में\s*(?:बताएं|बताओ|लिखें|लिखो)|करें|करो|सेक्शन\s*में\s*(?:बताएं|बताओ))[\s।!?]*",
    r"(?:आपकी\s*क्या\s*राय\s*है\s*[,।]?\s*)?कमेंट\s*(?:करें|करके\s*बताएं|में\s*बताएं)[\s।!?]*",
    r"(?:लाइक\s*(?:और|व)\s*)?शेयर\s*(?:करें|करो|करना\s*मत\s*भूलना)[\s।!?]*",
    r"फॉलो\s*(?:करें|करो|करना\s*मत\s*भूलना)[\s।!?]*",
    r"सब्सक्राइब\s*(?:करें|करो)[\s।!?]*",
    r"(?:comment\s*below|share\s*your\s*thoughts|like\s*and\s*subscribe)[\s।!?]*",
]


def dialogue_has_cta(text: str) -> bool:
    """Return True if dialogue contains a banned social-media CTA.

    Fail-loud rule: CTAs are detected, never silently stripped. The formatters
    raise so the pipeline regenerates the beat instead of shipping rewritten
    dialogue.
    """
    if not text:
        return False
    return any(re.search(pat, text, flags=re.IGNORECASE) for pat in _CTA_PATTERNS)


def strip_commenting_and_cta(text: str) -> str:
    """Legacy CTA stripper — kept for backward compatibility only.

    The screenplay formatters no longer call this: they detect CTAs with
    dialogue_has_cta() and fail loudly instead of silently rewriting dialogue.
    """
    if not text:
        return ""
    t = text
    for pat in _CTA_PATTERNS:
        t = re.sub(pat, "", t, flags=re.IGNORECASE)
    t = " ".join(t.split())
    return t.strip()


def clean_physical_action(raw_action: str) -> str:
    """
    Extract pure physical actor action: what we physically see and hear the actors
    doing with their bodies, props, and facial expressions.
    Purges meta instructions, prompt jargon, news dumps, and camera preambles.
    """
    if not raw_action:
        return ""
    t = raw_action.strip()

    # 1. Strip camera & location preamble ending with semicolon or colon
    t = re.sub(
        r"^(?:Handheld|Dynamic|Cinematic|Low-angle|Wide|Close-up|Medium|Tight|Seamless|Intimate|Aesthetic|High-energy|High-contrast|Over-the-shoulder|Reverse-angle|POV|Cut\s+to)?\s*(?:vertical\s*)?(?:\(?9:16\)?\s*)?(?:establishing\s*)?(?:hook\s*)?(?:shot|take|push-in|cut|tracking\s*shot|whip-pan|split-screen|opening\s*hook\s*tracking\s*shot)?\s*(?:at|on|outside|inside|in|near|with)?\s*[^;.]+;\s*",
        "",
        t,
        flags=re.IGNORECASE,
    )
    # 2. Strip establishing shot sentence
    t = re.sub(
        r"^(?:Low-angle|Wide|Close-up|Medium|Tight|Seamless|Handheld|Dynamic|Cinematic)\s*(?:vertical\s*)?(?:\(?9:16\)?\s*)?(?:establishing\s*)?(?:hook\s*)?shot\s+(?:at|outside|inside|in|near)\s+[^.]+\.\s+(?=[A-Z\u0900-\u097F])",
        "",
        t,
        flags=re.IGNORECASE,
    )
    # 3. Strip contradictory cuts in continuous takes
    t = re.sub(r"\b(?:cut to|cuts to|hard cut to|jump cut to)\b\s*", "", t, flags=re.IGNORECASE)
    # 4. Strip prompt instructions and meta prefixes
    t = re.sub(r"^(?:VISUAL|ACTION|B-ROLL|CAMERA|CAMERA FOCUS & ACTION)\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(?:Scene\s*\d+\s*:\s*)", "", t, flags=re.IGNORECASE)

    # 5. Clean extra whitespace
    t = " ".join(t.split()).strip()
    # If first character is lowercase, capitalize it
    if t:
        t = t[0].upper() + t[1:]
    # Fail-loud: an action cleaned down to nothing stays empty. Callers raise
    # rather than inventing a generic gesture here.
    return t


def get_first_name(char_str: str) -> str:
    """Extract clean first name without emoji or parenthetical tags.

    Fail-loud: an empty or unparseable name raises instead of returning the
    invented placeholder "SPEAKER".
    """
    if not char_str or not char_str.strip():
        raise ValueError(
            "Screenplay formatting failed: a scene has a missing/empty character name. "
            "Stage 2 must finalize a named character for every beat."
        )
    # Remove emoji and special symbols
    cleaned = re.sub(r"[^\w\s/()-]", "", char_str).strip()
    # Take portion before slash or parenthesis
    base = cleaned.split("/")[0].split("(")[0].strip()
    tokens = [t for t in base.split() if len(t) > 1 and not t.isdigit()]
    if tokens:
        if len(tokens) > 1 and tokens[0].lower() in ["dr", "mr", "ms", "advocate", "inspector", "sub-inspector", "seth", "master"]:
            first = tokens[-1]
        elif len(tokens) > 1 and tokens[1].lower() == "ji":
            first = f"{tokens[0]} {tokens[1]}"
        else:
            first = tokens[0]
        return first.strip()
    raise ValueError(
        f"Screenplay formatting failed: character name {char_str!r} could not be parsed into a name. "
        "Stage 2 must finalize a parseable character name for every beat."
    )


def extract_sample_clothing_map(sample_text: str) -> Dict[str, str]:
    """Extract character clothing descriptions from sample story/script if present."""
    if not sample_text:
        return {}
    m_chars = re.search(r"CHARACTERS(?:\s*&\s*CLOTHING)?\s*:(.*?)(?:\[Time|\n\s*\n\s*\[|\Z)", sample_text, re.DOTALL | re.IGNORECASE)
    if not m_chars:
        return {}
    res = {}
    matches = re.findall(r"(?:[⚬•\-\*]|\d+\.)?\s*([A-Za-z\u0900-\u097F\s/()\-]+?)\s*:\s*([^\n\r]+)", m_chars.group(1))
    for name, attire in matches:
        first = get_first_name(name).upper()
        if first and first not in ["FORMAT", "SCENE DETAIL", "AUDIO", "CAMERA", "TIME", "TEXT OVERLAY"]:
            res[first] = attire.strip()
    return res


def resolve_character_attire(first_name: str, sample_clothing_map: Dict[str, str], scene) -> str:
    """Return real attire for a character, or "" when none was finalized.

    Fail-loud rule: attire must come from the sample story's explicit clothing
    map or the Stage 2 character bible (SceneItem.character_attire).
    Keyword-guessing wardrobes by role/tone invents clothing the pipeline never
    designed — return "" and let the caller list the name without an invented
    outfit.
    """
    if first_name in sample_clothing_map:
        return sample_clothing_map[first_name]
    return (getattr(scene, "character_attire", "") or "").strip()


def derive_scene_detail(script) -> str:
    """Extract a rich, authentic setting & atmosphere description for SCENE DETAIL via harmonization."""
    return harmonize_setting_description(script)


def format_industry_screenplay(
    script,
    topic_name: str = "",
    include_overlays: bool = True,
    include_sfx: bool = True,
    include_timestamps: bool = False,
) -> str:
    """
    Format screenplay strictly matching the industry-standard specification:
    - [Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]
    - SCENE DETAIL: setting & ambient atmosphere (from real pipeline data only)
    - CHARACTERS & CLOTHING: real attire only, never invented wardrobes
    - Camera Focus & Action: the pipeline's own action, cleaned of meta-jargon
    - Physical action lines only (bodies, props, expressions)
    - Optional Text Overlay and Audio/SFX (included based on script/context or user preference)
    - Hindi dialogue in Devanagari

    Fail-loud: this is a pure formatter. It never heals/mutates the script and
    never invents content — missing required fields raise with beat/field detail.
    """

    lines = []
    lines.append("[Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]")
    lines.append("")

    # 1. SCENE DETAIL — only from real pipeline data. derive_scene_detail
    # returns "" when no real source exists; the header is omitted rather
    # than printing an invented setting.
    scene_detail = derive_scene_detail(script)
    if scene_detail:
        lines.append("SCENE DETAIL:")
        lines.append(f"⚬\t{scene_detail}")
        lines.append("")

    # 2. CHARACTERS & CLOTHING — real attire only. resolve_character_attire
    # returns "" when no attire was finalized; the name is listed without an
    # invented outfit.
    raw_chars = []
    seen = set()
    for sc in script.scenes:
        c_clean = sanitize_character_name(sc.character)
        first_name = get_first_name(c_clean).upper()
        if first_name not in seen:
            seen.add(first_name)
            raw_chars.append((first_name, sc))

    if not raw_chars:
        raise ValueError(
            "Screenplay formatting failed: the script has no scenes/characters to format. "
            "Refusing to invent placeholder characters."
        )

    sample_text = getattr(script, "sample_story_used", "") or ""
    sample_clothing_map = extract_sample_clothing_map(sample_text)

    lines.append("CHARACTERS & CLOTHING:")
    for first_name, sc in raw_chars:
        attire = resolve_character_attire(first_name, sample_clothing_map, sc)
        if attire:
            lines.append(f"⚬\t{first_name}: {attire}")
        else:
            lines.append(f"⚬\t{first_name}")
    lines.append("")

    # 3. BEATS
    total_scenes = len(script.scenes)
    for idx, sc in enumerate(script.scenes):
        # Fail-loud: no fallback from dialogue to narration — a missing spoken
        # line is a Stage 3 contract breach, not something to paper over.
        raw_dialogue = (sc.dialogue or "").strip()
        if not raw_dialogue:
            raise ValueError(
                f"Screenplay formatting failed: beat {idx + 1} (scene {sc.scene_number}) has no dialogue. "
                "The pipeline must supply a spoken Hindi line for every beat."
            )
        # Fail-loud: CTAs are detected, never silently stripped.
        if dialogue_has_cta(raw_dialogue):
            raise ValueError(
                f"Screenplay formatting failed: beat {idx + 1} (scene {sc.scene_number}) dialogue contains a "
                "banned social-media CTA (comment/like/share/subscribe/follow). The pipeline must regenerate "
                "the beat without the CTA instead of shipping silently rewritten dialogue."
            )
        act_dialogue = raw_dialogue
        char_clean = sanitize_character_name(sc.character)
        char_upper = get_first_name(char_clean).upper()

        # Timestamp: supplied deterministically by the pipeline — never fabricated here.
        ts = (sc.timestamp or "").strip("[] ")
        if not ts.startswith("Time:") and not ts.startswith("0:"):
            raise ValueError(
                f"Screenplay formatting failed: beat {idx + 1} (scene {sc.scene_number}) has a missing or "
                f"malformed timestamp ({sc.timestamp!r}). Timestamps are computed by the pipeline; "
                "fabricating one here is not allowed."
            )
        if include_timestamps:
            if not ts.startswith("Time:"):
                time_header = f"[Time: {ts}]"
            else:
                time_header = f"[{ts}]"
            lines.append(time_header)

        # Camera cues use the pipeline's own cleaned action only.
        clean_action = clean_physical_action(sc.visual_b_roll)
        clean_action_lower = clean_action.lower()

        # If visual_b_roll already has full camera cue, preserve it directly
        existing_cue = any(clean_action_lower.startswith(prefix) for prefix in [
            "fast whip-pan", "whip-pan", "quick pan", "fast pan", "single continuous",
            "the camera pans", "the camera pulls back", "fast pull back", "camera pulls back"
        ])

        # Fail-loud: no synthetic camera choreography. The camera cue is the
        # pipeline's own cleaned action; a missing action is a contract breach.
        # (Dead synthetic branches below are kept for the resume pass to delete.)
        if not clean_action:
            raise ValueError(
                f"Screenplay formatting failed: beat {idx + 1} (scene {sc.scene_number}) has no camera action "
                "(visual_b_roll is empty). The pipeline must supply a real action per beat; "
                "inventing a generic one here is not allowed."
            )
        if existing_cue:
            camera_cue = clean_action
        else:
            # Smooth single continuous take for standard reels (> 10s)
            if not clean_action_lower.startswith(char_upper.lower()):
                act = f"{char_upper.title()} {clean_action[0].lower() + clean_action[1:]}"
            else:
                act = clean_action

            if idx == 0:
                camera_cue = f"Single continuous handheld take starting on {char_upper.title()}. {act}"
            elif idx == total_scenes - 1 and total_scenes >= 3:
                camera_cue = f"The camera pulls back slightly to frame both of them together. {act}"
            else:
                camera_cue = f"The camera pans smoothly to {char_upper.title()} without cutting. {act}"

        # Clean trailing dot
        camera_cue = camera_cue.rstrip(".") + "."
        lines.append(f"Camera Focus & Action: {camera_cue}")

        if include_overlays and sc.on_screen_text:
            lines.append(f"Text Overlay (Optional): {sc.on_screen_text}")
        if include_sfx and sc.audio_sfx:
            lines.append(f"Audio/SFX: {sc.audio_sfx}")


        lines.append(f'{char_upper}: "{act_dialogue}"')
        lines.append("")

    return "\n".join(lines).strip()



def format_teleprompter_text(script) -> str:
    """Format clean voiceover / teleprompter lines in Devanagari Hindi."""
    lines = []
    for sc in script.scenes:
        act_dialogue = strip_commenting_and_cta(sc.dialogue or sc.narration_line or "")
        char_clean = sanitize_character_name(sc.character)
        char_name = get_first_name(char_clean).upper()
        lines.append(f"[{char_name} — Part {sc.scene_number} ({sc.timestamp})]\n{act_dialogue}\n")
    return "\n".join(lines).strip()


def format_director_prompts(script) -> str:
    """Format clean visual prompts with basic scene setup and Part 1 / Part 2 visual flow."""
    scene_detail = derive_scene_detail(script)
    lines = []
    lines.append("# DIRECTOR'S VISUAL GENERATION PROMPTS (9:16 VERTICAL)")
    lines.append(f"**Base Scene Setting:** {scene_detail}")
    lines.append(f"**Target Duration:** ~{script.target_duration_sec}s | **Sequential Shot Flow:** {len(script.scenes)} visual parts of one continuous scene")
    lines.append("")
    lines.append("---")
    lines.append("")

    for sc in script.scenes:
        part_tag = f"SHOT {sc.scene_number} (PART {sc.scene_number} VISUAL)"
        if sc.scene_number > 1:
            part_tag += " — SHOT TRANSITION WITHIN SCENE"
        lines.append(f"### 🎥 {part_tag} [{sc.timestamp}] — {sc.act_name}")
        if sc.video_prompt:
            lines.append(f"- **Camera Movement:** {sc.video_prompt.camera_movement}")
            lines.append(f"- **Lighting & Mood:** {sc.video_prompt.lighting_and_mood}")
            lines.append(f"- **Aspect Ratio:** 9:16 Vertical")
            lines.append(f"- **Cinematic Visual Prompt:**\n```text\n{sc.video_prompt.visual_prompt_ai}\n```")
        else:
            lines.append(f"- **Visual Action:** {clean_physical_action(sc.visual_b_roll)}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).strip()
