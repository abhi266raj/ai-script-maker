"""Local Apple FM availability probe: exponential timeout retries and honest timeout messages.

Covers issue #4 — the `fm respond` probe must tolerate slow first-run
on-device model init (up to two retries with exponential per-attempt
timeouts: 30s, 30s, 60s) and must report a timeout as "still initializing",
not as proof the model is missing or restricted.

`subprocess.run` is mocked throughout: there is no `fm` binary on Linux CI.
"""

import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.dual_engine import (
    DualEngine,
    FM_PROBE_TIMEOUT_SECONDS,
    FM_PROBE_ATTEMPT_TIMEOUTS,
)


def _ok_probe():
    return SimpleNamespace(returncode=0, stdout="OK", stderr="")


class FmProbeTimeoutTests(unittest.TestCase):
    def _engine(self):
        # Explicit fm_bin skips binary resolution; shutil.which is patched
        # per-test so the probe branch is reached on Linux.
        return DualEngine(fm_bin="/usr/bin/fm")

    def _check_status(self, engine, run_side_effect):
        with patch("core.dual_engine.subprocess.run", side_effect=run_side_effect):
            with patch("core.dual_engine.shutil.which", return_value="/usr/bin/fm"):
                return engine.check_status(force=True)

    def test_attempt_timeouts_are_exponential(self):
        self.assertEqual(FM_PROBE_TIMEOUT_SECONDS, 30.0)
        self.assertEqual(
            tuple(FM_PROBE_ATTEMPT_TIMEOUTS),
            (FM_PROBE_TIMEOUT_SECONDS, FM_PROBE_TIMEOUT_SECONDS, FM_PROBE_TIMEOUT_SECONDS * 2),
        )
        timeouts = []
        calls = {"n": 0}

        def fake_run(*args, **kwargs):
            calls["n"] += 1
            timeouts.append(kwargs.get("timeout"))
            if calls["n"] < 3:
                raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))
            return _ok_probe()

        status = self._check_status(self._engine(), fake_run)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(timeouts, [30.0, 30.0, 60.0])
        self.assertTrue(status["fm"]["available"])

    def test_probe_uses_named_timeout_constant_and_command(self):
        seen = {}

        def fake_run(*args, **kwargs):
            seen["timeout"] = kwargs.get("timeout")
            seen["cmd"] = args[0]
            return _ok_probe()

        self._check_status(self._engine(), fake_run)
        self.assertEqual(seen["timeout"], FM_PROBE_TIMEOUT_SECONDS)
        self.assertEqual(seen["cmd"][:3], ["/usr/bin/fm", "respond", "--no-stream"])

    def test_first_probe_timeout_retry_succeeds(self):
        engine = self._engine()
        calls = {"n": 0}

        def fake_run(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise subprocess.TimeoutExpired(cmd=args[0], timeout=FM_PROBE_TIMEOUT_SECONDS)
            return _ok_probe()

        status = self._check_status(engine, fake_run)

        self.assertEqual(calls["n"], 2, "probe must be retried after a first-attempt timeout")
        self.assertTrue(status["fm"]["available"])
        self.assertEqual(status["fm"]["message"], "Apple Foundation Model ready (On-Device)")
        self.assertFalse(engine._fm_restricted)

    def test_two_timeouts_then_doubled_retry_succeeds(self):
        engine = self._engine()
        calls = {"n": 0}

        def fake_run(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))
            return _ok_probe()

        status = self._check_status(engine, fake_run)

        self.assertEqual(calls["n"], 3, "probe must be attempted three times before succeeding")
        self.assertTrue(status["fm"]["available"])
        self.assertEqual(status["fm"]["message"], "Apple Foundation Model ready (On-Device)")
        self.assertFalse(engine._fm_restricted)

    def test_all_three_probes_timeout_yields_honest_initializing_message(self):
        engine = self._engine()
        calls = {"n": 0}

        def fake_run(*args, **kwargs):
            calls["n"] += 1
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

        status = self._check_status(engine, fake_run)

        self.assertEqual(calls["n"], 3, "probe must be attempted exactly three times, then give up")
        self.assertFalse(status["fm"]["available"])
        message = status["fm"]["message"]
        # Honest message: initializing, not "unavailable"/"restricted", with
        # actionable guidance — and no invented success state.
        self.assertIn("timed out", message.lower())
        self.assertIn("initializing", message.lower())
        self.assertIn("Apple Intelligence", message)
        self.assertNotIn("not available", message.lower())
        self.assertTrue(engine._fm_restricted, "fail loud: timeout must still block fm_only")

    def test_non_timeout_probe_error_still_fails_loud(self):
        engine = self._engine()

        def fake_run(*args, **kwargs):
            raise OSError("No such file or directory: '/usr/bin/fm'")

        status = self._check_status(engine, fake_run)

        self.assertFalse(status["fm"]["available"])
        self.assertIn("Probe failed", status["fm"]["message"])
        self.assertTrue(engine._fm_restricted)


if __name__ == "__main__":
    unittest.main()
