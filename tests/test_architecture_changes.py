"""Architecture contract tests for the 2026-09-24 pipeline changes.

Covers (all AI engines mocked — logic/flow only, never model output):
  1. News coverage = AI judge ONLY. No token/regex/substring matching.
     The judge sees ONLY the short news title / basic content (never the
     full verified-facts list); its VERDICT + REASON are surfaced; engine
     errors become a VISIBLE warning, never a silent pass/fail.
  2. Fail-fast validation: first sub-check failure stops the rest, skipped
     checks are marked "Skipped (X failed)" (never "Not reached"), and checks
     run most-failure-prone-first (Structure -> News -> Tone -> Language).
  3. Cumulative preview: the preview accumulates EVERY completed stage's
     output (not just the current stage), each in its own section, via ONE
     shared renderer used by both continuous and stepwise modes.
  4. Facts piping: Stage 1 verified_facts reach Stage 2/3/4/5 prompts —
     no stage operates on the headline alone.

Run: python3 -m pytest tests/test_architecture_changes.py -v
"""

import ast
import inspect
import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import agents.dialogue_writer as dw
import agents.chief_editor as ce_mod

PASS_MARK = []


# ---------------------------------------------------------------- helpers

FACTS = ["Project cost estimated at Rs 4,200 crore",
         "Six new stations sanctioned on the corridor"]
NEWS_TOPIC = "Metro line extension approved in the city"
HOOK = "Commuters cheer as metro gets 40km extension"


class FakeJudgeAgent:
    """Mock AI engine for ai_judge_news_coverage: records the prompt it got."""

    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.last_prompt = None
        self.calls = 0

    def execute(self, prompt, engine_mode=None):
        self.calls += 1
        self.last_prompt = prompt
        if self.exc is not None:
            raise self.exc
        return self.response


def good_beats():
    return [
        {"character": "Rohan", "dialogue": "सुना? मेट्रो को 40 किलोमीटर का विस्तार मिल गया!"},
        {"character": "Meena", "dialogue": "हाँ भाई, अब सफ़र आसान हो जाएगा!"},
    ]


def make_check_specs(calls, fail_at=None):
    """Build 4 ordered check specs; the check at fail_at index reports problems."""

    def _mk(name, idx):
        def _run():
            calls.append(name)
            if fail_at == idx:
                return {
                    "problems": [f"{name} broken"],
                    "pass_output": "Passed",
                    "feedback": f"fix {name}",
                }
            return {"problems": [], "pass_output": "Passed", "feedback": ""}
        return _run

    names = ["Structure check", "News coverage check", "Tone check", "Language check"]
    return [
        {"sub": str(i + 1), "name": n, "input": f"input for {n}", "run": _mk(n, i)}
        for i, n in enumerate(names)
    ]


# ============================================================ 1. NEWS COVERAGE

