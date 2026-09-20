"""Test Suite for Master Agent Instruction Decomposition and Sub-Instruction Dispatch."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.metrics import get_duration_budget
from agents.chief_editor import chief_editor
from workflow import reel_workflow


def test_decompose_master_instruction():
    """Verify that Master Agent divides instructions into 7 sub-instructions with strict dialogue word limits."""
    topic = "ISRO Gaganyaan Mission: Human spaceflight trial test successful."
    target_seconds = 30
    budget = get_duration_budget(target_seconds)

    sub_instructions = chief_editor.decompose_master_instruction(
        master_instruction="Create a dialogue screenplay for ISRO news.",
        news_topic=topic,
        target_seconds=target_seconds,
        tone="🇮🇳 Desi Swag & Cultural Pride (भारतीय गौरव)",
        angle="Inspirational & Uplifting",
        character_count=2,
        scene_style="Dialogue",
        batch_size=1,
        max_retries=5,
        budget=budget,
    )

    # 1. Must contain all 7 specialized agents
    expected_agents = [
        "news_validator",
        "hook_strategist",
        "dialogue_writer",
        "timing_auditor",
        "scene_director",
        "video_prompt_engineer",
        "video_quality_gate",
    ]
    for agent_key in expected_agents:
        assert agent_key in sub_instructions, f"Missing sub-instruction for {agent_key}"
        assert len(sub_instructions[agent_key]) > 20, f"Sub-instruction for {agent_key} is too short"

    # 2. Dialogue writer sub-instruction MUST specify exact dialogue word count limits
    dw_sub = sub_instructions["dialogue_writer"]
    assert f"~{budget['recommended_words']}" in dw_sub, "Missing recommended words in dialogue_writer sub-instruction"
    assert f"{budget['max_words']} words" in dw_sub, "Missing max words in dialogue_writer sub-instruction"
    assert f"{budget['min_words']} words" in dw_sub, "Missing min words in dialogue_writer sub-instruction"
    assert "Speech Rate" in dw_sub
    assert "PACING ASYMMETRY" in dw_sub

    # 3. Timing auditor sub-instruction must specify strict verification
    ta_sub = sub_instructions["timing_auditor"]
    assert f"{budget['max_words']}w" in ta_sub
    assert "smart trim" in ta_sub


def test_custom_durations_sub_instructions():
    """Verify that different durations adjust dialogue word limits in sub-instructions."""
    for dur in [5, 15, 60]:
        budget = get_duration_budget(dur)
        subs = chief_editor.decompose_master_instruction(
            master_instruction="Test instruction",
            news_topic="Test Topic",
            target_seconds=dur,
            tone="Urgent",
            angle="Breaking",
            character_count=1,
            scene_style="Narration",
            batch_size=1,
            max_retries=3,
            budget=budget,
        )
        dw = subs["dialogue_writer"]
        assert f"~{budget['recommended_words']}" in dw
        assert f"{budget['max_words']} words" in dw


if __name__ == "__main__":
    print("Running Instruction Decomposition tests...")
    test_decompose_master_instruction()
    print("✅ test_decompose_master_instruction passed")
    test_custom_durations_sub_instructions()
    print("✅ test_custom_durations_sub_instructions passed")
    print("\n🎉 ALL INSTRUCTION DECOMPOSITION TESTS PASSED!")
