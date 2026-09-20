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
from core.script_analyzer import harmonize_setting_description, analyze_and_heal_script

POLITICAL_NAMES_BLACKLIST = {
    "rahul", "modi", "narendra", "kejriwal", "gandhi", "amit shah", "amit",
    "yogi", "adityanath", "sonia", "priyanka", "mamata", "stalin", "pawar",
    "fadnavis", "shinde", "thackeray", "nitish", "lalu", "tejaswi"
}


def sanitize_character_name(name: str) -> str:
    """Ensure characters never use politician names to prevent policy flags."""
    if not name:
        return "CREATOR"
    t = name
    for pol in POLITICAL_NAMES_BLACKLIST:
        if re.search(rf"\b{pol}\b", t, re.IGNORECASE):
            t = re.sub(rf"\b{pol}\b", "Rohan", t, flags=re.IGNORECASE)
            t = t.replace("राहुल", "रोहन").replace("अमित", "आरव").replace("मोदी", "कबीर")
    return t


def strip_commenting_and_cta(text: str) -> str:
    """Purge social media commenting, subscriber calls, and meta-CTAs from dialogue."""
    if not text:
        return ""
    t = text
    patterns = [
        r"(?:नीचे\s*)?कमेंट\s*(?:में\s*(?:बताएं|बताओ|लिखें|लिखो)|करें|करो|सेक्शन\s*में\s*(?:बताएं|बताओ))[\s।!?]*",
        r"(?:आपकी\s*क्या\s*राय\s*है\s*[,।]?\s*)?कमेंट\s*(?:करें|करके\s*बताएं|में\s*बताएं)[\s।!?]*",
        r"(?:लाइक\s*(?:और|व)\s*)?शेयर\s*(?:करें|करो|करना\s*मत\s*भूलना)[\s।!?]*",
        r"फॉलो\s*(?:करें|करो|करना\s*मत\s*भूलना)[\s।!?]*",
        r"सब्सक्राइब\s*(?:करें|करो)[\s।!?]*",
        r"(?:comment\s*below|share\s*your\s*thoughts|like\s*and\s*subscribe)[\s।!?]*",
    ]
    for pat in patterns:
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
        return "Delivers spoken lines with expressive gestures."
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
    return t or "Delivers spoken lines with expressive comedic gestures."


def get_first_name(char_str: str) -> str:
    """Extract clean first name without emoji or parenthetical tags."""
    if not char_str:
        return "SPEAKER"
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
    return "SPEAKER"


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


