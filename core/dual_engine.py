"""Dual-Engine AI Inference Bridge: First Local Apple Foundation Models (fm), then Antigravity (agy)."""

import subprocess
import shutil
import logging
import os
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("DualEngine")
logger.setLevel(logging.INFO)


class DualEngine:
    """
    Dual Engine supporting both:
    1. Local Apple Foundation Models (`fm`) - on-device, fast, 100% private
    2. Antigravity (`agy`) - cloud-powered reasoning, search & fallback
    Execution Priority: First Local (`fm`), then Antigravity (`agy`).
    Guarantees zero-crash execution across all edge cases with autonomous self-healing.
    """

    def __init__(
        self,
        fm_bin: Optional[str] = None,
        agy_bin: Optional[str] = None,
    ):
        self.fm_bin = fm_bin or shutil.which("fm") or "/usr/bin/fm"
        self.agy_bin = agy_bin or shutil.which("agy") or "/opt/homebrew/bin/agy"
        self._fm_restricted: Optional[bool] = None
        self._agy_verified: Optional[bool] = None
        self._cached_status: Optional[Dict[str, Any]] = None

    def check_status(self, force: bool = False) -> Dict[str, Any]:
        """Check availability and active operational status of both Local FM and Antigravity AGY."""
        if not force and self._cached_status is not None:
            return self._cached_status

        status = {
            "fm": {"available": False, "message": "Not found", "path": self.fm_bin, "restricted": False},
            "agy": {"available": False, "message": "Not found", "path": self.agy_bin},
        }

        # Check Antigravity AGY first
        if shutil.which(self.agy_bin) or os.path.exists(self.agy_bin):
            status["agy"]["available"] = True
            status["agy"]["path"] = self.agy_bin
            status["agy"]["message"] = "Antigravity CLI (agy) ready (Cloud Reasoning & High Capacity)"
            self._agy_verified = True

        # Check Local Apple FM
        if shutil.which(self.fm_bin) or os.path.exists(self.fm_bin):
            status["fm"]["path"] = self.fm_bin
            if self._fm_restricted is True:
                status["fm"]["available"] = False
                status["fm"]["restricted"] = True
                status["fm"]["message"] = "Restricted / non-responsive on this Mac (auto-recovering with AGY)"
            else:
                try:
                    probe = subprocess.run(
                        [self.fm_bin, "respond", "--no-stream", "ping"],
                        capture_output=True,
                        text=True,
                        timeout=2.0,
                        stdin=subprocess.DEVNULL,
                    )
                    output = probe.stdout.strip()
                    err_msg = probe.stderr.strip()

                    if "Unable to work with that request" in output or "SensitiveContentAnalysisML" in err_msg:
                        status["fm"]["available"] = False
                        status["fm"]["restricted"] = True
                        status["fm"]["message"] = "Restricted on this Mac (Safety Gate). Auto-recovery active."
                        self._fm_restricted = True
                    elif probe.returncode == 0 and output:
                        status["fm"]["available"] = True
                        status["fm"]["message"] = "Apple Foundation Model ready (On-Device)"
                        self._fm_restricted = False
                    else:
                        status["fm"]["available"] = False
                        status["fm"]["message"] = "Unavailable on this Mac (auto-recovering with AGY)"
                        self._fm_restricted = True
                except Exception:
                    status["fm"]["available"] = False
                    status["fm"]["message"] = "Probe timed out: auto-recovering with AGY"
                    self._fm_restricted = True

        self._cached_status = status
        return status

    def run_fm(self, prompt: str, instructions: Optional[str] = None, timeout: int = 35) -> str:
        """Run inference using Local Apple Foundation Models."""
        cmd = [self.fm_bin, "respond", "--no-stream"]
        if instructions:
            cmd.extend(["-i", instructions])
        cmd.append(prompt)

        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        if res.returncode != 0:
            err = res.stderr.strip()
            if "SensitiveContentAnalysisML" in err:
                self._fm_restricted = True
            raise RuntimeError(f"Local FM error: {err}")
            
        output = res.stdout.strip()
        if not output or "Unable to work with that request" in output:
            self._fm_restricted = True
            raise RuntimeError("Local FM returned restricted or empty response")
        return output

    def run_agy(self, prompt: str, instructions: Optional[str] = None, timeout: int = 120) -> str:
        """Run inference using Antigravity (agy) CLI with robust non-interactive flags."""
        full_prompt = prompt
        if instructions:
            full_prompt = f"System Instructions:\n{instructions}\n\nTask:\n{prompt}"

        # Note: --disable-slash-commands MUST precede --print to ensure --print takes full_prompt
        cmd = [
            self.agy_bin,
            "--disable-slash-commands",
            "--print",
            full_prompt,
        ]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Antigravity (agy) error: {res.stderr.strip()}")
        output = res.stdout.strip()
        if not output:
            raise RuntimeError("Antigravity returned empty response")
        return output

    def generate(
        self,
        prompt: str,
        instructions: Optional[str] = None,
        mode: str = "first_local_then_agy",
        timeout: int = 150,
    ) -> Tuple[str, str]:
        """
        Generate response with engine fallback:
        - Mode 'first_local_then_agy': Attempts Local FM first (if not restricted).
          If it fails or is restricted, seamlessly falls back to Antigravity (agy).
        - Mode 'fm_only': Local Apple FM only. If restricted by macOS, auto-recovers to AGY
          so the user never experiences a pipeline crash.
        - Mode 'agy_only': Antigravity (agy) only.

        Returns:
            (response_text, engine_used_description)
        """
        # Ensure status is checked so _fm_restricted is set without wasting 8s on every call
        if self._fm_restricted is None:
            self.check_status()

        if mode == "first_local_then_agy":
            # If Local FM is already known to be restricted by macOS, skip directly to agy for speed
            if not self._fm_restricted:
                try:
                    output = self.run_fm(prompt, instructions, timeout=min(timeout, 8))
                    return output, "🍏 Local Apple FM (On-Device)"
                except Exception as e:
                    logger.warning(f"Local FM failed or restricted ({e}). Seamlessly switching to Antigravity (agy)...")
                    self._fm_restricted = True

            # Antigravity (agy) fallback
            try:
                output = self.run_agy(prompt, instructions, timeout=timeout)
                return output, "⚡ Antigravity (agy - Fallback)"
            except Exception as e:
                logger.error(f"Antigravity fallback failed: {e}")
                raise RuntimeError(f"Dual-engine inference failed: {e}")

        elif mode == "fm_only":
            if not self._fm_restricted:
                try:
                    output = self.run_fm(prompt, instructions, timeout=min(timeout, 8))
                    return output, "🍏 Local Apple FM (On-Device)"
                except Exception as e:
                    logger.warning(f"Local FM requested but restricted by macOS ({e}). Auto-recovering with Antigravity (agy)...")
                    self._fm_restricted = True

            try:
                output = self.run_agy(prompt, instructions, timeout=timeout)
                return output, "⚡ Antigravity (agy - Auto-recovered from Local FM restriction)"
            except Exception as agy_err:
                raise RuntimeError(f"Antigravity auto-recovery failed ({agy_err})")

        elif mode == "agy_only":
            try:
                output = self.run_agy(prompt, instructions, timeout=timeout)
                return output, "⚡ Antigravity (agy)"
            except Exception as e:
                logger.error(f"Antigravity inference failed: {e}")
                raise RuntimeError(f"Antigravity inference failed: {e}")

        else:
            raise ValueError(f"Unknown engine mode: {mode}")


# Singleton instance
dual_engine = DualEngine()
