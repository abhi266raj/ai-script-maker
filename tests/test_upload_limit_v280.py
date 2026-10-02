"""#280 — the upload widgets must not show a file-size limit caption.

The app places no practical limit on upload size (generated videos can be
hundreds of MB), but st.file_uploader renders Streamlit's native
"{size} per file" caption from server.maxUploadSize. Two-part contract:

1. .streamlit/config.toml raises maxUploadSize to an effectively-unlimited
   value, so "no upload limit" is TRUE — not a hidden real limit.
2. The theme CSS hides the now-meaningless caption line
   (data-testid="stFileUploaderDropzoneInstructions") while leaving the
   dropzone itself, its label, and the Browse button fully visible.

Run: python -m pytest tests/test_upload_limit_v280.py -q
"""
import re
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / ".streamlit" / "config.toml"
APP_PY = REPO_ROOT / "app.py"

# 10240 MB = 10 GB: far beyond any real upload (generated videos are tens to
# hundreds of MB), so for this app the limit is effectively "no limit".
EFFECTIVELY_UNLIMITED_MB = 10240

_INSTRUCTIONS_RULE = re.compile(
    r'\[data-testid="stFileUploaderDropzoneInstructions"\]\s*\{([^}]*)\}',
    re.DOTALL,
)
_DROPZONE_HIDDEN_RULE = re.compile(
    r'\[data-testid="stFileUploaderDropzone"\]\s*\{[^}]*display\s*:\s*none',
    re.DOTALL,
)


def _server_cfg():
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f).get("server", {})


def test_config_max_upload_size_effectively_unlimited():
    """#280: the server must not enforce a practical upload cap.

    Fails loudly if maxUploadSize is unset (Streamlit's 200MB default would
    apply and the hidden caption would be a lie) or lowered below the
    effectively-unlimited value.
    """
    cfg = _server_cfg()
    assert "maxUploadSize" in cfg, (
        "#280: .streamlit/config.toml must set server.maxUploadSize — "
        "without it Streamlit enforces its 200MB default while the UI "
        "claims there is no limit"
    )
    assert cfg["maxUploadSize"] >= EFFECTIVELY_UNLIMITED_MB, (
        f"#280: maxUploadSize={cfg['maxUploadSize']}MB is a real constraint; "
        f"expected >= {EFFECTIVELY_UNLIMITED_MB}MB (effectively no limit)"
    )


def test_limit_caption_hidden_in_theme_css():
    """#280: the native "{size} per file" caption line must not render."""
    css = APP_PY.read_text(encoding="utf-8")
    m = _INSTRUCTIONS_RULE.search(css)
    assert m is not None, (
        '#280: expected a CSS rule for [data-testid='
        '"stFileUploaderDropzoneInstructions"] in app.py'
    )
    assert re.search(r"display\s*:\s*none\s*!important", m.group(1)), (
        "#280: the dropzone-instructions rule must hide the limit caption "
        "(display: none !important)"
    )


def test_dropzone_itself_not_hidden():
    """#280 guard: hiding the caption must not hide the uploader widget."""
    css = APP_PY.read_text(encoding="utf-8")
    assert _DROPZONE_HIDDEN_RULE.search(css) is None, (
        "#280: the stFileUploaderDropzone container itself must stay "
        "visible — only the instructions caption line may be hidden"
    )
    # The dropzone keeps its themed surface rule (proves the selector still
    # targets a visible widget).
    assert re.search(
        r'\[data-testid="stFileUploaderDropzone"\]\s*\{[^}]*background',
        css,
        re.DOTALL,
    ), "#280: expected the themed stFileUploaderDropzone rule to survive"


def test_no_fake_limit_text_in_css():
    """#280 honesty: the CSS must not paint a fabricated limit string."""
    css = APP_PY.read_text(encoding="utf-8")
    css_no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    assert "per file" not in css_no_comments.lower(), (
        "#280: theme CSS must hide the limit caption, never render a "
        "hard-coded replacement value"
    )
