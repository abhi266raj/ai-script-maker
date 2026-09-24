"""Central constants for the reel pipeline — no magic strings.

All vibe values, format values, stage names, source names, and UI sentinel
values live here. Import from here instead of hardcoding strings.
"""

# ---------------------------------------------------------------------------
# Vibe internal values (pipeline-facing; creator UI shows VIBE_DISPLAY_NAMES)
# ---------------------------------------------------------------------------
VIBE_DESI_SWAG = "Desi Swag"
VIBE_HERITAGE = "Heritage"
VIBE_VIRAL = "Viral"
VIBE_COMEDY = "Joke"
VIBE_BREAKING = "Breaking"
VIBE_ANALYSIS = "Analysis"
VIBE_CINEMATIC = "Cinematic"
VIBE_EMOTIONAL = "Emotional"
VIBE_HEATED = "Heated"

ALL_VIBES = [
    VIBE_DESI_SWAG,
    VIBE_HERITAGE,
    VIBE_VIRAL,
    VIBE_COMEDY,
    VIBE_BREAKING,
    VIBE_ANALYSIS,
    VIBE_CINEMATIC,
    VIBE_EMOTIONAL,
    VIBE_HEATED,
]

# ---------------------------------------------------------------------------
# Vibe display names (creator UI ONLY — emoji-prefixed for visual scanning).
# Pipeline-facing VIBE_* values stay plain text; agents NEVER receive emojis.
# ---------------------------------------------------------------------------
VIBE_DISPLAY_NAMES = {
    VIBE_DESI_SWAG: "\U0001F1EE\U0001F1F3 Desi Swag",
    VIBE_HERITAGE: "\U0001FAB2 Heritage",
    VIBE_VIRAL: "\U0001F525 Viral",
    VIBE_COMEDY: "\U0001F602 Joke",
    VIBE_BREAKING: "\u26A1 Breaking",
    VIBE_ANALYSIS: "\U0001F4A1 Analysis",
    VIBE_CINEMATIC: "\U0001F3AD Cinematic",
    VIBE_EMOTIONAL: "\U0001F622 Emotional",
    VIBE_HEATED: "\u2694\uFE0F Heated",
}


def vibe_display_name(plain: str) -> str:
    """Emoji-prefixed creator-facing label for a plain pipeline vibe value."""
    return VIBE_DISPLAY_NAMES.get(plain, plain)


def vibe_plain_name(display: str) -> str:
    """Reverse lookup: map a UI display name back to the plain pipeline value."""
    for plain, disp in VIBE_DISPLAY_NAMES.items():
        if disp == display:
            return plain
    return display

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
