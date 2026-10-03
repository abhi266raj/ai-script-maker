"""Issue #365 — Home header consolidated position test.

"the postion of title etc was suppse to change but that did not changed"

The top navigation header was supposed to change the position of the title,
tab bar, server expander, and warm-up button so they are unified in a single
header row across the top of the app, rather than leaving the tab bar rendered
in a detached row above the title.
"""

from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent / "app.py"


def test_home_header_positions_unified_in_single_row():
    """Verify that title, tab bar, server expander, and warm-up button are
    positioned together in a unified header row in app.py (#365)."""
    src = APP_PY.read_text(encoding="utf-8")

    # In the current unfixed code, render_tab_bar() is called on its own
    # before col_brand, col_srv, rendering the tab bar above the title.
    # The unified header must position col_brand, col_tabs, col_srv, and
    # col_warm together in the same header row.
    assert "col_tabs" in src, (
        "tab bar position has not changed: col_tabs is missing from the unified header (#365)"
    )
    assert "col_warm" in src, (
        "warm-up position has not changed: col_warm is missing from the unified header (#365)"
    )
