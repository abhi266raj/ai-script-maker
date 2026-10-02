"""Primary-button specificity regression tests (issue #271, reopened).

Root cause: the theme's *secondary* button rules contained catch-all
selectors like `div[data-testid="stButton"] button` (specificity 0,1,2)
that also match PRIMARY buttons and out-specify the primary rule
`button[data-testid="stBaseButton-primary"]` (0,1,1). Both declarations
are `!important`, so the higher-specificity secondary rule won:
white `--card` background on the primary button, while the primary
`*` descendant rule kept the label `--on-accent` (white) — white text
on a white background, exactly the reopened #271 screenshot.

The fix guards every catch-all selector in the secondary base/hover/
active button rules with
`:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):not([data-testid="baseButton-primary"])`.

These tests simulate the CSS cascade (specificity + source order +
!important) for the synthetic 1.64 button DOM and assert the winning
declarations — they fail on the pre-fix CSS and pass after.
"""

import inspect
import re
from pathlib import Path

REPO = Path(inspect.getfile(inspect.currentframe())).resolve().parent.parent
APP_PY = REPO / "app.py"


def _css() -> str:
    src = APP_PY.read_text()
    m = re.search(r"<style>(.*?)</style>", src, re.S)
    assert m, "no <style> block in app.py"
    return re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)


def _rules(css: str):
    """Yield (selectors: list[str], declarations: str, order: int)."""
    out = []
    for i, m in enumerate(re.finditer(r"([^{}]+)\{([^{}]*)\}", css)):
        selectors = [s.strip() for s in m.group(1).split(",") if s.strip()]
        out.append((selectors, m.group(2), i))
    return out


# --- Minimal selector engine (subset used by the theme CSS) ---

_ATTR_RE = re.compile(r'\[([a-zA-Z0-9_-]+)(?:="([^"]*)")?\]')


def _split_not(selector: str):
    """Split off :not(...) parts; return (base, [not_inner, ...])."""
    nots = []
    base = selector
    while True:
        m = re.search(r":not\(([^()]*)\)", base)
        if not m:
            break
        nots.append(m.group(1))
        base = base[: m.start()] + base[m.end():]
    return base, nots


def _match_compound(compound: str, tag: str, attrs: dict, pseudos: set) -> bool:
    base, nots = _split_not(compound)
    # The synthetic 1.64 DOM carries no ids and no classes: an id or class
    # selector can never match. (Strip quoted attr values first so a dot
    # inside e.g. [data-testid="stBaseButton-primary"] is not mistaken.)
    unquoted = re.sub(r'"[^"]*"', '""', base)
    if re.search(r"#[a-zA-Z0-9_-]+", unquoted):
        return False
    if re.search(r"\.[a-zA-Z_-][a-zA-Z0-9_-]*", unquoted):
        return False
    # pseudo-classes remaining in base must be active
    for pm in re.finditer(r":([a-zA-Z-]+)", base):
        if pm.group(1) not in pseudos:
            return False
    base = re.sub(r":[a-zA-Z-]+", "", base)
    # type selector / universal
    m = re.match(r"^([a-zA-Z*][a-zA-Z0-9_-]*)", base.strip())
    rest = base.strip()
    if m:
        if m.group(1) != "*" and m.group(1).lower() != tag.lower():
            return False
        rest = rest[m.end():]
    for am in _ATTR_RE.finditer(rest):
        name, val = am.group(1), am.group(2)
        if name not in attrs:
            return False
        if val is not None and attrs[name] != val:
            return False
    # :not() inners must NOT match
    for n in nots:
        if _match_compound(n, tag, attrs, pseudos):
            return False
    return True


def _match_selector(selector: str, chain: list, pseudos: set) -> bool:
    """chain: list of (tag, attrs) from root to target element."""
    # tokenize on combinators, keeping them
    toks = re.findall(r"[^ >]+|>", selector)
    # build [combinator, compound] pairs from the right
    parts = []
    i = len(toks) - 1
    comb = " "
    while i >= 0:
        if toks[i] == ">":
            comb = ">"
            i -= 1
            continue
        parts.append((comb, toks[i]))
        comb = " "
        i -= 1
    # parts[0] is the target compound
    idx = len(chain) - 1
    tag, attrs = chain[idx]
    if not _match_compound(parts[0][1], tag, attrs, pseudos):
        return False
    for comb, compound in parts[1:]:
        if comb == ">":
            idx -= 1
            if idx < 0:
                return False
            tag, attrs = chain[idx]
            if not _match_compound(compound, tag, attrs, pseudos):
                return False
        else:  # descendant
            found = False
            idx -= 1
            while idx >= 0:
                tag, attrs = chain[idx]
                if _match_compound(compound, tag, attrs, pseudos):
                    found = True
                    break
                idx -= 1
            if not found:
                return False
    return True


