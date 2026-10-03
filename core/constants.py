"""Central constants for the reel pipeline — no magic strings.

All emotion values, format values, stage names, source names, and UI sentinel
values live here. Import from here instead of hardcoding strings.
"""

# ---------------------------------------------------------------------------
# Emotion internal values (pipeline-facing). #354: the frozen canonical
# palette of 8 genuine human emotions for news reel generation. The creator
# UI shows these directly — no composite marketing phrases.
# ---------------------------------------------------------------------------
EMOTION_ANGER = "Anger"
EMOTION_SHOCK = "Shock"
EMOTION_JOKE = "Joke"
EMOTION_SORROW = "Sorrow"
EMOTION_CURIOSITY = "Curiosity"
EMOTION_PRIDE = "Pride"
EMOTION_FEAR = "Fear"
EMOTION_HOPE = "Hope"

# Frozen order per #354 — do not reorder; UI and tests pin this sequence.
ALL_EMOTIONS = [
    EMOTION_ANGER,
    EMOTION_SHOCK,
    EMOTION_JOKE,
    EMOTION_SORROW,
    EMOTION_CURIOSITY,
    EMOTION_PRIDE,
    EMOTION_FEAR,
    EMOTION_HOPE,
]

# Hindi names for the creator UI and agent prompts.
EMOTION_HINDI = {
    EMOTION_ANGER: "क्रोध / गुस्सा",
    EMOTION_SHOCK: "स्तब्ध / झटका",
    EMOTION_JOKE: "मज़ाक / हास्य",
    EMOTION_SORROW: "शोक / दुख",
    EMOTION_CURIOSITY: "जिज्ञासा / पड़ताल",
    EMOTION_PRIDE: "गर्व / स्वाभिमान",
    EMOTION_FEAR: "डर / चिंता",
    EMOTION_HOPE: "उम्मीद / राहत",
}

# Delivery direction per emotion: how the feeling is spoken/performed.
# Screenplay parentheticals, teleprompter headers, and the dialogue writer
# all ground on these — an actor reading "(Anger)" knows the delivery.
EMOTION_DELIVERY = {
    EMOTION_ANGER: "fast, abrupt, aggressive, interruptive",
    EMOTION_SHOCK: "gasping, wide-eyed disbelief, rapid urgency",
    EMOTION_JOKE: "punchline timing, witty banter, teasing",
    EMOTION_SORROW: "quiet grief, respectful restraint, somber pauses",
    EMOTION_CURIOSITY: "inquisitive, investigative, steady",
    EMOTION_PRIDE: "confident, celebratory, inspiring",
    EMOTION_FEAR: "rapid, cautious, tense concern",
    EMOTION_HOPE: "warm, relaxed, comforting reassurance",
}

# News triggers per emotion: what human reaction the emotion answers.
EMOTION_TRIGGERS = {
    EMOTION_ANGER: "scams, price hikes, bureaucratic negligence, injustice",
    EMOTION_SHOCK: "sudden breaking developments, unbelievable numbers, scandals",
    EMOTION_JOKE: "absurd policies, funny quirks, ironies of daily life",
    EMOTION_SORROW: "tragic loss, casualties, disasters, heartbreak",
    EMOTION_CURIOSITY: "investigations, tech/space mysteries, 'why this matters'",
    EMOTION_PRIDE: "national triumphs, space missions (ISRO), championship wins",
    EMOTION_FEAR: "cyber scams, health warnings, financial threats",
    EMOTION_HOPE: "crises averted, rescues, inflation cooling, good news",
}


def emotion_hindi_name(emotion: str) -> str:
    """Hindi name for a frozen emotion. Fails loudly on unknown emotions."""
    if emotion not in EMOTION_HINDI:
        raise ValueError(
            f"Unknown emotion {emotion!r}: not in the frozen palette {ALL_EMOTIONS}. "
            "Refusing to invent a Hindi name."
        )
    return EMOTION_HINDI[emotion]


