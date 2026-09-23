import os
import sys
import unittest
from unittest.mock import patch

from core.dual_engine import (
    DualEngine,
    ModelGenerationError,
    _is_codex_rate_limit,
    _is_codex_hard_quota,
    _extract_codex_stream_text,
    _extract_codex_error,
)


class CodexEngineTests(unittest.TestCase):
    def test_detects_hard_quota_vs_rate_limit(self):
        hard_quota_msg = (
            "You’ve hit your usage limit. To continue using Codex and get access to GPT-5.3-Codex, "
            "start a free trial of Plus today (https://chatgpt.com/explore/plus), or try again at Oct 14th, 2026 7:12 PM."
        )
        self.assertTrue(_is_codex_hard_quota(hard_quota_msg))
        self.assertFalse(_is_codex_rate_limit(hard_quota_msg))
        self.assertTrue(_is_codex_rate_limit("HTTP 429 too many requests"))
        self.assertFalse(_is_codex_hard_quota("HTTP 429 too many requests"))

    def test_hard_quota_fails_fast_without_retries(self):
        engine = DualEngine(codex_bin="/opt/homebrew/bin/codex")
        engine._codex_min_interval = 0
        calls = {"n": 0}

        def fake_once(prompt, instructions, timeout):
            calls["n"] += 1
            raise RuntimeError(
                "You’ve hit your usage limit. To continue using Codex, start a free trial of Plus today."
            )

        with patch.object(engine, "_run_codex_once", side_effect=fake_once):
            err_cls = sys.modules["core.dual_engine"].ModelGenerationError
            with self.assertRaises(err_cls) as ctx:
                engine.run_codex("test")
            self.assertIn("Codex quota limit reached", str(ctx.exception))
            # Must not retry when hard quota is reached
            self.assertEqual(calls["n"], 1)

    def test_detects_rate_limit_messages(self):
        self.assertTrue(_is_codex_rate_limit("Error: Rate limit exceeded for request"))
        self.assertTrue(_is_codex_rate_limit("HTTP 429 too many requests"))
        self.assertFalse(_is_codex_rate_limit("model timed out after 120 seconds"))

    def test_extracts_codex_stream_text_from_json(self):
        sample_json = (
            '{"type":"thread.started","thread_id":"01a0c61b"}\n'
            '{"type":"turn.started"}\n'
            '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"नमस्ते भारत"}}\n'
            '{"type":"turn.completed","usage":{"output_tokens":5}}\n'
        )
        text = _extract_codex_stream_text(sample_json)
        self.assertEqual(text, "नमस्ते भारत")

    def test_extracts_codex_error_from_json(self):
        sample_err = '{"type":"error","message":"Invalid API key provided"}\n'
        err = _extract_codex_error(sample_err)
        self.assertEqual(err, "Invalid API key provided")

    def test_retries_then_succeeds(self):
        engine = DualEngine(codex_bin="/opt/homebrew/bin/codex")
        engine._codex_min_interval = 0
        engine._codex_max_retries = 3
        calls = {"n": 0}

        def fake_once(prompt, instructions, timeout):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("Codex error (exit 1): Codex rate-limit/quota error: Rate limit exceeded")
            return "OK_CODEX_SCRIPT"

        with patch.object(engine, "_run_codex_once", side_effect=fake_once):
            with patch("core.dual_engine.time.sleep"):
                result = engine.run_codex("write a reel")

        self.assertEqual(result, "OK_CODEX_SCRIPT")
        self.assertEqual(calls["n"], 3)

    def test_codex_generate_mode(self):
        engine = DualEngine(codex_bin="/opt/homebrew/bin/codex")
        with patch.object(engine, "run_codex", return_value="HELLO_FROM_CODEX"):
            out, desc = engine.generate("Say hello", mode="codex_only")
        self.assertEqual(out, "HELLO_FROM_CODEX")
        self.assertIn("Codex", desc)

    def test_subprocess_env_includes_homebrew_paths(self):
        from core.dual_engine import _get_subprocess_env
        with patch.dict("os.environ", {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}, clear=True):
            env = _get_subprocess_env()
            path_val = env.get("PATH", "")
            self.assertIn("/opt/homebrew/bin", path_val)
            self.assertIn("/usr/bin", path_val)

    def test_augment_process_path_modifies_os_environ(self):
        from core.dual_engine import _augment_process_path
        with patch.dict("os.environ", {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}, clear=True):
            _augment_process_path()
            self.assertIn("/opt/homebrew/bin", os.environ.get("PATH", ""))

    def test_codex_run_passes_augmented_env_to_subprocess(self):
        engine = DualEngine(codex_bin="/opt/homebrew/bin/codex")
        with patch.dict("os.environ", {"PATH": "/usr/bin:/bin"}, clear=True):
            with patch("core.dual_engine.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = '{"type":"item.completed","item":{"type":"agent_message","text":"RESULT"}}\n'
                mock_run.return_value.stderr = ""
                res = engine._run_codex_once("hello", None, 30)
                self.assertEqual(res, "RESULT")
                self.assertTrue(mock_run.called)
                _, kwargs = mock_run.call_args
                self.assertIn("env", kwargs)
                self.assertIn("/opt/homebrew/bin", kwargs["env"]["PATH"])

    def test_codex_validate_mode(self):
        engine = DualEngine(codex_bin="/opt/homebrew/bin/codex")
        with patch.object(engine, "check_status", return_value={"codex": {"available": True, "message": "Ready"}}):
            status = engine.validate_mode("codex_only")
            self.assertTrue(status["codex"]["available"])

    def test_end_to_end_pipeline_with_codex_only(self):
        from workflow import reel_workflow

        def fake_codex(self_engine, prompt, instructions=None, timeout=120):
            if "Fact Check" in prompt or "news" in prompt.lower():
                return "VERIFIED: Story confirmed by official wire reports."
            if "Hook" in prompt or "hook" in prompt.lower():
                return "🔥 क्या आपको पता है? | फॉलो करें!"
            if "dialogue" in prompt.lower() or "screenplay" in prompt.lower():
                return "राहुल: क्या खबर सुनी? प्रिया: हां सच में अद्भुत है!"
            if "scene" in prompt.lower():
                return "Scene 1: Close-up shot with dynamic lighting."
            return "Generated content for testing"

        with patch("core.dual_engine.DualEngine.run_codex", fake_codex):
            with patch("core.dual_engine.DualEngine.check_status", return_value={"codex": {"available": True, "message": "Ready"}}):
                gen = reel_workflow.run_stream(
                    news_input="ISRO deep space AI navigation test",
                    scenario="Funny & Relatable",
                    batch_size=1,
                    target_seconds=10,
                    engine_mode="codex_only",
                    max_retries=2,
                )
                results = list(gen)
                self.assertGreater(len(results), 0)
                final_step = results[-1]
                self.assertTrue(final_step.get("completed", False))
                batch_res = final_step["data"]["batch_result"]
                self.assertEqual(len(batch_res.scripts), 1)
                self.assertEqual(batch_res.scripts[0].engine_used, "codex_only")

    def test_dual_engine_module_reload_safety(self):
        """Ensure reloading core.dual_engine does not fail due to namespace shadowing by the singleton."""
        import sys
        import importlib
        import core
        self.assertIn("core.dual_engine", sys.modules)
        mod = sys.modules["core.dual_engine"]
        reloaded = importlib.reload(mod)
        self.assertIsNotNone(reloaded)
        self.assertTrue(hasattr(reloaded, "DualEngine"))
        self.assertTrue(hasattr(reloaded, "dual_engine"))
        self.assertIn("codex_only", reloaded.CODEX_MODES)


if __name__ == "__main__":
    unittest.main()
