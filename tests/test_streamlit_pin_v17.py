"""v1.7 (#200) — Streamlit is pinned; DOM markers verified against the pin.

#200: requirements.txt left streamlit unpinned, yet every centering rule in
app.py / library_ui.py selects on Streamlit's exact DOM — e.g. the Library
section rows depend on the chain
    div[data-testid="stElementContainer"]:has([data-marker=...])
    + div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]
    > div[data-testid="stColumn"]
(library_ui.py). Two past alignment bugs (#68, #112) were exactly this: a
selector silently not matching the real DOM. Streamlit 1.51 even removed
stVerticalBlockBorderWrapper outright, silently killing the card rules at
app.py:546, 1147-1149, 1287-1300.

Defense in depth:
1. requirements.txt pins streamlit with an exact ``==`` specifier.
2. This test fails loudly when the pin is removed or relaxed, when the
   installed streamlit differs from the pin, or when a DOM marker the CSS
   structurally depends on is absent from the pinned Streamlit's shipped
   frontend bundle (``<streamlit>/static``).
3. Every ``data-testid`` in the app's CSS must be classified below
   (REQUIRED_DOM_MARKERS or TOLERATED_ABSENT with a reason) — a new marker
   fails loudly until classified, and a stale classification fails loudly
   until removed.

Marker verification (2026-10-02, streamlit 1.64.0 bundle): all 49 required
markers present; the 7 tolerated-absent markers documented below.

Run: python -m pytest tests/test_streamlit_pin_v17.py -q
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
REQ_FILE = REPO_ROOT / "requirements.txt"
CSS_SOURCES = (REPO_ROOT / "app.py", REPO_ROOT / "library_ui.py")

# data-testid values the app's CSS structurally depends on: if one of these
# vanishes from Streamlit's DOM, the rule silently stops matching (the #68 /
# #112 / #200 failure mode). Verified present in the pinned bundle — see
# test_css_dom_markers_present_in_pinned_bundle.
REQUIRED_DOM_MARKERS = frozenset({
    # Section-row centering chain (library_ui.py): the marker's
    # stElementContainer must be immediately followed by
    # stLayoutWrapper > stHorizontalBlock > stColumn (#162, #192).
    "stElementContainer",
    "stLayoutWrapper",
    "stHorizontalBlock",
    "stColumn",
    # Everything else the CSS selects on, verified against the pinned bundle.
    "stAlert",
    "stApp",
    "stAppViewContainer",
    "stBottom",
    "stBottomBlockContainer",
    "stButton",
    "stButtonGroup",
    "stCheckbox",
    "stCode",
    "stDialog",
    "stDownloadButton",
    "stExpandSidebarButton",
    "stExpander",
    "stFileUploaderDropzone",
    "stFileUploaderDropzoneInstructions",
    "stFormSubmitButton",
    "stHeader",
    "stImage",
    "stLinkButton",
    "stMain",
    "stMainBlockContainer",
    "stMainMenu",
    "stMarkdownContainer",
    "stNumberInput",
    "stNumberInputContainer",
    "stNumberInputField",
    "stNumberInputStepDown",
    "stNumberInputStepUp",
    "stPopover",
    "stPopoverBody",
    "stPopoverButton",
    "stRadio",
    "stSelectbox",
    "stSelectboxVirtualDropdown",
    "stSidebar",
    "stSidebarCollapseButton",
    "stSidebarContent",
    "stSidebarUserContent",
    "stSpinner",
    "stSpinnerIcon",
    "stStatusWidget",
    "stTabs",
    "stTextArea",
    "stTextInput",
    "stToast",
    "stToolbar",
    "stVerticalBlock",
    "stWidgetLabel",
})

# data-testid values in the CSS that are (currently) absent from the pinned
# bundle, each with a documented reason. Format: marker -> (kind, reason).
# Kinds: "fallback" (selector list still matches via another selector),
# "harmless" (rule is a no-op when the marker is absent),
# "removed" (Streamlit removed the marker; rules using it are dead — the test
# asserts it STAYS absent so a reintroduction fails loudly instead of silently
# reactivating dead rules).
TOLERATED_ABSENT = {
    "stBaseButton-primary": (
        "fallback",
        "selector list also matches button[kind=\"primary\"] / .stButton",
    ),
    "stBaseButton-secondary": (
        "fallback",
        "selector list also matches button[kind=\"secondary\"] / .stButton",
    ),
    "baseButton-primary": (
        "fallback",
        "legacy variant in the same selector list as stBaseButton-primary",
    ),
    "baseButton-secondary": (
        "fallback",
        "legacy variant in the same selector list as stBaseButton-secondary",
    ),
    "stDecoration": (
        "harmless",
        "hide-chrome selector list; other selectors still hide the chrome",
    ),
    "stNotification": (
        "harmless",
        "color-scheme selector list; no visual rule depends on it alone",
    ),
    "stVerticalBlockBorderWrapper": (
        "removed",
        "removed in Streamlit 1.51 — the card rules at app.py:546, 1147-1149, "
        "1287-1300 are dead until re-anchored (follow-up to #200)",
    ),
}

_TESTID_RE = re.compile(r'data-testid=\\?"([^"]+)"')


def _markers_found_in_bundle(bundle, markers):
    """Single-pass scan: which markers occur as standalone tokens."""
    combined = re.compile(
        "|".join(
            r"(?<![A-Za-z0-9_-])" + re.escape(m) + r"(?![A-Za-z0-9_-])"
            for m in sorted(markers)
        )
    )
    return set(combined.findall(bundle))


def _css_testids():
    """Every data-testid value used by the app's CSS selectors."""
    found = set()
    for path in CSS_SOURCES:
        src = path.read_text(encoding="utf-8")
        found.update(_TESTID_RE.findall(src))
    return found


