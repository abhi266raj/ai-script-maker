# Grok

When Grok writes or edits this repo: Python 3.11, existing style, no new dependencies.

1. **Token budget:** Grok token limit is very low. Commit often in small increments, keep diffs tiny, and avoid reaching token exhaustion.
2. No unapproved packages.
3. Assert invalid input. No silent fallback, fake placeholder, or swallowed exception.
4. Minimal diff. Keep comments, docstrings, issue refs.
5. Honor `core/models.py` and `agents/output_contract.py`.