def get_character_attire(char_raw: str, tone: str = "Funny & Relatable") -> str:
    """Derive authentic character wardrobe matching role and genre without tone clashes."""
    c_lower = char_raw.lower()
    is_comedy = any(w in tone.lower() for w in ["funny", "comedy", "sarcasm", "ह्यूमर", "मजाकिया", "relatable"])

    # Avoid tragic tone clash in comedy
    if is_comedy:
        if "auto" in c_lower or "driver" in c_lower or "चालक" in c_lower:
            return "Everyday street casual wear or khaki driver uniform shirt."
        if "delivery" in c_lower or "rider" in c_lower or "राइडर" in c_lower:
            return "Delivery company jacket, sling bag, and denim jeans."
        if "tech" in c_lower or "founder" in c_lower or "फाउंडर" in c_lower:
            return "Smart-casual tech park attire with corporate ID lanyard."
        if "lawyer" in c_lower or "advocate" in c_lower or "वकील" in c_lower:
            return "Black advocate coat over white collared shirt."
        if "police" in c_lower or "दरोगा" in c_lower or "कांस्टेबल" in c_lower:
            return "Khaki police uniform with brass badge and name plate."
        if "corporator" in c_lower or "netaji" in c_lower or "पार्षद" in c_lower or "नेता" in c_lower:
            return "Crisp white kurta-pyjama with a colorful Nehru jacket."
        if "scientist" in c_lower or "isro" in c_lower or "वैज्ञानिक" in c_lower:
            return "Crisp light-blue formal shirt with official project ID lanyard and security badge."
        if "pilot" in c_lower or "captain" in c_lower or "विमानचालक" in c_lower:
            return "Crisp white pilot uniform shirt with four gold shoulder epaulets and aviation necktie."
        if "loco" in c_lower or "railway" in c_lower or "रेलवे" in c_lower:
            return "Khaki railway service uniform with brass zonal badge and service cap."
        if "coach" in c_lower or "player" in c_lower or "athlete" in c_lower or "खिलाड़ी" in c_lower:
            return "Official athletic team sportswear and training track jacket."
        if "bullion" in c_lower or "jeweller" in c_lower or "सर्राफा" in c_lower:
            return "Fine silk kurta with tailored Nehru vest and gold watch chain."
        if "builder" in c_lower or "hardhat" in c_lower or "साइट" in c_lower:
            return "Crisp linen shirt with yellow project hardhat and site boots."
        if "officer" in c_lower or "अधिकारी" in c_lower or "clerk" in c_lower or "babu" in c_lower or "बाबू" in c_lower:
            return "Crisp half-sleeve formal collared shirt with ballpoint pens in front pocket and official government ID lanyard."
        if "investor" in c_lower or "businessman" in c_lower or "उद्यमी" in c_lower or "landowner" in c_lower or "stakeholder" in c_lower:
            return "Smart-casual collared shirt and trousers, holding a blue official document file folder."
        if "doctor" in c_lower or "चिकित्सक" in c_lower:
            return "Hospital lab coat over scrubs with stethoscope around neck."
        if "teacher" in c_lower or "मास्टर" in c_lower:
            return "Neat formal shirt and trousers with spectacles."
        if "vendor" in c_lower or "tapri" in c_lower or "दुकानदार" in c_lower:
            return "Casual cotton shirt with a tea vendor apron."
        # Relational roles: Husband, Wife, Father, Son, Colleague, Neighbor
        if "wife" in c_lower or "पत्नी" in c_lower or "गृहिणी" in c_lower or "homemaker" in c_lower:
            return "Casual traditional printed cotton saree or simple kurti."
        if "husband" in c_lower or "पति" in c_lower or "salaried" in c_lower:
            return "Everyday collared casual shirt and trousers."
        if "father" in c_lower or "पिता" in c_lower or "chacha" in c_lower or "बुजुर्ग" in c_lower:
            return "Traditional cotton kurta-pyjama with reading spectacles."
        if "son" in c_lower or "बेटा" in c_lower or "youth" in c_lower or "gen-z" in c_lower:
            return "Modern casual hoodie or oversized t-shirt and denim jeans."
        if "colleague" in c_lower or "कलीग" in c_lower or "coworker" in c_lower:
            return "Smart-casual office attire with corporate RFID lanyard."
        if "neighbor" in c_lower or "पड़ोसी" in c_lower:
            return "Casual everyday neighborhood wear (kurta or polo shirt)."
        # Generic young creator / student / friend
        if any(w in c_lower for w in ["priya", "ananya", "sneha", "meera"]):
            return "Casual college-going attire (e.g., jeans and a simple kurti)."
        return "Everyday street casual wear (e.g., t-shirt and jeans)."


    # Non-comedy tones
    if "scientist" in c_lower or "isro" in c_lower or "वैज्ञानिक" in c_lower:
        return "Crisp light-blue formal shirt with official project ID lanyard and security badge."
    if "pilot" in c_lower or "captain" in c_lower or "विमानचालक" in c_lower:
        return "Crisp white pilot uniform shirt with four gold shoulder epaulets and aviation necktie."
    if "loco" in c_lower or "railway" in c_lower or "रेलवे" in c_lower:
        return "Khaki railway service uniform with brass zonal badge and service cap."
    if "coach" in c_lower or "player" in c_lower or "athlete" in c_lower or "खिलाड़ी" in c_lower:
        return "Official athletic team sportswear and training track jacket."
    if "bullion" in c_lower or "jeweller" in c_lower or "सर्राफा" in c_lower:
        return "Fine silk kurta with tailored Nehru vest and gold watch chain."
    if "builder" in c_lower or "hardhat" in c_lower or "साइट" in c_lower:
        return "Crisp linen shirt with yellow project hardhat and site boots."
    if "officer" in c_lower or "अधिकारी" in c_lower or "clerk" in c_lower or "babu" in c_lower or "बाबू" in c_lower:
        return "Crisp half-sleeve formal collared shirt with ballpoint pens in front pocket and official government ID lanyard."
    if "investor" in c_lower or "businessman" in c_lower or "उद्यमी" in c_lower or "landowner" in c_lower or "stakeholder" in c_lower:
        return "Smart-casual collared shirt and trousers, holding a blue official document file folder."
    if "court" in c_lower or "lawyer" in c_lower:
        return "Formal black legal attire with white neckband."
    if "police" in c_lower:
        return "Standard police service uniform."
    if "wife" in c_lower or "पत्नी" in c_lower or "गृहिणी" in c_lower or "homemaker" in c_lower:
        return "Casual traditional printed cotton saree or simple kurti."
    if "husband" in c_lower or "पति" in c_lower:
        return "Everyday collared casual shirt and trousers."
    if "father" in c_lower or "पिता" in c_lower or "chacha" in c_lower or "बुजुर्ग" in c_lower:
        return "Traditional cotton kurta-pyjama with reading spectacles."
    if "son" in c_lower or "बेटा" in c_lower:
        return "Modern casual hoodie or oversized t-shirt and denim jeans."
    if "colleague" in c_lower or "कलीग" in c_lower or "coworker" in c_lower:
        return "Smart-casual office attire with corporate RFID lanyard."
    if "neighbor" in c_lower or "पड़ोसी" in c_lower:
        return "Casual everyday neighborhood wear (kurta or polo shirt)."
    if "culture" in tone.lower() or "heritage" in tone.lower():
        return "Traditional Indian attire (kurta-pyjama or elegant saree)."
    if "sad" in tone.lower() or "lament" in tone.lower():
        return "Subdued, modest everyday attire reflecting solemnity."
    return "Everyday smart-casual attire."


