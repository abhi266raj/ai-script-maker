"""Combinatorial Instruction Matrix for Tones, Angles, Scene Styles & Sample Story Style Reference."""

from typing import Optional, Dict, Any
from core.metrics import get_duration_budget


TONE_INSTRUCTIONS: Dict[str, str] = {
    "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)": (
        "🇮🇳 TONE DIRECTIVE: Infuse unapologetic cultural pride, authentic Indian idioms, "
        "respectful yet confident desi swagger, and celebrate national triumphs and grassroots heritage."
    ),
    "🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)": (
        "🪔 TONE DIRECTIVE: Bring timeless Indian wisdom, deep cultural reverence, soulful philosophical depth, "
        "and evocative aesthetic cadence honoring traditions and ancient roots."
    ),
    "🔥 Viral & High Energy (धमाकेदार)": (
        "🔥 TONE DIRECTIVE: Deliver high-voltage adrenaline, rapid punchy delivery, shock-value opening hooks, "
        "and electrifying viral pacing that commands immediate viewer attention."
    ),
    "😂 Relatable Comedy & Sarcasm (देसी ह्यूमर)": (
        "😂 TONE DIRECTIVE: THIS MUST BE GENUINELY FUNNY! Use real everyday jokes, witty banter, relatable desi observations, "
        "and comedic exaggeration. Characters must tease, quip, and avoid dry, robotic news delivery."
    ),
    "⚡ Urgent Breaking News (ताज़ा खबर)": (
        "⚡ TONE DIRECTIVE: Fast-paced journalistic urgency, high-stakes development framing, crisp clarity, "
        "and delivering critical facts without fluff."
    ),
    "💡 Deep Analysis & Curious (गहन पड़ताल)": (
        "💡 TONE DIRECTIVE: Intellectual curiosity, investigative depth, peeling back layers of the story, "
        "and addressing 'why this matters to you' with illuminating insight."
    ),
    "🎭 Cinematic Storytelling (भावुक कहानी)": (
        "🎭 TONE DIRECTIVE: Emotionally resonant narrative arc, cinematic tension, character-driven journey, "
        "and a heartfelt, inspiring resolution."
    ),
    "😢 Emotional & Heartbreaking (भावुक / दुखद)": (
        "😢 TONE DIRECTIVE (Sadness & Grief): Infuse deep emotional weight, tender vulnerability, somber empathy, "
        "and heartfelt sorrow. Spoken Hindi should carry quiet pathos, touching sensitivity, "
        "and profound respect for human suffering and loss. Avoid loud, rushed, or robotic cadence."
    ),
    "⚔️ Heated Argument & Clash": (
        "⚔️ TONE DIRECTIVE (Heated Argument & Clash): Deliver fiery high-voltage verbal friction, sharp counter-arguments, "
        "passionate convictions, and snappy comebacks. Characters challenge each other's assumptions aggressively "
        "yet entertainingly, trading defensive justifications and emotional comebacks."
    ),
}


