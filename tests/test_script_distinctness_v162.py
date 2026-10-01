"""#138: generated scripts must be distinct — never one script repeated N times.

Covers:
1. Identical SCRIPT blocks across a batch raise ModelGenerationError (loudly).
2. Near-duplicate (>90% similar) blocks raise.
3. Distinct blocks pass and each narration keeps its own block's content
   (parsing never duplicates one block into another slot).
4. The batch prompt template mandates SCRIPT N headers and distinctness.
5. Multi-script retry keeps the batch generation prompt (the single-script
   refine prompt would collapse the batch to one script).
"""
import os
import re
import sys
from unittest.mock import patch

import pytest

# NOTE: `agents/__init__.py` does `from .dialogue_writer import dialogue_writer`
# (the singleton instance), shadowing the submodule — so `from agents import
# dialogue_writer` binds the INSTANCE. Reach the module via sys.modules.
_dw_instance = None  # resolved lazily below
dw_mod = sys.modules.get("agents.dialogue_writer")
if dw_mod is None:
    import importlib
    dw_mod = importlib.import_module("agents.dialogue_writer")
from core.dual_engine import ModelGenerationError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ITEMS_4 = [
    {"angle": "Angle one", "hook": "पहला हुक"},
    {"angle": "Angle two", "hook": "दूसरा हुक"},
    {"angle": "Angle three", "hook": "तीसरा हुक"},
    {"angle": "Angle four", "hook": "चौथा हुक"},
]


def _beat_block(script_no, lines):
    beats = "\n".join(
        f'BEAT {i + 1}:\nCHARACTER: Host\nDIALOGUE: "{ln}"'
        for i, ln in enumerate(lines)
    )
    return f"SCRIPT {script_no}:\n{beats}\n"


def _distinct_batch_raw():
    return (
        _beat_block(1, ["आज बाज़ार में सब्ज़ियों के दाम आसमान छू रहे हैं।",
                        "हाँ भाई, टमाटर तो सोने के भाव बिक रहा है।"])
        + _beat_block(2, ["ट्रैफिक पुलिस ने नया चालान अभियान शुरू किया है।",
                          "अब तो हेलमेट पहनना ही पड़ेगा, कोई चारा नहीं।"])
        + _beat_block(3, ["स्कूलों में गर्मी की छुट्टियां बढ़ा दी गई हैं।",
                          "बच्चों की तो मौज हो गई, खेलने का पूरा समय।"])
        + _beat_block(4, ["रेलवे ने त्योहारों पर स्पेशल ट्रेनें चलाने का ऐलान किया।",
                          "अब घर जाने में टिकट की मारामारी नहीं होगी।"])
    )


def _call(items, raw_outputs, **kw):
    """Run write_dialogues_batch with stubbed model output(s)."""
    agent = dw_mod.dialogue_writer
    params = dict(
        news_input="test news", items=items, tone="Neutral", duration_sec=20,
        verification=None, character_count=1, scene_style="Monologue",
        _max_retries=0,
    )
    params.update(kw)
    with patch.object(agent, "execute", side_effect=raw_outputs), \
         patch.object(dw_mod, "ai_judge_script_quality",
                      return_value=(True, "", True, "")), \
         patch.object(dw_mod, "find_formal_hindi", return_value=[]):
        return agent.write_dialogues_batch(**params)


