"""v1.7 (#73, #196, #325) — the Refresh button owns its loading state.

Regression test: the headline fetch used to render a detached
``st.spinner`` — first in the card gutter (#73), then in a separate
``refresh_indicator`` below the button (#196). Per HIG §3 (the starting
control owns its loading state), the Refresh button now swaps its own
icon to a spinner (``:material/progress_activity:``) while busy and
stays disabled. No detached spinner exists for the headline fetch.

``app.py`` is a top-level Streamlit script (not importable), so these tests
assert the placement structurally via the AST:

1. No ``st.spinner("Loading headlines…")`` exists (the old detached pattern).
2. No ``refresh_indicator`` empty-container pattern exists.
3. The Refresh button (key="refresh_news") swaps its icon based on the
   busy state.

Run: python -m pytest tests/test_source_loader_position_73.py -q
"""
import ast
from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent / "app.py"


def _parse():
    return ast.parse(APP_PY.read_text(encoding="utf-8"))


def test_no_detached_headline_spinner():
    """The old detached st.spinner pattern is gone (#325)."""
    tree = _parse()
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            call = item.context_expr
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "spinner"
            ):
                args = call.args
                if args and isinstance(args[0], ast.Constant):
                    assert args[0].value != "Loading headlines…", (
                        "detached 'Loading headlines…' spinner still present; "
                        "the Refresh button should own its loading state (#325)"
                    )
    # Also: no refresh_indicator empty-container pattern.
    src = APP_PY.read_text(encoding="utf-8")
    assert "refresh_indicator" not in src, (
        "refresh_indicator pattern still present; "
        "the Refresh button should own its loading state (#325)"
    )


def test_refresh_button_swaps_icon_when_busy():
    """The Refresh button shows a spinner icon while a fetch is in flight (#325)."""
    src = APP_PY.read_text(encoding="utf-8")
    assert '":material/progress_activity:"' in src, (
        "Refresh button does not swap to a spinner icon when busy (#325)"
    )
    assert 'key="refresh_news"' in src
