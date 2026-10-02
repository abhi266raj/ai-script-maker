"""Focused tests for GitHub issue #208 — stray empty markdown spacers.

Covers (static source checks, no Streamlit runtime needed):
  1. No empty ``st.markdown('')`` spacer CALLS remain in library_ui.py
     (the bug class: invisible blank paragraphs whose margins drift when
     Streamlit changes its empty-paragraph styling).
  2. The replacement ``.lib-spacer-delete`` class exists in the injected
     CSS with an explicit fixed height, and a div carrying that class is
     rendered between the story radio list and the Delete-All trigger in
     ``render_library_page`` — so the spacing intent is named and
     version-proof.

Run: python3 -m pytest tests/test_library_empty_spacer_208.py -v
"""

import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_PATH = os.path.join(ROOT, "library_ui.py")


def _source():
    with open(LIB_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


# Matches an actual call like `st.markdown("")` at statement position,
# but NOT a mention inside a comment (e.g. "Replaces a stray st.markdown("")").
EMPTY_SPC_CALL = re.compile(r'^\s*st\.markdown\(\s*["\']{2}\s*\)')


def test_no_empty_markdown_spacers_in_library_ui():
    """#208: no empty st.markdown('') spacer calls remain in library_ui.py."""
    src = _source()
    hits = [
        (i, line)
        for i, line in enumerate(src.splitlines(), start=1)
        if EMPTY_SPC_CALL.search(line)
    ]
    assert not hits, (
        "empty st.markdown('') spacer call(s) remain in library_ui.py: "
        + ", ".join(f"line {i}: {line.strip()}" for i, line in hits)
    )


def test_named_spacer_css_class_exists_with_fixed_height():
    """#208: .lib-spacer-delete defines an explicit fixed height in the
    injected Library CSS (not a margin that can drift)."""
    src = _source()
    css = re.search(r"\.lib-spacer-delete\s*\{([^}]*)\}", src)
    assert css, ".lib-spacer-delete CSS class not found in library_ui.py"
    assert re.search(r"height\s*:\s*\d+px", css.group(1)), (
        ".lib-spacer-delete must define an explicit fixed height "
        f"(found: {css.group(1).strip()!r})"
    )


def test_named_spacer_used_before_delete_all():
    """#208: the named spacer div is rendered just before the Delete-All
    popover trigger in the master column."""
    src = _source()
    pattern = re.compile(
        r'st\.markdown\(\s*\'<div class="lib-spacer-delete"></div>\'',
        re.DOTALL,
    )
    m = pattern.search(src)
    assert m, "no <div class=\"lib-spacer-delete\"> st.markdown call found"
    # Sanity: the popover trigger must follow the spacer in render_library_page.
    tail = src[m.end():]
    assert re.search(r"_delete_popover\(", tail), (
        "spacer div exists but no _delete_popover call follows it"
    )