def _specificity(selector: str):
    """(ids, classes/attrs/pseudo-classes, elements) — :not() args count."""
    base, nots = _split_not(selector)
    a = len(re.findall(r"#[a-zA-Z0-9_-]+", base))
    b = len(_ATTR_RE.findall(base)) + len(re.findall(r":[a-zA-Z-]+", base))
    b += sum(
        len(_ATTR_RE.findall(n)) + len(re.findall(r":[a-zA-Z-]+", n))
        for n in nots
    )
    c = len(re.findall(r"(?:^|[ >])([a-zA-Z][a-zA-Z0-9_-]*)", base))
    return (a, b, c)


def _declarations(block: str):
    out = []
    for decl in block.split(";"):
        decl = decl.strip()
        if ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop, val = prop.strip().lower(), val.strip()
        important = val.endswith("!important")
        if important:
            val = val[: -len("!important")].strip()
        out.append((prop, val, important))
    return out


def _cascaded(prop_names, chain, pseudos):
    """Winning (value, selector) for the property among matching rules."""
    best = None  # (important, specificity, order)
    best_val = best_sel = None
    for selectors, block, order in _rules(_css()):
        for sel in selectors:
            if not _match_selector(sel, chain, pseudos):
                continue
            for prop, val, important in _declarations(block):
                if prop not in prop_names:
                    continue
                key = (1 if important else 0, _specificity(sel), order)
                if best is None or key > best:
                    best, best_val, best_sel = key, val, sel
    assert best is not None, f"no rule sets {prop_names}"
    return best_val, best_sel


# Synthetic Streamlit 1.64 DOM for st.button(type="primary"):
# <div data-testid="stButton"><button kind="primary"
#   data-testid="stBaseButton-primary">…</button></div>
PRIMARY_CHAIN = [
    ("div", {"data-testid": "stButton"}),
    ("button", {"kind": "primary", "data-testid": "stBaseButton-primary"}),
]
SECONDARY_CHAIN = [
    ("div", {"data-testid": "stButton"}),
    ("button", {"kind": "secondary", "data-testid": "stBaseButton-secondary"}),
]
BG_PROPS = ("background", "background-color")


def test_primary_button_background_is_accent():
    val, sel = _cascaded(BG_PROPS, PRIMARY_CHAIN, set())
    assert "var(--accent)" in val, f"primary bg is {val!r} from {sel!r}"


def test_primary_button_hover_background_is_accent_hover():
    val, sel = _cascaded(BG_PROPS, PRIMARY_CHAIN, {"hover"})
    assert "var(--accent-hover)" in val, f"primary :hover bg is {val!r} from {sel!r}"


def test_primary_button_active_background_stays_accent():
    # No dedicated primary :active rule: the base accent fill must survive.
    val, sel = _cascaded(BG_PROPS, PRIMARY_CHAIN, {"active"})
    assert "var(--accent)" in val, f"primary :active bg is {val!r} from {sel!r}"


def test_primary_button_label_is_on_accent():
    chain = PRIMARY_CHAIN + [("span", {})]
    val, sel = _cascaded(("color",), chain, set())
    assert "var(--on-accent)" in val, f"primary label color is {val!r} from {sel!r}"


def test_disabled_primary_button_is_sunken_with_ink3():
    # #269 contract: disabled primary = --sunken bg, --ink-3 text (intended).
    val, _ = _cascaded(BG_PROPS, PRIMARY_CHAIN, {"disabled"})
    assert "var(--sunken)" in val, f"disabled primary bg is {val!r}"
    chain = PRIMARY_CHAIN + [("span", {})]
    val, _ = _cascaded(("color",), chain, {"disabled"})
    assert "var(--ink-3)" in val, f"disabled primary label color is {val!r}"


def test_secondary_button_background_unaffected():
    val, sel = _cascaded(BG_PROPS, SECONDARY_CHAIN, set())
    assert "var(--card)" in val, f"secondary bg changed to {val!r} from {sel!r}"


def test_no_catchall_button_selector_touches_primary():
    """Structural guard: any selector that can match a plain
    `div[data-testid="stButton"] button` (or form/popover/download
    variants) in a background-setting rule must exclude primary kinds."""
    catchalls = (
        'div[data-testid="stButton"] button',
        '[data-testid="stFormSubmitButton"] button',
        '[data-testid="stDownloadButton"] button',
        '[data-testid="stPopover"] button',
    )
    primary_markers = (
        '[kind="primary"]',
        '[data-testid="stBaseButton-primary"]',
        '[data-testid="baseButton-primary"]',
    )
    for selectors, block, _ in _rules(_css()):
        decls = _declarations(block)
        if not any(p in BG_PROPS for p, _, _ in decls):
            continue
        for sel in selectors:
            if ":disabled" in sel:
                # Disabled buttons intentionally share one rule (#269:
                # disabled primary = --sunken bg + --ink-3 text).
                continue
            target = re.split(r"[ >]", sel.strip())[-1]
            if any(m in target for m in primary_markers):
                # Selector already pins the primary kind: primary rule.
                continue
            for ca in catchalls:
                if ca in sel:
                    assert ':not([kind="primary"])' in sel, (
                        f"catch-all {sel!r} sets background without "
                        "excluding primary buttons"
                    )