ANGLE_INSTRUCTIONS: Dict[str, str] = {
    "Funny & Relatable": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Funny & Relatable):\n"
        "- Imagine an everyday relatable situation grounded in THIS news story (e.g. two friends reacting on a video call, dealing with hilarious daily absurdities).\n"
        "- Characters make comedic comparisons, express funny shock, and banter naturally.\n"
        "- Do NOT default to a chai tapri / tea stall setting \u2014 imagine a fresh, story-specific setting from the news itself.\n"
        "- Examples above are format inspiration only: NEVER copy an example's characters, location, or situation."
    ),
    "Sarcastic & Edgy": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Sarcastic & Edgy):\n"
        "- Roast the absurdities, ironies, and expectations vs reality with sharp, unapologetic wit.\n"
        "- Use clever sarcasm to highlight the core truth."
    ),
    "Dramatic Storytelling": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Dramatic Storytelling):\n"
        "- Frame like a high-stakes cinema thriller with rising tension, mystery, and an unexpected plot twist."
    ),
    "Investigative Deep-Dive": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Investigative Deep-Dive):\n"
        "- Frame as an insider uncovering startling behind-the-scenes facts that the mainstream headlines missed."
    ),
    "Inspirational & Uplifting": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Inspirational & Uplifting):\n"
        "- Frame as a triumphant underdog story of resilience, innovation, and national pride overcoming odds."
    ),
    "Gen-Z Hinglish": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Gen-Z Hinglish):\n"
        "- Deliver with modern urban cadence, popular Hindi-English slang, relatable meme references, and casual conversational flow."
    ),
    "Bollywood Masala": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Bollywood Masala):\n"
        "- Inject dramatic Hindi cinema flair, punchy heroic one-liners, emotional musical beats, and theatrical excitement."
    ),
    "Tragic & Heartbreaking": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Tragic & Heartbreaking):\n"
        "- Frame the scene around the deeply human, vulnerable personal loss or emotional toll behind the news.\n"
        "- Depict a quiet, solemn atmosphere (e.g. solitary contemplation, grieving memories, soft raindrops on glass, tender words of comfort).\n"
        "- Emphasize poignant vulnerability, heartfelt empathy, and emotional truth."
    ),
}


# Vibe -> Angle mapping (mirrors TONE_TO_ANGLE in app.py for the streamlined 2-dropdown UI)
_VIBE_TO_ANGLE_KEY = {
    "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)": "Inspirational & Uplifting",
    "🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)": "Inspirational & Uplifting",
    "🔥 Viral & High Energy (धमाकेदार)": "Gen-Z Hinglish",
    "😂 Relatable Comedy & Sarcasm (देसी ह्यूमर)": "Funny & Relatable",
    "⚡ Urgent Breaking News (ताज़ा खबर)": "Dramatic Storytelling",
    "💡 Deep Analysis & Curious (गहन पड़ताल)": "Investigative Deep-Dive",
    "🎭 Cinematic Storytelling (भावुक कहानी)": "Dramatic Storytelling",
    "😢 Emotional & Heartbreaking (भावुक / दुखद)": "Tragic & Heartbreaking",
    "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)": "Sarcastic & Edgy",
}


# Plain pipeline vibe values (core.constants VIBE_*) -> TONE_INSTRUCTIONS key.
# The UI passes plain values ("Joke", "Breaking", ...); without this map they
# never matched the emoji-prefixed tone keys and fell into invented generics.
_PLAIN_VIBE_TO_TONE_KEY = {
    "Desi Swag": "🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)",
    "Heritage": "🪔 Traditional Heritage & Wisdom (सांस्कृतिक धरोहर)",
    "Viral": "🔥 Viral & High Energy (धमाकेदार)",
    "Joke": "😂 Relatable Comedy & Sarcasm (देसी ह्यूमर)",
    "Breaking": "⚡ Urgent Breaking News (ताज़ा खबर)",
    "Analysis": "💡 Deep Analysis & Curious (गहन पड़ताल)",
    "Cinematic": "🎭 Cinematic Storytelling (भावुक कहानी)",
    "Emotional": "😢 Emotional & Heartbreaking (भावुक / दुखद)",
    "Heated": "⚔️ Heated Argument & Clash",
}


def _build_vibe_instructions() -> Dict[str, str]:
    """Merge tone + angle into a single concise Vibe directive per vibe."""
    result = {}
    for vibe_key, tone_dir in TONE_INSTRUCTIONS.items():
        angle_key = _VIBE_TO_ANGLE_KEY.get(vibe_key, "")
        angle_dir = ANGLE_INSTRUCTIONS.get(angle_key, "")
        combined = f"{tone_dir}\n{angle_dir}" if angle_dir else tone_dir
        result[vibe_key] = combined
    return result


VIBE_INSTRUCTIONS: Dict[str, str] = _build_vibe_instructions()


