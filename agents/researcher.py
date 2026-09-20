"""Research Agent: Synthesizes live news sources and background information."""

from typing import List, Optional, Callable
from agents.base import BaseAgent
from core.models import NewsArticle, ResearchBrief
from core.prompt_loader import load_prompt, render_prompt


RESEARCHER_INSTRUCTIONS = load_prompt("researcher/prompt.md")


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Research Specialist",
            role="Information Gathering & Intelligence Briefing",
            icon="🔬",
            instructions=RESEARCHER_INSTRUCTIONS,
            prompt_file="researcher/prompt.md",
        )

    def analyze(
        self,
        topic: str,
        articles: List[NewsArticle],
        status_callback: Optional[Callable[[str, str], None]] = None,
    ) -> ResearchBrief:
        """Analyze gathered articles and extract key facts into a structured dossier."""
        sources_text = ""
        for idx, art in enumerate(articles, 1):
            sources_text += f"\n[Source {idx}]: {art.title} (Outlet: {art.source})\n"
            if art.snippet:
                sources_text += f"Snippet: {art.snippet}\n"
            if art.published:
                sources_text += f"Published: {art.published}\n"

        prompt = render_prompt(
            "researcher/analyze.md",
            topic=topic,
            sources_text=sources_text if sources_text else "No external articles retrieved. Synthesize from your knowledge.",
        )

        raw_output = self.execute(prompt, status_callback=status_callback)

        # Parse sections loosely for structured data
        overview = ""
        key_facts = []
        perspectives = []
        quotes_data = []

        lines = raw_output.split("\n")
        current_section = None
        for line in lines:
            line_str = line.strip()
            if "1. Executive Summary" in line_str or "## Executive Summary" in line_str:
                current_section = "overview"
            elif "2. Key Facts" in line_str or "## Key Facts" in line_str:
                current_section = "facts"
            elif "3. Stakeholders" in line_str or "## Stakeholders" in line_str:
                current_section = "perspectives"
            elif "4. Key Metrics" in line_str or "## Key Metrics" in line_str:
                current_section = "quotes"
            elif "5. Knowledge Gaps" in line_str or "## Knowledge Gaps" in line_str:
                current_section = "gaps"
            else:
                if current_section == "overview" and line_str and not line_str.startswith("#"):
                    overview += line_str + " "
                elif current_section == "facts" and (line_str.startswith("-") or line_str.startswith("*")):
                    key_facts.append(line_str.lstrip("-* "))
                elif current_section == "perspectives" and (line_str.startswith("-") or line_str.startswith("*")):
                    perspectives.append(line_str.lstrip("-* "))
                elif current_section == "quotes" and (line_str.startswith("-") or line_str.startswith("*")):
                    quotes_data.append(line_str.lstrip("-* "))

        return ResearchBrief(
            topic=topic,
            overview=overview.strip() or f"Comprehensive research brief covering {topic}.",
            key_facts=key_facts,
            perspectives=perspectives,
            quotes_or_data=quotes_data,
            raw_response=raw_output,
            sources=articles,
        )
