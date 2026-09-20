"""Agent 2: Hook & Angle Strategist Agent."""

import re
from typing import Tuple, List, Optional
from agents.base import BaseAgent
from core.models import NewsVerificationReport
from core.dual_engine import ModelGenerationError
from core.prompt_loader import load_prompt, render_prompt

HOOK_STRATEGIST_INSTRUCTIONS = load_prompt("hook_strategist/craft_hook.md")


class HookAndAngleAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Hook & Angle Strategist",
            role="Viral Hook Formulation & Angle Framing",
            icon="🎯",
            instructions=HOOK_STRATEGIST_INSTRUCTIONS,
            prompt_file="hook_strategist/craft_hook.md",
        )

    def craft_hook(
        self,
        news_topic: str,
        angle_name: str,
        angle_desc: str,
        tone: str,
        verification: NewsVerificationReport,
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> Tuple[str, str]:
        """Generate a viral 0-3s Hindi hook and an engaging Call-To-Action (CTA)."""
        cta_guidance = (
            "Keep CTA ultra-short (1-2 words e.g. 'फॉलो करें!') because reel is very short."
            if duration_sec <= 10 else
            "Keep CTA concise (3-5 words e.g. 'फॉलो करें और राय बताएं!')."
        )
        sub_directive = f"\nChief Editor Directive:\n{sub_instruction}\n" if sub_instruction else ""
        prompt = render_prompt(
            "hook_strategist/craft_hook.md",
            news_topic=news_topic,
            angle_name=angle_name,
            angle_desc=angle_desc,
            tone=tone,
            duration_sec=duration_sec,
            cta_guidance=cta_guidance,
            sub_directive=sub_directive,
            verification_summary=verification.verification_summary,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        hook = f"🔥 अरे सुनिए! {news_topic[:40]} को लेकर बड़ा अपडेट आ गया है!"
        cta = "फॉलो करें!" if duration_sec <= 10 else "फॉलो करें और अपनी राय कमेंट में बताएं!"

        for line in raw_output.split("\n"):
            line_str = line.strip()
            if line_str.startswith("HOOK:"):
                hook = line_str.replace("HOOK:", "").strip("[] \"'")
            elif line_str.startswith("CTA:"):
                cta = line_str.replace("CTA:", "").strip("[] \"'")

        return hook, cta

    def craft_hooks_batch(
        self,
        news_topic: str,
        angles: List[Tuple[str, str]],
        tone: str,
        verification: NewsVerificationReport,
        duration_sec: int = 30,
        sub_instruction: Optional[str] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> List[Tuple[str, str]]:
        """Generate viral hooks and CTAs for multiple angles in a single optimized inference call."""
        angles_text = "\n".join([f"ANGLE {i+1}: {a[0]} ({a[1]})" for i, a in enumerate(angles)])
        cta_guidance = (
            f"Because reel is {duration_sec}s, keep CTA strictly 1 to 3 words (e.g. 'फॉलो करें!' or 'शेयर करें!')."
            if duration_sec <= 10 else
            f"Keep CTA concise (under 6 words)."
        )
        sub_directive = f"\nChief Editor Directive for Hooks & Angles:\n{sub_instruction}\n" if sub_instruction else ""
        facts_text = "\n".join([f"- {f}" for f in (verification.verified_facts if verification else [])[:3]])
        prompt = render_prompt(
            "hook_strategist/craft_hooks_batch.md",
            news_topic=news_topic,
            tone=tone,
            duration_sec=duration_sec,
            cta_guidance=cta_guidance,
            sub_directive=sub_directive,
            facts_text=facts_text or news_topic,
            verification_summary=verification.verification_summary if verification else news_topic,
            angles_text=angles_text,
        )

        try:
            raw_output = self.execute(prompt, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        results: List[Tuple[str, str]] = []
        blocks = re.split(r"ANGLE\s*(\d+):", raw_output, flags=re.IGNORECASE)

        parsed_map = {}
        if len(blocks) > 1:
            for i in range(1, len(blocks), 2):
                idx = int(blocks[i]) - 1
                content = blocks[i + 1]
                h = None
                c = None
                for line in content.split("\n"):
                    ls = line.strip()
                    if ls.startswith("HOOK:"):
                        h = ls.replace("HOOK:", "").strip("[] \"'")
                    elif ls.startswith("CTA:"):
                        c = ls.replace("CTA:", "").strip("[] \"'")
                if h and c:
                    parsed_map[idx] = (h, c)

        default_c = "फॉलो करें!" if duration_sec <= 10 else "शेयर करें और अपनी राय नीचे कमेंट में बताएं!"
        for i, a in enumerate(angles):
            if i in parsed_map:
                results.append(parsed_map[i])
            else:
                default_h = f"🔥 {a[0].split('(')[0].strip()}: क्या आपको ये खबर पता चली?"
                results.append((default_h, default_c))

        return results


hook_strategist = HookAndAngleAgent()
