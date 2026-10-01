"""v1.7 (#73) — the "Loading headlines…" spinner must anchor to the Headline row.

Regression test: on the Source page the headline fetch used to run at the
config-card level, so ``with st.spinner("Loading headlines…")`` rendered in
the card's left gutter — orphaned between the Source row and the Headline
row. The fix moves the fetch inside the Headline row's value column
(``hl_dd``), so the spinner anchors to the dropdown it populates.

``app.py`` is a top-level Streamlit script (not importable), so these tests
assert the placement structurally via the AST:

1. Exactly one ``st.spinner("Loading headlines…")`` exists.
2. It is nested inside a ``with hl_dd:`` block (the Headline value column).
3. The old card-level pattern is gone: no ``if is_feed_mode and
   (refresh_news …)`` guard wrapping the spinner outside the columns.

Run: python -m pytest tests/test_source_loader_position_73.py -q
"""
import ast
from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent / "app.py"
SPINNER_TEXT = "Loading headlines…"


def _parse():
    return ast.parse(APP_PY.read_text(encoding="utf-8"))


def _spinner_nodes(tree):
    """All `with st.spinner("Loading headlines…"):` With-nodes."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            call = item.context_expr
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "spinner"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and call.args[0].value == SPINNER_TEXT
            ):
                found.append(node)
    return found


def _ancestor_with_names(tree, target):
    """Names of enclosing `with <name>:` blocks, innermost first."""
    names = []

    def visit(node, stack):
        if node is target:
            names.extend(stack)
            return True
        for child in ast.iter_child_nodes(node):
            extra = []
            if isinstance(child, ast.With):
                for item in child.items:
                    ctx = item.context_expr
                    if isinstance(ctx, ast.Name):
                        extra.append(ctx.id)
            if visit(child, stack + extra):
                return True
        return False

    visit(tree, [])
    return names


def _has_card_level_fetch_guard(tree):
    """Old pattern: `if is_feed_mode and (refresh_news …)` directly holding the spinner."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test_src = ast.dump(node.test)
        if "is_feed_mode" in test_src and "refresh_news" in test_src:
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.With):
                    for item in child.items:
                        call = item.context_expr
                        if (
                            isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and call.func.attr == "spinner"
                            and call.args
                            and isinstance(call.args[0], ast.Constant)
                            and call.args[0].value == SPINNER_TEXT
                        ):
                            return True
    return False


def test_exactly_one_headlines_spinner():
    tree = _parse()
    spinners = _spinner_nodes(tree)
    assert len(spinners) == 1, (
        f"expected exactly one st.spinner({SPINNER_TEXT!r}); found {len(spinners)}")


def test_spinner_anchored_in_headline_value_column():
    tree = _parse()
    (spinner,) = _spinner_nodes(tree)
    enclosing = _ancestor_with_names(tree, spinner)
    assert "hl_dd" in enclosing, (
        "the 'Loading headlines…' spinner must render inside the Headline "
        f"row's value column (with hl_dd:); enclosing with-blocks: {enclosing}")


def test_no_card_level_fetch_guard_for_spinner():
    tree = _parse()
    assert not _has_card_level_fetch_guard(tree), (
        "old pattern still present: the headline fetch must not be guarded by "
        "a card-level `if is_feed_mode and (refresh_news …)` wrapping the spinner")