class TestNewsCoverageJudgeOnly:
    def test_no_token_matching_function_exists(self):
        # The regex/token validator was deleted; coverage is judge-only.
        assert not hasattr(dw, "validate_news_coverage"), (
            "validate_news_coverage still exists — token matching was supposed "
            "to be removed entirely"
        )
        src = inspect.getsource(dw)
        assert "validate_news_coverage" not in src

    def test_judge_accepts_dialogue_that_states_news(self):
        agent = FakeJudgeAgent(
            "VERDICT: YES\nREASON: The dialogue clearly states the 40km metro extension."
        )
        ok, reason = dw.ai_judge_news_coverage(agent, good_beats(), NEWS_TOPIC, HOOK)
        assert ok is True
        assert "YES" in reason

    def test_judge_rejects_generic_filler(self):
        agent = FakeJudgeAgent(
            "VERDICT: NO\nREASON: Only generic filler, no specific event mentioned."
        )
        ok, reason = dw.ai_judge_news_coverage(agent, good_beats(), NEWS_TOPIC, HOOK)
        assert ok is False
        assert "NO" in reason

    def test_judge_reason_is_surfaced_not_hidden(self):
        agent = FakeJudgeAgent(
            "VERDICT: YES\nREASON: Mentions the metro extension and the 40km figure."
        )
        ok, reason = dw.ai_judge_news_coverage(agent, good_beats(), NEWS_TOPIC, HOOK)
        assert "Mentions the metro extension and the 40km figure." in reason, (
            f"judge REASON not surfaced in output: {reason!r}"
        )

    def test_judge_sees_only_basic_content_never_full_facts(self):
        # Contract: the judge signature must not even accept verified facts.
        sig = inspect.signature(dw.ai_judge_news_coverage)
        assert "verified_facts" not in sig.parameters, (
            f"judge still accepts verified_facts: {list(sig.parameters)}"
        )
        agent = FakeJudgeAgent("VERDICT: YES\nREASON: Clear.")
        dw.ai_judge_news_coverage(agent, good_beats(), NEWS_TOPIC, HOOK)
        prompt = agent.last_prompt
        assert NEWS_TOPIC in prompt, "news title missing from judge prompt"
        for f in FACTS:
            assert f not in prompt, (
                f"full fact leaked into judge prompt: {f!r} — judge must see "
                "ONLY the short news title / basic content"
            )
        assert "VERIFIED FACTS" not in prompt

    def test_judge_engine_error_is_visible_warning(self):
        agent = FakeJudgeAgent(exc=RuntimeError("connection reset by peer"))
        ok, reason = dw.ai_judge_news_coverage(agent, good_beats(), NEWS_TOPIC, HOOK)
        # Not a silent pass...
        assert ok is False
        # ...and not a silent fail: the warning carries the error detail.
        assert "⚠️" in reason, f"no visible warning marker: {reason!r}"
        assert "connection reset by peer" in reason, (
            f"error detail hidden: {reason!r}"
        )
        assert "RuntimeError" in reason

    def test_check_news_path_is_judge_only(self):
        # write_dialogues_batch's news check must call the judge, never tokens.
        src = inspect.getsource(dw.DialogueNarrationAgent.write_dialogues_batch)
        assert "ai_judge_news_coverage" in src
        assert "validate_news_coverage" not in src


# ============================================================ 2. FAIL-FAST

