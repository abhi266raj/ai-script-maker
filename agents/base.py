"""Base Agent class supporting Dual-Engine (Local FM first, then Antigravity)."""

import time
from typing import Callable, Optional
from core.dual_engine import dual_engine
from core.prompt_loader import load_prompt


class BaseAgent:
    """Base class for autonomous newsroom agents powered by Dual Engine (FM + Antigravity)."""

    def __init__(
        self,
        name: str,
        role: str,
        icon: str,
        instructions: Optional[str] = None,
        prompt_file: Optional[str] = None,
    ):
        self.name = name
        self.role = role
        self.icon = icon
        if prompt_file:
            # Strict: the declared prompt file MUST exist and be readable.
            # A missing prompt file fails loudly here instead of silently
            # running the agent on stale embedded instructions.
            self.instructions = load_prompt(prompt_file)
        else:
            self.instructions = instructions or ""

    def execute(
        self,
        prompt: str,
        status_callback: Optional[Callable[[str, str], None]] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> str:
        """
        Execute agent task with engine priority: First Local FM, then Antigravity.

        Args:
            prompt: The task input.
            status_callback: Optional callback func(agent_name, status_message)
            engine_mode: 'first_local_then_agy', 'fm_only', or 'agy_only'
        """
        if status_callback:
            status_callback(self.name, f"⚡ {self.icon} {self.name} is thinking (Local FM → Antigravity)...")

        start_time = time.time()
        response, engine_used = dual_engine.generate(
            prompt=prompt,
            instructions=self.instructions,
            mode=engine_mode,
        )
        elapsed = round(time.time() - start_time, 2)

        if status_callback:
            status_callback(self.name, f"✅ {self.icon} {self.name} done in {elapsed}s via {engine_used}")

        return response