class TestDuplicateDetection:
    def test_identical_blocks_raise_loudly(self):
        dup_block = _beat_block(1, ["आज बहुत गर्मी है और बाज़ार बंद है।",
                                    "हाँ, सब लोग घरों में दुबके हैं।"])
        raw = dup_block + dup_block.replace("SCRIPT 1:", "SCRIPT 2:") \
            + dup_block.replace("SCRIPT 1:", "SCRIPT 3:") \
            + dup_block.replace("SCRIPT 1:", "SCRIPT 4:")
        with pytest.raises(ModelGenerationError, match="[Dd]uplicate"):
            _call(ITEMS_4, [raw])

    def test_near_duplicate_blocks_raise(self):
        base = ("राम ने कहा कि आज बहुत गर्मी है और बाज़ार में सब्ज़ियां महंगी हो गई हैं "
                "इसलिए लोग परेशान हैं और सरकार से मदद मांग रहे हैं।")
        near = ("राम ने कहा कि आज बहुत गर्मी है और बाज़ार में सब्ज़ियां महंगी हो गयी हैं "
                "इसलिए लोग परेशान हैं और सरकार से मदद मांग रहे हैं।")
        raw = _beat_block(1, [base]) + _beat_block(2, [near])
        with pytest.raises(ModelGenerationError, match="[Dd]uplicate"):
            _call(ITEMS_4[:2], [raw])

    def test_distinct_blocks_pass(self):
        result = _call(ITEMS_4, [_distinct_batch_raw()])
        assert len(result) == 4, f"expected 4 narrations, got {len(result)}"

    def test_parsing_does_not_duplicate_blocks(self):
        """Each narration must contain its own block's unique content."""
        result = _call(ITEMS_4, [_distinct_batch_raw()])
        texts = [str(n) for n in result]
        assert "सब्ज़ियों के दाम" in texts[0]
        assert "चालान अभियान" in texts[1]
        assert "गर्मी की छुट्टियां" in texts[2]
        assert "स्पेशल ट्रेनें" in texts[3]
        # No block's content leaks into another narration.
        assert "चालान अभियान" not in texts[0]
        assert "सब्ज़ियों के दाम" not in texts[3]