class TestFailFastValidation:
    def test_first_failure_skips_remaining_checks(self):
        calls = []
        specs = make_check_specs(calls, fail_at=0)  # Structure fails
        checks, _feedback = dw.run_validation_checks_fail_fast(specs, "3", 2)
        assert calls == ["Structure check"], (
            f"checks after the failure still ran: {calls}"
        )
        assert checks[0]["stage"] == "3.2.1"
        assert checks[0]["passed"] is False
        for c in checks[1:]:
            assert c["passed"] is None, f"{c['stage']} should be skipped, got passed={c['passed']}"
            assert c.get("skipped") is True

    def test_skipped_marked_explicitly_not_not_reached(self):
        calls = []
        specs = make_check_specs(calls, fail_at=0)
        checks, _ = dw.run_validation_checks_fail_fast(specs, "3", 2)
        for c in checks[1:]:
            assert "Skipped (" in c["output"], f"bad skip output: {c['output']!r}"
            assert "3.2.1 Structure check failed" in c["output"], (
                f"skip must name the failed check: {c['output']!r}"
            )
            assert "Not reached" not in c["output"]

    def test_middle_failure_skips_only_later_checks(self):
        calls = []
        specs = make_check_specs(calls, fail_at=1)  # News coverage fails
        checks, _ = dw.run_validation_checks_fail_fast(specs, "3", 2)
        assert calls == ["Structure check", "News coverage check"]
        assert checks[0]["passed"] is True
        assert checks[1]["passed"] is False
        assert checks[2]["passed"] is None and checks[2].get("skipped") is True
        assert checks[3]["passed"] is None and checks[3].get("skipped") is True
        assert "3.2.2 News coverage check failed" in checks[2]["output"]
        assert "3.2.2 News coverage check failed" in checks[3]["output"]

    def test_all_pass_runs_every_check(self):
        calls = []
        specs = make_check_specs(calls, fail_at=None)
        checks, feedback = dw.run_validation_checks_fail_fast(specs, "3", 2)
        assert calls == [
            "Structure check", "News coverage check", "Tone check", "Language check",
        ]
        assert all(c["passed"] is True for c in checks)
        assert feedback == []

    def test_retry_feedback_covers_first_failure_only(self):
        calls = []
        specs = make_check_specs(calls, fail_at=0)
        _checks, feedback = dw.run_validation_checks_fail_fast(specs, "3", 2)
        assert feedback == ["fix Structure check"], (
            f"retry must fix the FIRST failure only, got: {feedback}"
        )

    def test_emit_reports_skipped_status(self):
        calls = []
        events = []
        specs = make_check_specs(calls, fail_at=0)
        dw.run_validation_checks_fail_fast(
            specs, "3", 2,
            emit=lambda s, n, p, **kw: events.append((s, n, p, kw.get("status"))),
        )
        skipped = [e for e in events if e[2] == "complete" and e[3] == "skipped"]
        assert len(skipped) == 3, f"expected 3 skipped emits, got: {events}"
        assert skipped[0][0] == "3.2.2"

    def test_stage3_checks_ordered_most_failure_prone_first(self):
        # The spec list order IS the contract: Structure (most prone) first,
        # Language (least prone) last.
        src = inspect.getsource(dw.DialogueNarrationAgent.write_dialogues_batch)
        m = re.search(r"_check_specs\s*=\s*\[(.*?)\]\s*\n", src, re.DOTALL)
        assert m, "_check_specs list not found in write_dialogues_batch"
        names = re.findall(r'"name":\s*"([^"]+)"', m.group(1))
        assert names == [
            "Structure check",
            "News coverage check",
            "Tone check",
            "Language check",
        ], f"checks not ordered by failure likelihood: {names}"


# ============================================================ 3. CUMULATIVE PREVIEW

class _Expander:
    def __init__(self, rec, title):
        self._rec = rec
        self._title = title

    def __enter__(self):
        self._rec.append(("expander", self._title))
        return FakeSt(self._rec)

    def __exit__(self, *exc):
        return False


class FakeSt:
    """Recording stand-in for streamlit."""

    def __init__(self, rec=None):
        self._rec = rec if rec is not None else []

    def expander(self, title, expanded=False):
        return _Expander(self._rec, title)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def _record(*a, **k):
            self._rec.append((name, a[0] if a else ""))
            return None

        return _record


def load_preview_functions():
    """Exec the REAL preview functions from app.py source (verbatim)."""
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    wanted = {
        "_render_cumulative_preview",
        "_render_stage_output_card",
        "_render_dialogue_beats",
        "_stage_output_retry_badge",
        "_stage3_retry_count",
    }
    segs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            segs[node.name] = ast.get_source_segment(src, node)
    for node in tree.body:  # module-level _STAGE_NAMES assignment
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_STAGE_NAMES":
                    segs["_STAGE_NAMES"] = ast.get_source_segment(src, node)
    missing = (wanted | {"_STAGE_NAMES"}) - set(segs)
    assert not missing, f"preview functions missing from app.py: {missing}"
    st = FakeSt()
    ns = {"st": st}
    exec(segs["_STAGE_NAMES"], ns)  # noqa: S102 - test harness on trusted repo code
    for name in wanted:
        exec(segs[name], ns)  # noqa: S102
    ns["_fake_st"] = st
    return ns


def stage_fixture(num):
    if num == 1:
        return {
            "verification": SimpleNamespace(
                is_verified=True,
                confidence_score=92,
                verification_summary="Metro line approved.",
                verified_facts=FACTS,
                sources=[],
            )
        }
    if num == 2:
        return {"finalized_characters": [{"name": "Rohan", "role_or_job": "Vendor"}]}
    if num == 3:
        return {"narrations": [{"scene_lines": [
            {"character": "Rohan", "dialogue": "सुना?", "action": "हंसता है"},
        ]}]}
    if num == 4:
        return {"derived_scenes_per_script": [[{"location_name": "Metro site"}]]}
    if num == 5:
        return {"scripts": [{"scenes": [1, 2], "video_prompts": ["p1"]}]}
    if num == 6:
        return {
            "batch_result": SimpleNamespace(scripts=[1], validation_issues=[]),
            "total_time": 12,
        }
    raise AssertionError(num)


