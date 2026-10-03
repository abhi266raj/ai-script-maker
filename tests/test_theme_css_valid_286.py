"""#286 — theme CSS validity gate: the theme must be all-or-nothing.

Root cause of the #286 class: the entire warm-paper theme ships as injected
``<style>`` blocks (one in app.py, three in library_ui.py). Browsers parse
CSS forgivingly — a single structural defect (unbalanced brace, stray
``</style>``) silently drops that rule AND every rule after it until the
parser resynchronizes. The visible result is exactly #286: some components
themed, others rendering native, with zero errors anywhere.

Nothing validated the CSS before this test. It fails loudly on any
structural defect, using only the standard library (no cssutils/tinycss2
dependency — this must run in CI and on the user's machine alike).

It also pins the theme's core contracts: the :root variable blocks, the
primary-button accent rule, and the text-input rule must keep existing —
if a refactor silently drops one, the theme is no longer all-or-nothing.

HIG §4 (https://developer.apple.com/design/human-interface-guidelines/):
semantic colors only — which is exactly what the :root contract below guards.

Run: python -m pytest tests/test_theme_css_valid_286.py -q
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PY = REPO_ROOT / "app.py"
LIB_UI_PY = REPO_ROOT / "library_ui.py"

_STYLE_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
_PREMATURE_CLOSE_RE = re.compile(r"</style", re.IGNORECASE)


def extract_style_blocks(path: Path) -> list[str]:
    """Return the raw CSS of every <style>...</style> block in the file."""
    return _STYLE_RE.findall(path.read_text(encoding="utf-8"))


def structural_errors(css: str) -> list[str]:
    """Statically validate one CSS block's structure (stdlib only).

    Tracks braces while respecting /* comments */, 'single'/\"double\" quoted
    strings, and backslash escapes. Returns a list of human-readable errors;
    empty means structurally sound.
    """
    errors: list[str] = []
    depth = 0
    i = 0
    n = len(css)
    in_comment = False
    in_string: str | None = None
    line = 1

    while i < n:
        ch = css[i]
        if ch == "\n":
            line += 1

        if in_comment:
            if ch == "*" and i + 1 < n and css[i + 1] == "/":
                in_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_string is not None:
            if ch == "\\" and i + 1 < n:
                if css[i + 1] == "\n":
                    line += 1
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue

        # normal code
        if ch == "/" and i + 1 < n and css[i + 1] == "*":
            in_comment = True
            i += 2
            continue
        if ch in ("'", '"'):
            in_string = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                errors.append(f"line {line}: unmatched closing brace '}}'")
                depth = 0
        i += 1

    if in_comment:
        errors.append("unclosed /* comment */ at end of block")
    if in_string is not None:
        errors.append(f"unclosed {in_string}-quoted string at end of block")
    if depth > 0:
        errors.append(f"{depth} unclosed '{{' brace(s) at end of block")
    return errors


def test_app_theme_style_block_present_exactly_once():
    blocks = extract_style_blocks(APP_PY)
    assert len(blocks) == 1, (
        f"app.py must inject exactly one theme <style> block, found {len(blocks)} — "
        "a missing block means NO theme at all; duplicates invite divergence (#286)"
    )
    assert "KHABARWAANI" in blocks[0], "app.py theme block lost its KHABARWAANI marker"
    assert len(blocks[0].strip()) > 10_000, (
        "app.py theme block suspiciously small — did the CSS get truncated?"
    )


def test_library_ui_style_blocks_present():
    blocks = extract_style_blocks(LIB_UI_PY)
    assert len(blocks) >= 1, "library_ui.py lost all its <style> blocks"


def test_all_style_blocks_structurally_valid():
    failures: list[str] = []
    for path in (APP_PY, LIB_UI_PY):
        for idx, css in enumerate(extract_style_blocks(path)):
            for err in structural_errors(css):
                failures.append(f"{path.name} block #{idx}: {err}")
    assert not failures, (
        "structurally invalid theme CSS — browsers silently drop the broken "
        "rule and everything after it (#286):\n" + "\n".join(failures)
    )


def test_no_premature_style_terminator():
    # Inside a <style> raw-text element, the FIRST "</style" ends the block
    # for the HTML parser. One stray occurrence truncates the theme.
    for path in (APP_PY, LIB_UI_PY):
        for idx, css in enumerate(extract_style_blocks(path)):
            assert not _PREMATURE_CLOSE_RE.search(css), (
                f"{path.name} block #{idx} contains '</style' inside the CSS — "
                "the browser would terminate the <style> element there and "
                "drop every rule after it (#286)"
            )


def test_theme_defines_palette_variables_on_root():
    (css,) = extract_style_blocks(APP_PY)
    assert re.search(r":root\s*,?\s*\[data-theme=\"light\"\]\s*\{", css), (
        "theme lost its ':root, [data-theme=\"light\"]' semantic mapping — "
        "variables would not resolve and every var() rule breaks (#286)"
    )
    for var in ("--accent", "--on-accent", "--ink", "--paper", "--card", "--line"):
        assert re.search(rf"{re.escape(var)}\s*:", css), (
            f"theme no longer defines {var} — components using it render unthemed (#286)"
        )


def test_primary_button_contract_present():
    # #285/#286: the primary button MUST keep its accent-fill contract.
    (css,) = extract_style_blocks(APP_PY)
    assert 'button[kind="primary"]' in css, (
        "theme lost the button[kind=\"primary\"] selector — primary buttons "
        "render native (white-on-white, #285/#286)"
    )
    m = re.search(
        r"button\[kind=\"primary\"\][^{]*\{([^}]*)\}", css, re.DOTALL
    )
    assert m and "var(--accent)" in m.group(1), (
        "primary-button rule no longer paints var(--accent) — the one-orange-"
        "button contract is broken (#285/#286)"
    )


def test_text_input_contract_present():
    (css,) = extract_style_blocks(APP_PY)
    assert "data-baseweb=\"textarea\"" in css or "textarea" in css, (
        "theme lost text-input/textarea rules — inputs would render native "
        "while buttons stay themed (partial theming, #286)"
    )




def test_launcher_fingerprint_covers_requirements_and_server_config():
    # #286: a pin/config change without a server restart leaves the server
    # on stale deps — the fingerprint must include those inputs.
    src = (REPO_ROOT / "HindiReelStudio.command").read_text(encoding="utf-8")
    assert "requirements.txt" in src, (
        "launcher fingerprint ignores requirements.txt — a Streamlit pin bump "
        "would not trigger a restart (#286)"
    )
    assert ".streamlit/config.toml" in src, (
        "launcher fingerprint ignores .streamlit/config.toml — a server-config "
        "change would not trigger a restart (#286)"
    )
