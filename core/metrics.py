"""Metrics and verification utilities for Reel Scripts (Flexible 5s increments and custom durations)."""

import re
from typing import Tuple


def count_words(text: str) -> int:
    """Accurately count words in Hindi (Devanagari) and mixed script text."""
    if not text:
        return 0
    cleaned = re.sub(r"[#*_`~>\[\]\(\)\{\}\-+=:;!?।,\"]", " ", text)
    tokens = [w for w in cleaned.split() if w.strip()]
    return len(tokens)


# Standardized duration to spoken Hindi dialogue word limits:
# Hindi speech rate in reels: ~2.0 - 2.3 words/sec.
# STRICT PACING ASYMMETRY:
# - Less words is completely SAFE (gives breathing room for dramatic pauses, B-roll, SFX).
# - More words than max_words IS AN ISSUE (causes duration overflow or rushed unnatural speech).
DURATION_WORD_LIMITS = {
    5: {"min_words": 4, "recommended_words": 10, "max_words": 11, "scenes": 1},
    10: {"min_words": 8, "recommended_words": 20, "max_words": 23, "scenes": 2},
    15: {"min_words": 12, "recommended_words": 30, "max_words": 34, "scenes": 2},
    20: {"min_words": 16, "recommended_words": 40, "max_words": 46, "scenes": 3},
    25: {"min_words": 20, "recommended_words": 50, "max_words": 58, "scenes": 3},
    30: {"min_words": 24, "recommended_words": 60, "max_words": 69, "scenes": 3},
    45: {"min_words": 36, "recommended_words": 90, "max_words": 104, "scenes": 4},
    60: {"min_words": 48, "recommended_words": 120, "max_words": 138, "scenes": 4},
    90: {"min_words": 72, "recommended_words": 180, "max_words": 207, "scenes": 5},
    120: {"min_words": 96, "recommended_words": 240, "max_words": 276, "scenes": 5},
    180: {"min_words": 144, "recommended_words": 360, "max_words": 414, "scenes": 5},
}


def get_duration_budget(target_seconds: int) -> dict:
    """
    Dynamically calculate spoken dialogue word limits (min, recommended, max)
    and scene recommendations for any duration.
    
    STRICT PACING ASYMMETRY:
    - Less words is NOT an issue (provides space for pauses and B-roll).
    - More words than max_words IS an issue (overflows reel length).
    """
    t = max(5, target_seconds)

    if t in DURATION_WORD_LIMITS:
        cfg = DURATION_WORD_LIMITS[t]
        min_words = cfg["min_words"]
        recommended_words = cfg["recommended_words"]
        max_words = cfg["max_words"]
        scenes = cfg["scenes"]
    else:
        # Dynamic calculation for custom seconds
        min_words = max(3, int(t * 0.8))
        recommended_words = max(6, int(t * 2.0))
        max_words = max(8, int(t * 2.3))
        scenes = 1 if t <= 8 else (2 if t <= 15 else (3 if t <= 30 else 4))

    # Dynamic scene breakdown recommendation
    if t <= 8:
        breakdown = f"Scene 1 (0-{t}s Hook & Punchline)"
    elif t <= 15:
        breakdown = f"Scene 1 (0-3s Hook), Scene 2 (3-{t}s Core & Punchline)"
    elif t <= 25:
        breakdown = f"Scene 1 (0-3s Hook), Scene 2 (3-{t-5}s Context), Scene 3 ({t-5}-{t}s CTA)"
    elif t <= 45:
        breakdown = f"Scene 1 (0-3s Hook), Scene 2 (3-{t//2}s Fact), Scene 3 ({t//2}-{t-6}s Impact), Scene 4 ({t-6}-{t}s CTA)"
    else:
        breakdown = f"Scene 1 (0-3s Hook), Scene 2 (3-{t//3}s Context), Scene 3 ({t//3}-{2*t//3}s Core), Scene 4 ({2*t//3}-{t-6}s Twist), Scene 5 ({t-6}-{t}s CTA)"

    words_str = f"Min: {min_words}w | Rec: {recommended_words}w | Max: {max_words}w"

    return {
        "duration": t,
        "min_words": min_words,
        "recommended_words": recommended_words,
        "max_words": max_words,
        "scenes": scenes,
        "breakdown": breakdown,
        "words_str": words_str,
        # Backwards compatible keys
        "target_words": recommended_words,
        "optimal_min": min_words,
        "optimal_max": max_words,
        "min": min_words,
        "max": max_words,
    }


