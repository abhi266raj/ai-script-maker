"""Combinatorial Instruction Matrix for Emotions, Angles, Scene Styles & Sample Story Style Reference."""

from typing import Optional, Dict, Any
from core.metrics import get_duration_budget
from core.constants import (
    ALL_EMOTIONS,
    EMOTION_HINDI,
    EMOTION_DELIVERY,
    EMOTION_TRIGGERS,
    EMOTION_TO_ANGLE,
)


# ---------------------------------------------------------------------------
# Frozen emotion directives (#354). One genuine human feeling per emotion:
# what it reacts to, how it is delivered, and the 70% / zero-contradiction
# compliance contract. The derived editorial angle is merged in (same as the
# old vibe system) so the creative situation-setting survives.
# ---------------------------------------------------------------------------
_EMOTION_CORE: Dict[str, str] = {
    "Anger": (
        "EMOTION DIRECTIVE (Anger — क्रोध / गुस्सा):\n"
        "- GENUINE HUMAN FEELING: anger at scams, price hikes, bureaucratic negligence, injustice.\n"
        "- DELIVERY: fast, abrupt, aggressive, interruptive. Write every line to be SPOKEN furious — "
        "short bursts, interruptions, rising heat. An actor reading the (Anger) parenthetical must feel the fury.\n"
        "- COMPLIANCE: at least 70% of beats must clearly embody this anger; ZERO beats may contradict it "
        "(no jokes about the outrage, no calm detachment, no somber grief)."
    ),
    "Shock": (
        "EMOTION DIRECTIVE (Shock — स्तब्ध / झटका):\n"
        "- GENUINE HUMAN FEELING: shock at sudden breaking developments, unbelievable numbers, scandals.\n"
        "- DELIVERY: gasping, wide-eyed disbelief, rapid urgency. Write every line to be SPOKEN stunned — "
        "sharp intakes, 'are you serious?!' disbelief, breathless pace.\n"
        "- COMPLIANCE: at least 70% of beats must clearly embody this shock; ZERO beats may contradict it "
        "(no calm analysis, no jokes deflating the disbelief)."
    ),
    "Joke": (
        "EMOTION DIRECTIVE (Joke — मज़ाक / हास्य):\n"
        "- GENUINE HUMAN FEELING: amusement at absurd policies, funny quirks, ironies of daily life.\n"
        "- DELIVERY: punchline timing, witty banter, teasing. Write every line to be SPOKEN funny — "
        "real setups and punchlines, never a 'humorous tone' with no actual joke.\n"
        "- COMPLIANCE: at least 70% of beats must be GENUINELY FUNNY (setup + punchline); ZERO beats may "
        "contradict it (no somber grief, no horror, no dry lecturing)."
    ),
    "Sorrow": (
        "EMOTION DIRECTIVE (Sorrow — शोक / दुख):\n"
        "- GENUINE HUMAN FEELING: sorrow at tragic loss, casualties, disasters, heartbreak.\n"
        "- DELIVERY: quiet grief, respectful restraint, somber pauses. Write every line to be SPOKEN grieving — "
        "tender, hushed, dignified. An actor reading the (Sorrow) parenthetical must slow down and soften.\n"
        "- COMPLIANCE: at least 70% of beats must be CLEARLY sorrowful; ZERO jokes, ZERO laughter, ZERO comedic "
        "beats anywhere. Somber throughout."
    ),
    "Curiosity": (
        "EMOTION DIRECTIVE (Curiosity — जिज्ञासा / पड़ताल):\n"
        "- GENUINE HUMAN FEELING: curiosity about investigations, tech/space mysteries, 'why this matters'.\n"
        "- DELIVERY: inquisitive, investigative, steady. Write every line to be SPOKEN curious — probing questions, "
        "peeling layers, 'but why?' energy without hysteria.\n"
        "- COMPLIANCE: at least 70% of beats must clearly embody this curiosity; ZERO beats may contradict it "
        "(no incurious recitation, no mocking the mystery)."
    ),
    "Pride": (
        "EMOTION DIRECTIVE (Pride — गर्व / स्वाभिमान):\n"
        "- GENUINE HUMAN FEELING: pride at national triumphs, space missions (ISRO), championship wins.\n"
        "- DELIVERY: confident, celebratory, inspiring. Write every line to be SPOKEN proud — chest-out celebration, "
        "uplifting cadence, genuine goosebumps.\n"
        "- COMPLIANCE: at least 70% of beats must clearly embody this pride; ZERO beats may contradict it "
        "(no cynicism, no sarcastic deflation of the triumph)."
    ),
    "Fear": (
        "EMOTION DIRECTIVE (Fear — डर / चिंता):\n"
        "- GENUINE HUMAN FEELING: fear of cyber scams, health warnings, financial threats.\n"
        "- DELIVERY: rapid, cautious, tense concern. Write every line to be SPOKEN afraid — urgent warnings, "
        "nervous checking, tight-throated caution.\n"
        "- COMPLIANCE: at least 70% of beats must clearly embody this fear; ZERO beats may contradict it "
        "(no jokes about the danger, no breezy dismissal)."
    ),
    "Hope": (
        "EMOTION DIRECTIVE (Hope — उम्मीद / राहत):\n"
        "- GENUINE HUMAN FEELING: hope at crises averted, rescues, inflation cooling, good news.\n"
        "- DELIVERY: warm, relaxed, comforting reassurance. Write every line to be SPOKEN hopeful — gentle relief, "
        "optimistic steadiness, a hand on the shoulder.\n"
        "- COMPLIANCE: at least 70% of beats must clearly embody this hope; ZERO beats may contradict it "
        "(no despair, no cynical doom)."
    ),
}