class TestPromptMandate:
    def _template(self):
        path = os.path.join(REPO_ROOT, "prompts", "dialogue_writer", "write_dialogue_batch.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_template_mandates_script_headers(self):
        content = self._template()
        assert "SCRIPT 1:" in content, "template must show the SCRIPT 1: header format"
        assert "num_scripts" in content, "template must reference the script count"

    def test_template_mandates_distinctness(self):
        content = self._template()
        assert "DISTINCT" in content, "template must demand distinct scripts"
        assert re.search(r"[Nn]ever copy.*repeat|duplicat", content), \
            "template must ban copying/repeating content between scripts"

    def test_render_includes_script_count(self):
        rendered = dw_mod.render_prompt(
            "dialogue_writer/write_dialogue_batch.md",
            role_identity="x", news_input="x", duration_sec=20, actual_scenes=2,
            rec_words=10, max_words=20, min_words=5, per_scene_words=5,
            per_scene_max=8, narrative_name="n", narrative_desc="d",
            character_count=1, personas_list="- x", setting_location="s",
            scene_setting_lines="", dialogue_type_directive="d",
            physical_props="p", core_conflict="c", facts_text="f",
            creative_rules="", sample_directive="", sub_directive="",
            revision_directive="", guidance="", items_desc="SCRIPT 1:\n...",
            num_scripts=4, sample_scenes="s", tone="Neutral",
        )
        assert "SCRIPT 4" in rendered, "rendered prompt must enumerate all 4 scripts"


class TestMultiScriptRetry:
    def test_retry_keeps_batch_prompt_for_multi_script(self):
        """A validation failure on a 2-script batch must retry with the batch
        generation prompt — never the single-script refine prompt (which would
        collapse the batch)."""
        bad = (
            "SCRIPT 1:\n"
            "BEAT 1:\nCHARACTER: Host\nDIALOGUE: \"Welcome to the show?\"\n"
            "BEAT 2:\nCHARACTER: Guest\nDIALOGUE: \"Thanks, shall we begin?\"\n"
            "SCRIPT 2:\n"
            "BEAT 1:\nCHARACTER: Host\nDIALOGUE: \"आज की बड़ी खबर क्या है?\"\n"
            "BEAT 2:\nCHARACTER: Host\nDIALOGUE: \"मैं ही बता देता हूँ।\"\n"
        )
        fixed = (
            "SCRIPT 1:\n"
            "BEAT 1:\nCHARACTER: Host\nDIALOGUE: \"Welcome to the show?\"\n"
            "BEAT 2:\nCHARACTER: Guest\nDIALOGUE: \"Thanks, happy to be here.\"\n"
            "SCRIPT 2:\n"
            "BEAT 1:\nCHARACTER: Host\nDIALOGUE: \"आज की बड़ी खबर क्या है?\"\n"
            "BEAT 2:\nCHARACTER: Guest\nDIALOGUE: \"सुनिए, बहुत दिलचस्प मामला है।\"\n"
        )
        agent = dw_mod.dialogue_writer
        prompts_seen = []
        items = [{"angle": "A1", "hook": "h1"}, {"angle": "A2", "hook": "h2"}]

        def fake_execute(prompt, **kw):
            prompts_seen.append(prompt)
            return [bad, fixed][len(prompts_seen) - 1]

        with patch.object(agent, "execute", side_effect=fake_execute), \
             patch.object(dw_mod, "ai_judge_script_quality",
                          return_value=(True, "", True, "")), \
             patch.object(dw_mod, "find_formal_hindi", return_value=[]):
            result = agent.write_dialogues_batch(
                news_input="talk show", items=items, tone="Neutral",
                duration_sec=20, verification=None, character_count=2,
                scene_style="Interview", _max_retries=1,
            )
        assert len(prompts_seen) == 2, f"expected 1 retry, saw {len(prompts_seen)} prompts"
        retry_prompt = prompts_seen[1]
        assert "SURGICAL REFINEMENT" not in retry_prompt, \
            "multi-script retry must NOT use the single-script refine prompt"
        assert "Scripts to Write" in retry_prompt, \
            "multi-script retry must keep the batch generation prompt"
        assert "SCRIPT 2" in retry_prompt, \
            "retry prompt must still enumerate both scripts"
        assert result and len(result) == 2


class TestStage6DuplicateGate:
    """#138: execute_stage_6 must fail loudly when the assembled batch
    result would contain duplicated scripts — the last line of defense
    before res.scripts reaches the UI."""

    def _script(self, sid, narration):
        from core.models import ReelScript
        return ReelScript(
            id=sid, title=f"Reel #{sid}", angle=f"Angle {sid}",
            hook_hindi=f"hook {sid}", narration_hindi=narration,
        )

    def _state(self, scripts):
        from core.models import NewsVerificationReport
        return {
            "scripts": scripts,
            "target_seconds": 30,
            "active_sample_story": "",
            "news_input": "test news",
            "scenario": "test",
            "verification": NewsVerificationReport(is_verified=True, confidence_score=90),
            "sub_instructions": {},
            "total_retries": 0,
            "start_time": 0,
            "agent_audits": [],
            "script_dialogues": [],
            "derived_scenes_per_script": [],
            "finalized_characters": [],
        }

    def _run_stage6(self, scripts):
        import sys as _sys
        ce_mod = _sys.modules["agents.chief_editor"]
        chief = ce_mod.chief_editor_coordinator
        state = self._state(scripts)
        with patch.object(chief, "run_validation_gate",
                          return_value={"passed": True, "issues": [], "summary": "ok"}):
            return chief.execute_stage_6(state, engine_mode="test")

    def test_duplicate_narrations_raise_loudly(self):
        s1 = self._script(1, "यह पहली कहानी है, बाज़ार में हलचल है।")
        s2 = self._script(2, "यह पहली कहानी है, बाज़ार में हलचल है।")
        with pytest.raises(ModelGenerationError, match="duplicates"):
            self._run_stage6([s1, s2])

    def test_shared_object_reference_raises_loudly(self):
        s1 = self._script(1, "यह पहली कहानी है, बाज़ार में हलचल है।")
        with pytest.raises(ModelGenerationError, match="SAME object"):
            self._run_stage6([s1, s1])

    def test_distinct_scripts_pass(self):
        scripts = [
            self._script(1, "यह पहली कहानी है, बाज़ार में हलचल है।"),
            self._script(2, "मौसम विभाग ने भारी बारिश की चेतावनी दी है।"),
        ]
        state = self._run_stage6(scripts)
        br = state["batch_result"]
        assert len(br.scripts) == 2
        assert br.scripts[0].narration_hindi != br.scripts[1].narration_hindi
