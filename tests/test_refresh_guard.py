"""Refresh-button loading-state guard (#196). Pure session-state logic; no Streamlit."""
import unittest

from core.refresh_guard import (
    CLAIM_COOLDOWN_S,
    claim_refresh,
    is_refresh_busy,
    release_refresh,
    reset_refresh_claim,
)


class RefreshGuardTests(unittest.TestCase):
    def test_idle_by_default(self):
        self.assertFalse(is_refresh_busy({}))

    def test_claim_sets_busy_and_wins_once(self):
        state = {}
        self.assertTrue(claim_refresh(state, now=100.0))
        self.assertTrue(is_refresh_busy(state))
        # Stacked re-click while in flight is rejected: no second fetch, ever.
        self.assertFalse(claim_refresh(state, now=100.1))

    def test_release_clears_busy(self):
        state = {}
        claim_refresh(state, now=100.0)
        release_refresh(state)
        self.assertFalse(is_refresh_busy(state))

    def test_cooldown_rejects_immediate_reclaim(self):
        state = {}
        self.assertTrue(claim_refresh(state, now=100.0))
        release_refresh(state)
        # Fetch finished 0.2s after the claim — still inside the cooldown.
        self.assertFalse(claim_refresh(state, now=100.2))

    def test_claim_allowed_after_cooldown(self):
        state = {}
        self.assertTrue(claim_refresh(state, now=100.0))
        release_refresh(state)
        self.assertTrue(claim_refresh(state, now=100.0 + CLAIM_COOLDOWN_S))

    def test_reset_claim_allows_immediate_retry_after_loud_failure(self):
        state = {}
        self.assertTrue(claim_refresh(state, now=100.0))
        release_refresh(state)
        reset_refresh_claim(state)
        self.assertTrue(claim_refresh(state, now=100.2))

    def test_release_is_idempotent(self):
        state = {}
        release_refresh(state)  # never claimed: must not raise, stays idle
        self.assertFalse(is_refresh_busy(state))
        self.assertTrue(claim_refresh(state, now=50.0))

    def test_busy_blocks_claim_even_past_cooldown(self):
        state = {}
        self.assertTrue(claim_refresh(state, now=100.0))
        # Busy flag still set (e.g. crash between claim and finally): a new click
        # long after the cooldown must still be rejected while busy is set.
        self.assertFalse(claim_refresh(state, now=100.0 + CLAIM_COOLDOWN_S + 60))


if __name__ == "__main__":
    unittest.main()
