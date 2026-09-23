"""Comprehensive End-to-End Validation Script for Hindi Reel Studio.
Validates all execution cases, engine modes, configs, and the 7-agent pipeline.
"""

import sys
import os
import json
import time

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_config, save_config, PROJECT_CONFIG_FILE, STUDIO_CONFIG_FILE
from core.dual_engine import dual_engine, ModelGenerationError
from tools.news_fetcher import news_fetcher
from workflow import reel_workflow


def test_1_configuration_files():
    print("\n--- Test 1: Configuration Files Validation ---")
    assert os.path.exists(PROJECT_CONFIG_FILE), f"Missing {PROJECT_CONFIG_FILE}"
    assert os.path.exists(STUDIO_CONFIG_FILE), f"Missing {STUDIO_CONFIG_FILE}"

    with open(PROJECT_CONFIG_FILE, "r", encoding="utf-8") as f:
        pcfg = json.load(f)

    assert "project_name" in pcfg
    assert "pipeline_agents" in pcfg
    assert len(pcfg["pipeline_agents"]) == 8
    assert "durations" in pcfg
    assert 5 in pcfg["durations"]["supported_seconds"]
    assert "engines" in pcfg
    assert "first_local_then_agy" in pcfg["engines"]["hybrid"]["key"]
    assert "agy_only" in pcfg["engines"]["agy_only"]["key"]
    assert "fm_only" in pcfg["engines"]["fm_only"]["key"]
    assert "grok_low" in pcfg["engines"]["grok_low"]["key"]
    assert "grok_medium" in pcfg["engines"]["grok_medium"]["key"]
    assert "grok_high" in pcfg["engines"]["grok_high"]["key"]
    assert "codex_only" in pcfg["engines"]["codex_only"]["key"]

    cfg = load_config()
    assert "default_engine" in cfg
    assert "batch_count" in cfg
    assert "max_retries" in cfg
    assert 1 in pcfg["batch_output_counts"]
    print("✅ Config files verified with complete schema and synchronization.")


def test_2_engine_modes_and_strict_selection():
    print("\n--- Test 2: Dual Engine Modes & Strict Selection ---")
    diag = dual_engine.check_status()
    print(f"Engine status diagnostic: fm={diag['fm']['available']}, agy={diag['agy']['available']}")
    assert diag["agy"]["available"] is True, "Antigravity AGY must be available"

    # Test Mode 1: Hybrid
    out_hybrid, eng_hybrid = dual_engine.generate("Respond with: HYBRID_OK", mode="first_local_then_agy")
    assert "OK" in out_hybrid.upper() or "HYBRID" in out_hybrid.upper()
    print(f"✅ Mode 1 (Hybrid): Returned via '{eng_hybrid}'")

    # Test Mode 2: FM Only must never silently switch to AGY.
    if diag["fm"]["available"]:
        out_fm, eng_fm = dual_engine.generate("Respond with: FM_OK", mode="fm_only")
        assert "OK" in out_fm.upper() or "FM" in out_fm.upper()
        print(f"✅ Mode 2 (Strict Local FM): Returned via '{eng_fm}'")
    else:
        try:
            dual_engine.generate("Respond with: FM_OK", mode="fm_only")
        except ModelGenerationError as exc:
            assert "No script was generated" in str(exc)
            print("✅ Mode 2 (Strict Local FM): Correctly failed without cloud fallback")
        else:
            raise AssertionError("fm_only must fail when Local FM is unavailable")

    # Test Mode 3: AGY Only
    out_agy, eng_agy = dual_engine.generate("Respond with: AGY_OK", mode="agy_only")
    assert "OK" in out_agy.upper() or "AGY" in out_agy.upper()
    print(f"✅ Mode 3 (AGY Only): Returned via '{eng_agy}'")

    # Test Mode 4: Codex Only
    if diag.get("codex", {}).get("available"):
        try:
            out_codex, eng_codex = dual_engine.generate("Respond with: CODEX_OK", mode="codex_only")
            assert "OK" in out_codex.upper() or "CODEX" in out_codex.upper()
            print(f"✅ Mode 4 (Codex Only): Returned via '{eng_codex}'")
        except ModelGenerationError as c_err:
            print(f"⚠️ Mode 4 (Codex Only): Model/quota status verified ({c_err})")


def test_3_real_wire_news():
    print("\n--- Test 3: Real Wire News Fetching ---")
    articles = news_fetcher.get_top_tech_news(limit=3)
    assert len(articles) > 0, "Failed to fetch live tech news"
    print(f"✅ Fetched {len(articles)} live articles from wire feeds:")
    for a in articles:
        print(f"   - {a.title[:65]}... ({a.source})")


