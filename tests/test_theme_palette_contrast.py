"""Khabarwaani theme palette — contrast + token-discipline tests.

Parses the theme CSS in app.py (raw --pal-* palette + the three semantic
appearance blocks), resolves var() chains, and enforces:

- TIER 1 (>= 4.5:1, WCAG AA): essential text pairs. FAILS LOUDLY.
- TIER 2 (>= 3:1, WCAG large-text/UI floor): the user's explicit
  sub-4.5 spec values (light primary button, light success/warning
  solids, dark danger badge). Each is pinned to its EXACT measured ratio
  so drift fails loudly — measured, never faked.
- Quaternary is decorative-only: strictly faintest tier, never used for
  essential text.
- No hex literals in the three semantic appearance blocks: every value
  must be a var() reference (or the --scheme keyword), so theme colors
  change in exactly one place.
- The raw --pal-* values match the user-supplied spec verbatim
  (docs/COLOR_PALETTE.md).
- TOKEN DISCIPLINE: no blue-range hex anywhere in component CSS
  (rules: no blue for info/chips/links — ever), and no hard-coded hex
  outside :root palette blocks in app.py or library_ui.py.

HIG: contrast minimum 4.5:1, aim 7:1 for small text (see
~/workspace/docs/apple-hig-notes.md §4).
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_PY = REPO / "app.py"
LIB_UI_PY = REPO / "library_ui.py"

# User-supplied spec, verbatim (docs/COLOR_PALETTE.md). (name, light, dark)
# Non-hex values (scrim/shadow) compare as verbatim strings.
USER_PALETTE = {
    "--pal-paper-light": "#F5F3EE", "--pal-paper-dark": "#1C1B19",
    "--pal-card-light": "#FFFFFF", "--pal-card-dark": "#262522",
    "--pal-sunken-light": "#EFECE4", "--pal-sunken-dark": "#2E2D29",
    "--pal-popover-light": "#FFFFFF", "--pal-popover-dark": "#2E2D29",
    "--pal-hover-light": "#F0EDE5", "--pal-hover-dark": "#34332E",
    "--pal-line-light": "#E3DFD5", "--pal-line-dark": "#3A3833",
    "--pal-line-strong-light": "#CFCABD", "--pal-line-strong-dark": "#4A4740",
    "--pal-ink-light": "#1F1E1B", "--pal-ink-dark": "#F1EEE6",
    "--pal-ink2-light": "#6B675F", "--pal-ink2-dark": "#A39E92",
    "--pal-ink3-light": "#9A958A", "--pal-ink3-dark": "#77726A",
    "--pal-on-accent-light": "#FFFFFF", "--pal-on-accent-dark": "#1C1B19",
    "--pal-accent-light": "#E0692A", "--pal-accent-dark": "#EA7A3D",
    "--pal-accent-hover-light": "#C9581D",
    "--pal-accent-hover-dark": "#F28C54",
    "--pal-accent-tint-light": "#F8E6DA", "--pal-accent-tint-dark": "#3A2A20",
    "--pal-danger-light": "#B3382C", "--pal-danger-dark": "#E5604F",
    "--pal-danger-tint-light": "#F7E4E1", "--pal-danger-tint-dark": "#3A2220",
    "--pal-success-light": "#3F7D58", "--pal-success-dark": "#5DAE7F",
    "--pal-success-tint-light": "#E3F0E8",
    "--pal-success-tint-dark": "#1F2E25",
    "--pal-warning-light": "#A8741A", "--pal-warning-dark": "#D9A441",
    "--pal-warning-tint-light": "#F7ECD6",
    "--pal-warning-tint-dark": "#33291A",
    "--pal-scrim-light": "rgba(31, 30, 27, .40)",
    "--pal-scrim-dark": "rgba(0, 0, 0, .60)",
    "--radius": "10px",
    "--radius-lg": "12px",
    "--pal-shadow-sm-light": "0 1px 2px rgba(31, 30, 27, .06)",
    "--pal-shadow-sm-dark": "none",
    "--pal-shadow-pop-light": "0 8px 24px rgba(31, 30, 27, .12)",
    "--pal-shadow-pop-dark": "0 8px 24px rgba(0, 0, 0, .40)",
}

# Derived (documented in docs/COLOR_PALETTE.md): decorative tier only.
DERIVED = {
    "--pal-quaternary-light": "#C4BFAF", "--pal-quaternary-dark": "#57534A",
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
    # Raw palette: the bare ":root {" block holding --pal-* values.
    raw_blocks = re.findall(r":root\s*\{(.*?)\}", css, re.DOTALL)
    raw_hits = [b for b in raw_blocks if "--pal-paper-light" in b]
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


def test_raw_values_match_user_spec():
    """The --pal-* source of truth matches docs/COLOR_PALETTE.md verbatim."""
    _load()
    bad = []
    for name, want in {**USER_PALETTE, **DERIVED}.items():
        got = RAW.get(name, "")
        if want.startswith("#"):
            ok = got.upper() == want.upper()
        else:
            ok = re.sub(r"\s+", " ", got) == re.sub(r"\s+", " ", want)
        if not ok:
            bad.append(f"{name}: css={got!r} spec={want!r}")
    assert not bad, "palette drifted from the user spec:\n" + "\n".join(bad)


def test_no_hex_literals_in_semantic_blocks():
    """Single source of truth: appearance blocks hold only var()/keywords."""
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
    lq = resolve("--quaternary", "light")
    dq = resolve("--quaternary", "dark_attr")
    assert lq != dq, "quaternary must have distinct light/dark values"


def _tier1_pairs():
    # (fg, bg, modes) — modes restricted where the user's explicit spec
    # value is tier-2 in one mode (see _tier2_pins).
    return [
        ("--ink", "--paper", ("light", "dark_media", "dark_attr")),
        ("--ink", "--card", ("light", "dark_media", "dark_attr")),
        ("--ink", "--sunken", ("light", "dark_media", "dark_attr")),
        ("--ink-2", "--paper", ("light", "dark_media", "dark_attr")),
        ("--ink-2", "--card", ("light", "dark_media", "dark_attr")),
        ("--ink-2", "--sunken", ("light", "dark_media", "dark_attr")),
        ("--danger", "--paper", ("light", "dark_media", "dark_attr")),
        ("--success", "--paper", ("dark_media", "dark_attr")),
        ("--warning", "--paper", ("dark_media", "dark_attr")),
        ("--ink", "--accent-tint", ("light", "dark_media", "dark_attr")),
        ("--ink", "--danger-tint", ("light", "dark_media", "dark_attr")),
        ("--ink", "--success-tint", ("light", "dark_media", "dark_attr")),
        ("--ink", "--warning-tint", ("light", "dark_media", "dark_attr")),
        ("--on-accent", "--accent", ("dark_media", "dark_attr")),
        ("--danger", "--danger-tint", ("light",)),
        ("--success", "--success-tint", ("dark_media", "dark_attr")),
        ("--warning", "--warning-tint", ("dark_media", "dark_attr")),
    ]


def test_tier1_contrast_essential_pairs():
    """WCAG AA 4.5:1 for every essential text pair. FAILS LOUDLY."""
    _load()
    failures = []
    for fg_tok, bg_tok, modes in _tier1_pairs():
        for mode in modes:
            label = {"light": "light", "dark_media": "dark@media",
                     "dark_attr": "dark[attr]"}[mode]
            fg, bg = resolve(fg_tok, mode), resolve(bg_tok, mode)
            r = contrast(fg, bg)
            if r < 4.5:
                failures.append(
                    f"{label}: {fg_tok} ({fg}) on {bg_tok} ({bg}) = {r:.2f}:1 < 4.5")
    assert not failures, "TIER-1 contrast failures:\n" + "\n".join(failures)


def _tier2_pins():
    # (fg, bg, mode, exact_ratio): the user's explicit spec values that sit
    # at the WCAG large-text/UI floor. The exact ratio is pinned so any
    # drift fails loudly — measured, never faked.
    return [
        ("--on-accent", "--accent", "light", 3.37),
        ("--success", "--paper", "light", 4.42),
        ("--warning", "--paper", "light", 3.66),
        ("--accent", "--paper", "light", 3.04),
        ("--success", "--success-tint", "light", 4.18),
        ("--warning", "--warning-tint", "light", 3.46),
        ("--danger", "--danger-tint", "dark_attr", 4.28),
    ]


def test_tier2_user_spec_values_pinned():
    """Sub-4.5 user-spec pairs: >= 3:1 floor AND exact measured ratio."""
    _load()
    failures = []
    for fg_tok, bg_tok, mode, pinned in _tier2_pins():
        fg, bg = resolve(fg_tok, mode), resolve(bg_tok, mode)
        r = contrast(fg, bg)
        if r < 3.0:
            failures.append(
                f"{mode}: {fg_tok} ({fg}) on {bg_tok} ({bg}) = {r:.2f}:1 < 3.0")
        elif abs(r - pinned) > 0.06:
            failures.append(
                f"{mode}: {fg_tok} on {bg_tok} drifted: {r:.2f}:1 "
                f"(pinned {pinned:.2f}:1)")
    assert not failures, "TIER-2 pin failures:\n" + "\n".join(failures)


def test_tertiary_is_non_reading_tier():
    """ink-3 is placeholders/disabled ONLY — 'never anything that must be
    read' (user spec). It deliberately sits below the 3.0 floor; the exact
    ratios are pinned so drift fails loudly."""
    _load()
    expected = {"light": 2.69, "dark_media": 3.61, "dark_attr": 3.61}
    for mode, pinned in expected.items():
        fg, bg = resolve("--tertiary", mode), resolve("--bg-primary", mode)
        r = contrast(fg, bg)
        assert abs(r - pinned) < 0.06, (
            f"{mode}: tertiary ratio drifted: {r:.2f}:1 (pinned {pinned:.2f}:1)")
        assert r < 4.5, f"{mode}: tertiary unexpectedly reached 4.5:1"


def test_quaternary_is_strictly_faintest():
    """Quaternary: strictly faintest tier, decorative-only."""
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
    assert resolve("--primary", "light") == "#E0692A"
    assert resolve("--primary", "dark_attr") == "#EA7A3D"
    assert resolve("--accent-hover", "light") == "#C9581D"
    assert resolve("--accent-hover", "dark_attr") == "#F28C54"
    assert resolve("--on-accent", "light") == "#FFFFFF"
    assert resolve("--on-accent", "dark_attr") == "#1C1B19"
    # dark primary button: ink text on accent clears 4.5:1
    assert contrast("#1C1B19", "#EA7A3D") >= 4.5


def _all_style_css(path: Path) -> str:
    src = path.read_text()
    return "\n".join(re.findall(r"<style>(.*?)</style>", src, re.DOTALL))


def _is_blue_hex(h: str) -> bool:
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return b > r + 30 and b >= g


def test_no_blue_hex_in_component_css():
    """Rules: no blue for info/chips/links — ever. Any blue-range hex in
    component CSS fails loudly."""
    offenders = []
    for path in (APP_PY, LIB_UI_PY):
        css = _all_style_css(path)
        for m in re.finditer(r"#[0-9a-fA-F]{6}\b", css):
            if _is_blue_hex(m.group(0)):
                line = css[:m.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}: {m.group(0)}")
    assert not offenders, "blue hex in component CSS:\n" + "\n".join(offenders)


def test_no_hex_outside_root_palette_blocks():
    """Token discipline: hard-coded hex may only appear inside :root
    palette blocks — component CSS references tokens."""
    offenders = []
    for path in (APP_PY, LIB_UI_PY):
        css = _all_style_css(path)
        # strip every :root { ... } block (palette + semantic)
        stripped = re.sub(r":root[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", "", css)
        stripped = re.sub(r"url\([^)]*\)", "", stripped)
        for m in re.finditer(r"#[0-9a-fA-F]{6}\b", stripped):
            line = stripped[:m.start()].count("\n") + 1
            offenders.append(f"{path.name} ~line {line}: {m.group(0)}")
    assert not offenders, (
        "hard-coded hex outside :root palette blocks — use a token:\n"
        + "\n".join(offenders[:20])
    )
