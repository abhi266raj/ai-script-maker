# Failures (`scripts/` and `tests/`)

`./runut` only if `.py` changed. Skip for `.md`, guidelines, prompts, docs.

Triage:

| Defect | Action | Report Params |
| :--- | :--- | :--- |
| `scripts/*` defect / outdated CLI | Do not bypass; update existing issue or report bug | Title, script path, error, required fix, label `bug` |
| Regression from edit | Fix implementation | N/A |
| Baseline fail (`./runut --baseline <target>`) | Note in PR; do not expand scope | N/A |
| Defective test (`tests/*`) | Do not edit or weaken test; update existing issue or report bug | Title, test file path, why code is correct, test defect, label `bug` |
