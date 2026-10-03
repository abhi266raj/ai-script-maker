# Feature

New capability, UI, model, emotion, format, or prompt. Need an approved spec (`docs/REQUIREMENTS_vX.Y.md` or GitHub issue) and a plan before code. Output: `feature/` branch, fail-loud code, old payloads still load, `./runut` if `.py` changed, PR.

1. No feature commits without that spec + plan.
2. Missing data raises. No silent fallback or invented default.
3. Enums/constants → `core/constants.py`. Models → `core/models.py`. Prompts → `core/prompt_matrix.py` and `prompts/`. UI → `app.py`.
4. Saved stories and old schemas must still load.

```bash
./create_branch feature/<name>
./runut   # .py only; fails → guidelines/workflows/failure.md
git add <files> && git commit -m "feat: <desc>"
./open_pr -t "feat: <desc>" -b "## Summary\n<details>"
# show PR; ./merge_pr <n> only after user approval
```
