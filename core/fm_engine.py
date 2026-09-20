"""Apple Foundation Models (fm CLI) Engine wrapper for macOS."""

import subprocess
import shutil
import logging
from typing import Optional, Tuple

logger = logging.getLogger("FM_Engine")
logger.setLevel(logging.INFO)


class FMEngine:
    """Wrapper around Apple's macOS on-device Foundation Model CLI ('fm')."""

    def __init__(self, fm_bin_path: Optional[str] = None):
        self.fm_bin = fm_bin_path or shutil.which("fm") or "/usr/bin/fm"

    def is_available(self) -> Tuple[bool, str]:
        """Check if 'fm' binary exists and the system foundation model is ready."""
        if not shutil.which(self.fm_bin):
            return False, f"The 'fm' binary was not found at '{self.fm_bin}'. Ensure macOS Foundation Models is installed."

        try:
            res = subprocess.run(
                [self.fm_bin, "available"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = res.stdout.strip() or res.stderr.strip()
            if res.returncode == 0:
                return True, output or "Apple Foundation Model is ready"
            return False, f"Model unavailable: {output}"
        except Exception as e:
            return False, f"Failed to check model availability: {str(e)}"

    def generate(
        self,
        prompt: str,
        instructions: Optional[str] = None,
        use_case: Optional[str] = None,
        timeout: int = 120
    ) -> str:
        """
        Execute an on-device inference using `fm respond`.

        Args:
            prompt: The user or agent prompt.
            instructions: System instructions for the model's persona/role.
            use_case: Optional use case ('general', 'content-tagging').
            timeout: Maximum execution time in seconds.
        """
        cmd = [self.fm_bin, "respond", "--no-stream"]

        if instructions:
            cmd.extend(["-i", instructions])

        if use_case:
            cmd.extend(["--use-case", use_case])

        cmd.append(prompt)

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if res.returncode != 0:
                err_msg = res.stderr.strip()
                logger.error(f"fm CLI error (code {res.returncode}): {err_msg}")
                raise RuntimeError(f"Apple FM error: {err_msg}")

            output = res.stdout.strip()
            return output
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Apple Foundation Model timed out after {timeout} seconds.")
        except Exception as e:
            logger.error(f"Error executing fm CLI: {e}")
            raise


# Global singleton instance
fm_engine = FMEngine()
