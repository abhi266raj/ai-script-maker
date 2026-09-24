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
        # Fail loudly: verification must be grounded in live wire sources.
        # Telling the model to "verify using factual reasoning" with zero
        # sources invites hallucination, so a source outage is a visible error.
        if not articles:
            raise ModelGenerationError(
                "Stage 1 failed: the live wire feed returned no articles for this topic, "
                "so there are no sources to verify against. "
                f"News input: {news_input[:200]!r}. "
                "Try a more specific headline or different topic wording."
            )

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
            sources_text=sources_text,
        )

        try:
            raw_output = self.execute(prompt, status_callback=status_callback, engine_mode=engine_mode)
        except ModelGenerationError:
            raise
        except Exception as e:
            # Fail loudly: never continue with empty output when the engine itself failed.
            raise ModelGenerationError(
                f"Stage 1 failed: news validation engine error ({type(e).__name__}): {e}. "
                f"News input: {news_input[:200]!r}"
            ) from e

        score_match = re.search(r"CONFIDENCE SCORE:\s*\[?(\d{2,3})\]?%", raw_output, re.IGNORECASE)
        if not score_match:
            # Fail loudly: the report format mandates a parseable confidence score.
            # Never silently fall back to a default 90.
            raise ModelGenerationError(
                "Stage 1 failed: model returned no parseable CONFIDENCE SCORE. "
                f"News input was: {news_input[:200]!r}. "
                f"Raw output snippet: {(raw_output or '')[:400]!r}"
            )
        score = int(score_match.group(1))

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
            # Fail loudly: never substitute a headline snippet as verified facts.
            raise ModelGenerationError(
                "Stage 1 fact extraction failed: model returned no VERIFIED FACTS section. "
                f"News input was: {news_input[:200]!r}. "
                "The model must output concise reel-usable facts (who, what happened, key number/figure).",
            )

        # Strip verification-process narration from the summary: only usable
        # facts belong in the output (e.g. "remain insufficiently verified
        # from the supplied excerpts").
        summary = re.sub(r"[^.]*insufficiently verified[^.]*\.\s*", "", summary, flags=re.IGNORECASE)
        summary = re.sub(r"[^.]*supplied excerpts[^.]*\.\s*", "", summary, flags=re.IGNORECASE)
        summary = re.sub(r"[^.]*based on the (?:provided|supplied) sources[^.]*\.\s*", "", summary, flags=re.IGNORECASE)
        summary = re.sub(r"\s{2,}", " ", summary).strip()
        if not summary:
            # Fail loudly: never substitute a generic "check completed" line as the summary.
            raise ModelGenerationError(
                "Stage 1 failed: model returned no usable SUMMARY section. "
                f"News input was: {news_input[:200]!r}. "
                "The model must output a one-line summary of confirmed usable facts.",
            )

        # No invented fallbacks for props/locations/actions: Stage 1 reports only
        # what is real. Empty lists are fine — creative invention belongs to Stage 2
        # and downstream consumers already guard empty lists.

        if not conflict:
            # Fail loudly: never invent a "viral controversy" line when the model
            # did not identify the core conflict.
            raise ModelGenerationError(
                "Stage 1 failed: model returned no CORE CONFLICT OR IRONY section. "
                f"News input was: {news_input[:200]!r}. "
                "The model must identify the central conflict, irony, or controversy driving the story.",
            )

        converted_articles = []
        for a in articles:
            if isinstance(a, NewsArticle):
                converted_articles.append(a)
            elif isinstance(a, dict):
                converted_articles.append(NewsArticle(**a))
            else:
                converted_articles.append(NewsArticle(
                    title=str(getattr(a, "title", "")),
                    link=str(getattr(a, "link", getattr(a, "url", ""))),
                    source=str(getattr(a, "source", "")),
                    snippet=str(getattr(a, "snippet", getattr(a, "description", ""))),
                    published=str(getattr(a, "published", "")),
                ))

        return NewsVerificationReport(
            is_verified=is_verified,
            confidence_score=score,
            verification_summary=summary.strip(),
            verified_facts=facts,
            flagged_claims=flags,
            sources=converted_articles,
            physical_props=props,
            key_locations=locations,
            core_conflict_or_irony=conflict.strip(),
            tangible_actions=actions,
        )


news_validator = NewsValidationAgent()
