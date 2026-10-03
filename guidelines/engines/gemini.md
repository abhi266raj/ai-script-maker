# Gemini

When Gemini writes or edits this repo.

1. Python 3.11. `typing` (`Optional`, `List`, `Dict`, `Tuple`, `Any`). Annotate params and returns.
2. No invented defaults, no `try/except: pass`. `ValueError` or domain error with input, expected, stage.
3. Patch a block. Do not rewrite a file for a few lines. Keep docstrings and `#138` `#207` `#217` `#338` `#344`.
4. Streamlit: no hardcoded colors or CSS that breaks light/dark (#207, #219). `st.warning()` not `st.error()` (#217).
5. Cite edits as `file://` markdown links.
