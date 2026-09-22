"""Codex execution, rate-limit backoff, and parsing unit tests."""

import unittest
from unittest.mock import patch

from core.dual_engine import (
    DualEngine,
    _is_codex_rate_limit,
    _extract_codex_stream_text,
    _extract_codex_error,
)


class CodexEngineTests(unittest.TestCase):
    def test_detects_rate_limit_messages(self):
        self.assertTrue(_is_codex_rate_limit("Error: Rate limit exceeded for request"))
        self.assertTrue(_is_codex_rate_limit("HTTP 429 too many requests"))
        self.assertTrue(_is_codex_rate_limit("You exceeded your current quota"))
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


if __name__ == "__main__":
    unittest.main()
