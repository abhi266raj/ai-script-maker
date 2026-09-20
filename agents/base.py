"""Base Agent class supporting Dual-Engine (Local FM first, then Antigravity)."""

import time
from typing import Callable, Optional
from core.dual_engine import dual_engine


class BaseAgent:
    """Base class for autonomous newsroom agents powered by Dual Engine (FM + AGY)."""

    def __init__(self, name: str, role: str, icon: str, instructions: str):
        self.name = name
        self.role = role
        self.icon = icon
        self.instructions = instructions

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
            status_callback(self.name, f"⚡ {self.icon} {self.name} is thinking (Local FM → AGY)...")

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
