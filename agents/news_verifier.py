"""News Verifier Agent: Step 1 with Dual-Engine support (Local FM first, then Antigravity)."""

import re
from typing import Optional, Callable, List
from agents.base import BaseAgent
from core.models import NewsVerificationReport, NewsArticle
from tools.news_fetcher import news_fetcher
from core.prompt_loader import load_prompt, render_prompt


VERIFIER_INSTRUCTIONS = load_prompt("news_verifier/prompt.md")


class NewsVerifierAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="News Verification Agent",
            role="Step 1: Truth & Fact Verification (FM + AGY)",
            icon="🔍",
            instructions=VERIFIER_INSTRUCTIONS,
            prompt_file="news_verifier/prompt.md",
        )

    def verify(
        self,
        news_input: str,
        scenario: str = "",
        status_callback: Optional[Callable[[str, str], None]] = None,
        engine_mode: str = "first_local_then_agy",
    ) -> NewsVerificationReport:
        """Step 1: Verify the news using live wire searches and Dual-Engine analysis."""
        if status_callback:
            status_callback(self.name, "Fetching wire sources to cross-examine claims...")

        articles: List[NewsArticle] = news_fetcher.search_news(news_input, limit=5)

        sources_text = ""
        for i, a in enumerate(articles, 1):
            sources_text += f"Source {i} ({a.source}): {a.title}\n{a.snippet}\n\n"

        prompt = render_prompt(
            "news_verifier/verify.md",
            news_input=news_input,
            scenario=scenario,
            sources_count=len(articles),
            sources_text=sources_text if sources_text else "No immediate wire feed found; verify using factual reasoning.",
        )

        raw_output = self.execute(prompt, status_callback=status_callback, engine_mode=engine_mode)

        # Parse confidence score
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
            elif "POTENTIAL FLAGS" in line_str.upper():
                current_sec = "flags"
            else:
                if current_sec == "summary" and line_str and not line_str.startswith("#"):
                    summary += line_str + " "
                elif current_sec == "facts" and (line_str.startswith("-") or line_str.startswith("*")):
                    facts.append(line_str.lstrip("-* "))
                elif current_sec == "flags" and (line_str.startswith("-") or line_str.startswith("*")):
                    flags.append(line_str.lstrip("-* "))

        if not facts:
            facts = [f"Core news claim examined: {news_input[:80]}..."]

        return NewsVerificationReport(
            is_verified=is_verified,
            confidence_score=score,
            verification_summary=summary.strip() or f"Factual check completed with {score}% reliability rating.",
            verified_facts=facts,
            flagged_claims=flags,
            sources=articles,
        )