def emotion_delivery(emotion: str) -> str:
    """Delivery direction for a frozen emotion. Fails loudly on unknown emotions."""
    if emotion not in EMOTION_DELIVERY:
        raise ValueError(
            f"Unknown emotion {emotion!r}: not in the frozen palette {ALL_EMOTIONS}. "
            "Refusing to invent delivery direction."
        )
    return EMOTION_DELIVERY[emotion]


# ---------------------------------------------------------------------------
# Emotion -> Angle derivation (each frozen emotion suggests an editorial angle).
# The 2-dropdown UI (Emotion + Scene Style) never asks for an angle; the
# pipeline derives one so downstream prompt machinery keeps working.
# ---------------------------------------------------------------------------
EMOTION_TO_ANGLE = {
    EMOTION_ANGER: "Dramatic Storytelling",
    EMOTION_SHOCK: "Dramatic Storytelling",
    EMOTION_JOKE: "Funny & Relatable",
    EMOTION_SORROW: "Tragic & Heartbreaking",
    EMOTION_CURIOSITY: "Investigative Deep-Dive",
    EMOTION_PRIDE: "Inspirational & Uplifting",
    EMOTION_FEAR: "Dramatic Storytelling",
    EMOTION_HOPE: "Inspirational & Uplifting",
}


def emotion_to_angle(emotion: str) -> str:
    """Derive the pipeline angle from the selected emotion. Fail-loud."""
    if emotion not in EMOTION_TO_ANGLE:
        raise ValueError(
            f"Unknown emotion {emotion!r}: no angle derivation exists. "
            f"Valid emotions: {ALL_EMOTIONS}."
        )
    return EMOTION_TO_ANGLE[emotion]

# ---------------------------------------------------------------------------
# Format internal values (pipeline-facing; creator UI shows FORMAT_DISPLAY_NAMES)
# ---------------------------------------------------------------------------
FORMAT_DIALOGUE = "Dialogue"
FORMAT_ARGUMENT = "Argument"
FORMAT_SPEECH = "Speech"
FORMAT_NARRATION = "Narration"
FORMAT_INTERVIEW = "Interview"
FORMAT_DEBATE = "Debate"
FORMAT_MONOLOGUE = "Monologue"
FORMAT_LAMENT = "Lament"

ALL_FORMATS = [
    FORMAT_DIALOGUE,
    FORMAT_ARGUMENT,
    FORMAT_SPEECH,
    FORMAT_NARRATION,
    FORMAT_INTERVIEW,
    FORMAT_DEBATE,
    FORMAT_MONOLOGUE,
    FORMAT_LAMENT,
]

# ---------------------------------------------------------------------------
# Stage names (1-indexed; STAGE_NAMES[i] is stage i+1)
# ---------------------------------------------------------------------------
STAGE_NAMES = [
    "1. Facts & Verification",
    "2. Character Finalisation",
    "3. Dialogue",
    "4. Scene Finalisation",
    "5. Storyboard & Video",
    "6. Integration & Validation",
]

STAGE_FACTS = 1
STAGE_CHARACTERS = 2
STAGE_DIALOGUE = 3
STAGE_SCENES = 4
STAGE_STORYBOARD = 5
STAGE_VALIDATION = 6

# ---------------------------------------------------------------------------
# News source names
# ---------------------------------------------------------------------------
SOURCE_MANUAL = "\u270F\uFE0F Manual Topic"
SOURCE_TRENDING_HASHTAG = "#\uFE0F\u20E3 Trending Hashtags"
SOURCE_INSTAGRAM_HASHTAG = "\U0001F4F8 Instagram Hashtag"

# ---------------------------------------------------------------------------
# UI sentinel values
# ---------------------------------------------------------------------------
OPTION_TYPE_OWN = "\u2710\uFE0F Type my own\u2026"
