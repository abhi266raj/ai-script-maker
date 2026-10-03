# Grok Engine & Model Rules

---

## 🚦 When to Apply & What to Expect

- **When to Apply:** Generating scripts, hooks, or character personas via xAI's Grok engine (`grok_low`, `grok_medium`, `grok_high`).
- **What to Expect:** High-speed remote reasoning, snappy conversational banter, and adherence to CLI rate-limiting policies.

---

## 🛑 Rules & Invariants

1. **Rate Limiting & Team Caps:**
   - Grok CLI calls are strictly capped at **2 requests per second** across the process.
   - All invocations must route through `_wait_for_grok_slot()` and `_mark_grok_call()` in [`core/dual_engine.py`](file:///Users/abhiraj/Documents/news/agent/core/dual_engine.py).
2. **Exponential Backoff on 429:**
   - Any HTTP 429 / quota error must trigger exponential backoff retry up to `_grok_max_retries` attempts.
   - Do NOT treat a rate limit as an immediate fatal error during preflight checks.
3. **Effort Levels:**
   - Respect configured effort levels: `low`, `medium`, or `high`.
4. **Timeout Handling:**
   - Remote model timeout defaults to 120 seconds (`REMOTE_MODEL_TIMEOUT_SECONDS`).
   - If Grok CLI returns empty or fails, fail loudly with an informative error rather than silently falling back to unverified defaults.
