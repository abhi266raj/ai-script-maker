"""#201: toast notification icons must be Material icon shortcodes, never emoji.

Streamlit renders ``st.toast(icon=...)`` with Material Symbols
(``:material/<name>:``). Emoji in the notification chrome broke the
app's icon-only Material-icon rule (HIG section 2), so every
``_notify``/``st.toast`` icon must be a Material shortcode or ``None``.
"""

import re
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Emoji ranges covering ✅ (U+2705), ℹ️ (U+2139 U+FE0F), ⚠️ (U+26A0 U+FE0F)
# and the wider emoji blocks, so future regressions are caught too.
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]"
)
_MATERIAL_SHORTCODE_RE = re.compile(r"^:material/[a-z][a-z0-9_]*:$")


def _library_ui_module():
    """Import library_ui with stubbed third-party modules.

    streamlit/feedparser/httpx/bs4/pydantic are not installed in this
    environment (and a full requirements install does not fit on this
    machine's /tmp); the same stub pattern the existing suite uses for
    streamlit is extended to the other missing modules. Only
    ``_refresh_outcome_icon`` (a pure function) is exercised, so the
    stubs never observe real behaviour. sys.modules is restored
    afterwards, matching the existing ``_ui_with_fake_st`` convention.
    """
    saved = dict(sys.modules)
    try:
        class _StubMeta(type):
            def __getattr__(cls, name):
                sub = _StubMeta(name, (), {"__module__": cls.__name__})
                return sub

            def __call__(cls, *a, **k):
                return _StubMeta("ret", (), {})

        class _Stub(metaclass=_StubMeta):
            pass

        for name in ("streamlit", "streamlit.components",
                     "streamlit.components.v1",
                     "feedparser", "httpx", "bs4", "pydantic"):
            stub = _StubMeta(name, (), {"__module__": name})
            sys.modules[name] = stub
        sys.modules.pop("library_ui", None)
        import library_ui
        return library_ui
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def test_refresh_outcome_icon_returns_material_shortcodes():
    lui = _library_ui_module()
    assert lui._refresh_outcome_icon("succeeded") == ":material/check_circle:"
    assert lui._refresh_outcome_icon("no_change") == ":material/info:"
    assert lui._refresh_outcome_icon("failed") == ":material/warning:"
    assert lui._refresh_outcome_icon("interrupted") == ":material/warning:"


def test_refresh_outcome_icon_unknown_status_falls_back_to_info():
    lui = _library_ui_module()
    assert lui._refresh_outcome_icon("bogus") == ":material/info:"


def test_refresh_outcome_icons_are_valid_material_shortcode_shape():
    lui = _library_ui_module()
    for status in ("succeeded", "no_change", "failed", "interrupted", "bogus"):
        icon = lui._refresh_outcome_icon(status)
        assert _MATERIAL_SHORTCODE_RE.match(icon), (
            f"status {status!r} -> {icon!r} is not a :material/<name>: shortcode"
        )
        assert not _EMOJI_RE.search(icon), (
            f"status {status!r} -> {icon!r} contains emoji"
        )


def test_no_emoji_codepoints_in_toast_icon_literals():
    """Scan library_ui.py source: every ``icon="..."`` literal passed to a
    toast (via _notify) must be pure ASCII — no emoji codepoints."""
    src = (REPO_ROOT / "library_ui.py").read_text(encoding="utf-8")
    literals = re.findall(r'''icon\s*=\s*(?:"([^"]*)"|'([^']*)')''', src)
    assert literals, "no icon= literals found — scan pattern may be stale"
    for double_quoted, single_quoted in literals:
        literal = double_quoted or single_quoted
        assert not _EMOJI_RE.search(literal), (
            f"emoji in toast icon literal: {literal!r}"
        )
