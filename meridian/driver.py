"""Meridian episode driver — runs a bounded simulated-time receivables episode end-to-end.

Flow: seeded market + agents → each agent underwrites its invoices → post decisions → resolve the
funded advances to paid/default (from the hidden truth) → post outcomes → read CGR reputation back →
emit an evidence pack.

Three DoD guarantees baked in:
  * DETERMINISM — everything derives from `--seed`; no unseeded RNG. Given (seed, episode) the posted
    content is identical.
  * IDEMPOTENCY — invoice ids are namespaced by a fresh `--episode` (default includes a short
    timestamp), so a re-run never double-posts the same id into the live tenant. Pass `--episode` to
    reproduce exact ids.
  * LIVE JOIN-VERIFY — reports "N judgment-certifies posted → M resolved" from the real CGR posterior
    (n_resolved), proving outcomes actually join to decisions (the RLS/HITL silent-no-op class), not
    just "records landed".

Safety: `--scorer local` (default) touches no network. `--scorer grafomem` posts to the live tenant
and requires ENV creds — run it only after the tenant is provisioned + attested.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from meridian.agents import mint_agents
from meridian.entities import Decision, Outcome
from meridian.generative import generate_market
from meridian.scorer import LocalScorer, Scorer

_SIM_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)      # deterministic sim clock (not wall-clock)
_JUDGMENT_THRESHOLD = 25_000.0                              # amounts below this auto-approve (rule)
# PERFORMANCE channel: a capable underwriter's certified book pays better on the SAME raw invoice
# (pricing/covenants/monitoring). p_eff = base_pp + KAPPA·(capability − 0.5). Combined with the
# SELECTION channel (agents.decide), this is what spreads per-agent paid-rates so CGR can rank them.
_KAPPA = 0.9


def _p_effective(base_pp: float, capability: float) -> float:
    return float(np.clip(base_pp + _KAPPA * (capability - 0.5), 0.02, 0.98))


@dataclass
class EvidencePack:
    episode: str
    seed: int
    n_agents: int
    decisions_posted: int = 0
    judgment_certifies: int = 0
    rule_certifies: int = 0
    rejects: int = 0
    outcomes_posted: int = 0
    paid: int = 0
    default: int = 0
    cgr_n_resolved: int = 0
    cgr_n_pending: int = 0
    reputation_ordering: list[dict] = field(default_factory=list)
    capability_score_spearman: float | None = None
    join_verify: str = ""
    notes: list[str] = field(default_factory=list)


def run_episode(scorer: Scorer, *, seed: int = 42, n_agents: int = 20, episode: str | None = None,
                n_clients: int = 40, n_invoices: int = 200, write_ground_truth: bool = True) -> EvidencePack:
    episode = episode or f"s{seed}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    rng = np.random.default_rng(seed)

    market = generate_market(seed, episode=episode, n_clients=n_clients, n_invoices=n_invoices)
    agents = mint_agents(seed, n_agents)
    cap_by_key = {a.agent_key: a.capability for a in agents}
    handle_by_key = {a.agent_key: a.agent_handle for a in agents}

    ev = EvidencePack(episode=episode, seed=seed, n_agents=n_agents)

    # ── assign each invoice to an agent (seeded) and underwrite ──
    outcomes_to_post: list[Outcome] = []
    truth_rows: list[dict] = []                                # realized answer key (local, git-ignored)
    for inv in market.invoices_public:
        agent = agents[int(rng.integers(0, n_agents))]
        base_pp = market.base_pp(inv.invoice_id)
        d: Decision = agent.decide(inv, base_pp, rng, judgment_threshold=_JUDGMENT_THRESHOLD)
        d.ts = _SIM_EPOCH.isoformat()                          # deterministic sim clock (not posted)
        scorer.post_decision(d)
        ev.decisions_posted += 1
        if d.decision == "reject":
            ev.rejects += 1
            truth_rows.append({"invoice_id": inv.invoice_id, "agent_handle": agent.agent_handle,
                               "capability": round(agent.capability, 4), "base_pp": round(base_pp, 4),
                               "decision": "reject", "tag": d.verifiability_tag, "outcome": None})
            continue
        ev.judgment_certifies += int(d.verifiability_tag == "judgment")
        ev.rule_certifies += int(d.verifiability_tag == "rule")
        # PERFORMANCE channel — the realized outcome is conditioned on the acting agent's capability
        p_eff = _p_effective(base_pp, agent.capability)
        result = "paid" if rng.random() < p_eff else "default"
        outcome_date = (_SIM_EPOCH + timedelta(days=inv.tenor_days)).isoformat()
        outcomes_to_post.append(Outcome(invoice_ref=inv.invoice_id, outcome=result,
                                        outcome_date=outcome_date,
                                        amount_recovered=(inv.amount if result == "paid" else 0.0)))
        truth_rows.append({"invoice_id": inv.invoice_id, "agent_handle": agent.agent_handle,
                           "capability": round(agent.capability, 4), "base_pp": round(base_pp, 4),
                           "p_effective": round(p_eff, 4), "decision": "certify",
                           "tag": d.verifiability_tag, "outcome": result})

    if write_ground_truth:                                     # realized answer key stays LOCAL
        import json as _json, os as _os
        _os.makedirs("ground_truth", exist_ok=True)
        with open(f"ground_truth/{episode}.ground_truth.json", "w") as _f:
            _json.dump({"seed": seed, "episode": episode, "kappa": _KAPPA, "rows": truth_rows}, _f, indent=2)

    for o in outcomes_to_post:
        scorer.post_outcome(o)
        ev.outcomes_posted += 1
        ev.paid += int(o.outcome == "paid")
        ev.default += int(o.outcome == "default")

    # ── read CGR reputation back (Grafomem computes; sim only reads) ──
    # Scope every metric to THIS episode's agents (cap_by_key) — the tenant may hold other episodes,
    # so summing over all agents would mismatch this episode's judgment_certifies.
    reps = [r for r in scorer.reputation() if r.agent_key in cap_by_key]
    if reps:
        ev.cgr_n_resolved = sum(r.n_resolved for r in reps)
        ev.cgr_n_pending = sum(r.n_pending for r in reps)
        rows, caps, scores = [], [], []
        for r in sorted(reps, key=lambda x: x.cgr_score, reverse=True):
            cap = cap_by_key[r.agent_key]
            rows.append({"agent_handle": r.agent_handle or handle_by_key.get(r.agent_key),
                         "cgr_score": round(r.cgr_score, 4), "n_resolved": r.n_resolved,
                         "n_pending": r.n_pending, "hidden_capability": round(cap, 3)})
            caps.append(cap); scores.append(r.cgr_score)
        ev.reputation_ordering = rows
        if len(caps) >= 3 and len(set(scores)) > 1:
            from scipy.stats import spearmanr
            rho = spearmanr(caps, scores).correlation
            ev.capability_score_spearman = None if rho is None or np.isnan(rho) else round(float(rho), 4)
        ev.join_verify = (f"{ev.judgment_certifies} judgment-certifies posted → {ev.cgr_n_resolved} "
                          f"resolved by CGR ({'OK' if ev.cgr_n_resolved >= ev.judgment_certifies else 'SHORTFALL — investigate'})")
    else:
        ev.notes.append("local scorer: no CGR computed (sandbox) — join-verify runs only against grafomem")
        ev.join_verify = f"{ev.judgment_certifies} judgment-certifies posted (local sandbox; no CGR)"
    return ev


def coupling_spearman(*, seed: int = 42, n_agents: int = 20, n_invoices: int = 4000,
                      n_clients: int = 60) -> dict:
    """OFFLINE acceptance gate (Cowork): with NO posting, does hidden capability correlate with the
    realized paid-rate of each agent's judgment-certified book? Returns the Spearman + sample stats.
    Uses the exact decide→realize path (same rng order as run_episode), at a large sample so the
    per-agent paid-rate is well-estimated ('full sample'). Gate: rho ≥ ~0.6 before any live re-run."""
    from scipy.stats import spearmanr
    market = generate_market(seed, episode="coupling", n_clients=n_clients, n_invoices=n_invoices)
    agents = mint_agents(seed, n_agents)
    rng = np.random.default_rng(seed)
    paid: dict[int, int] = {}
    tot: dict[int, int] = {}
    for inv in market.invoices_public:
        agent = agents[int(rng.integers(0, n_agents))]
        base_pp = market.base_pp(inv.invoice_id)
        d = agent.decide(inv, base_pp, rng, judgment_threshold=_JUDGMENT_THRESHOLD)
        if d.decision == "certify" and d.verifiability_tag == "judgment":
            res = "paid" if rng.random() < _p_effective(base_pp, agent.capability) else "default"
            tot[agent.index] = tot.get(agent.index, 0) + 1
            paid[agent.index] = paid.get(agent.index, 0) + int(res == "paid")
    caps, rates, ns = [], [], []
    for a in agents:
        n = tot.get(a.index, 0)
        if n > 0:
            caps.append(a.capability); rates.append(paid[a.index] / n); ns.append(n)
    rho = (spearmanr(caps, rates).correlation if len(caps) >= 3 and len(set(rates)) > 1 else float("nan"))
    return {"spearman": round(float(rho), 4), "agents_scored": len(caps),
            "resolved_per_agent_median": int(np.median(ns)) if ns else 0,
            "paid_rate_sd": round(float(np.std(rates)), 4) if rates else 0.0,
            "paid_rate_min": round(min(rates), 3) if rates else None,
            "paid_rate_max": round(max(rates), 3) if rates else None}


def _make_scorer(kind: str) -> Scorer:
    if kind == "local":
        return LocalScorer()
    if kind == "grafomem":
        from meridian.grafomem_adapter import GrafomemScorer
        return GrafomemScorer.from_env()
    raise SystemExit(f"unknown scorer: {kind!r} (use 'local' or 'grafomem')")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--agents", type=int, default=20)
    ap.add_argument("--clients", type=int, default=40)
    ap.add_argument("--invoices", type=int, default=200)
    ap.add_argument("--episode", default=None, help="namespace for invoice ids (default: fresh, idempotent)")
    ap.add_argument("--scorer", choices=["local", "grafomem"], default="local",
                    help="'local' = offline sandbox (no network); 'grafomem' = live tenant (needs ENV, post-attest)")
    ap.add_argument("--check-coupling", action="store_true",
                    help="offline acceptance gate only: print Spearman(capability, certified-book paid-rate); no posting")
    args = ap.parse_args(argv)

    if args.check_coupling:
        print(json.dumps(coupling_spearman(seed=args.seed, n_agents=args.agents), indent=2))
        return

    scorer = _make_scorer(args.scorer)
    try:
        ev = run_episode(scorer, seed=args.seed, n_agents=args.agents, episode=args.episode,
                         n_clients=args.clients, n_invoices=args.invoices)
    finally:
        close = getattr(scorer, "close", None)
        if callable(close):
            close()
    print(json.dumps(asdict(ev), indent=2))


if __name__ == "__main__":
    main()
