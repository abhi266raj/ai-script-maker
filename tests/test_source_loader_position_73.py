"""v1.7 (#73, #196, #325) + #365 — the Refresh button owns its loading state.

Regression test: the headline fetch used to render a detached
``st.spinner`` — first in the card gutter (#73), then in a separate
``refresh_indicator`` below the button (#196). Per HIG §3 (the starting
control owns its loading state) the button stayed disabled while busy;
#325 implemented that as an icon swap to ``:material/progress_activity:``.

#365 replaces the swap with the stricter HIG §3 pattern: the button keeps
its stable ``:material/refresh:`` icon in both states and stays disabled
while busy, and an unlabeled spinner wraps the in-flight fetch at the
fetch site. No icon swap, no detached labeled spinner.

``app.py`` is a top-level Streamlit script (not importable), so these tests
assert the placement structurally via the AST:

1. No ``st.spinner("Loading headlines…")`` exists (the old detached pattern).
2. No ``refresh_indicator`` empty-container pattern exists.
3. The Refresh button (key="refresh_news") keeps a stable icon — no
   ``:material/progress_activity:`` swap — and stays disabled while busy.
4. An unlabeled ``st.spinner("")`` wraps the fetch work.

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
    # #365: no icon swap on the refresh button anymore.
    assert '":material/progress_activity:"' not in src, (
        "progress_activity icon swap still present; the Refresh button must "
        "keep its stable icon while busy (#365)"
    )


def test_refresh_button_stable_icon_and_spinner_while_busy():
    """The Refresh button keeps its stable icon in both states, stays
    disabled while a fetch is in flight, and an unlabeled spinner wraps
    the fetch work (#365)."""
    src = APP_PY.read_text(encoding="utf-8")
    assert 'icon=":material/refresh:"' in src, (
        "Refresh button must use the stable :material/refresh: icon (#365)"
    )
    assert 'key="refresh_news"' in src
    assert "disabled=_refresh_busy" in src, (
        "Refresh button must stay disabled while a fetch is in flight"
    )
    assert 'with st.spinner(""):' in src, (
        "an unlabeled spinner must wrap the in-flight headline fetch (#365)"
    )