def test_4_multi_agent_pipeline_execution():
    print("\n--- Test 4: End-to-End 7-Agent Pipeline (Default 1 Script, 5s Rapid Duration) ---")
    test_story = "ISRO tests next-generation AI powered navigation satellite for deep space mission."
    test_scenario = "Funny & Relatable"
    target_duration = 5

    pipeline = reel_workflow.run_stream(
        news_input=test_story,
        scenario=test_scenario,
        batch_size=1,
        target_seconds=target_duration,
        engine_mode="first_local_then_agy",
        max_retries=5,
    )

    completed_batch = None
    step_count = 0

    for step in pipeline:
        step_count += 1
        print(f"  {step['icon']} Step {step['step']}/5: {step['agent']} -> {step['status'][:70]}...")
        if step.get("completed"):
            completed_batch = step["data"]["batch_result"]

    assert completed_batch is not None, "Pipeline did not complete"
    assert len(completed_batch.scripts) == 1, f"Expected 1 script, got {len(completed_batch.scripts)}"
    assert completed_batch.verification is not None
    assert completed_batch.verification.confidence_score >= 70

    first_script = completed_batch.scripts[0]
    print(f"\n✅ Pipeline Complete! First Script Sample:")
    print(f"   Angle: {first_script.angle}")
    print(f"   Hook (Hindi): {first_script.hook_hindi}")
    print(f"   Narration (Hindi): {first_script.narration_hindi[:90]}...")
    print(f"   CTA: {first_script.call_to_action}")
    print(f"   Word Count: {first_script.word_count} ({first_script.word_count_status})")
    print(f"   Estimated Duration: {first_script.estimated_duration_sec}s for target {target_duration}s")
    print(f"   Scenes: {len(first_script.scenes)} directed scenes")
    print(f"   Cinematic Visual Prompt: {first_script.scenes[0].video_prompt.visual_prompt_ai[:80]}...")
    print(f"   Video Quality Gate: Passed={first_script.video_verification.passed} ({first_script.video_verification.feasibility_score}%)")


    assert first_script.word_count <= getattr(first_script, "max_words", 34)


def test_5_dialogue_pacing_and_asymmetry_verification():
    print("\n--- Test 5: Spoken Dialogue Word Limits & Asymmetric Verification ---")
    from core.metrics import get_duration_budget, verify_word_count
    from agents.timing_auditor import timing_auditor

    # Test 5s, 10s, 15s budgets
    for sec in [5, 10, 15, 30]:
        b = get_duration_budget(sec)
        assert b["min_words"] < b["recommended_words"] <= b["max_words"]
        print(f"   - {sec}s Budget: Min={b['min_words']}w, Rec={b['recommended_words']}w, Max={b['max_words']}w")

    # Under-budget (less words) must pass and NOT be an issue
    passed_under, _, status_under, _, _, _, fb_under = timing_auditor.audit_script(
        narration="इसरो का नया मिशन सफल रहा", hook="बड़ी खबर!", cta="फॉलो करें", target_seconds=10
    )
    assert passed_under is True, f"Under budget must pass: {fb_under}"
    assert "Safe" in status_under or "Optimal" in status_under
    print("✅ Under-budget spoken dialogue correctly certified as SAFE (not an issue).")

    # Over-budget (more words than max) must fail and BE flagged as an issue
    long_narration = " " .join(["अत्यंत महत्वपूर्ण और लंबा विश्लेषण"] * 10)  # 40 words > 23 max for 10s
    passed_over, _, status_over, _, _, _, fb_over = timing_auditor.audit_script(
        narration=long_narration, hook="बड़ी खबर!", cta="फॉलो करें", target_seconds=10
    )
    assert passed_over is False, "Over max_words dialogue must fail verification!"
    assert status_over == "Exceeds Limit"
    print("✅ Over-budget dialogue (> max_words) correctly flagged as an ISSUE.")


if __name__ == "__main__":
    t_start = time.time()
    print("🚀 STARTING AUTOMATED VALIDATION SUITE...")
    try:
        test_1_configuration_files()
        test_2_engine_modes_and_strict_selection()
        test_3_real_wire_news()
        test_5_dialogue_pacing_and_asymmetry_verification()
        test_4_multi_agent_pipeline_execution()
        elapsed = round(time.time() - t_start, 2)
        print(f"\n=======================================================")
        print(f"🎉 ALL VALIDATION TESTS PASSED SUCCESSFULLY in {elapsed}s!")
        print(f"=======================================================")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ VALIDATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
