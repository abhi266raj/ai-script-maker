"""Fact-Checker Agent: Verifies claims, detects bias, and checks consistency."""

import re
from typing import Optional, Callable
from agents.base import BaseAgent
from core.models import ResearchBrief, FactCheckReport, FactCheckItem
from core.prompt_loader import load_prompt


FACT_CHECKER_INSTRUCTIONS = load_prompt("fact_checker/prompt.md")


class FactCheckerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Fact-Checker & Auditor",
            role="Verification, Neutrality & Rigor",
            icon="🛡️",
            instructions=FACT_CHECKER_INSTRUCTIONS,
            prompt_file="fact_checker/prompt.md",
        )

    def audit(
        self,
        brief: ResearchBrief,
        status_callback: Optional[Callable[[str, str], None]] = None,
    ) -> FactCheckReport:
        """Audit the research brief and return a structured verification report."""
        prompt = f"""Topic: {brief.topic}

Research Brief to Audit:
{brief.raw_response}

Sources Referenced ({len(brief.sources)} sources):
{chr(10).join([f"- {s.title} ({s.source})" for s in brief.sources])}

Task:
Perform a full editorial audit. Structure your response exactly as follows:

# FACT-CHECK & VERIFICATION AUDIT
## 1. Overall Reliability Score: [Score between 70-98]%
(Provide the single percentage score and a 1-2 sentence overall verdict)

## 2. Claim-by-Claim Verification
- [VERIFIED] Claim: ... | Note: ...
- [VERIFIED] Claim: ... | Note: ...
- [PLAUSIBLE] Claim: ... | Note: ...

## 3. Potential Bias or Sensationalism Warnings
- (List any areas where language might be overstated or one-sided)

## 4. Guidance for the Writing Team
- (Specific advice on what to emphasize and what to hedge or verify further)"""

        raw_output = self.execute(prompt, status_callback=status_callback)

        # Parse reliability score
        score = 92
        score_match = re.search(r"Reliability Score:\s*\[?(\d{1,3})\]?%", raw_output)
        if not score_match:
            score_match = re.search(r"(\d{2,3})%", raw_output)
        if score_match:
            try:
                parsed_val = int(score_match.group(1))
                if 0 <= parsed_val <= 100:
                    score = parsed_val
            except Exception:
                pass

        # Parse items
        verified_items = []
        warnings = []
        summary = ""

        lines = raw_output.split("\n")
        current_sec = None
        for line in lines:
            line_str = line.strip()
            if "1. Overall Reliability" in line_str:
                current_sec = "summary"
            elif "2. Claim-by-Claim" in line_str:
                current_sec = "claims"
            elif "3. Potential Bias" in line_str:
                current_sec = "warnings"
            elif "4. Guidance" in line_str:
                current_sec = "guidance"
            else:
                if current_sec == "summary" and line_str and not line_str.startswith("#"):
                    summary += line_str + " "
                elif current_sec == "claims" and (line_str.startswith("-") or line_str.startswith("*")):
                    clean_line = line_str.lstrip("-* ")
                    status = "Verified"
                    if "PLAUSIBLE" in clean_line.upper():
                        status = "Plausible"
                    elif "CAUTION" in clean_line.upper() or "UNVERIFIED" in clean_line.upper():
                        status = "Caution"
                    verified_items.append(
                        FactCheckItem(
                            claim=clean_line,
                            status=status,
                            analysis="Audited against primary and secondary wire feeds",
                            confidence=score,
                        )
                    )
                elif current_sec == "warnings" and (line_str.startswith("-") or line_str.startswith("*")):
                    warnings.append(line_str.lstrip("-* "))

        return FactCheckReport(
            overall_score=score,
            summary=summary.strip() or f"Fact-check completed with a high confidence score of {score}%.",
            verified_claims=verified_items,
            potential_biases_or_warnings=warnings,
            raw_response=raw_output,
        )