def expander_titles(rec):
    return [t for kind, t in rec if kind == "expander"]


class TestCumulativePreview:
    def test_preview_accumulates_all_completed_stages(self):
        ns = load_preview_functions()
        st = FakeSt()
        ns["st"] = st
        ns["_render_cumulative_preview"]({1: stage_fixture(1), 2: stage_fixture(2), 3: stage_fixture(3)})
        titles = expander_titles(st._rec)
        assert any(t.startswith("✅ Stage 1") for t in titles), titles
        assert any(t.startswith("✅ Stage 2") for t in titles), titles
        assert any(t.startswith("✅ Stage 3") for t in titles), titles

    def test_preview_shows_stages_in_numeric_order(self):
        ns = load_preview_functions()
        st = FakeSt()
        ns["st"] = st
        ns["_render_cumulative_preview"](
            {3: stage_fixture(3), 1: stage_fixture(1), 2: stage_fixture(2)}
        )
        titles = [t for t in expander_titles(st._rec) if t.startswith("✅ Stage")]
        order = [int(re.search(r"Stage (\d)", t).group(1)) for t in titles]
        assert order == [1, 2, 3], f"stages not in order: {titles}"

    def test_new_stage_is_added_never_replaces(self):
        ns = load_preview_functions()
        for data in ({1: stage_fixture(1)},
                     {1: stage_fixture(1), 2: stage_fixture(2)}):
            st = FakeSt()
            ns["st"] = st
            ns["_render_cumulative_preview"](data)
            titles = expander_titles(st._rec)
            assert any(t.startswith("✅ Stage 1") for t in titles), (
                f"Stage 1 card disappeared after later stage completed: {titles}"
            )
        # final render still carries both stages
        assert any(t.startswith("✅ Stage 2") for t in titles)

    def test_each_stage_gets_own_section(self):
        ns = load_preview_functions()
        st = FakeSt()
        ns["st"] = st
        data = {1: stage_fixture(1), 4: stage_fixture(4), 6: stage_fixture(6)}
        ns["_render_cumulative_preview"](data)
        headers = [t for t in expander_titles(st._rec) if t.startswith("✅ Stage")]
        assert len(headers) == 3, f"expected 3 stage sections, got: {headers}"

    def test_empty_preview_shows_placeholder(self):
        ns = load_preview_functions()
        st = FakeSt()
        ns["st"] = st
        ns["_render_cumulative_preview"]({})
        texts = [t for kind, t in st._rec if kind in ("caption", "markdown")]
        assert any("No stage output yet" in str(t) for t in texts), texts

    def test_one_shared_renderer_for_both_modes(self):
        # Continuous, stepwise, failure and done views must all call the SAME
        # cumulative preview function — shared logic, not per-mode copies.
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        calls = re.findall(r"_render_cumulative_preview\(", src)
        assert len(calls) >= 4, (
            f"expected shared preview used in >=4 views (continuous/stepwise/"
            f"failure/done), found {len(calls)} call sites"
        )
        defs = re.findall(r"def _render_cumulative_preview", src)
        assert len(defs) == 1, "must be exactly one shared preview renderer"

    def test_retry_badge_only_when_retry_actually_ran(self):
        ns = load_preview_functions()
        badge = ns["_stage_output_retry_badge"]
        # No retry info -> no phantom badge.
        assert badge(3, {}) == ""
        assert badge(3, {"stage3_validation_steps": [{"stage": "3.1"}, {"stage": "3.2"}]}) == ""
        # One real retry (3.1 gen, 3.2 val, 3.3 retry-gen) -> badge shows.
        assert badge(3, {"stage3_validation_steps": [
            {"stage": "3.1"}, {"stage": "3.2"}, {"stage": "3.3"}, {"stage": "3.4"},
        ]}) == " 🔄 Retry 1"