def _pinned_streamlit_version():
    """The exact streamlit version pinned in requirements.txt.

    Fails loudly if the pin is missing or not an exact ``==`` specifier.
    """
    assert REQ_FILE.is_file(), f"{REQ_FILE} not found"
    for raw in REQ_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        m = re.match(r"(?i)^streamlit(?![A-Za-z0-9_-])\s*(.*?)\s*$", line)
        if not m:
            continue
        rest = m.group(1)
        m = re.fullmatch(r"==\s*(\d+\.\d+\.\d+)", rest)
        assert m, (
            "#200: requirements.txt must pin streamlit with an exact "
            f"'==X.Y.Z' specifier — found {raw.strip()!r}. An unpinned or "
            "range-pinned Streamlit can silently un-center every section row "
            "when its DOM drifts (see #68, #112)."
        )
        return m.group(1)
    raise AssertionError(
        "#200: no streamlit pin found in requirements.txt — the exact "
        "'streamlit==X.Y.Z' pin was removed. Restore it: every centering rule "
        "depends on the pinned Streamlit's DOM."
    )


def test_streamlit_pinned_exact():
    """#200: streamlit must stay pinned with an exact == specifier."""
    version = _pinned_streamlit_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"#200: pinned streamlit version {version!r} is not a full X.Y.Z"
    )


def _import_streamlit():
    try:
        import streamlit
    except ImportError:
        pytest.skip(
            "streamlit is not installed in this environment — "
            "run: pip install -r requirements.txt"
        )
    return streamlit


def test_installed_streamlit_matches_pin():
    """#200: the installed streamlit must be exactly the pinned version.

    A different installed version means the DOM the CSS was verified against
    is not the DOM being served — fail loudly, do not silently test the wrong
    bundle.
    """
    pinned = _pinned_streamlit_version()
    streamlit = _import_streamlit()
    installed = streamlit.__version__
    assert installed == pinned, (
        f"#200: installed streamlit is {installed}, but requirements.txt pins "
        f"{pinned}. The CSS was verified against the pinned version's DOM — "
        "run: pip install -r requirements.txt"
    )


def _bundle_text(streamlit):
    static_dir = Path(streamlit.__file__).resolve().parent / "static"
    assert static_dir.is_dir(), (
        f"#200: cannot verify DOM markers — {static_dir} missing from the "
        f"installed streamlit {streamlit.__version__}"
    )
    chunks = []
    for path in sorted(static_dir.rglob("*")):
        if path.is_file():
            try:
                chunks.append(path.read_bytes().decode("utf-8", "ignore"))
            except OSError:
                continue
    bundle = "\n".join(chunks)
    assert bundle.strip(), f"#200: {static_dir} is empty — cannot verify markers"
    return bundle


def test_css_dom_markers_present_in_pinned_bundle():
    """#200: every structural DOM marker must exist in the pinned bundle.

    Fails loudly when a Streamlit upgrade removes/renames a data-testid the
    CSS selects on, when the CSS gains an unclassified marker, or when a
    classification goes stale.
    """
    pinned = _pinned_streamlit_version()
    streamlit = _import_streamlit()
    if streamlit.__version__ != pinned:
        pytest.skip(
            f"installed streamlit {streamlit.__version__} != pinned {pinned}: "
            "markers can only be verified against the pinned bundle "
            "(see test_installed_streamlit_matches_pin)"
        )

    css_ids = _css_testids()
    classified = REQUIRED_DOM_MARKERS | frozenset(TOLERATED_ABSENT)
    unclassified = sorted(css_ids - classified)
    assert not unclassified, (
        "#200: new data-testid value(s) in the app's CSS are not classified: "
        f"{unclassified}. Add each to REQUIRED_DOM_MARKERS (structural — must "
        "exist in the pinned bundle) or TOLERATED_ABSENT with a reason."
    )
    stale = sorted(classified - css_ids)
    assert not stale, (
        "#200: classified marker(s) no longer used by the app's CSS: "
        f"{stale}. Remove them from REQUIRED_DOM_MARKERS / TOLERATED_ABSENT "
        "to keep the classification honest."
    )

    bundle = _bundle_text(streamlit)
    found = _markers_found_in_bundle(
        bundle, REQUIRED_DOM_MARKERS | frozenset(TOLERATED_ABSENT)
    )
    missing = sorted(REQUIRED_DOM_MARKERS - found)
    assert not missing, (
        f"#200: DOM marker(s) required by the app's CSS are ABSENT from the "
        f"pinned streamlit {pinned} frontend bundle: {missing}. The selectors "
        "using them silently match nothing (the #68/#112 failure mode). Either "
        "re-anchor the CSS to the new DOM or pin a Streamlit that still ships "
        "these markers."
    )
    reintroduced = sorted(
        m for m, (kind, _reason) in TOLERATED_ABSENT.items()
        if kind == "removed" and m in found
    )
    assert not reintroduced, (
        "#200: marker(s) classified as Streamlit-removed are PRESENT again in "
        f"the pinned bundle: {reintroduced}. Move them to REQUIRED_DOM_MARKERS "
        "and re-enable the CSS rules that were dead."
    )
