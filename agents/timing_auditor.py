"""Agent 4: Timing & Duration Auditor Agent."""

from typing import Tuple, Optional
from core.metrics import verify_word_count, verify_timeline_fit, evaluate_clarity, get_duration_budget


class WordCountDurationAgent:
    """Mathematical and pacing auditor for speech length and duration fit."""

    def __init__(self):
        self.name = "Timing & Duration Auditor"
        self.role = "Word Count & Timeline Pacing Audit"
        self.icon = "⏱️"

    def audit_script(
        self,
        narration: str,
        hook: str,
        cta: str,
        target_seconds: int,
        sub_instruction: Optional[str] = None,
    ) -> Tuple[bool, int, str, float, str, int, str]:
        """
        Audit the spoken dialogue mathematically for word budget and speech timeline.
        
        CRITICAL VERIFICATION RULE:
        - Less words is completely fine and NOT an issue (provides breathing room for B-roll, SFX, and dramatic pauses).
        - Exceeding max_words IS A STRICT ISSUE (causes reel overflow or unnaturally fast speech).
        
        Returns:
            (passed, word_count, word_status, est_duration, timeline_status, clarity_score, feedback)
        """
        budget = get_duration_budget(target_seconds)
        min_w = budget["min_words"]
        rec_w = budget["recommended_words"]
        max_w = budget["max_words"]

        w_count, w_status, w_feedback = verify_word_count(narration, target_seconds)
        e_dur, t_status, t_feedback = verify_timeline_fit(w_count, target_seconds)
        clarity = evaluate_clarity(narration, hook, cta)

        # STRICT VERIFICATION:
        # Over max_words -> FAIL (Issue)
        # Less than or equal to max_words -> PASS (No issue if less)
        if w_status == "Exceeds Limit" or w_count > max_w:
            passed = False
            over = w_count - max_w
            feedback = (
                f"❌ Over Budget Issue: Spoken dialogue ({w_count} words) exceeds max allowed {max_w} words "
                f"by +{over} words for {target_seconds}s reel (Rec: {rec_w}w, Min: {min_w}w). "
                f"Reel duration will overflow!"
            )
        elif t_status == "Over Limit":
            passed = False
            diff = round(e_dur - target_seconds, 1)
            feedback = f"❌ Timeline Overflow: Estimated speech time ({e_dur}s) exceeds {target_seconds}s target by +{diff}s."
        elif w_status == "Concise (Safe)":
            passed = True  # NOT an issue if less!
            feedback = (
                f"✅ Pacing Certified: Spoken dialogue is concise ({w_count} words < {min_w}w min, Max: {max_w}w). "
                f"Safe for {target_seconds}s delivery with spacious B-roll and audio pauses."
            )
        else:
            passed = True
            feedback = (
                f"✅ Pacing Certified: Spoken dialogue ({w_count} words) is optimal for {target_seconds}s reel "
                f"(Rec: {rec_w}w, Min: {min_w}w, Max: {max_w}w)."
            )

        return passed, w_count, w_status, e_dur, t_status, clarity, feedback


timing_auditor = WordCountDurationAgent()