def _build_emotion_instructions() -> Dict[str, str]:
    """Merge the emotion core directive with its derived editorial angle."""
    result = {}
    for emotion in ALL_EMOTIONS:
        core = _EMOTION_CORE[emotion]
        angle_key = EMOTION_TO_ANGLE.get(emotion, "")
        angle_dir = ANGLE_INSTRUCTIONS.get(angle_key, "")
        result[emotion] = f"{core}\n{angle_dir}" if angle_dir else core
    return result


# Built after ANGLE_INSTRUCTIONS is defined below — the merge needs it.
EMOTION_INSTRUCTIONS: Dict[str, str] = {}


def get_emotion_instruction(emotion: str) -> str:
    """Retrieve the frozen directive for an emotion. Fails loudly on unknown emotions."""
    if not emotion or not emotion.strip():
        raise ValueError("Emotion is required: no emotion was supplied.")
    key = emotion.strip()
    if key in EMOTION_INSTRUCTIONS:
        return EMOTION_INSTRUCTIONS[key]
    # Case-insensitive fallback — still frozen-palette only, never invented.
    for k, v in EMOTION_INSTRUCTIONS.items():
        if k.lower() == key.lower():
            return v
    raise ValueError(
        f"Unknown emotion {emotion!r}: not in the frozen palette {ALL_EMOTIONS}. "
        "Refusing to invent a directive."
    )


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


# Build the merged emotion directives now that ANGLE_INSTRUCTIONS exists.
EMOTION_INSTRUCTIONS.update(_build_emotion_instructions())


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




def build_tailored_instruction(
    topic: str,
    duration_sec: int,
    tone: str = "",
    angle: str = "",
    scene_style: str = "Dialogue",
    character_count: int = 1,
    sample_story: Optional[str] = None,
    vibe: str = "",
    emotion: str = "",
) -> str:
    """
    Streamlined for 2-dropdown UI (Emotion + Scene Style).
    Emotion = the frozen genuine feeling driving dialogue & delivery (#354).
    """
    budget = get_duration_budget(duration_sec)
    active_topic = topic.strip() if topic else ""
    if not active_topic:
        raise ValueError(
            "Topic is required: refusing to build an instruction around a '[topic]' placeholder."
        )

    effective_emotion = (emotion or vibe or tone).strip()
    if effective_emotion:
        # A selected emotion always resolves through the frozen directive
        # (which fails loudly on unknown emotions) — never an empty creative
        # block, never an invented one.
        creative_block = get_emotion_instruction(effective_emotion)
    else:
        raise ValueError(
            "Emotion is required: no emotion was supplied to build_tailored_instruction. "
            f"Valid emotions: {ALL_EMOTIONS}."
        )

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
            "⭐ SAMPLE STORY \u2014 DIRECTOR'S GUIDE (highest creative precedence):\n"
            'Reference Sample Story: "' + sample_clean + '"\n'
            "This sample is the author/director's guide for what they want. Follow its "
            "characters, names, relationships, direction, structure, rhythm, and tone. "
            "When the sample conflicts with the emotion, character count, or scene style "
            "settings above, the SAMPLE WINS on every creative choice.\n"
            "HARD BOUNDARY \u2014 verified news facts always outrank the sample: adapt the "
            "sample's creative direction to the confirmed facts; never invent or alter "
            "facts to match the sample."
        )

    return "\n\n".join(parts)
