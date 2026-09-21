"""Grok rate-limit backoff, spacing, and preflight behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.dual_engine import DualEngine, _is_grok_rate_limit


class GrokRateLimitTests(unittest.TestCase):
    def test_detects_rate_limit_exceeded_message(self):
        self.assertTrue(_is_grok_rate_limit("Error: Rate limit exceeded for request"))
        self.assertTrue(_is_grok_rate_limit("HTTP 429 too many requests"))
        self.assertFalse(_is_grok_rate_limit("model timed out after 120 seconds"))

    def test_retries_then_succeeds(self):
        engine = DualEngine(grok_bin="/opt/homebrew/bin/grok")
        engine._grok_min_interval = 0
        engine._grok_max_retries = 3
        calls = {"n": 0}

        def fake_once(prompt, instructions, timeout):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("Grok error (exit 1): Grok rate-limit/quota error: Rate limit exceeded for request")
            return "OK_SCRIPT"

        with patch.object(engine, "_run_grok_once", side_effect=fake_once):
            with patch("core.dual_engine.time.sleep"):
                result = engine.run_grok("write a reel")

        self.assertEqual(result, "OK_SCRIPT")
        self.assertEqual(calls["n"], 3)

    def test_probe_rate_limit_keeps_grok_available(self):
        engine = DualEngine(grok_bin="/opt/homebrew/bin/grok")
        status = {
            "grok": {"available": True, "message": "found", "path": engine.grok_bin},
        }
        fake = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="rate limit exceeded for request",
        )
        with patch("core.dual_engine.subprocess.run", return_value=fake):
            updated = engine._probe_grok_service(status)
        self.assertTrue(updated["grok"]["available"])
        self.assertIn("rate limit", updated["grok"]["message"].lower())


if __name__ == "__main__":
    unittest.main()
