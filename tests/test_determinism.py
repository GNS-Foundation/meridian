"""Determinism (DoD #2) — a seeded episode is fully reproducible: same (seed, episode) ⇒ identical
posted decisions + outcomes. No unseeded RNG anywhere on the content path."""
from __future__ import annotations

from meridian.driver import run_episode
from meridian.scorer import LocalScorer


def _run():
    s = LocalScorer()
    run_episode(s, seed=7, n_agents=12, episode="t-fixed", n_clients=20, n_invoices=80,
                write_ground_truth=False)
    return s


def test_same_seed_episode_is_reproducible():
    a, b = _run(), _run()
    da = [d.model_dump() for d in a.decisions]
    db = [d.model_dump() for d in b.decisions]
    assert da == db and len(da) == 80, "decisions must be identical across runs of the same (seed, episode)"
    oa = [o.model_dump() for o in a.outcomes]
    ob = [o.model_dump() for o in b.outcomes]
    assert oa == ob, "outcomes must be identical across runs"
    # agent identities are deterministic too
    from meridian.agents import mint_agents
    assert [x.agent_key for x in mint_agents(7, 12)] == [x.agent_key for x in mint_agents(7, 12)]


def test_different_seed_changes_content():
    s1 = LocalScorer(); run_episode(s1, seed=1, n_agents=12, episode="t", n_clients=20, n_invoices=80, write_ground_truth=False)
    s2 = LocalScorer(); run_episode(s2, seed=2, n_agents=12, episode="t", n_clients=20, n_invoices=80, write_ground_truth=False)
    assert [d.model_dump() for d in s1.decisions] != [d.model_dump() for d in s2.decisions]