# ============================================================ 4. FACTS PIPING

def make_verification():
    return SimpleNamespace(
        verified_facts=list(FACTS),
        physical_props=["Helmets"],
        key_locations=["Metro site"],
        core_conflict_or_irony="Commuters cheer, shopkeepers worry",
        tangible_actions=["Officials signed the order"],
    )


def base_state(verif):
    return {
        "news_input": NEWS_TOPIC,
        "batch_size": 1,
        "active_angle": "Funny & Relatable",
        "active_tone": "Joke",
        "verification": verif,
        "target_seconds": 30,
        "character_count": 2,
        "scene_style": "Dialogue",
        "scenario": "",
        "active_sample_story": "",
        "max_retries": 3,
        "budget": {
            "recommended_words": 60, "min_words": 40, "max_words": 80,
            "beats": 4, "frames": 4,
        },
        "agent_audits": [],
        "sub_instructions": {
            "scene_director": "instr:scene_director",
            "video_prompt_engineer": "instr:video_prompt_engineer",
            "video_quality_gate": "instr:video_quality_gate",
        },
    }


def make_chief():
    ed = ce_mod.ChiefEditorCoordinatorAgent()
    # Isolate the facts-piping contract from sub-instruction building.
    ed.ensure_sub_instructions = lambda state, *keys: {k: f"instr:{k}" for k in keys}
    return ed


class FakeNarration:
    def __init__(self, text, scene_lines):
        self._text = text
        self.scene_lines = scene_lines

    def __str__(self):
        return self._text