def verify_word_count(text: str, target_seconds: int = 30) -> Tuple[int, str, str]:
    """
    Step 2: Verify spoken Hindi dialogue word count against reel target duration.
    
    CRITICAL RULE:
    - Less words than recommended or min is NOT an issue.
    - Exceeding max_words IS an issue (status: 'Exceeds Limit').
    
    Returns:
        (word_count, status, feedback_message)
    """
    words = count_words(text)
    budget = get_duration_budget(target_seconds)
    min_w = budget["min_words"]
    rec_w = budget["recommended_words"]
    max_w = budget["max_words"]

    if words > max_w:
        status = "Exceeds Limit"
        over = words - max_w
        feedback = (
            f"❌ Over Budget Issue: Spoken dialogue ({words} words) exceeds max allowed limit of "
            f"{max_w} words (+{over} words) for a {target_seconds}s reel (Rec: {rec_w}w, Min: {min_w}w). "
            f"Narration will overflow duration or sound rushed."
        )
    elif words < min_w:
        status = "Concise (Safe)"
        feedback = (
            f"✅ Within Budget: Spoken dialogue ({words} words) is below min ({min_w}w, Rec: {rec_w}w, Max: {max_w}w). "
            f"Safe for {target_seconds}s reel pacing—leaves ample room for B-roll and sound design pauses."
        )
    else:
        status = "Optimal"
        feedback = (
            f"✅ Optimal Pacing: Spoken dialogue ({words} words) fits comfortably within {min_w}–{max_w} words "
            f"(Recommended: {rec_w}w) for a {target_seconds}s reel."
        )

    return words, status, feedback


def verify_timeline_fit(word_count: int, target_seconds: int = 30) -> Tuple[float, str, str]:
    """
    Step 3: Verify whether the script fits into the target timeline.
    
    Standard Hindi Reel voiceover rate is ~2.2 words/sec
    plus pause buffer (~0.5s for <=10s, ~1.0s for >10s).
    
    Returns:
        (estimated_duration_sec, fit_status, feedback)
    """
    budget = get_duration_budget(target_seconds)
    max_w = budget["max_words"]
    speech_rate = 2.2
    pause_buffer = 0.5 if target_seconds <= 10 else 1.0

    estimated_seconds = round((word_count / speech_rate) + pause_buffer, 1)
    diff = round(estimated_seconds - target_seconds, 1)

    # Less is not an issue. More is an issue.
    if word_count > max_w or diff > 1.5:
        status = "Over Limit"
        feedback = f"⏱️ Pacing Alert: Estimated {estimated_seconds}s exceeds {target_seconds}s target by +{diff}s. Strict trimming needed."
    elif diff < -2.0:
        status = "Spacious Timeline (Safe)"
        feedback = f"🎯 Timeline Fit: Estimated {estimated_seconds}s is shorter than {target_seconds}s. Safe pacing with room for music & B-roll."
    else:
        status = "Fits Timeline"
        feedback = f"🎯 Timeline Fit: Estimated {estimated_seconds}s fits perfectly in {target_seconds}s slot (Difference: {diff:+}s)."

    return estimated_seconds, status, feedback


def evaluate_clarity(narration: str, hook: str, cta: str) -> int:
    """
    Step 4: Score clarity, retention hook, and call to action (0 - 100).
    """
    score = 80
    if hook and len(hook.strip()) > 4:
        score += 8
    if cta and len(cta.strip()) > 4:
        score += 7
    if any(p in hook for p in ["!", "?", "🚀", "🔥", "😂", "क्या", "सावधान", "भाई", "सुनो"]):
        score += 5
    return min(score, 99)
