"""Apple-palette contrast + single-source-of-truth tests.

Parses the theme CSS in app.py (raw --apple-* palette + the three
semantic appearance blocks), resolves var() chains, and enforces:

- TIER 1 (>= 4.5:1, WCAG AA): essential text pairs. FAILS LOUDLY.
- TIER 2 (>= 3.0:1, WCAG large-text/UI floor): tertiary text.
- Quaternary is decorative-only (mirrors Apple's 18% quaternaryLabel):
  asserted to be strictly fainter than tertiary, never used for
  essential text.
- No hex literals in the three semantic appearance blocks: every value
  must be a var() reference (or color-mix() derivation / --scheme
  keyword), so theme colors change in exactly one place.
- The raw --apple-* values match Apple's documented 2025 unified
  system colors.
- The quaternary role exists in all three appearance blocks.

HIG: contrast minimum 4.5:1, aim 7:1 for small text (see
~/workspace/docs/apple-hig-notes.md §4).
"""

import re
from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent / "app.py"

# Apple's 2025 unified system colors (HIG -> Color -> Specifications),
# sampled from Apple's published swatches. (name, light, dark)
APPLE_DOCUMENTED = {
    "--apple-orange-light": "#FF8D28", "--apple-orange-dark": "#FF9230",
    "--apple-orange-ic-light": "#C55300", "--apple-orange-ic-dark": "#FFA056",
    "--apple-gray-light": "#8E8E93", "--apple-gray-dark": "#8E8E93",
    "--apple-gray-ic-light": "#6C6C70", "--apple-gray-ic-dark": "#AEAEB2",
    "--apple-gray2-light": "#AEAEB2", "--apple-gray2-dark": "#636366",
    "--apple-gray3-light": "#C7C7CC", "--apple-gray3-dark": "#48484A",
}

STYLE = None
RAW = {}
BLOCKS = {}  # mode -> {token: raw_value}


def _style_text():
    global STYLE
    if STYLE is None:
        src = APP_PY.read_text()
        m = re.search(r"<style>(.*?)</style>", src, re.DOTALL)
        assert m, "no <style> block found in app.py"
        STYLE = m.group(1)
    return STYLE


def _declarations(block_text):
    out = {}
    for name, value in re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", block_text):
        out["--" + name] = value.strip()
    return out


def _load():
    global RAW, BLOCKS
    if BLOCKS:
        return
    css = _style_text()
    # Raw palette: the bare ":root {" block holding --apple-* values.
    raw_blocks = re.findall(r":root\s*\{(.*?)\}", css, re.DOTALL)
    raw_hits = [b for b in raw_blocks if "--apple-orange-light" in b]
    assert len(raw_hits) == 1, f"expected 1 raw palette block, found {len(raw_hits)}"
    RAW.update(_declarations(raw_hits[0]))

    light = re.search(
        r':root,\s*\[data-theme="light"\]\s*\{(.*?)\n    \}', css, re.DOTALL
    )
    assert light, "light semantic block not found"
    dark_media = re.search(
        r':root:not\(\[data-theme="light"\]\),\s*'
        r'html:not\(\[data-theme="light"\]\),\s*'
        r'body:not\(\[data-theme="light"\]\)\s*\{(.*?)\n        \}',
        css, re.DOTALL,
    )
    assert dark_media, "dark @media semantic block not found"
    dark_attr = re.search(
        r':root\[data-theme="dark"\],\s*'
        r'html\[data-theme="dark"\],\s*'
        r'body\[data-theme="dark"\],\s*'
        r'\[data-theme="dark"\]\s*\{(.*?)\n    \}',
        css, re.DOTALL,
    )
    assert dark_attr, "dark [data-theme] semantic block not found"
    BLOCKS["light"] = _declarations(light.group(1))
    BLOCKS["dark_media"] = _declarations(dark_media.group(1))
    BLOCKS["dark_attr"] = _declarations(dark_attr.group(1))


def resolve(token, mode):
    """Resolve a semantic token to a hex color for the given mode."""
    _load()
    block = BLOCKS[mode]
    seen = set()
    if token in block:
        value = block[token]
    elif token in RAW:
        value = RAW[token]
    else:
        raise AssertionError(f"{token}: not defined in {mode} block or raw palette")
    while True:
        m = re.fullmatch(r"var\(\s*(--[a-z0-9-]+)\s*\)", value)
        if not m:
            break
        name = m.group(1)
        assert name not in seen, f"var() cycle resolving {token}"
        seen.add(name)
        if name in block:
            value = block[name]
        elif name in RAW:
            value = RAW[name]
        else:
            raise AssertionError(f"{token}: unresolvable {name}")
    m = re.fullmatch(r"#[0-9a-fA-F]{6}", value)
    assert m, f"{token} ({mode}) did not resolve to hex: {value!r}"
    return value.upper()


def luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(fg, bg):
    hi, lo = max(luminance(fg), luminance(bg)), min(luminance(fg), luminance(bg))
    return (hi + 0.05) / (lo + 0.05)


def test_apple_raw_values_match_documented_table():
    _load()
    bad = [
        f"{name}: css={RAW.get(name)} documented={want}"
        for name, want in APPLE_DOCUMENTED.items()
        if RAW.get(name, "").upper() != want.upper()
    ]
    assert not bad, "raw Apple palette drifted from documented values:\n" + "\n".join(bad)


def test_no_hex_literals_in_semantic_blocks():
    """Single source of truth: appearance blocks hold only var()/color-mix()/keywords."""
    _load()
    offenders = []
    for mode, block in BLOCKS.items():
        for token, value in block.items():
            if value in ("light", "dark"):
                continue  # --scheme keyword
            if re.fullmatch(r"var\(\s*--[a-z0-9-]+\s*\)", value):
                continue
            if value.startswith("color-mix("):
                continue
            offenders.append(f"{mode} {token}: {value!r}")
    assert not offenders, (
        "hex literals (or non-var values) in semantic appearance blocks — "
        "move them to the raw :root palette:\n" + "\n".join(offenders)
    )


def test_quaternary_role_exists_in_all_modes():
    _load()
    for mode, block in BLOCKS.items():
        assert "--quaternary" in block, f"--quaternary missing in {mode}"
        assert "--text-quaternary" in block, f"--text-quaternary missing in {mode}"
    # quaternary must actually vary by mode (not a constant)
    lq = resolve("--quaternary", "light")
    dq = resolve("--quaternary", "dark_attr")
    assert lq != dq, "quaternary must have distinct light/dark values"


def _tier1_pairs():
    return [
        ("--text-primary", "--bg-primary"),
        ("--text-primary", "--bg-secondary"),
        ("--text-secondary", "--bg-primary"),
        ("--text-secondary", "--bg-secondary"),
        ("--text-secondary", "--bg-tertiary"),
        ("--on-primary", "--primary-strong"),
        ("--ok-text", "--bg-primary"),
        ("--bad-text", "--bg-primary"),
    ]


def test_tier1_contrast_essential_pairs():
    """WCAG AA 4.5:1 for every essential text pair, both modes. FAILS LOUDLY."""
    _load()
    failures = []
    for mode in ("light", "dark_media", "dark_attr"):
        label = {"light": "light", "dark_media": "dark@media", "dark_attr": "dark[attr]"}[mode]
        for fg_tok, bg_tok in _tier1_pairs():
            fg, bg = resolve(fg_tok, mode), resolve(bg_tok, mode)
            r = contrast(fg, bg)
            if r < 4.5:
                failures.append(f"{label}: {fg_tok} ({fg}) on {bg_tok} ({bg}) = {r:.2f}:1 < 4.5")
    assert not failures, "TIER-1 contrast failures:\n" + "\n".join(failures)


def test_tier2_contrast_tertiary():
    """Tertiary text: WCAG large-text/UI floor of 3.0:1, both modes."""
    _load()
    for mode in ("light", "dark_media", "dark_attr"):
        fg, bg = resolve("--text-tertiary", mode), resolve("--bg-primary", mode)
        r = contrast(fg, bg)
        assert r >= 3.0, f"{mode}: text-tertiary ({fg}) on bg-primary ({bg}) = {r:.2f}:1 < 3.0"


def test_quaternary_is_strictly_faintest():
    """Quaternary mirrors Apple's quaternaryLabel: strictly fainter than
    tertiary, decorative-only — never for essential text."""
    _load()
    for mode in ("light", "dark_media", "dark_attr"):
        ls = luminance(resolve("--secondary", mode))
        lt = luminance(resolve("--tertiary", mode))
        lq = luminance(resolve("--quaternary", mode))
        lbg = luminance(resolve("--bg-primary", mode))
        if lbg > 0.5:  # light mode: fainter == higher luminance
            assert ls < lt < lq, f"{mode}: quaternary not strictly faintest"
        else:  # dark mode: fainter == lower luminance
            assert ls > lt > lq, f"{mode}: quaternary not strictly faintest"


def test_primary_roles_sane():
    _load()
    # vivid primary varies by mode (Apple Orange light/dark)
    assert resolve("--primary", "light") == "#FF8D28"
    assert resolve("--primary", "dark_attr") == "#FF9230"
    # primary-strong is Apple's IC Orange in BOTH modes: the darkest Apple
    # orange that keeps white button text at >= 4.5:1
    assert resolve("--primary-strong", "light") == "#C55300"
    assert resolve("--primary-strong", "dark_attr") == "#C55300"
    assert contrast("#FFFFFF", "#C55300") >= 4.5