class TestFactsPiping:
    def test_stage2_passes_verification_with_facts(self):
        ed = make_chief()
        verif = make_verification()
        captured = {}

        def fake_fcg(**kwargs):
            captured.update(kwargs)
            c1 = SimpleNamespace(name="Rohan", role_or_job="Vendor", attire="kurta",
                                 emotional_stance="happy", relationship_dynamic="friends")
            c2 = SimpleNamespace(name="Meena", role_or_job="Teacher", attire="saree",
                                 emotional_stance="witty", relationship_dynamic="friends")
            return [c1, c2], [c1]

        ce_mod.hook_strategist = SimpleNamespace(
            name="hs", icon="x",
            finalise_character_groups=fake_fcg,
            derive_scene_options=MagicMock(),
            # Stage 2 generates hooks via the model (fail-loud); mock it here.
            craft_hooks_batch=MagicMock(return_value=[("H", "C")]),
        )
        ed.execute_stage_2(base_state(verif), engine_mode="test")
        v = captured.get("verification")
        assert v is verif, "Stage 2 must pass the Stage 1 verification object through"
        assert list(v.verified_facts) == FACTS

    def test_stage3_passes_verification_to_dialogue_writer(self):
        ed = make_chief()
        verif = make_verification()
        captured = {}

        def fake_write(**kwargs):
            captured.update(kwargs)
            return [FakeNarration(
                "Rohan: सुना? Meena: हाँ!",
                [{"character": "Rohan", "dialogue": "सुना?"},
                 {"character": "Meena", "dialogue": "हाँ!"}],
            )]

        ce_mod.dialogue_writer = SimpleNamespace(
            name="dialogue_writer", icon="✍️",
            write_dialogues_batch=fake_write,
            last_retry_count=0, last_attempt_history=[], last_validation_steps=[],
        )
        ce_mod.timing_auditor = SimpleNamespace(
            name="ta", icon="x",
            audit_script=MagicMock(
                return_value=(True, 50, "Pass", 25.0, "Pass", 0.95, "all good")
            ),
        )
        state = base_state(verif)
        state.update({
            "selected_angles": [("Funny & Relatable", "why")],
            "hooks_and_ctas": [(HOOK, "Follow!")],
            "finalized_characters": [],
        })
        ed.execute_stage_3(state, engine_mode="test")
        v = captured.get("verification")
        assert v is verif, "Stage 3 must pass the Stage 1 verification object through"
        assert list(v.verified_facts) == FACTS

    def test_stage4_passes_verification_to_scene_derivation(self):
        ed = make_chief()
        verif = make_verification()
        captured = {}

        def fake_derive(**kwargs):
            captured.update(kwargs)
            sc = SimpleNamespace(location_name="Metro site")
            return [sc], [sc]

        ce_mod.hook_strategist = SimpleNamespace(
            name="hs", icon="x",
            finalise_character_groups=MagicMock(),
            derive_scene_options=fake_derive,
        )
        state = base_state(verif)
        state["script_dialogues"] = [{
            "scene_lines": [{"character": "Rohan", "dialogue": "सुना?",
                             "action": "stands at metro site"}],
            "angle_tuple": ("Funny & Relatable", ""),
        }]
        state["finalized_characters"] = []
        ed.execute_stage_4(state, engine_mode="test")
        v = captured.get("verification")
        assert v is verif, "Stage 4 must pass the Stage 1 verification object through"
        assert list(v.verified_facts) == FACTS
        # Dialogue beats (not just the headline) must reach derivation.
        assert captured.get("dialogue_beats"), "derivation needs dialogue beats"

    def test_stage5_passes_facts_to_storyboard_and_video_prompts(self):
        ed = make_chief()
        verif = make_verification()
        captured_direct, captured_prompts = {}, {}

        def fake_direct(**kwargs):
            captured_direct.update(kwargs)
            return [SimpleNamespace(scene_location="", props=["Helmet"],
                                    location_name="Metro site")]

        def fake_prompts(**kwargs):
            captured_prompts.update(kwargs)
            return ["Cinematic vertical video prompt..."]

        ce_mod.scene_director = SimpleNamespace(
            name="sd", icon="x", direct_scenes=fake_direct)
        ce_mod.video_prompt_engineer = SimpleNamespace(
            name="vp", icon="x", generate_prompts=fake_prompts)
        ce_mod.video_quality_gate = SimpleNamespace(
            name="vq", icon="x",
            audit_prompts=MagicMock(return_value=SimpleNamespace(
                passed=True, feasibility_score=90, feedback="ok")),
        )
        # Isolate the facts-piping contract from persona sampling.
        ce_mod.get_character_personas = lambda *a, **k: ["Rohan", "Meena"]
        state = base_state(verif)
        state["script_dialogues"] = [{
            "idx": 0,
            "angle_tuple": ("Funny & Relatable", ""),
            "hook": HOOK, "cta": "Follow!",
            "narration": "Rohan: सुना? Meena: हाँ!",
            "scene_lines": [{"character": "Rohan", "dialogue": "सुना?"}],
            "attempt": 0, "retry_notes": [],
            "w_cnt": 50, "w_stat": "Pass", "e_dur": 25.0, "t_stat": "Pass",
            "clarity": 0.95, "audit_feedback": "all good",
        }]
        state["finalized_characters"] = []
        state["derived_scenes_per_script"] = [
            [SimpleNamespace(location_name="Metro site", props=["Helmet"])]
        ]
        ed.execute_stage_5(state, engine_mode="test")
        assert list(captured_direct.get("verified_facts", [])) == FACTS, (
            "storyboard director must receive Stage 1 verified facts"
        )
        assert list(captured_prompts.get("verified_facts", [])) == FACTS, (
            "video prompt engineer must receive Stage 1 verified facts"
        )

    def test_no_stage_operates_on_headline_alone(self):
        # Every downstream stage's agent call must carry the facts, not just
        # the news_input headline string.
        for path, needle in [
            ("prompts/hook_strategist/derive_scene_options.md", "{verified_facts}"),
            ("prompts/video_prompt_engineer/generate_prompts.md", "{verified_facts}"),
        ]:
            text = open(os.path.join(ROOT, path), encoding="utf-8").read()
            assert needle in text, f"{path} must render verified facts into the prompt"
