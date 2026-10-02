"""Issue #301: every button/toggle/download control must carry a help= hover tag.

AST-scans library_ui.py and app.py and asserts that every
st.button / st.download_button / st.toggle / st.checkbox call has a
help= keyword. A literal None is not acceptable; a dynamic (variable
or f-string) value counts as present since its content cannot be
judged statically; a static string must be non-empty.

One deliberate exception: the st.button inside the _danger_button
helper forwards **kwargs to Streamlit, so help is supplied at its
call sites instead (per the issue: specific wording at call sites,
not generic text in the helper). The test therefore also asserts
that every _danger_button( call passes help=.

Help text rules enforced on static strings: ASCII-only (house rule —
no emoji), verb-first per HIG §8 (must not open with an
article/preposition or describe the click gesture), max 75 chars.
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGETS = {"button", "download_button", "toggle", "checkbox"}
FILES = ["library_ui.py", "app.py"]

# First words that are NOT verbs — a verb-first help tag must not
# start with one of these.
_NON_VERB_OPENERS = {
    "the", "a", "an", "this", "that", "these", "those",
    "to", "for", "with", "without", "on", "in", "at",
    "click", "tick",  # describe the gesture, not the action
}


def _iter_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.calls = []          # (lineno, kind, node, enclosing_func)
            self.danger_calls = []   # (lineno, node) for _danger_button(
            self._stack = []

        def visit_FunctionDef(self, node):
            self._stack.append(node.name)
            self.generic_visit(node)
            self._stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            f = node.func
            enclosing = self._stack[-1] if self._stack else "<module>"
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "st" and f.attr in TARGETS:
                self.calls.append((node.lineno, f.attr, node, enclosing))
            elif isinstance(f, ast.Name) and f.id == "_danger_button":
                self.danger_calls.append((node.lineno, node))
            self.generic_visit(node)

    v = Visitor()
    v.visit(tree)
    return v.calls, v.danger_calls


def _help_status(node):
    """Return 'absent', 'none' (literal None), 'dynamic', or ('static', text)."""
    for kw in node.keywords:
        if kw.arg != "help":
            continue
        val = kw.value
        if isinstance(val, ast.Constant) and val.value is None:
            return "none"
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            return ("static", val.value)
        return "dynamic"
    return "absent"


def test_every_control_has_help():
    missing = []
    for fname in FILES:
        calls, _ = _iter_calls(REPO / fname)
        for lineno, kind, node, enclosing in calls:
            # The _danger_button helper forwards **kwargs; its call
            # sites carry the help text (asserted separately below).
            if enclosing == "_danger_button":
                continue
            status = _help_status(node)
            if status in ("absent", "none"):
                missing.append(f"{fname}:{lineno}: st.{kind}() in {enclosing}()")
            elif isinstance(status, tuple) and not status[1].strip():
                missing.append(f"{fname}:{lineno}: st.{kind}() empty help")
    assert not missing, (
        "controls without help= (issue #301):\n" + "\n".join(missing)
    )


def test_danger_button_call_sites_have_help():
    missing = []
    for fname in FILES:
        _, danger_calls = _iter_calls(REPO / fname)
        for lineno, node in danger_calls:
            status = _help_status(node)
            bad = status in ("absent", "none") or \
                (isinstance(status, tuple) and not status[1].strip())
            if bad:
                missing.append(f"{fname}:{lineno}: _danger_button() call")
    assert not missing, (
        "_danger_button call sites without help= (issue #301):\n"
        + "\n".join(missing)
    )


def test_help_text_quality():
    problems = []
    for fname in FILES:
        calls, danger_calls = _iter_calls(REPO / fname)
        nodes = [(lineno, node) for lineno, _k, node, _e in calls]
        nodes += list(danger_calls)
        for lineno, node in nodes:
            status = _help_status(node)
            if not isinstance(status, tuple):
                continue  # absent/dynamic: covered above / not statically checkable
            stripped = status[1].strip()
            if not stripped:
                continue  # reported by the coverage tests
            if not all(ord(c) < 128 for c in stripped):
                problems.append(f"{fname}:{lineno}: non-ASCII (emoji?) in {stripped!r}")
            elif stripped.split()[0].lower() in _NON_VERB_OPENERS:
                problems.append(f"{fname}:{lineno}: not verb-first: {stripped!r}")
            elif len(stripped) > 75:
                problems.append(f"{fname}:{lineno}: over 75 chars: {stripped!r}")
    assert not problems, "help text quality (issue #301):\n" + "\n".join(problems)
