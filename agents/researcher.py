"""Research Agent: Synthesizes live news sources and background information."""

from typing import List, Optional, Callable
from agents.base import BaseAgent
from core.models import NewsArticle, ResearchBrief


RESEARCHER_INSTRUCTIONS = """You are a senior Investigative News Researcher and Intelligence Analyst.
Your duty is to examine news articles and user topics to produce an objective, structured Research Brief.
You must:
1. Identify the core news story and why it matters.
2. Extract verified key facts, dates, entities, and developments in clear bullet points.
3. Highlight multiple perspectives, quotes, or stakeholders involved.
4. Note any gaps, unanswered questions, or conflicting claims in the sources.
Maintain strict journalistic neutrality and factual rigor."""


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Research Specialist",
            role="Information Gathering & Intelligence Briefing",
            icon="🔬",
            instructions=RESEARCHER_INSTRUCTIONS,
        )

    def analyze(
        self,
        topic: str,
        articles: List[NewsArticle],
        status_callback: Optional[Callable[[str, str], None]] = None,
    ) -> ResearchBrief:
        """Analyze gathered articles and create a structured Research Brief."""
        # Format sources into a readable context block
        sources_text = ""
        for idx, art in enumerate(articles, 1):
            sources_text += f"\n[Source {idx}]: {art.title} (Outlet: {art.source})\n"
            if art.snippet:
                sources_text += f"Snippet: {art.snippet}\n"
            if art.published:
                sources_text += f"Published: {art.published}\n"

        prompt = f"""Topic: {topic}

Gathered News Articles & Live Sources:
{sources_text if sources_text else "No external articles retrieved. Synthesize from your knowledge."}

Task:
Produce a comprehensive Research Dossier formatted as:
# RESEARCH BRIEF: {topic}
## 1. Executive Summary
(2-3 sentences summarizing the event or status)

## 2. Key Facts & Verified Chronology
(Bullet points with specific dates, figures, and actions)

## 3. Stakeholders & Perspectives
(Different parties and their statements/positions)

## 4. Key Metrics & Quotes
(Noteworthy numbers, quotes, or findings)

## 5. Knowledge Gaps or Developing Questions
(What is still unknown or pending)"""

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
