# TODO — v1.1.1 release checklist

## Next (to do)
- [ ] core/ fallback audit finishes (in progress)
- [ ] agents/ fallback audit finishes (in progress)
- [ ] Verify retry/verification wiring actually landed in code (configurable retries, auto correction blocks, bypass checks, retry-with-instructions, full attempt history)
- [ ] Integrated read-back + diff of concurrently edited files (dialogue_writer.py, core/models.py, chief_editor.py, audit_prompts.md, prompt_loader.py) — resolve overlaps
- [ ] Compile every changed file (py_compile)
- [ ] Run full test suite + export/import audit
- [ ] Bump version to 1.1.1 in all authoritative references
- [ ] Commit to feature/stepwise-script-generation (never merge to master/main)
- [ ] Tag the release commit v1.1.1
- [ ] Restart Streamlit; live-verify Stages 1–6 in continuous and stepwise modes, including the exact Stage 5 regression case (74% feasibility / 7-second scene / complex camera)
- [ ] Fix 14 broken test call sites from the required-fields audit (app runtime is clean; tests only): tests/test_agent_coordination.py:96,105 add ai_engine= to VideoScenePrompt; tests/test_character_and_creative_scenes.py add video_verification=VideoPassVerification(...) to ReelScript at lines 123,182,284,310,636,754,802,913,1000,1064; tests/test_tapri_guard.py:77,86 replace tone="x" with a valid tone key.
- [ ] Retry-spec gaps (verification 2026-09-24: PARTIAL): add retry loops to execute_stage_2 and execute_stage_4; build the per-stage AI verifier with strict JSON contract (overall verdict + per-aspect pass/fail + reasons; exactly one verifier call per stage after deterministic checks); add "Retry with my instructions" text box and "Bypass checks and continue" to the failure UI (both modes) with checks-bypassed badges; automatic CORRECTION blocks for stages 1/2/4/5; attempt history for all stages; wire up or delete dead _build_refine_directive in chief_editor.py; decide retries_per_stage naming vs existing max_retries (default 5, UI 1-5).
- [ ] Fix format_teleprompter_text landmine: it accesses sc.narration_line which SceneItem does not define (AttributeError if a beat ever has empty dialogue) — guard with getattr when the formatter is next touched.

## Done
- [x] Stage 5 video quality gate killed — advisory-only, cannot fail a run
- [x] hook_strategist.py SyntaxError fixed (4 lines), file compiles
- [x] Stage 1 + Stage 3 strict-JSON backend (46/46 tests pass)
- [x] prompts/ fallback audit (4 files fixed)
- [x] app.py dead extract_scene_context() with invented defaults deleted
- [x] NEXT_FEATURES.md created for parked features
- [x] Working checkpoint: fallback audits wrapped, Stage 5 gate killed, JSON backend in (2026-09-24)
