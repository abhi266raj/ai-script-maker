# Grok Code Generation Guidelines

Operational standards when **Grok models / CLI** generate, edit, or refactor code in this repository.

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Any task where Grok is generating code, authoring patches, or refactoring modules.
- **What to Expect:** Concise, performant Python 3.11 code, minimal external dependencies, and strict adherence to codebase contracts.

---

## 🛑 Code Generation Invariants

1. **Idiomatic Python 3.11:**
   - Adhere to the project's existing architecture and coding conventions.
   - Do NOT introduce unapproved third-party libraries or external package dependencies.
2. **Fail-Loud Validation:**
   - Write explicit assertions and guardrails.
   - Do NOT introduce silent fallbacks, invented synthetic placeholders, or catch-all exception swallowers.
3. **Surgical Diff Discipline:**
   - Generate focused, minimal diffs targeting the exact requirement or bug fix.
   - Preserve all existing code comments, docstrings, and historical issue references.
4. **Contract Fidelity:**
   - Adhere to existing schemas in [`core/models.py`](file:///Users/abhiraj/Documents/news/agent/core/models.py) and output contracts in [`agents/output_contract.py`](file:///Users/abhiraj/Documents/news/agent/agents/output_contract.py).
