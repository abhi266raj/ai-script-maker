"""#138 regression: every script in a multi-script batch must carry a DISTINCT
editorial angle.

Root cause: execute_stage_2 stamped the SAME preferred_angle on all N batch
slots (get_effective_angle() never returns empty, so the REEL_ANGLES cycling
branch was dead code). The batch prompt then carried N identical SCRIPT
briefs and the model repeated script 1 N times. Detection gates (#147)
cannot fix identical inputs.

These tests pin build_batch_angles: preferred angle keeps slot 1, remaining
slots cycle REEL_ANGLES with the preferred angle excluded, all normalized-
distinct. They FAIL on pristine develop (no build_batch_angles there) and
PASS with the fix.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.chief_editor import build_batch_angles, _norm_angle_name  # noqa: E402


def _distinct_normed(angles):
    return len({_norm_angle_name(a[0]) for a in angles})


def test_preferred_angle_keeps_first_slot():
    angles = build_batch_angles(4, "Funny & Relatable")
    assert angles[0][0] == "Funny & Relatable"
    assert angles[0][1] == "User-selected editorial angle"


def test_all_slots_distinct_with_preferred_angle():
    # The exact #138 scenario: 4 scripts, vibe-derived angle always set.
    angles = build_batch_angles(4, "Funny & Relatable")
    assert len(angles) == 4
    assert _distinct_normed(angles) == 4, (
        "every batch slot must carry a distinct angle, got: "
        f"{[a[0] for a in angles]}"
    )


def test_preferred_angle_deduped_against_reel_angles():
    # "Funny & Relatable" must not reappear as "1. Funny & Relatable".
    angles = build_batch_angles(4, "Funny & Relatable")
    normed = [_norm_angle_name(a[0]) for a in angles]
    assert normed.count("funny & relatable") == 1


def test_all_slots_distinct_without_preferred_angle():
    angles = build_batch_angles(3, "")
    assert len(angles) == 3
    assert _distinct_normed(angles) == 3


def test_single_script_keeps_preferred_angle():
    angles = build_batch_angles(1, "Dramatic Storytelling")
    assert len(angles) == 1
    assert angles[0][0] == "Dramatic Storytelling"


def test_batch_items_carry_distinct_angles_end_to_end():
    # Mirrors execute_stage_3's batch_items construction: N distinct
    # (angle, hook) pairs must reach the batch prompt. Distinct angles are
    # the structural guarantee; identical angles were the #138 input bug.
    total = 4
    selected_angles = build_batch_angles(total, "Gen-Z Hinglish")
    hooks = [f"hook-{i}-distinct" for i in range(total)]
    batch_items = [
        {"angle": selected_angles[i][0], "hook": hooks[i]}
        for i in range(total)
    ]
    angle_set = {_norm_angle_name(it["angle"]) for it in batch_items}
    assert len(angle_set) == total, (
        f"batch prompt briefs must be pairwise distinct by angle, got: "
        f"{[it['angle'] for it in batch_items]}"
    )


def test_norm_strips_numbering_and_case():
    assert _norm_angle_name("1. Funny & Relatable") == _norm_angle_name("Funny & Relatable")
    assert _norm_angle_name("  10. Audience Debate & Engagement Poll ") == (
        "audience debate & engagement poll"
    )
