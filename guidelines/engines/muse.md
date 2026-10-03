# Muse (Local FM) Engine Rules

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Generating scripts via Apple's on-device Foundation Model (`fm` CLI / Local FM).
- **What to Expect:** Zero-cost, 100% private, ultra-low-latency on-device generation with local token and memory constraints.

---

## 🛑 Rules & Invariants

1. **Local Execution & Binary:**
   - Inferences execute via `/usr/bin/fm respond --no-stream` managed by [`core/fm_engine.py`](file:///Users/abhiraj/Documents/news/agent/core/fm_engine.py).
   - Requires Apple Intelligence / macOS Foundation Models availability.
2. **Token & Context Limits:**
   - On-device context is bounded; prompts must be concise, structured, and token-lean.
   - Separate system instructions passed via `-i <instructions>` flag where supported.
3. **Fail-Fast & Seamless Fallback:**
   - If Local FM returns empty, restricted, or times out (default 120s), log explicitly and fail loudly or gracefully fallback according to the dual-engine policy (`first_local_then_agy`).
   - Never hang indefinitely if the local model daemon becomes unresponsive.
4. **No External Network Dependencies:**
   - Muse operates entirely offline; do not attempt network probes or remote API calls within the local FM execution path.
