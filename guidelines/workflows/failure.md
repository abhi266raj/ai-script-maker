# Failures (`scripts/` and `tests/`)

`./runut` only if `.py` changed. Skip for `.md`, guidelines, prompts, docs.

Triage:

- `scripts/*` bug, outdated CLI, or bad assumption: do not bypass with manual git. If issue already known, update it; otherwise `gh issue create --title "bug(script): <name>" --body "## Defect\n- Script: scripts/<name>\n- Error: …\n- Fix: …" --label bug`.
- Test fail caused by your edit: fix the implementation.
- Fail on clean develop (`./runut --baseline <target>`): note in the PR. Do not expand scope.
- Test is wrong (stale assert, bad mock): do not edit, delete, or weaken it. If issue already known, update it; otherwise `gh issue create --title "bug(test): <name> in tests/<file>.py" --body "## Defect\n- File: tests/<file>.py\n- Why code is correct: …\n- Test defect: …" --label bug`.
