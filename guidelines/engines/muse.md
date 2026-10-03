# Muse

When Muse (or on-device model) works on this repo.

1. **Diffs:** Small, targeted block edits. Keep signatures, docstrings, issue notes.
2. **Environment:** Python 3.11, stdlib, macOS Apple Silicon. No network/cloud APIs during authoring.
3. **Fail-loud:** Raise. No silent `None` or empty fallback.
4. **Token:** Read `GH_TOKEN` from `~/.config/muse/repos/ai-script-maker/github_token` if default `gh` is read-only. Never expose token.
5. **Write fallback:** If no token, use chat token or prefilled GitHub compare/issue URLs.
6. **Attribution:** Pass `--ai Muse` (or `AI_NAME=Muse`) to `./open_pr` / `./resolve_comment`; append `_Raised by Muse_` to issues/comments.
