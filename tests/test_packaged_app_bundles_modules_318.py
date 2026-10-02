"""#318 — packaged Mac app must bundle every top-level module app.py imports.

Regression test: scripts/build_macos_app.sh drives PyInstaller's --add-data.
If app.py gains an `import <top_level_module>` and the build script is not
updated, the frozen .app crashes with ModuleNotFoundError (as story_library
did). This test parses both files and fails loudly when they drift.
"""
import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_PY = REPO / "app.py"
BUILD_SH = REPO / "scripts" / "build_macos_app.sh"


def _top_level_imports():
    """Module names imported by app.py that live as <name>.py in the repo root."""
    tree = ast.parse(APP_PY.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    return {n for n in names if (REPO / f"{n}.py").is_file()}


def _add_data_files():
    """Filenames listed in the build script's --add-data entries."""
    text = BUILD_SH.read_text()
    files = set()
    for m in re.finditer(r'--add-data\s+"([^":]+):[^"]*"', text):
        src = m.group(1)
        if "/" not in src and src.endswith(".py"):
            files.add(src[:-3])  # strip .py -> module name
    return files


def test_build_script_bundles_all_top_level_app_imports():
    imported = _top_level_imports()
    bundled = _add_data_files()
    missing = imported - bundled
    assert not missing, (
        f"#318: scripts/build_macos_app.sh --add-data is missing: {sorted(missing)}; "
        f"the frozen .app would crash with ModuleNotFoundError"
    )


def test_story_library_specifically_bundled():
    # The exact module from the #318 crash report.
    assert "story_library" in _add_data_files()
    assert "library_ui" in _add_data_files()
