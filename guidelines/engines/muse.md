# Muse (On-Device) Code Generation Guidelines

Operational standards when **Muse / Apple on-device models** generate, edit, or patch code in this repository.

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Any task where Muse or local on-device models are generating patches, small functions, or code edits.
- **What to Expect:** Token-lean, highly focused code modifications that fit comfortably within local context memory.

---

## 🛑 Code Generation Invariants

1. **Token-Lean Code Output:**
   - Focus exclusively on the specific function or code block being added or patched.
   - Do NOT regenerate entire files or large boilerplates when modifying existing modules.
2. **Standard Library & macOS Compatibility:**
   - Generate standard Python 3.11 code compatible with the local macOS Apple Silicon environment.
   - Do NOT assume external network connectivity or cloud APIs during local code authoring.
3. **Fail-Loud Principles:**
   - Ensure all generated code adheres to strict error handling—raise explicit exceptions rather than returning silent nulls or empty fallback values.
4. **Preserve Surrounding Context:**
   - Retain existing function contracts, signatures, docstrings, and issue annotations.
