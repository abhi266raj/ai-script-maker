"""Editor Agent: Final quality control, executive summary, and publication sign-off."""

from typing import Optional, Callable
from agents.base import BaseAgent
from core.models import ResearchBrief, FactCheckReport, ArticleDraft, FinalPublication
from core.prompt_loader import load_prompt


EDITOR_INSTRUCTIONS = load_prompt("editor/prompt.md")


class ChiefEditorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Chief Managing Editor",
            role="Final Polish, Curation & Publication Approval",
            icon="📰",
            instructions=EDITOR_INSTRUCTIONS,
            prompt_file="editor/prompt.md",
        )

    def review_and_publish(
        self,
        topic: str,
        brief: ResearchBrief,
        audit: FactCheckReport,
        draft: ArticleDraft,
        status_callback: Optional[Callable[[str, str], None]] = None,
    ) -> FinalPublication:
        """Review the draft, polish the prose, generate summary and takeaways, and approve."""
        prompt = f"""Topic: {topic}

DRAFT HEADLINE: {draft.headline}
DRAFT SUBHEADLINE: {draft.subheadline}

WRITER'S DRAFT ARTICLE:
{draft.content}

FACT-CHECK AUDIT (Reliability Score: {audit.overall_score}%):
{audit.summary}

Task:
Produce the finalized publication package in this exact markdown structure:

# FINAL_TITLE: [Refined Headline]
# FINAL_SUBTITLE: [Refined Subheadline]

## EXECUTIVE_SUMMARY
(A concise, authoritative 2-sentence summary)

## KEY_TAKEAWAYS
- [Takeaway 1]
- [Takeaway 2]
- [Takeaway 3]

## POLISHED_ARTICLE
(The complete, polished body of the article with clean headings and formatting)

## EDITORIAL_SIGN_OFF
(1 brief sentence on fact-check verification and editorial sign-off)"""

        raw_output = self.execute(prompt, status_callback=status_callback)

        # Parse sections
        title = draft.headline
        subtitle = draft.subheadline
        executive_summary = ""
        key_takeaways = []
        polished_article_lines = []
        sign_off = f"Verified by Fact-Check Auditor ({audit.overall_score}% confidence). Approved for publication."

        lines = raw_output.split("\n")
        current_sec = None

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("# FINAL_TITLE:"):
                title = line_str.replace("# FINAL_TITLE:", "").strip()
            elif line_str.startswith("# FINAL_SUBTITLE:"):
                subtitle = line_str.replace("# FINAL_SUBTITLE:", "").strip()
            elif "## EXECUTIVE_SUMMARY" in line_str:
                current_sec = "exec_summary"
            elif "## KEY_TAKEAWAYS" in line_str:
                current_sec = "takeaways"
            elif "## POLISHED_ARTICLE" in line_str:
                current_sec = "body"
            elif "## EDITORIAL_SIGN_OFF" in line_str:
                current_sec = "sign_off"
            else:
                if current_sec == "exec_summary" and line_str and not line_str.startswith("#"):
                    executive_summary += line_str + " "
                elif current_sec == "takeaways" and (line_str.startswith("-") or line_str.startswith("*")):
                    key_takeaways.append(line_str.lstrip("-* "))
                elif current_sec == "body":
                    polished_article_lines.append(line)
                elif current_sec == "sign_off" and line_str and not line_str.startswith("#"):
                    sign_off = line_str

        polished_article = "\n".join(polished_article_lines).strip()
        if not polished_article:
            polished_article = draft.content

        return FinalPublication(
            topic=topic,
            title=title,
            subtitle=subtitle,
            executive_summary=executive_summary.strip() or f"Comprehensive editorial report on {topic}.",
            key_takeaways=key_takeaways or ["Verified report completed by newsroom agents."],
            article_body=polished_article,
            fact_check_score=audit.overall_score,
            editorial_notes=sign_off,
            sources_used=brief.sources,
        )
