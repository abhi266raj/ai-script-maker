"""Inference bridge for Local Apple FM, Grok, and Antigravity."""

import subprocess
import shutil
import logging
import os
import re
import json
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("DualEngine")
logger.setLevel(logging.INFO)

AGY_FAILURE_MARKERS = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "quota",
    "resource exhausted",
    "429",
    "unauthorized",
    "authentication",
    "sign in",
    "login",
    "capacity",
    "service unavailable",
)
GROK_FAILURE_MARKERS = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "quota",
    "429",
    "unauthorized",
    "authentication",
    "sign in",
    "login",
    "capacity",
    "service unavailable",
)
LOCAL_MODEL_TIMEOUT_SECONDS = 240
REMOTE_MODEL_TIMEOUT_SECONDS = 120
LOCAL_CONTEXT_CHAR_LIMIT = 12000
LOCAL_GROUNDING_CHAR_LIMIT = 3500
GROK_MODES = {
    "grok_low": "low",
    "grok_medium": "medium",
    "grok_high": "high",
}


def _compact_local_text(text: Optional[str], limit: int) -> Optional[str]:
    """Summarize repetitive sections while preserving the beginning and task ending."""
    if not text or len(text) <= limit:
        return text

    paragraphs = re.split(r"\n\s*\n", text)
    summarized = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > 1800:
            head = 850
            tail = 750
            paragraph = (
                paragraph[:head]
                + "\n[Repetitive examples/details summarized for local context.]\n"
                + paragraph[-tail:]
            )
        summarized.append(paragraph)

    compacted = "\n\n".join(summarized)
    if len(compacted) <= limit:
        return compacted

    # Last resort: retain high-value task boundaries, not an arbitrary middle
    # slice that could remove the output format or hard constraints.
    lines = compacted.splitlines()
    priority = re.compile(
        r"(task|format|output|news|story|fact|verified|target|duration|tone|angle|"
        r"character|agent|stage|step|scene|beat|dialogue|script|must|strict|"
        r"rule|instruction|directive|requirement)",
        re.IGNORECASE,
    )
    selected = [line for line in lines if priority.search(line)]
    result = "\n".join(selected)
    if len(result) <= limit:
        return result

    head = max(1500, limit // 2)
    tail = limit - head
    return (
        result[:head]
        + "\n[Additional repetitive context summarized for the on-device model.]\n"
        + result[-tail:]
    )


def _extract_news_grounding(text: str, limit: int = LOCAL_GROUNDING_CHAR_LIMIT) -> str:
    """Extract real story/source facts so compaction cannot remove them."""
    lines = text.splitlines()
    selected = []
    seen = set()
    labels = re.compile(
        r"(source\s*\d+|live wire|news story|news to verify|news topic|headline|"
        r"verified facts?|core news claim|research(?:ed)? story|claim examined|"
        r"key (?:facts?|entities)|official)",
        re.IGNORECASE,
    )
    for index, line in enumerate(lines):
        clean = line.strip()
        if not clean or not labels.search(clean):
            continue
        for candidate in (clean, lines[index + 1].strip() if index + 1 < len(lines) else ""):
            if candidate and candidate not in seen:
                selected.append(candidate)
                seen.add(candidate)
    grounding = "\n".join(selected)
    if len(grounding) <= limit:
        return grounding
    return _compact_local_text(grounding, limit) or grounding[:limit]


def _compact_local_request(prompt: str, instructions: Optional[str]) -> Tuple[str, Optional[str]]:
    """Compact instructions and prompt for one fresh local inference request."""
    if len(prompt) + len(instructions or "") <= LOCAL_CONTEXT_CHAR_LIMIT:
        return prompt, instructions

    # Keep the agent's full operating rules intact whenever possible. The
    # generated task prompt is where repeated examples and directives occur.
    instruction_budget = min(6000, len(instructions or ""))
    grounding = _extract_news_grounding(prompt)
    grounding_block = (
        "\n\nMANDATORY LIVE NEWS GROUNDING — use these facts and sources:\n"
        + grounding
        if grounding
        else ""
    )
    prompt_budget = max(
        1000,
        LOCAL_CONTEXT_CHAR_LIMIT - instruction_budget - len(grounding_block),
    )
    summarized_prompt = _compact_local_text(prompt, prompt_budget) or prompt
    summarized_prompt = summarized_prompt + grounding_block
    return (
        summarized_prompt,
        instructions if len(instructions or "") <= instruction_budget else _compact_local_text(instructions, instruction_budget),
    )


def _classify_agy_error(details: str) -> str:
    """Keep the provider's real error while adding a useful category."""
    lower = details.lower()
    if any(marker in lower for marker in ("rate limit", "rate_limit", "too many requests", "quota", "429", "resource exhausted")):
        return f"Antigravity rate-limit/quota error: {details}"
    if any(marker in lower for marker in ("unauthorized", "authentication", "sign in", "login")):
        return f"Antigravity authentication error: {details}"
    if any(marker in lower for marker in ("service unavailable", "capacity")):
        return f"Antigravity service-capacity error: {details}"
    return details


def _classify_grok_error(details: str) -> str:
    """Keep Grok's provider/CLI error while identifying common failure types."""
    lower = details.lower()
    if any(marker in lower for marker in (
        "rate limit", "rate_limit", "too many requests", "quota", "429",
        "usage limit", "free grok build", "reached your", "try again later",
    )):
        return f"Grok rate-limit/quota error: {details}"
    if any(marker in lower for marker in ("unauthorized", "authentication", "sign in", "login")):
        return f"Grok authentication error: {details}"
    if any(marker in lower for marker in ("service unavailable", "capacity")):
        return f"Grok service-capacity error: {details}"
    return details


def _extract_grok_error(raw: str) -> str:
    """Extract concise provider errors from Grok's streaming JSON output."""
    errors = []
    for line in (raw or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        values = event.get("errors", [])
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            errors.extend(str(value) for value in values if value)
        if event.get("type") == "error":
            message = event.get("message") or event.get("error")
            if message:
                errors.append(str(message))
    return "\n".join(dict.fromkeys(errors)).strip()


def _extract_grok_stream_text(raw: str) -> str:
    """Extract assistant text from Grok streaming JSON without exposing thinking logs."""
    text_parts = []
    final_result = ""
    for line in (raw or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "stream_event":
            delta = event.get("event", {}).get("delta", {})
            if delta.get("type") == "text_delta":
                text_parts.append(delta.get("text", ""))
        elif event.get("type") == "result" and event.get("result"):
            final_result = event["result"]
        elif event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    final_result = block.get("text", "")
    return "".join(text_parts).strip() or final_result.strip()


class ModelGenerationError(RuntimeError):
    """Raised when the selected inference engine cannot generate a response."""

    def __init__(self, message: str, partial_output: str = ""):
        super().__init__(message)
        self.partial_output = partial_output or ""


class DualEngine:
    """
    Inference bridge supporting:
    1. Local Apple Foundation Models (`fm`) - on-device, fast, 100% private
    2. Grok (`grok`) - cloud model via the installed CLI
    3. Antigravity (`agy`) - cloud-powered reasoning and search
    The explicit model modes are strict. The hybrid mode
    retains local-first/cloud-fallback behavior by design.
    """

    def __init__(
        self,
        fm_bin: Optional[str] = None,
        agy_bin: Optional[str] = None,
        grok_bin: Optional[str] = None,
    ):
        self.fm_bin = fm_bin or shutil.which("fm") or "/usr/bin/fm"
        self.agy_bin = agy_bin or shutil.which("agy") or "/opt/homebrew/bin/agy"
        self.grok_bin = grok_bin or shutil.which("grok") or "/opt/homebrew/bin/grok"
        self._fm_restricted: Optional[bool] = None
        self._agy_verified: Optional[bool] = None
        self._grok_verified: Optional[bool] = None
        self._grok_effort = "low"
        self._cached_status: Optional[Dict[str, Any]] = None

    def check_status(self, force: bool = False, check_fm: bool = True) -> Dict[str, Any]:
        """Check availability and active operational status of both Local FM and Antigravity AGY."""
        if force:
            # A model may become available after a transient service failure.
            # Re-probe it on an explicit preflight instead of retaining a stale
            # restricted state for the lifetime of the Streamlit process.
            self._fm_restricted = None
            self._agy_verified = None
            self._grok_verified = None

        if not force and self._cached_status is not None:
            return self._cached_status

        status = {
            "fm": {"available": False, "message": "Not found", "path": self.fm_bin, "restricted": False},
            "agy": {"available": False, "message": "Not found", "path": self.agy_bin},
            "grok": {"available": False, "message": "Not found", "path": self.grok_bin},
        }

        # Check Antigravity AGY first
        if shutil.which(self.agy_bin) or os.path.exists(self.agy_bin):
            status["agy"]["available"] = True
            status["agy"]["path"] = self.agy_bin
            status["agy"]["message"] = "Antigravity CLI found; service and quota are checked before generation"
            self._agy_verified = True

        # Check the Grok CLI. Authentication/model access is validated by
        # `grok models` only when Grok is selected, keeping other modes fast.
        if shutil.which(self.grok_bin) or os.path.exists(self.grok_bin):
            status["grok"]["available"] = True
            status["grok"]["path"] = self.grok_bin
            status["grok"]["message"] = "Grok CLI found; login and model access are checked before generation"
            self._grok_verified = True

        # Check Local Apple FM
        if check_fm and (shutil.which(self.fm_bin) or os.path.exists(self.fm_bin)):
            status["fm"]["path"] = self.fm_bin
            if self._fm_restricted is True:
                status["fm"]["available"] = False
                status["fm"]["restricted"] = True
                status["fm"]["message"] = "Restricted / non-responsive on this Mac"
            else:
                try:
                    # `ping` is rejected by Apple's safety layer even when the
                    # model is healthy. Use a harmless real generation probe.
                    probe = subprocess.run(
                        [self.fm_bin, "respond", "--no-stream", "Reply with exactly OK."],
                        capture_output=True,
                        text=True,
                        timeout=8.0,
                        stdin=subprocess.DEVNULL,
                    )
                    output = probe.stdout.strip()
                    err_msg = probe.stderr.strip()
                    probe_details = err_msg or output or "No probe details returned"

                    if "Unable to work with that request" in output or "SensitiveContentAnalysisML" in err_msg:
                        status["fm"]["available"] = False
                        status["fm"]["restricted"] = True
                        status["fm"]["message"] = f"Restricted on this Mac (Safety Gate): {probe_details}"
                        self._fm_restricted = True
                    elif probe.returncode == 0 and output:
                        status["fm"]["available"] = True
                        status["fm"]["message"] = "Apple Foundation Model ready (On-Device)"
                        self._fm_restricted = False
                    else:
                        status["fm"]["available"] = False
                        status["fm"]["message"] = f"Unavailable on this Mac: {probe_details}"
                        self._fm_restricted = True
                except Exception as e:
                    status["fm"]["available"] = False
                    status["fm"]["message"] = f"Probe failed: {e}"
                    self._fm_restricted = True

        self._cached_status = status
        return status

    def _probe_grok_service(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Grok login/model access without spending a generation."""
        if not status["grok"]["available"]:
            return status

        try:
            probe = subprocess.run(
                [self.grok_bin, "models"],
                capture_output=True,
                text=True,
                timeout=15.0,
                stdin=subprocess.DEVNULL,
            )
            output = probe.stdout.strip()
            err = probe.stderr.strip()
            details = err or output or "No status details returned"
            if probe.returncode != 0:
                status["grok"]["available"] = False
                status["grok"]["message"] = (
                    f"Grok status failed (exit {probe.returncode}): "
                    f"{_classify_grok_error(details)}"
                )
            elif any(marker in details.lower() for marker in GROK_FAILURE_MARKERS):
                status["grok"]["available"] = False
                status["grok"]["message"] = f"Grok service rejected the request: {_classify_grok_error(details)}"
            elif not output:
                status["grok"]["available"] = False
                status["grok"]["message"] = "Grok returned no available models"
            else:
                status["grok"]["message"] = "Grok login and model access verified"
            self._grok_verified = status["grok"]["available"]
        except subprocess.TimeoutExpired:
            status["grok"]["available"] = False
            status["grok"]["message"] = "Grok status check timed out after 15 seconds"
            self._grok_verified = False
        except Exception as e:
            status["grok"]["available"] = False
            status["grok"]["message"] = f"Grok status check failed: {e}"
            self._grok_verified = False

        self._cached_status = status
        return status

    def _probe_agy_service(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Antigravity service/auth access without spending a generation."""
        if not status["agy"]["available"]:
            return status

        try:
            probe = subprocess.run(
                [self.agy_bin, "models"],
                capture_output=True,
                text=True,
                timeout=12.0,
                stdin=subprocess.DEVNULL,
            )
            output = probe.stdout.strip()
            err = probe.stderr.strip()
            details = err or output or "No status details returned"
            if probe.returncode != 0:
                status["agy"]["available"] = False
                status["agy"]["message"] = (
                    f"Antigravity status failed (exit {probe.returncode}): "
                    f"{_classify_agy_error(details)}"
                )
            elif any(marker in details.lower() for marker in AGY_FAILURE_MARKERS):
                status["agy"]["available"] = False
                status["agy"]["message"] = (
                    f"Antigravity service rejected the request: {_classify_agy_error(details)}"
                )
            elif not output:
                status["agy"]["available"] = False
                status["agy"]["message"] = "Antigravity returned no available models"
            else:
                status["agy"]["message"] = (
                    "Antigravity service reachable; generation rate limits are checked on the real request"
                )
            self._agy_verified = status["agy"]["available"]
        except subprocess.TimeoutExpired:
            status["agy"]["available"] = False
            status["agy"]["message"] = "Antigravity status check timed out after 12 seconds"
            self._agy_verified = False
        except Exception as e:
            status["agy"]["available"] = False
            status["agy"]["message"] = f"Antigravity status check failed: {e}"
            self._agy_verified = False

        self._cached_status = status
        return status

    def validate_mode(self, mode: str) -> Dict[str, Any]:
        """Fail fast when the user-selected model is not ready."""
        if mode not in {"first_local_then_agy", "fm_only", "agy_only", *GROK_MODES}:
            raise ValueError(f"Unknown engine mode: {mode}")

        status = self.check_status(force=True, check_fm=mode not in {"agy_only", *GROK_MODES})
        if mode == "agy_only" and status["agy"]["available"]:
            status = self._probe_agy_service(status)
        if mode in GROK_MODES and status["grok"]["available"]:
            status = self._probe_grok_service(status)
        if mode == "fm_only" and not status["fm"]["available"]:
            raise ModelGenerationError(
                f"On-device Apple Foundation Model is not available: {status['fm']['message']}. "
                "Please make sure Apple Foundation Models is enabled and try again. "
                "No script was generated."
            )
        if mode == "agy_only" and not status["agy"]["available"]:
            raise ModelGenerationError(
                f"Antigravity model is not available: {status['agy']['message']}. "
                "Please start or sign in to Antigravity and try again. No script was generated."
            )
        if mode in GROK_MODES and not status["grok"]["available"]:
            raise ModelGenerationError(
                f"Grok model is not available: {status['grok']['message']}. "
                "Please sign in to Grok and try again. No script was generated."
            )
        if mode == "first_local_then_agy" and not (
            status["fm"]["available"] or status["agy"]["available"]
        ):
            raise ModelGenerationError(
                "No selected inference model is available. Please try again after "
                "starting Apple Foundation Models or Antigravity. No script was generated."
            )
        return status

    def run_fm(self, prompt: str, instructions: Optional[str] = None, timeout: int = LOCAL_MODEL_TIMEOUT_SECONDS) -> str:
        """Run inference using Local Apple Foundation Models."""
        # Each subprocess is intentionally a fresh one-shot session: no
        # --continue/--resume is used, and oversized context is compacted
        # before it reaches Apple's model context window.
        prompt, instructions = _compact_local_request(prompt, instructions)
        cmd = [self.fm_bin, "respond", "--stream"]
        if instructions:
            cmd.extend(["-i", instructions])
        cmd.append(prompt)

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as e:
            partial = e.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            raise ModelGenerationError(
                f"Local FM timed out after {timeout} seconds.",
                partial_output=partial,
            ) from e
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "No error details returned"
            if "SensitiveContentAnalysisML" in err:
                self._fm_restricted = True
            raise RuntimeError(f"Local FM error: {err}")
            
        output = res.stdout.strip()
        if not output or "Unable to work with that request" in output:
            self._fm_restricted = True
            raise RuntimeError("Local FM returned restricted or empty response")
        return output

    def run_agy(self, prompt: str, instructions: Optional[str] = None, timeout: int = REMOTE_MODEL_TIMEOUT_SECONDS) -> str:
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
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as e:
            partial = e.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            raise ModelGenerationError(
                f"Antigravity timed out after {timeout} seconds.",
                partial_output=partial,
            ) from e
        output = res.stdout.strip()
        err = res.stderr.strip()
        combined = f"{err}\n{output}".strip()
        combined_lower = combined.lower()

        if res.returncode != 0:
            details = combined or "No error details returned"
            raise RuntimeError(
                f"Antigravity error (exit {res.returncode}): {_classify_agy_error(details)}"
            )
        # Prefer stderr for service diagnostics so normal model text containing
        # words such as "capacity" is not mistaken for a quota error. Some CLI
        # failures are emitted on stdout, so also recognize clearly prefixed
        # error responses there.
        output_looks_like_error = output.lower().startswith(
            ("error", "rate limit", "too many requests", "unauthorized", "quota", "429")
        )
        if any(marker in err.lower() for marker in AGY_FAILURE_MARKERS) or output_looks_like_error:
            raise RuntimeError(
                f"Antigravity service/model error: {_classify_agy_error(combined)}"
            )
        if not output:
            raise RuntimeError("Antigravity returned empty response")
        return output

    def run_grok(self, prompt: str, instructions: Optional[str] = None, timeout: int = REMOTE_MODEL_TIMEOUT_SECONDS) -> str:
        """Run one fresh Grok CLI request; never resumes a prior conversation."""
        full_prompt = prompt
        if instructions:
            full_prompt = f"System Instructions:\n{instructions}\n\nTask:\n{prompt}"

        # Grok is used here as a model provider, not as an autonomous coding
        # agent. Disable planning, subagents, and web tools so a reel step is
        # bounded by the app timeout and uses the live news already in prompt.
        cmd = [
            self.grok_bin,
            "--single",
            full_prompt,
            "--output-format",
            "streaming-messages-json",
            "--include-partial-messages",
            "--no-plan",
            "--no-subagents",
            "--disable-web-search",
            "--reasoning-effort",
            getattr(self, "_grok_effort", "low"),
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as e:
            partial = _extract_grok_stream_text(e.stdout or "")
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            raise ModelGenerationError(
                f"Grok timed out after {timeout} seconds.",
                partial_output=partial,
            ) from e

        output = _extract_grok_stream_text(res.stdout)
        err = res.stderr.strip()
        raw_output = res.stdout.strip()
        provider_error = _extract_grok_error(raw_output)
        combined = f"{err}\n{provider_error or raw_output}".strip()
        if res.returncode != 0:
            details = combined or "No error details returned"
            raise RuntimeError(f"Grok error (exit {res.returncode}): {_classify_grok_error(details)}")
        if any(marker in err.lower() for marker in GROK_FAILURE_MARKERS):
            raise RuntimeError(f"Grok service/model error: {_classify_grok_error(combined)}")
        if not output:
            raise RuntimeError("Grok returned empty response")
        return output

    def generate(
        self,
        prompt: str,
        instructions: Optional[str] = None,
        mode: str = "first_local_then_agy",
        timeout: int = 150,
    ) -> Tuple[str, str]:
        """
        Generate response according to the selected engine mode:
        - Mode 'first_local_then_agy': Attempts Local FM first (if not restricted).
          If it fails or is restricted, seamlessly falls back to Antigravity (agy).
        - Mode 'fm_only': Strictly uses Local Apple FM and raises a model error on failure.
        - Mode 'agy_only': Strictly uses Antigravity (agy) and raises a model error on failure.
        - Modes 'grok_low', 'grok_medium', and 'grok_high': Strictly use Grok
          with the selected reasoning effort and raise a model error on failure.

        Returns:
            (response_text, engine_used_description)
        """
        # Ensure status is checked so _fm_restricted is set without wasting 8s on every call
        if mode not in {"agy_only", *GROK_MODES} and self._fm_restricted is None:
            self.check_status()

        if mode == "first_local_then_agy":
            # If Local FM is already known to be restricted by macOS, skip directly to agy for speed
            if not self._fm_restricted:
                try:
                    output = self.run_fm(prompt, instructions, timeout=min(timeout, LOCAL_MODEL_TIMEOUT_SECONDS))
                    return output, "🍏 Local Apple FM (On-Device)"
                except ModelGenerationError:
                    logger.warning("Local FM failed; switching to Antigravity (agy)...")
                    self._fm_restricted = True
                except Exception as e:
                    logger.warning(f"Local FM failed or restricted ({e}). Seamlessly switching to Antigravity (agy)...")
                    self._fm_restricted = True

            # Antigravity (agy) fallback
            try:
                output = self.run_agy(prompt, instructions, timeout=min(timeout, REMOTE_MODEL_TIMEOUT_SECONDS))
                return output, "⚡ Antigravity (Fallback)"
            except Exception as e:
                logger.error(f"Antigravity fallback failed: {e}")
                raise ModelGenerationError(
                    f"Antigravity fallback failed: {e}. "
                    "Please check Antigravity authentication, quota, rate limits, or service status. "
                    "No script was generated.",
                    partial_output=getattr(e, "partial_output", ""),
                ) from e

        elif mode == "fm_only":
            # This is a strict user selection. Never send its prompt to AGY.
            if self._fm_restricted:
                raise ModelGenerationError(
                    "On-device Apple Foundation Model is unavailable or restricted. "
                    "Please try again when the model is ready. No script was generated."
                )
            try:
                output = self.run_fm(prompt, instructions, timeout=min(timeout, LOCAL_MODEL_TIMEOUT_SECONDS))
                return output, "🍏 Local Apple FM (On-Device)"
            except ModelGenerationError as e:
                self._fm_restricted = True
                raise ModelGenerationError(
                    f"On-device Apple Foundation Model failed: {e}. "
                    "Please try again when the model is ready. No script was generated.",
                    partial_output=e.partial_output,
                ) from e
            except Exception as e:
                self._fm_restricted = True
                raise ModelGenerationError(
                    f"On-device Apple Foundation Model failed: {e}. "
                    "Please try again when the model is ready. No script was generated."
                ) from e

        elif mode == "agy_only":
            try:
                output = self.run_agy(prompt, instructions, timeout=min(timeout, REMOTE_MODEL_TIMEOUT_SECONDS))
                return output, "⚡ Antigravity"
            except ModelGenerationError as e:
                raise ModelGenerationError(
                    f"Antigravity model failed: {e}. "
                    "Please try again when the model is ready. No script was generated.",
                    partial_output=e.partial_output,
                ) from e

        elif mode in GROK_MODES:
            self._grok_effort = GROK_MODES[mode]
            try:
                output = self.run_grok(prompt, instructions, timeout=min(timeout, REMOTE_MODEL_TIMEOUT_SECONDS))
                return output, "🧠 Grok"
            except ModelGenerationError as e:
                raise ModelGenerationError(
                    f"Grok model failed: {e}. Please try again when the model is ready. No script was generated.",
                    partial_output=e.partial_output,
                ) from e
            except Exception as e:
                logger.error(f"Grok inference failed: {e}")
                raise ModelGenerationError(
                    f"Grok model failed: {e}. Please try again when the model is ready. No script was generated."
                ) from e
            except Exception as e:
                logger.error(f"Antigravity inference failed: {e}")
                raise ModelGenerationError(
                    f"Antigravity model failed: {e}. "
                    "Please try again when the model is ready. No script was generated."
                ) from e

        else:
            raise ValueError(f"Unknown engine mode: {mode}")


# Singleton instance
dual_engine = DualEngine()
