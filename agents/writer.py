"""Writer Agent: Drafts polished news articles incorporating research and fact-checks."""

from typing import Optional, Callable
from agents.base import BaseAgent
from core.models import ResearchBrief, FactCheckReport, ArticleDraft
from core.prompt_loader import load_prompt


WRITER_INSTRUCTIONS = load_prompt("writer/prompt.md")


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Senior News Journalist",
            role="Drafting, Narrative & Storytelling",
            icon="✍️",
            instructions=WRITER_INSTRUCTIONS,
            prompt_file="writer/prompt.md",
        )

    def write(
        self,
        topic: str,
        brief: ResearchBrief,
        audit: FactCheckReport,
        editorial_style: str = "Analytical Feature",
        status_callback: Optional[Callable[[str, str], None]] = None,
    ) -> ArticleDraft:
        """Draft a publication-grade article based on research and fact-check results."""
        prompt = f"""Topic: {topic}
Target Style: {editorial_style}

RESEARCH DOSSIER:
{brief.raw_response}

FACT-CHECKER AUDIT & GUIDELINES (Reliability: {audit.overall_score}%):
{audit.raw_response}

Task:
Draft a full-length, professional news article in Markdown format:
# [Catchy, Accurate Headline]
### [Subheadline: Context & Stakes]

**DATELINE** — [Compelling opening paragraph establishing what happened, when, and why it matters.]

## [Section Header 1: Key Developments & Background]
[Detailed reporting and context...]

## [Section Header 2: Stakeholders & Impact]
[Quotes, multiple perspectives, industry/social ripple effects...]

## [Section Header 3: Looking Forward]
[Upcoming decisions, what to watch, or broader implications.]"""

        raw_output = self.execute(prompt, status_callback=status_callback)

        # Extract headline and subheadline
        headline = f"Analysis: {topic}"
        subheadline = "A comprehensive editorial report."
        body_lines = []

        lines = raw_output.split("\n")
        headline_found = False
        subheadline_found = False

        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith("# ") and not headline_found:
                headline = trimmed.lstrip("# ").strip()
                headline_found = True
            elif trimmed.startswith("### ") and not subheadline_found:
                subheadline = trimmed.lstrip("### ").strip()
                subheadline_found = True
            elif trimmed.startswith("## ") and not subheadline_found and not trimmed.startswith("## ["):
                subheadline = trimmed.lstrip("## ").strip()
                subheadline_found = True
            else:
                body_lines.append(line)

        content = "\n".join(body_lines).strip()
        if not content:
            content = raw_output

        return ArticleDraft(
            headline=headline,
            subheadline=subheadline,
            tone=editorial_style,
            content=content,
            raw_response=raw_output,
        )
