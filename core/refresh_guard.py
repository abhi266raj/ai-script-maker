"""Session-state guard for the Source page "Refresh" headlines button (#196).

Apple HIG §3: the initiating control owns its progress. A Refresh click is
claimed here; while the claim is held the button renders disabled and any
stacked re-click is ignored, so rapid re-clicks cannot stack fetches.

These are pure functions over a session-state-like mapping — no Streamlit
import — so the guard logic is unit-testable without a Streamlit runtime.
"""

import time

BUSY_KEY = "refresh_headlines_busy"
LAST_CLAIM_KEY = "refresh_headlines_last_claim_ts"

# Minimum seconds between two accepted Refresh clicks. Eats accidental
# double-clicks and reruns queued while a fetch was still in flight. A fetch
# that just succeeded leaves fresh data behind, so ignoring the extra click
# is correct; a fetch that failed loudly resets the claim (see below) so an
# immediate retry is never swallowed.
CLAIM_COOLDOWN_S = 5.0


def is_refresh_busy(state) -> bool:
    """True while a refresh-triggered fetch is in flight."""
    return bool(state.get(BUSY_KEY, False))


def claim_refresh(state, now=None) -> bool:
    """Try to claim the Refresh action for this click.

    Returns True exactly once per accepted click and marks the refresh busy.
    Returns False when a refresh is already in flight or the previous claim
    is still inside the cooldown window — the caller must ignore the click
    (no second fetch, ever).
    """
    now = time.time() if now is None else now
    if is_refresh_busy(state):
        return False
    last_claim = state.get(LAST_CLAIM_KEY, 0.0) or 0.0
    if now - float(last_claim) < CLAIM_COOLDOWN_S:
        return False
    state[BUSY_KEY] = True
    state[LAST_CLAIM_KEY] = now
    return True


def release_refresh(state) -> None:
    """Mark the in-flight refresh finished. Always call from a finally block."""
    state[BUSY_KEY] = False


def reset_refresh_claim(state) -> None:
    """Allow an immediate retry after a loud fetch failure.

    The failure itself stays visible (warning/error banner); the cooldown
    must not swallow the user's retry click.
    """
    state[LAST_CLAIM_KEY] = 0.0
