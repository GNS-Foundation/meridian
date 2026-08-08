"""The moat boundary — the `meridian` package must contain NO CGR / vault / field-engine code, and
the sim must run end-to-end against a swapped-out scorer (the publishable-sandbox guarantee)."""
from __future__ import annotations

import pathlib

from meridian.driver import run_episode
from meridian.scorer import LocalScorer, ReputationView, Scorer

_PKG = pathlib.Path(__file__).resolve().parents[1] / "meridian"
# Genuine IMPLEMENTATION identifiers of CGR scoring / the vault / the field engine — these would only
# appear if scoring/substrate code were copied in. (The sim may NAME the boundary in prose — "CGR",
# "reputation", "the posterior" in docstrings is fine; that's not an implementation.)
_FORBIDDEN_IMPL = ["compute_scores", "compute_scores_from_rows", "score_agent(", "beta_prior(",
                   "reviewer_weights(", "def _embed_decision", "decision_embeddings", "memory_embeddings",
                   "TenantKeyManager", "MultiFernet", "generate_manifold", "train_som", "def to_tiergate"]


def test_no_cgr_or_vault_or_field_implementation_in_package():
    offenders = []
    for p in _PKG.rglob("*.py"):
        text = p.read_text()
        for tok in _FORBIDDEN_IMPL:
            if tok in text:
                offenders.append(f"{p.name}: {tok!r}")
    assert not offenders, f"moat boundary violated — CGR/vault/field IMPLEMENTATION in the sim: {offenders}"


def test_package_never_imports_grafomem_internals():
    """The sim talks to Grafomem ONLY over HTTP — it must not import any grafomem/aml/cgr module."""
    import re
    bad = re.compile(r"^\s*(?:from|import)\s+(?:aml|grafomem|cgr)\b", re.M)
    offenders = [p.name for p in _PKG.rglob("*.py") if bad.search(p.read_text())]
    assert not offenders, f"sim imports Grafomem internals (must be HTTP-only): {offenders}"


def test_local_scorer_computes_no_reputation():
    s = LocalScorer()
    run_episode(s, seed=5, n_agents=8, episode="b", n_clients=15, n_invoices=60, write_ground_truth=False)
    assert s.reputation() == [], "the sandbox scorer must compute no reputation (it lives in Grafomem)"
    assert len(s.decisions) == 60 and len(s.outcomes) >= 1


def test_both_scorers_satisfy_the_protocol():
    assert isinstance(LocalScorer(), Scorer)
    from meridian.grafomem_adapter import GrafomemScorer
    # construct without env (direct args) to check protocol conformance without a network call
    g = GrafomemScorer("https://example.invalid", "k")
    try:
        assert isinstance(g, Scorer)
    finally:
        g.close()


def test_reputation_view_is_passive_holder():
    rv = ReputationView(agent_key="k", agent_handle="h", cgr_score=0.7, confidence=3.0, n_resolved=2, n_pending=1)
    assert rv.cgr_score == 0.7  # just a dataclass; no logic