SCENE_STYLE_INSTRUCTIONS: Dict[str, str] = {
    "Dialogue": (
        "👥 SCENE STYLE DIRECTIVE (Dialogue):\n"
        "- Structure as an active, in-universe conversational exchange between designated characters.\n"
        "- Characters must talk directly to each other: reacting, teasing, countering, and building to a shared punchline or dramatic payoff.\n"
        "- STRICT RULE: NO social media commenting, NO asking viewers to comment ('कमेंट करें', 'लाइक करें'). Characters are having a genuine conversation with each other, NOT talking to comment sections!"
    ),
    "Speech": (
        "📢 SCENE STYLE DIRECTIVE (Speech):\n"
        "- A charismatic public address delivered with rhetorical punch, rallying cries, and direct emotional connection to the audience."
    ),
    "Narration": (
        "🎙️ SCENE STYLE DIRECTIVE (Narration):\n"
        "- Dynamic documentary voiceover with seamless transitions, cinematic scene descriptions, and captivating pacing."
    ),
    "Interview": (
        "🎤 SCENE STYLE DIRECTIVE (Interview):\n"
        "- Rapid-fire Q&A between an investigative host and an insider guest, revealing surprising insights in real time."
    ),
    "Debate": (
        "⚔️ SCENE STYLE DIRECTIVE (Debate):\n"
        "- Fiery, witty clash of two opposing perspectives with sharp counter-arguments and substantive exchanges."
    ),
    "Argument": (
        "🔥 SCENE STYLE DIRECTIVE (Argument / Heated Clash - तकरार):\n"
        "- A fiery, high-stakes verbal argument between characters with passionate, opposing convictions.\n"
        "- Characters clash directly over the situation: trading sharp comebacks, defensive justifications, and escalating emotional stakes.\n"
        "- Grounded in authentic relationship dynamics: colleagues arguing over deadlines/workplace rules, husband vs wife over household realities, father vs son across generational divides, or friends disputing news facts.\n"
        "- Concludes with a dramatic reveal, unexpected reality check, or humorous twist ending.\n"
        "- STRICT RULE: NO social media commenting, NO asking viewers to comment ('कमेंट करें', 'लाइक करें')."
    ),
    "Monologue": (
        "👤 SCENE STYLE DIRECTIVE (Monologue):\n"
        "- Expressive solo creator addressing the camera directly, breaking the 4th wall with high intimacy and strong reactions."
    ),
    "Lament": (
        "💔 SCENE STYLE DIRECTIVE (Lament / Eulogy):\n"
        "- A deeply moving, poignant expression of grief, tribute, and collective sorrow.\n"
        "- Spoken with tender emotional restraint, meaningful pauses, and heartfelt mutual consolation across scenes."
    ),
}


def get_tone_instruction(tone: str) -> str:
    """Retrieve the instruction for a chosen tone. Fails loudly on unknown tones."""
    if not tone or not tone.strip():
        raise ValueError("Tone is required: no tone/vibe was supplied.")
    # Plain pipeline vibe values (core.constants VIBE_*) map to their tone key.
    # Without this map every plain vibe fell through to an invented generic
    # directive below.
    key = _PLAIN_VIBE_TO_TONE_KEY.get(tone.strip(), tone.strip())
    for k, v in TONE_INSTRUCTIONS.items():
        if k == key or key.lower() in k.lower() or k.lower() in key.lower():
            return v
    valid = sorted(TONE_INSTRUCTIONS) + sorted(_PLAIN_VIBE_TO_TONE_KEY)
    raise ValueError(
        f"Unknown tone {tone!r}: no instruction exists. Valid tones: {valid}. "
        "Refusing to invent a generic directive."
    )


def get_angle_instruction(angle: str) -> str:
    """Retrieve the instruction for a chosen editorial angle. Fails loudly on unknown angles."""
    if not angle or not angle.strip():
        raise ValueError("Angle is required: no editorial angle was supplied.")
    for k, v in ANGLE_INSTRUCTIONS.items():
        if k == angle or angle.lower() in k.lower() or k.lower() in angle.lower():
            return v
    raise ValueError(
        f"Unknown angle {angle!r}: no instruction exists. Valid angles: {sorted(ANGLE_INSTRUCTIONS)}. "
        "Refusing to invent a generic directive."
    )