def derive_scene_detail(script) -> str:
    """Extract a rich, authentic setting & atmosphere description for SCENE DETAIL via harmonization."""
    return harmonize_setting_description(script)


def format_industry_screenplay(
    script,
    topic_name: str = "",
    include_overlays: bool = True,
    include_sfx: bool = True,
) -> str:
    """
    Format screenplay strictly matching the industry-standard specification:
    - [Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]
    - SCENE DETAIL: setting & ambient atmosphere
    - CHARACTERS & CLOTHING: tone-aligned wardrobe descriptions
    - Time intervals: clean [Time: 0:00 - 0:03] or [Time: 0:00 - 0:06]
    - Camera Focus & Action: logical take (fast whip-pan/pan for <=10s, smooth continuous take for >10s)
    - Physical action lines only (bodies, props, expressions)
    - Optional Text Overlay and Audio/SFX (included based on script/context or user preference)
    - Hindi dialogue in Devanagari
    """
    # 0. SCRIPT ANALYSIS & HEALING PHASE (Dialogue target auditor & visual kinematics enhancement)
    from agents.screenplay_coherence import screenplay_coherence_agent
    script = analyze_and_heal_script(script)
    script = screenplay_coherence_agent.align_screenplay_coherence(script)

    dur = getattr(script, "target_duration_sec", 15) or 15
    is_fast = dur <= 10

    lines = []
    lines.append("[Format Requirement: 9:16 Vertical Reel | All scene descriptions in English, Dialogues strictly in Hindi]")
    lines.append("")

    # 1. SCENE DETAIL
    scene_detail = derive_scene_detail(script)
    lines.append("SCENE DETAIL:")
    lines.append(f"⚬\t{scene_detail}")
    lines.append("")

    # 2. CHARACTERS & CLOTHING
    raw_chars = []
    seen = set()
    for sc in script.scenes:
        c_clean = sanitize_character_name(sc.character)
        first_name = get_first_name(c_clean).upper()
        if first_name not in seen:
            seen.add(first_name)
            raw_chars.append((first_name, c_clean))

    if not raw_chars:
        raw_chars = [("ANANYA", "Ananya"), ("VIKRAM", "Vikram")]

    sample_text = getattr(script, "sample_story_used", "") or ""
    sample_clothing_map = extract_sample_clothing_map(sample_text)

    lines.append("CHARACTERS & CLOTHING:")
    for first_name, full_name in raw_chars:
        if first_name in sample_clothing_map:
            attire = sample_clothing_map[first_name]
        else:
            attire = get_character_attire(full_name, script.angle)
        lines.append(f"⚬\t{first_name}: {attire}")
    lines.append("")

    # 3. BEATS
    total_scenes = len(script.scenes)
    for idx, sc in enumerate(script.scenes):
        act_dialogue = strip_commenting_and_cta(sc.dialogue or sc.narration_line or "")
        char_clean = sanitize_character_name(sc.character)
        char_upper = get_first_name(char_clean).upper()

        # Clean timestamp
        ts = sc.timestamp.strip("[] ")
        if not ts.startswith("Time:") and not ts.startswith("0:"):
            ts = f"0:{idx*6:02d} - 0:{(idx+1)*6:02d}"
        if not ts.startswith("Time:"):
            time_header = f"[Time: {ts}]"
        else:
            time_header = f"[{ts}]"
        lines.append(time_header)

        # Logical, non-contradictory camera cues
        clean_action = clean_physical_action(sc.visual_b_roll)
        clean_action_lower = clean_action.lower()

        # If visual_b_roll already has full camera cue, preserve it directly
        existing_cue = any(clean_action_lower.startswith(prefix) for prefix in [
            "fast whip-pan", "whip-pan", "quick pan", "fast pan", "single continuous",
            "the camera pans", "the camera pulls back", "fast pull back", "camera pulls back"
        ])

        if existing_cue:
            camera_cue = clean_action
        elif is_fast:
            # High-energy, snappy direction for <= 10s
            if idx == 0:
                if clean_action_lower.startswith(char_upper.lower()):
                    rest = clean_action[len(char_upper):].strip()
                    for vp, vi in [
                        ("slams", "slamming"), ("shoves", "shoving"), ("points", "pointing"),
                        ("gestures", "gesturing"), ("drops", "dropping"), ("holds", "holding"),
                        ("sets", "setting"), ("sips", "sipping"), ("takes", "taking"),
                        ("unfolds", "unfolding"), ("taps", "tapping"), ("waves", "waving"),
                        ("thrusts", "thrusting"), ("counts", "counting")
                    ]:
                        if rest.startswith(vp):
                            rest = vi + rest[len(vp):]
                            break
                        if " " in rest:
                            adv, verb_rest = rest.split(" ", 1)
                            if verb_rest.startswith(vp):
                                rest = f"{adv} {vi}{verb_rest[len(vp):]}"
                                break
                    camera_cue = f"Fast whip-pan to {char_upper.title()} {rest}" if rest else f"Fast whip-pan to {char_upper.title()}."
                else:
                    camera_cue = f"Fast whip-pan to {char_upper.title()} {clean_action[0].lower() + clean_action[1:]}"
            elif idx == total_scenes - 1 and total_scenes >= 2:
                if not clean_action_lower.startswith(char_upper.lower()):
                    act = f"{char_upper.title()} {clean_action[0].lower() + clean_action[1:]}"
                else:
                    act = clean_action
                camera_cue = f"Fast pull back to frame both. {act}"
            else:
                if clean_action_lower.startswith(char_upper.lower()):
                    rest = clean_action[len(char_upper):].strip()
                    for vp, vi in [
                        ("slams", "slamming"), ("shoves", "shoving"), ("points", "pointing"),
                        ("gestures", "gesturing"), ("drops", "dropping"), ("holds", "holding"),
                        ("sets", "setting"), ("sips", "sipping"), ("takes", "taking"),
                        ("unfolds", "unfolding"), ("taps", "tapping"), ("waves", "waving"),
                        ("thrusts", "thrusting"), ("counts", "counting")
                    ]:
                        if rest.startswith(vp):
                            rest = vi + rest[len(vp):]
                            break
                        if " " in rest:
                            adv, verb_rest = rest.split(" ", 1)
                            if verb_rest.startswith(vp):
                                rest = f"{adv} {vi}{verb_rest[len(vp):]}"
                                break
                    camera_cue = f"Quick pan to {char_upper.title()} {rest}" if rest else f"Quick pan to {char_upper.title()}."
                else:
                    camera_cue = f"Quick pan to {char_upper.title()} {clean_action[0].lower() + clean_action[1:]}"
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
