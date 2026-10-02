"""Focused tests for GitHub issue #208 — stray empty markdown spacers.

Covers (static source checks, no Streamlit runtime needed):
  1. No empty ``st.markdown('')`` spacer CALLS remain in library_ui.py
     (the bug class: invisible blank paragraphs whose margins drift when
     Streamlit changes its empty-paragraph styling).
  2. #290 superseded the ``.lib-spacer-delete`` named spacer: Delete-all
     moved into the "Stories · N" header row, so the spacer div and its
     CSS class are both fully gone — no dead spacer code may linger.

Run: python3 -m pytest tests/test_library_empty_spacer_208.py -v
"""

import os
import re

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


def test_spacer_delete_fully_removed_with_header_move():
    """#290: Delete-all moved into the header row, so the #208 named
    spacer must be completely gone — neither the div nor its CSS class
    may linger as dead code."""
    src = _source()
    assert "lib-spacer-delete" not in src, (
        ".lib-spacer-delete still referenced after the #290 header move")
    # The delete-all popover still exists — now in the header, still with
    # the explicit red verb (see the #58/#203 source-level tests).
    assert 'popover_key="lib_delpop_all"' in src
