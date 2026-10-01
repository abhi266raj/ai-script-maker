"""Deterministic tests for scripts/release_closing_keywords.sh.

The script shells out to `git` and `gh`; here both are replaced with canned
fakes on PATH so the test exercises the real script without network access.

Run: python -m pytest tests/test_release_closing_keywords.py -q
"""
import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "release_closing_keywords.sh"

FAKE_GIT = """#!/usr/bin/env bash
# Canned git for release_closing_keywords.sh tests.
if [ "$1" = "fetch" ]; then
  exit 0
fi
if [ "$1" = "log" ]; then
  cat "$CANNED_GIT_LOG"
  exit 0
fi
echo "unexpected git invocation: $*" >&2
exit 99
"""

FAKE_GH = """#!/usr/bin/env bash
# Canned gh for release_closing_keywords.sh tests: emit pre-joined TSV.
cat "$CANNED_GH_PRS"
exit 0
"""


@pytest.fixture
def canned_env(tmp_path, monkeypatch):
    """PATH with fake git/gh; returns a setter for the canned payloads."""
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    for name, src in (("git", FAKE_GIT), ("gh", FAKE_GH)):
        p = fakebin / name
        p.write_text(src)
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(fakebin) + os.pathsep + os.environ["PATH"])

    def _set(git_log: str, gh_prs: str):
        log_file = tmp_path / "git_log.txt"
        prs_file = tmp_path / "gh_prs.tsv"
        log_file.write_text(git_log)
        prs_file.write_text(gh_prs)
        monkeypatch.setenv("CANNED_GIT_LOG", str(log_file))
        monkeypatch.setenv("CANNED_GH_PRS", str(prs_file))

    return _set


def _run_script():
    return subprocess.run(
        ["bash", str(SCRIPT), "origin/main"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_generates_sorted_closing_lines(canned_env):
    canned_env(
        "fix: widget frobnicate (#10) (#20)\n"
        "fix: multi issue groups (#1, #2) (#3)\n"
        "fix: titles share row (issues #6, #7) (#40)\n"
        "docs: no numbers here\n",
        # number\tbody (as if already through the script's jq TSV join)
        "20\tFixes #10. Also closes #30. See #20 for context.\n"
        "3\tCloses #3 and fixes #2\n"
        "99\tCloses #100\n",
    )
    result = _run_script()
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "Closes #1",
        "Closes #2",
        "Closes #6",
        "Closes #7",
        "Closes #10",
        # #30: subject heuristic misfiles it as a PR number, but the gh API
        # proves it is not a PR, so the fallback keeps it.
        "Closes #30",
    ]


def test_fallback_excludes_only_genuine_pr_numbers(canned_env):
    """The fixed fallback: #30 is the last (#N) group of a custom squash
    message, so the subject heuristic misfiles it as a PR number — but the
    gh API proves it is not a PR, so "Closes #30" in PR #20's body must still
    produce a line. Genuine PRs (#20 itself, #3, #99) stay excluded."""
    canned_env(
        "fix: widget frobnicate (#10) (#20)\n"
        "fix: custom squash message left the issue in the tail (#30)\n",
        "20\tFixes #10. Closes #30. Closes #20. Closes #99.\n"
        "99\tCloses #100\n",
    )
    result = _run_script()
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    # #30 kept: heuristic PR_NUMS is not a real PR per the API.
    assert "Closes #30" in lines
    # Genuine PR numbers never become Closes lines.
    assert "Closes #20" not in lines
    assert "Closes #99" not in lines
    assert "Closes #100" not in lines  # PR #99 not in range: body ignored
    assert lines == ["Closes #10", "Closes #30"]


def test_no_issues_found_exits_nonzero(canned_env):
    canned_env("docs: no numbers here\n", "")
    result = _run_script()
    assert result.returncode == 1
    assert "No fixed issues found" in result.stderr
