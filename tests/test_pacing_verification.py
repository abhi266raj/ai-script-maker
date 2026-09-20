"""Test Suite for Duration-Based Spoken Dialogue Word Limits and Asymmetric Verification.

Verification Rule:
- Less words is NOT an issue (provides breathing room for pauses, B-roll, SFX).
- More words than max_words IS an issue (overflows target duration).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.metrics import get_duration_budget, verify_word_count, verify_timeline_fit, count_words
from agents.timing_auditor import timing_auditor


def test_duration_budget_min_rec_max():
    """Verify that get_duration_budget correctly specifies min, recommended, and max word counts."""
    # Test 5s
    b5 = get_duration_budget(5)
    assert b5["min_words"] == 4
    assert b5["recommended_words"] == 10
    assert b5["max_words"] == 11
    assert b5["min_words"] < b5["recommended_words"] <= b5["max_words"]

    # Test 10s
    b10 = get_duration_budget(10)
    assert b10["min_words"] == 8
    assert b10["recommended_words"] == 20
    assert b10["max_words"] == 23

    # Test 15s
    b15 = get_duration_budget(15)
    assert b15["min_words"] == 12
    assert b15["recommended_words"] == 30
    assert b15["max_words"] == 34

    # Test 30s
    b30 = get_duration_budget(30)
    assert b30["min_words"] == 24
    assert b30["recommended_words"] == 60
    assert b30["max_words"] == 69

    # Test 60s
    b60 = get_duration_budget(60)
    assert b60["min_words"] == 48
    assert b60["recommended_words"] == 120
    assert b60["max_words"] == 138

    # Test custom duration (e.g. 7s)
    b7 = get_duration_budget(7)
    assert b7["min_words"] > 0
    assert b7["recommended_words"] > b7["min_words"]
    assert b7["max_words"] >= b7["recommended_words"]


def test_asymmetric_word_count_verification():
    """
    Verify the asymmetry rule:
    - Less words is NOT an issue.
    - More words than max_words IS an issue.
    """
    target_sec = 10
    budget = get_duration_budget(target_sec)  # min=8, rec=20, max=23

    # Case 1: Less than min (e.g. 5 words) -> Safe, NOT an issue
    short_text = "इसरो ने नया उपग्रह भेजा"
    words_short, status_short, fb_short = verify_word_count(short_text, target_sec)
    assert words_short <= budget["min_words"]
    assert status_short == "Concise (Safe)"
    assert "Within Budget" in fb_short

    # Case 2: Recommended/Optimal (e.g. 18 words) -> Safe, Optimal
    optimal_text = " " .join(["शब्द"] * 18)
    words_opt, status_opt, fb_opt = verify_word_count(optimal_text, target_sec)
    assert budget["min_words"] <= words_opt <= budget["max_words"]
    assert status_opt == "Optimal"
    assert "Optimal Pacing" in fb_opt

    # Case 3: Exactly max_words (e.g. 23 words) -> Safe, Optimal
    exact_max_text = " " .join(["शब्द"] * budget["max_words"])
    words_max, status_max, fb_max = verify_word_count(exact_max_text, target_sec)
    assert words_max == budget["max_words"]
    assert status_max == "Optimal"

    # Case 4: Exceeds max_words (e.g. 30 words) -> ISSUE!
    over_text = " " .join(["शब्द"] * 30)
    words_over, status_over, fb_over = verify_word_count(over_text, target_sec)
    assert words_over > budget["max_words"]
    assert status_over == "Exceeds Limit"
    assert "❌ Over Budget Issue" in fb_over


def test_timing_auditor_agent_verification():
    """
    Test that Agent 4 (Timing & Duration Auditor) passes under-budget dialogue
    and fails over-budget dialogue.
    """
    target_sec = 15  # min=12, rec=30, max=34
    hook = "सावधान दोस्तों!"
    cta = "फॉलो जरूर करें!"

    # Test A: Very short dialogue (6 words) -> MUST PASS (less is not an issue)
    short_dialogue = "यह तकनीक पूरी दुनिया बदल देगी"
    passed, w_cnt, w_stat, e_dur, t_stat, clarity, feedback = timing_auditor.audit_script(
        narration=short_dialogue, hook=hook, cta=cta, target_seconds=target_sec
    )
    assert passed is True, f"Short dialogue should pass without issue, got: {feedback}"
    assert w_stat == "Concise (Safe)"
    assert "Pacing Certified" in feedback

    # Test B: Optimal dialogue (28 words) -> MUST PASS
    opt_dialogue = " " .join(["यह तकनीक पूरी दुनिया को हिलाकर रख देगी और भारत का नाम सबसे ऊपर होगा"] * 2)
    passed, w_cnt, w_stat, e_dur, t_stat, clarity, feedback = timing_auditor.audit_script(
        narration=opt_dialogue, hook=hook, cta=cta, target_seconds=target_sec
    )
    assert passed is True
    assert w_stat == "Optimal"

    # Test C: Over-budget dialogue (50 words > 34 max) -> MUST FAIL (issue if more)
    over_dialogue = " " .join(["खबर बहुत बड़ी है और विश्लेषण बहुत लंबा है"] * 7)
    passed, w_cnt, w_stat, e_dur, t_stat, clarity, feedback = timing_auditor.audit_script(
        narration=over_dialogue, hook=hook, cta=cta, target_seconds=target_sec
    )
    assert passed is False, f"Over-budget dialogue must fail verification, got: {feedback}"
    assert w_stat == "Exceeds Limit"
    assert "Over Budget Issue" in feedback


if __name__ == "__main__":
    print("Running Pacing & Verification tests...")
    test_duration_budget_min_rec_max()
    print("✅ test_duration_budget_min_rec_max passed")
    test_asymmetric_word_count_verification()
    print("✅ test_asymmetric_word_count_verification passed")
    test_timing_auditor_agent_verification()
    print("✅ test_timing_auditor_agent_verification passed")
    print("\n🎉 ALL ASYMMETRIC PACING TESTS PASSED!")
