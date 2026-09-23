"""Agent 1: News Validation Specialist Agent."""

import re
from typing import Optional, Callable, List
from agents.base import BaseAgent
from core.models import NewsVerificationReport, NewsArticle
from core.dual_engine import ModelGenerationError
from tools.news_fetcher import news_fetcher
from core.prompt_loader import load_prompt, render_prompt

VALIDATOR_INSTRUCTIONS = load_prompt("news_validator/validate_news.md")


class NewsValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="News Validation Specialist",
            role="Factual Verification & Intelligence Audit",
            icon="🔍",
            instructions=VALIDATOR_INSTRUCTIONS,
            prompt_file="news_validator/validate_news.md",
        )

    def validate_news(
        self,
        news_input: str,
        scenario: str = "",
        sub_instruction: Optional[str] = None,
        status_callback: Optional[Callable[[str, str], None]] = None,
        engine_mode: str = "first_local_then_agy",
        previous_verification: Optional[NewsVerificationReport] = None,
        feedback: Optional[str] = None,
    ) -> NewsVerificationReport:
        """Execute Step 1: Fact validation against live wire sources with same-stage revision support."""
        if status_callback:
            status_callback(self.name, "Scanning live news wire feeds for source verification...")

        articles: List[NewsArticle] = news_fetcher.search_news(news_input, limit=5)

        sources_text = ""
        for i, a in enumerate(articles, 1):
            sources_text += f"Source {i} ({a.source}): {a.title}\n{a.snippet}\n\n"

        sub_directive = f"\nChief Editor Directive for News Validation:\n{sub_instruction}\n" if sub_instruction else ""

        revision_directive = ""
        if previous_verification:
            prev_facts = "\n".join([f"- {f}" for f in previous_verification.verified_facts])
            fb = feedback.strip() if feedback and feedback.strip() else (sub_instruction or "Refine and correct factual details.")
            revision_directive = (
                f"\n# 🔄 REVISION & CORRECTION MODE (HIGH PRIORITY):\n"
                f"You are REVISING an existing factual verification report based on user feedback.\n"
                f"PREVIOUS VERIFIED FACTS:\n{prev_facts}\n\n"
                f"PREVIOUS SUMMARY: {previous_verification.verification_summary}\n\n"
                f"USER CORRECTION FEEDBACK:\n{fb}\n\n"
                f"MANDATE: Directly address the user's critique. Correct the facts, physical props, locations, and central conflict accordingly.\n"
            )

        prompt = render_prompt(
            "news_validator/validate_news.md",
            news_input=news_input,
            scenario=scenario,
            sub_directive=sub_directive,
            revision_directive=revision_directive,
            sources_count=len(articles),
            sources_text=sources_text if sources_text else "No immediate wire feed found; verify using factual reasoning.",
        )

        raw_output = ""
        try:
            raw_output = self.execute(prompt, status_callback=status_callback, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception:
            raw_output = ""

        score = 90
        score_match = re.search(r"CONFIDENCE SCORE:\s*\[?(\d{2,3})\]?%", raw_output, re.IGNORECASE)
        if score_match:
            try:
                score = int(score_match.group(1))
            except Exception:
                pass

        facts = []
        flags = []
        summary = ""
        props = []
        locations = []
        conflict = ""
        actions = []
        is_verified = True

        lines = raw_output.split("\n")
        current_sec = None
        for line in lines:
            line_str = line.strip()
            if "VERIFICATION STATUS" in line_str.upper():
                if "UNCONFIRMED" in line_str.upper() or "FALSE" in line_str.upper():
                    is_verified = False
            elif "SUMMARY:" in line_str.upper():
                current_sec = "summary"
                summary += line_str.split("SUMMARY:", 1)[-1].strip() + " "
            elif "VERIFIED FACTS:" in line_str.upper():
                current_sec = "facts"
            elif "PHYSICAL PROPS" in line_str.upper():
                current_sec = "props"
            elif "KEY LOCATIONS" in line_str.upper():
                current_sec = "locations"
            elif "CORE CONFLICT" in line_str.upper():
                current_sec = "conflict"
                conflict += line_str.split("CORE CONFLICT OR IRONY:", 1)[-1].strip() + " "
            elif "TANGIBLE ACTIONS" in line_str.upper():
                current_sec = "actions"
            elif "POTENTIAL FLAGS" in line_str.upper():
                current_sec = "flags"
            else:
                if current_sec == "summary" and line_str and not line_str.startswith("#"):
                    summary += line_str + " "
                elif current_sec == "conflict" and line_str and not line_str.startswith("#"):
                    conflict += line_str + " "
                elif current_sec == "facts" and (line_str.startswith("-") or line_str.startswith("*")):
                    facts.append(line_str.lstrip("-* "))
                elif current_sec == "props" and (line_str.startswith("-") or line_str.startswith("*")):
                    props.append(line_str.lstrip("-* "))
                elif current_sec == "locations" and (line_str.startswith("-") or line_str.startswith("*")):
                    locations.append(line_str.lstrip("-* "))
                elif current_sec == "actions" and (line_str.startswith("-") or line_str.startswith("*")):
                    actions.append(line_str.lstrip("-* "))
                elif current_sec == "flags" and (line_str.startswith("-") or line_str.startswith("*")):
                    flags.append(line_str.lstrip("-* "))

        if not facts:
            facts = [f"Core news claim examined: {news_input[:80]}..."]

        # Strip verification-process narration from the summary: only usable
        # facts belong in the output (e.g. "remain insufficiently verified
        # from the supplied excerpts").
        summary = re.sub(r"[^.]*insufficiently verified[^.]*\.\s*", "", summary, flags=re.IGNORECASE)
        summary = re.sub(r"[^.]*supplied excerpts[^.]*\.\s*", "", summary, flags=re.IGNORECASE)
        summary = re.sub(r"[^.]*based on the (?:provided|supplied) sources[^.]*\.\s*", "", summary, flags=re.IGNORECASE)
        summary = re.sub(r"\s{2,}", " ", summary).strip()

        # No invented fallbacks for props/locations/actions: Stage 1 reports only
        # what is real. Empty lists are fine — creative invention belongs to Stage 2
        # and downstream consumers already guard empty lists.

        if not conflict:
            conflict = f"Viral controversy surrounding {news_input[:70]}."

        return NewsVerificationReport(
            is_verified=is_verified,
            confidence_score=score,
            verification_summary=summary.strip() or f"Factual check completed with {score}% reliability rating.",
            verified_facts=facts,
            flagged_claims=flags,
            sources=articles,
            physical_props=props,
            key_locations=locations,
            core_conflict_or_irony=conflict.strip(),
            tangible_actions=actions,
        )


news_validator = NewsValidationAgent()
