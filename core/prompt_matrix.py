"""Combinatorial Instruction Matrix for Tones, Angles, Scene Styles & Sample Story Precedence."""

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
    "⚔️ Heated Argument & Clash (तीखी बहस / तकरार)": (
        "⚔️ TONE DIRECTIVE (Heated Argument & Clash / तीखी बहस): Deliver fiery high-voltage verbal friction, sharp counter-arguments, "
        "passionate convictions, and snappy comebacks. Characters challenge each other's assumptions aggressively "
        "yet entertainingly, trading defensive justifications and emotional comebacks."
    ),
}


ANGLE_INSTRUCTIONS: Dict[str, str] = {
    "Funny & Relatable": (
        "🎨 EDITORIAL ANGLE DIRECTIVE (Funny & Relatable):\n"
        "- Imagine an everyday relatable situation (e.g. friends at a local chai tapri, dealing with hilarious daily absurdities).\n"
        "- Characters make comedic comparisons, express funny shock, and banter naturally."
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
    """Retrieve or dynamically construct instruction for chosen tone."""
    for k, v in TONE_INSTRUCTIONS.items():
        if k == tone or tone.lower() in k.lower() or k.lower() in tone.lower():
            return v
    return f"🎙️ TONE DIRECTIVE: Deliver narration embodying {tone} with authentic spoken Hindi."


def get_angle_instruction(angle: str) -> str:
    """Retrieve or dynamically construct instruction for chosen editorial angle."""
    for k, v in ANGLE_INSTRUCTIONS.items():
        if k == angle or angle.lower() in k.lower() or k.lower() in angle.lower():
            return v
    return f"🎨 EDITORIAL ANGLE DIRECTIVE: Frame the reel through an imaginative scenario highlighting {angle}."


def get_scene_style_instruction(scene_style: str, character_count: int) -> str:
    """Retrieve scene style directive tailored to character count."""
    style_key = scene_style.capitalize()
    base = SCENE_STYLE_INSTRUCTIONS.get(style_key, SCENE_STYLE_INSTRUCTIONS["Dialogue"])
    if scene_style.lower() in ["dialogue", "argument", "debate"] and character_count > 1:
        base += f"\n- Distinctly feature {character_count} different characters speaking across the scenes directly to each other without commenting or social media CTAs."
    return base



def build_tailored_instruction(
    topic: str,
    duration_sec: int,
    tone: str,
    angle: str,
    scene_style: str,
    character_count: int = 1,
    batch_count: int = 1,
    max_retries: int = 5,
    sample_story: Optional[str] = None,
) -> str:
    """
    Construct a complete, highly structured master instruction combining all active configuration inputs:
    - Topic and exact duration
    - Word count bounds (Recommended, Min, Strict Max, and pacing ~2.0-2.3 w/s)
    - Specific tone directive
    - Specific angle imaginary scenario directive
    - Specific scene style directive with character allocation
    - Scripts batch count and Retries
    - Optional sample story with explicit discrepancy precedence rule
    (Engine and dead frame-scene configs are excluded from instruction).
    """
    budget = get_duration_budget(duration_sec)
    active_topic = topic.strip() or "[topic]"

    tone_dir = get_tone_instruction(tone)
    angle_dir = get_angle_instruction(angle)
    style_dir = get_scene_style_instruction(scene_style, character_count)

    instructions = [
        f"🎬 Create a {scene_style.lower()} screenplay from this topic: {active_topic}",
        f"⏱️ Target format: 9:16 vertical, exactly {duration_sec} seconds.",
        (
            f"📝 Dialogue Word Count: Recommended ~{budget['recommended_words']} words "
            f"(Min: {budget['min_words']} words, Strict Max: {budget['max_words']} words). "
            f"Spoken pace: ~2.0-2.3 words/sec. Spoken dialogue across all scenes combined must not exceed {budget['max_words']} words."
        ),
        f"{tone_dir}",
        f"{angle_dir}",
        f"{style_dir}",
        (
            f"⚙️ Configuration Parameters: {character_count} speaking character(s), "
            f"{batch_count} script version(s), {max_retries} validation retry attempt(s). "
            "Include timestamped scenes, visual B-roll direction, speaker character names, and exact spoken dialogue. "
            "STRICT PROHIBITION: Dialogue must be pure conversation between characters—NO social media commenting, NO asking viewers to comment, NO meta-CTAs."
        ),
    ]

    if sample_story and sample_story.strip():
        sample_clean = sample_story.strip()
        instructions.append(
            "⭐ OPTIONAL SAMPLE STORY & PRECEDENCE RULE:\n"
            f"Reference Sample Story: \"{sample_clean}\"\n"
            "CRITICAL PRECEDENCE INSTRUCTION: In case of any discrepancy or conflict between the general instructions "
            "and this sample story, THE SAMPLE STORY TAKES HIGHEST PRECEDENCE! "
            "If the sample story specifies or defines characters (e.g. Husband & Wife / पति-पत्नी, Father & Son / पिता-पुत्र, Colleagues, Friends, Doctor & Patient, or custom named characters), "
            "relationships, or scene descriptions, THOSE CHARACTERS AND RELATIONSHIPS MUST BE DIRECTLY EXTRACTED, RESPECTED, AND FEATURED "
            "as the speaking characters in the screenplay, while fitting within the strict word budget."
        )

    return "\n\n".join(instructions)