def get_scene_style_instruction(scene_style: str, character_count: int) -> str:
    """Retrieve scene style directive tailored to character count. Fails loudly on unknown styles."""
    if not scene_style or not scene_style.strip():
        raise ValueError("Scene style is required: none was supplied.")
    style_key = scene_style.strip().capitalize()
    if style_key not in SCENE_STYLE_INSTRUCTIONS:
        raise ValueError(
            f"Unknown scene style {scene_style!r}. Valid styles: {sorted(SCENE_STYLE_INSTRUCTIONS)}. "
            "Refusing to silently fall back to Dialogue."
        )
    base = SCENE_STYLE_INSTRUCTIONS[style_key]
    if scene_style.lower() in ["dialogue", "argument", "debate"] and character_count > 1:
        base += f"\n- Distinctly feature {character_count} different characters speaking across the scenes directly to each other without commenting or social media CTAs."
    return base




def get_vibe_instruction(vibe: str) -> str:
    """Retrieve the unified Vibe directive (tone + angle merged) for the streamlined 2-dropdown UI."""
    for k, v in VIBE_INSTRUCTIONS.items():
        if k == vibe or vibe.lower() in k.lower() or k.lower() in vibe.lower():
            return v
    return get_tone_instruction(vibe)


def build_tailored_instruction(
    topic: str,
    duration_sec: int,
    tone: str = "",
    angle: str = "",
    scene_style: str = "Dialogue",
    character_count: int = 1,
    sample_story: Optional[str] = None,
    vibe: str = "",
) -> str:
    """
    Streamlined for 2-dropdown UI (Vibe + Scene Style).
    Vibe = Tone + Angle merged into one directive.
    """
    budget = get_duration_budget(duration_sec)
    active_topic = topic.strip() if topic else ""
    if not active_topic:
        raise ValueError(
            "Topic is required: refusing to build an instruction around a '[topic]' placeholder."
        )

    effective_vibe = vibe or tone
    if effective_vibe:
        # A selected vibe always resolves through the unified directive (which
        # fails loudly on unknown vibes) — never an empty creative block.
        creative_block = get_vibe_instruction(effective_vibe)
    else:
        tone_dir = get_tone_instruction(tone) if tone else ""
        angle_dir = get_angle_instruction(angle) if angle else ""
        creative_block = "\n\n".join([d for d in [tone_dir, angle_dir] if d])

    style_dir = get_scene_style_instruction(scene_style, character_count)

    word_block = (
        "📝 Dialogue Word Count: Recommended ~" + str(budget['recommended_words']) + " words "
        "(Min: " + str(budget['min_words']) + " words, Strict Max: " + str(budget['max_words']) + " words). "
        "Spoken pace: ~2.0-2.3 words/sec. Spoken dialogue across all scenes combined must not exceed "
        + str(budget['max_words']) + " words."
    )

    config_block = (
        "⚙️ Configuration Parameters: " + str(character_count) + " speaking character(s). "
        "Include scene descriptions, visual B-roll direction, speaker character names, and exact spoken dialogue. "
        "STRICT PROHIBITION: Dialogue must be pure conversation between characters\u2014NO social media commenting, NO asking viewers to comment, NO meta-CTAs."
    )

    parts = [
        "🎬 Create a " + scene_style.lower() + " screenplay from this topic: " + active_topic,
        "⏱️ Target format: 9:16 vertical, exactly " + str(duration_sec) + " seconds.",
        word_block,
        creative_block,
        style_dir,
        config_block,
    ]

    if sample_story and sample_story.strip():
        sample_clean = sample_story.strip()
        parts.append(
            "⭐ OPTIONAL SAMPLE STORY \u2014 STYLE REFERENCE ONLY:\n"
            'Reference Sample Story: "' + sample_clean + '"\n'
            "Use this sample ONLY as inspiration for structure, rhythm, and tone. "
            "DO NOT copy its characters, names, relationships, locations, objects, "
            "dialogue, situations, or plot details \u2014 invent everything fresh for the current news story."
        )

    return "\n\n".join(parts)
