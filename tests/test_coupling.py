"""Offline acceptance gate (Cowork): hidden capability MUST couple to the realized paid-rate of each
agent's judgment-certified book, or CGR can't rank agents. Enforced BEFORE any live re-run. This is
the check that a naive "run it bigger" would have wasted a live run on — the coupling is proven in the
ground-truth book first (same discipline as the earlier tracks)."""
from __future__ import annotations

import pytest

from meridian.driver import coupling_spearman


@pytest.mark.parametrize("seed", [42, 137, 7])
def test_capability_couples_to_certified_book_paidrate(seed):
    r = coupling_spearman(seed=seed, n_agents=20, n_invoices=4000)
    assert r["spearman"] >= 0.6, f"coupling gate FAILED (seed {seed}) — capability not reaching outcomes: {r}"
    assert r["paid_rate_sd"] >= 0.10, f"per-agent paid-rate spread too small (seed {seed}): {r}"
    assert r["agents_scored"] == 20 and r["resolved_per_agent_median"] >= 20
