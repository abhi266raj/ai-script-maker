# Muse (Assistant) — Repo Operating Notes

Instructions specific to **Muse, the Meta personal AI assistant**, when working on this repository.

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Any task where this assistant works on this repo.
- **What to Expect:** All `guidelines/workflows/` rules apply as-is; the notes below cover Muse-specific environment handling only.

---

## 🛑 Muse-Specific Invariants

1. **GitHub Token (repo-scoped):** This VM's default `gh` is read-only. Every launch for this repo, read the token from `~/.config/muse/repos/ai-script-maker/github_token` (mode 600, user-managed and rotated) and use it as `GH_TOKEN="$(cat ~/.config/muse/repos/ai-script-maker/github_token)"` for `gh` writes (open PR, create issue, comment, merge).
2. **Never Expose the Token:** Never echo, print, or copy the token into chat replies, memory files, logs, or any other file.
3. **Write Fallbacks:** If the token file is absent, use a session token pasted in chat; if none is available, produce prefilled links instead of shell commands — `https://github.com/<owner>/<repo>/compare/develop...<branch>?title=<enc>&body=<enc>` for PRs, `https://github.com/<owner>/<repo>/issues/new?title=<enc>&body=<enc>&labels=<enc>` for issues (URL-encoded).
4. **Token-Lean Output:** Keep patches, summaries, and terminal output concise — no filler, no redundant explanations.
