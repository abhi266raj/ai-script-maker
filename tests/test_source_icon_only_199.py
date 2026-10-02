"""Regression tests for issue #199: Source page controls icon-only, no emoji.

Static AST/source checks on ``app.py`` — no Streamlit runtime needed.

The standing rule: every control is icon-only (no text labels, no emoji);
every icon-only button carries a Material icon shortcode plus a help tag
(tooltip / accessibility label) that begins with a verb, is sentence case,
and is at most 75 chars (Apple HIG help-tag guidance).

Run: python -m pytest tests/test_source_icon_only_199.py -q
"""
import ast
import re
from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent / "app.py"
SOURCE = APP_PY.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # pictographs & symbols
    "\u2600-\u27BF"          # misc symbols, dingbats
    "\u2B00-\u2BFF"          # misc symbols and arrows
    "\u2190-\u21FF"          # arrows
    "\u2713\u2714\u2715"     # check / ballot marks
    "\uFE0F"                 # variation selector-16
    "]"
)

# Widget keys of the twelve #199 buttons (Source page + step-wise error
# panel + compliance retry).
ISSUE_199_KEYS = {
    "clear_sample_story_btn",
    "update_inst_btn",
    "verify_config_btn",
    "launch_stepwise_btn",
    "reset_stepwise_btn",
    "restart_step1_btn",
    "launch_continuous_btn",
    "retry_stepwise_step",
    "back_stepwise_step",
    "cancel_stepwise_err",
    "retry_compliance_btn",
}


def _sl_rm_key(node):
    """The per-image remove button key is an f-string; match by prefix."""
    for kw in node.keywords:
        if kw.arg == "key" and isinstance(kw.value, ast.JoinedStr):
            prefix = "".join(
                v.value for v in kw.value.values if isinstance(v, ast.Constant)
            )
            if "sl_rm_" in prefix:
                return True
    return False


def _st_button_calls():
    for node in ast.walk(TREE):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "button"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st"
        ):
            yield node


def _kw(node, name):
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _label_of(node):
    if node.args and isinstance(node.args[0], ast.Constant):
        return node.args[0].value
    return None


def _help_template(node):
    """Static text of the help tag (f-string placeholders elided)."""
    v = _kw(node, "help")
    if isinstance(v, ast.Constant):
        return v.value
    if isinstance(v, ast.JoinedStr):
        return "".join(
            p.value if isinstance(p, ast.Constant) else "{…}"
            for p in v.values
        )
    return None


def _issue_199_buttons():
    found = []
    for node in _st_button_calls():
        key = _kw(node, "key")
        key_val = key.value if isinstance(key, ast.Constant) else None
        if key_val in ISSUE_199_KEYS or _sl_rm_key(node):
            found.append((key_val or "sl_rm_<i>", node))
    return found


def test_issue_199_buttons_present():
    """All twelve #199 buttons (plus the per-image remove) still exist."""
    found_keys = {k for k, _ in _issue_199_buttons()}
    assert ISSUE_199_KEYS <= found_keys, (
        f"missing #199 buttons: {ISSUE_199_KEYS - found_keys}"
    )
    assert any(k.startswith("sl_rm_") for k in found_keys)


def test_issue_199_buttons_icon_only():
    """#199 buttons: empty text label, Material icon shortcode, no emoji."""
    for key, node in _issue_199_buttons():
        label = _label_of(node)
        assert label == "", f"{key}: button label must be empty, got {label!r}"
        icon = _kw(node, "icon")
        assert isinstance(icon, ast.Constant) and re.fullmatch(
            r":material/[a-z_0-9]+:", icon.value
        ), f"{key}: icon must be a :material/ shortcode, got {ast.dump(icon) if icon else None}"
        seg = ast.get_source_segment(SOURCE, node) or ""
        assert not EMOJI_RE.search(seg), f"{key}: emoji found in button call"


def test_icon_only_buttons_have_verb_first_help():
    """Every icon-only button app-wide: help tag present, verb-first, ≤75 chars."""
    checked = 0
    for node in _st_button_calls():
        if _label_of(node) != "":
            continue
        checked += 1
        help_text = _help_template(node)
        assert help_text, f"line {node.lineno}: icon-only button needs a help tag"
        assert len(help_text) <= 75, (
            f"line {node.lineno}: help tag too long ({len(help_text)}): {help_text!r}"
        )
        assert help_text[0].isupper(), (
            f"line {node.lineno}: help tag must begin with a verb (sentence case): {help_text!r}"
        )
    assert checked >= 12, f"expected at least 12 icon-only buttons, found {checked}"


def test_config_banners_have_no_emoji():
    """The emoji-led banners/messages named in #199 are gone; shortcodes used."""
    removed = [
        "❌ Config Error",
        "⚠️ Config Warning",
        "❌ Setup has problems",
        "✅ Setup looks good",
        "⛔ Cannot start",
        "⛔ Cannot generate",
        "🪜 Step-Wise Active",
        "🗑️ Clear",
        "🔄 Update Instruction",
        "✓ Verify Setup",
        "🪜 Start Step-Wise Generation",
        "❌ Exit Step-Wise",
        "🚀 Restart Step 1",
        "✕ Remove",
        "🔄 Retry Generation with Recommended Settings",
        "🖼️ Article images",
    ]
    for s in removed:
        assert s not in SOURCE, f"emoji-led UI string still present: {s!r}"
    for shortcode in (":material/error:", ":material/warning:",
                      ":material/check_circle:", ":material/block:",
                      ":material/info:"):
        assert shortcode in SOURCE, f"expected Material shortcode {shortcode} in app.py"


def test_workflow_mode_radio_displays_no_emoji():
    """Generation Mode radio strips emoji from displayed labels (values kept
    emoji-prefixed for saved-config compatibility)."""
    target = None
    for node in ast.walk(TREE):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "radio"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st"
        ):
            key = _kw(node, "key")
            if isinstance(key, ast.Constant) and key.value == "workflow_mode_radio":
                target = node
                break
    assert target is not None, "workflow_mode_radio not found"
    fmt = _kw(target, "format_func")
    assert isinstance(fmt, ast.Lambda), "radio needs format_func stripping emoji"
    fn = eval(compile(ast.Expression(fmt), "<fmt>", "eval"))  # noqa: S307 — test-only, local AST
    displayed = [fn(v) for v in ["⚡ Continuous", "🪜 Step-Wise"]]
    assert displayed == ["Continuous", "Step-Wise"], displayed
    assert not any(EMOJI_RE.search(d) for d in displayed)
