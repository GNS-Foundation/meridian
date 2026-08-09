"""B2a offline acceptance gate (Cowork): on the ground-truth book the collusive ring must be
INVISIBLE to a naive raw paid-fraction (|gap| < 0.10) yet clearly flagged by the judgment-only rate
that CGR scores (gap < −0.30). Prove the contrast before spending a live run — the B1 discipline."""
from __future__ import annotations

import pytest

from meridian.driver import fraud_contrast


@pytest.mark.parametrize("seed", [200, 300, 137, 42, 7])
def test_naive_blind_but_judgment_flags(seed):
    r = fraud_contrast(seed=seed, n_agents=20, n_fraud=3)
    assert r["naive_blind"], f"naive scorer is NOT blind to the ring (seed {seed}): {r}"
    assert r["cgr_flags"], f"judgment-only rate did NOT flag the ring (seed {seed}): {r}"
    assert abs(r["naive_gap"]) < 0.10 and r["judgment_gap"] < -0.30, r


def test_ring_judgment_book_is_rotten():
    r = fraud_contrast(seed=300, n_agents=20, n_fraud=3)
    assert r["judgment_fraud"] <= 0.05, f"fabricated judgment book should ~all default: {r}"
    assert r["judgment_honest"] >= 0.40, f"honest judgment book should be healthy: {r}"


def test_bustout_also_flagged_by_judgment():
    r = fraud_contrast(seed=300, n_agents=20, n_fraud=2, bustout=1)
    assert r["cgr_flags"] and r["naive_blind"], r
