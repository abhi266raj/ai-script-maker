"""Issue #218 — HIG §2 help tags: verb-first, sentence case, ≤75 chars.

Parses ``library_ui.py`` with ``ast`` (no Streamlit runtime needed) and
asserts every literal ``help=`` / ``trigger_help=`` tooltip in the file is
verb-first (starts with a capital letter, not a status/state sentence) and
no longer than 75 characters — the HIG help-tag contract.

Regression guard for the six #218 rewrites (warm-up ×2, AI toggle, AI
engine picker, WhatsApp share, Telegram share).
"""

import ast
import re
import unittest
from pathlib import Path

LIBRARY_UI = Path(__file__).resolve().parent.parent / "library_ui.py"

# First words that fail "verb-first" (HIG §2: a help tag describes the
# hovered control and begins with a verb, never a status sentence).
_NON_VERB_FIRST = ("When", "While", "Engine", "Developer", "Warming",
                   "Loading", "Waiting", "This", "The", "It")


def _help_strings():
    """All literal help=/trigger_help= strings in library_ui.py, with lines."""
    tree = ast.parse(LIBRARY_UI.read_text(encoding="utf-8"))
    found = []

    class _V(ast.NodeVisitor):
        def visit_Call(self, node):
            for kw in node.keywords:
                if kw.arg in ("help", "trigger_help"):
                    try:
                        val = ast.literal_eval(kw.value)
                    except Exception:  # f-strings etc. — covered separately
                        continue
                    if isinstance(val, str) and val.strip():
                        found.append((node.lineno, kw.arg, val))
            self.generic_visit(node)

    _V().visit(tree)
    return found


class TestHelpTagsHig218(unittest.TestCase):
    def test_all_help_tags_verb_first_and_within_length(self):
        tips = _help_strings()
        self.assertTrue(tips, "expected help tags in library_ui.py")
        violations = []
        for lineno, arg, text in tips:
            if len(text) > 75:
                violations.append(
                    f"L{lineno} ({arg}): {len(text)} chars > 75: {text!r}")
            if text.split()[0] in _NON_VERB_FIRST:
                violations.append(
                    f"L{lineno} ({arg}): not verb-first: {text!r}")
            if not re.match(r"^[A-Z]", text):
                violations.append(
                    f"L{lineno} ({arg}): must start with a capital "
                    f"(sentence case): {text!r}")
        self.assertEqual(violations, [],
                         "help-tag violations:\n" + "\n".join(violations))

    def test_warmup_button_help_is_verb_first(self):
        # #218's exact report: the disabled warm-up button must not carry a
        # status sentence ("Warming up the on-device Apple FM model…").
        tips = _help_strings()
        texts = [t for _, _, t in tips]
        self.assertIn("Warm up the on-device Apple FM model", texts)
        self.assertNotIn("Warming up the on-device Apple FM model…", texts)

    def test_formerly_long_help_tags_are_short(self):
        tips = _help_strings()
        texts = [t for _, _, t in tips]
        # Pre-#218 offenders (now rewritten) must be gone.
        gone = [t for t in texts if len(t) > 75]
        self.assertEqual(gone, [], f"help tags still >75 chars: {gone}")
        self.assertFalse(
            any(t.startswith("Developer: warm up") for t in texts),
            "old 169-char warm-up help still present")
        self.assertFalse(
            any(t.startswith("When on, hashtag") for t in texts),
            "old 141-char AI-toggle help still present")


if __name__ == "__main__":
    unittest.main()
