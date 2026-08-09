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
    n_fraud: int = 0
    n_bustout: int = 0
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
    # B2a fraud contrast
    naive_honest_mean: float | None = None
    naive_fraud_mean: float | None = None
    naive_gap: float | None = None
    cgr_honest_mean: float | None = None
    cgr_fraud_mean: float | None = None
    cgr_gap: float | None = None
    fraud_at_bottom: bool | None = None
    fraud_handles: list[str] = field(default_factory=list)
    export_path: str | None = None
    notes: list[str] = field(default_factory=list)


def _episode_events(market, agents, rng, *, episode: str, rule_pad_rate: float | None,
                    fraud_decisions_per_agent: int) -> list[tuple]:
    """Deterministic full-episode event list: (agent, Decision, outcome|None). Honest agents underwrite
    the market pool; fraud/bustout agents emit their own streams. Shared by the live run AND the
    offline gate, so the gate predicts the live episode exactly (same decisions, same outcomes).

    `rule_pad_rate=None` ⇒ the ring CALIBRATES its healthy rule-pad fraction to the observed honest
    population's raw paid-rate — so the fraud is blind to a naive scorer BY CONSTRUCTION on any seed
    (a real ring pads to match the population it hides in), while its judgment book stays rotten."""
    from meridian.fraud import fraud_stream
    events: list[tuple] = []
    honest = [a for a in agents if a.kind == "honest"]
    for inv in market.invoices_public:
        a = honest[int(rng.integers(0, len(honest)))]
        base_pp = market.base_pp(inv.invoice_id)
        d = a.decide(inv, base_pp, rng, judgment_threshold=_JUDGMENT_THRESHOLD)
        if d.decision == "reject":
            events.append((a, d, None))
        else:
            result = "paid" if rng.random() < _p_effective(base_pp, a.capability) else "default"
            events.append((a, d, result))
    if rule_pad_rate is None:                                   # calibrate the ring to blend in
        hp = sum(1 for _, _, r in events if r == "paid")
        ht = sum(1 for _, _, r in events if r is not None)
        rule_pad_rate = float(np.clip(hp / ht, 0.30, 0.90)) if ht else 0.57
    for a in agents:
        if a.kind == "honest":
            continue
        for d, result in fraud_stream(a, fraud_decisions_per_agent, rng, episode=episode,
                                      judgment_threshold=_JUDGMENT_THRESHOLD, rule_pad_rate=rule_pad_rate):
            events.append((a, d, result))
    return events


def _tallies(events) -> dict:
    """Per-agent {paid,total, jpaid,jtotal} over RESOLVED decisions. naive = paid/total (all tags);
    judgment-rate = jpaid/jtotal (the ground-truth quantity CGR recovers)."""
    from collections import defaultdict
    t: dict = defaultdict(lambda: {"paid": 0, "total": 0, "jpaid": 0, "jtotal": 0})
    for a, d, result in events:
        if result is None:
            continue
        r = t[a.agent_key]; r["total"] += 1; r["paid"] += int(result == "paid")
        if d.verifiability_tag == "judgment":
            r["jtotal"] += 1; r["jpaid"] += int(result == "paid")
    return t


def fraud_contrast(*, seed: int = 200, n_agents: int = 20, n_fraud: int = 3, bustout: int = 0,
                   n_invoices: int = 1200, n_clients: int = 60, rule_pad_rate: float | None = None,
                   fraud_decisions_per_agent: int = 60) -> dict:
    """OFFLINE acceptance gate (Cowork B2a): on the ground-truth book, a NAIVE raw paid-fraction must
    be ~blind to fraud (|gap| < 0.10) while the JUDGMENT-only rate (what CGR scores) clearly flags it
    (gap < −0.30). Uses no CGR code — just the realized paid-rates the sim knows. Prove the contrast
    before spending a live run."""
    market = generate_market(seed, episode="fraudgate", n_clients=n_clients, n_invoices=n_invoices)
    agents = mint_agents(seed, n_agents, n_fraud=n_fraud, bustout=bustout)
    rng = np.random.default_rng(seed)
    events = _episode_events(market, agents, rng, episode="fraudgate",
                             rule_pad_rate=rule_pad_rate, fraud_decisions_per_agent=fraud_decisions_per_agent)
    t = _tallies(events)
    kind = {a.agent_key: a.kind for a in agents}

    def _mean(metric, is_fraud):
        vals = []
        for k, r in t.items():
            if r["total"] == 0:
                continue
            if (kind[k] != "honest") != is_fraud:
                continue
            vals.append((r["jpaid"] / r["jtotal"]) if metric == "j" and r["jtotal"] else
                        (r["paid"] / r["total"]) if metric == "naive" else None)
        vals = [v for v in vals if v is not None]
        return float(np.mean(vals)) if vals else float("nan")

    nh, nf = _mean("naive", False), _mean("naive", True)
    jh, jf = _mean("j", False), _mean("j", True)
    return {"naive_honest": round(nh, 4), "naive_fraud": round(nf, 4), "naive_gap": round(nf - nh, 4),
            "judgment_honest": round(jh, 4), "judgment_fraud": round(jf, 4), "judgment_gap": round(jf - jh, 4),
            "naive_blind": abs(nf - nh) < 0.10, "cgr_flags": (jf - jh) < -0.30}


def run_episode(scorer: Scorer, *, seed: int = 200, n_agents: int = 20, episode: str | None = None,
                n_clients: int = 60, n_invoices: int = 1200, n_fraud: int = 0, bustout: int = 0,
                rule_pad_rate: float | None = None, fraud_decisions_per_agent: int = 60,
                write_ground_truth: bool = True) -> EvidencePack:
    import json as _json, os as _os
    episode = episode or f"s{seed}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    rng = np.random.default_rng(seed)

    market = generate_market(seed, episode=episode, n_clients=n_clients, n_invoices=n_invoices)
    agents = mint_agents(seed, n_agents, n_fraud=n_fraud, bustout=bustout)
    cap_by_key = {a.agent_key: a.capability for a in agents}
    handle_by_key = {a.agent_key: a.agent_handle for a in agents}
    kind_by_key = {a.agent_key: a.kind for a in agents}

    ev = EvidencePack(episode=episode, seed=seed, n_agents=n_agents, n_fraud=n_fraud, n_bustout=bustout)
    ev.fraud_handles = [a.agent_handle for a in agents if a.kind != "honest"]

    events = _episode_events(market, agents, rng, episode=episode,
                             rule_pad_rate=rule_pad_rate, fraud_decisions_per_agent=fraud_decisions_per_agent)
    from collections import defaultdict
    timeline: dict = defaultdict(list)
    outcomes_to_post: list[Outcome] = []
    for a, d, result in events:
        d.ts = _SIM_EPOCH.isoformat()
        scorer.post_decision(d)
        ev.decisions_posted += 1
        timeline[a.agent_key].append({"invoice_id": d.invoice_id, "tag": d.verifiability_tag,
                                      "decision": d.decision, "outcome": result})
        if d.decision == "reject":
            ev.rejects += 1
            continue
        ev.judgment_certifies += int(d.verifiability_tag == "judgment")
        ev.rule_certifies += int(d.verifiability_tag == "rule")
        outcomes_to_post.append(Outcome(invoice_ref=d.invoice_id, outcome=result,
                                        outcome_date=(_SIM_EPOCH + timedelta(days=45)).isoformat(),
                                        amount_recovered=(d.context.get("amount", 0.0) if result == "paid" else 0.0)))

    for o in outcomes_to_post:
        scorer.post_outcome(o)
        ev.outcomes_posted += 1
        ev.paid += int(o.outcome == "paid")
        ev.default += int(o.outcome == "default")

    t = _tallies(events)
    naive_by_key = {k: (r["paid"] / r["total"]) for k, r in t.items() if r["total"] > 0}

    # ── read CGR back (full scan, episode-scoped) ──
    reps = [r for r in scorer.reputation() if r.agent_key in cap_by_key]
    if reps:
        ev.cgr_n_resolved = sum(r.n_resolved for r in reps)
        ev.cgr_n_pending = sum(r.n_pending for r in reps)
        rows, caps, scores = [], [], []
        for r in sorted(reps, key=lambda x: x.cgr_score, reverse=True):
            rows.append({"agent_handle": r.agent_handle or handle_by_key.get(r.agent_key),
                         "kind": kind_by_key[r.agent_key], "cgr_score": round(r.cgr_score, 4),
                         "naive_score": round(naive_by_key.get(r.agent_key, float("nan")), 4),
                         "n_resolved": r.n_resolved, "hidden_capability": round(cap_by_key[r.agent_key], 3)})
            caps.append(cap_by_key[r.agent_key]); scores.append(r.cgr_score)
        ev.reputation_ordering = rows
        if len(caps) >= 3 and len(set(scores)) > 1:
            from scipy.stats import spearmanr
            rho = spearmanr(caps, scores).correlation
            ev.capability_score_spearman = None if rho is None or np.isnan(rho) else round(float(rho), 4)
        ev.join_verify = (f"{ev.judgment_certifies} judgment-certifies posted → {ev.cgr_n_resolved} "
                          f"resolved ({'OK' if ev.cgr_n_resolved >= ev.judgment_certifies else 'SHORTFALL'})")
        # fraud contrast (naive-vs-CGR on the SAME live agents)
        cgr_by_key = {r.agent_key: r.cgr_score for r in reps}
        fkeys = [k for k in cgr_by_key if kind_by_key[k] != "honest"]
        hkeys = [k for k in cgr_by_key if kind_by_key[k] == "honest"]
        if fkeys and hkeys:
            ev.naive_honest_mean = round(float(np.mean([naive_by_key[k] for k in hkeys if k in naive_by_key])), 4)
            ev.naive_fraud_mean = round(float(np.mean([naive_by_key[k] for k in fkeys if k in naive_by_key])), 4)
            ev.naive_gap = round(ev.naive_fraud_mean - ev.naive_honest_mean, 4)
            ev.cgr_honest_mean = round(float(np.mean([cgr_by_key[k] for k in hkeys])), 4)
            ev.cgr_fraud_mean = round(float(np.mean([cgr_by_key[k] for k in fkeys])), 4)
            ev.cgr_gap = round(ev.cgr_fraud_mean - ev.cgr_honest_mean, 4)
            n_bad = len(fkeys)
            bottom = [r.agent_key for r in sorted(reps, key=lambda x: x.cgr_score)[:n_bad]]
            ev.fraud_at_bottom = all(kind_by_key[k] != "honest" for k in bottom)
    else:
        ev.join_verify = f"{ev.judgment_certifies} judgment-certifies posted (local sandbox; no CGR)"
        ev.notes.append("local scorer: no CGR — contrast runs only against grafomem")

    if write_ground_truth:                                     # WOW data export + answer key (local, git-ignored)
        _os.makedirs("episodes", exist_ok=True)
        export = {"episode": episode, "seed": seed, "kappa": _KAPPA, "rule_pad_rate": rule_pad_rate,
                  "contrast": {"naive_gap": ev.naive_gap, "cgr_gap": ev.cgr_gap,
                               "fraud_at_bottom": ev.fraud_at_bottom},
                  "agents": [{"agent_handle": handle_by_key[k], "agent_key": k, "kind": kind_by_key[k],
                              "capability": round(cap_by_key[k], 4),
                              "naive_score": round(naive_by_key.get(k, float("nan")), 4),
                              "cgr_score": next((row["cgr_score"] for row in ev.reputation_ordering
                                                 if row["agent_handle"] == handle_by_key[k]), None),
                              "timeline": timeline.get(k, [])} for k in cap_by_key]}
        ev.export_path = f"episodes/{episode}.export.json"
        with open(ev.export_path, "w") as _f:
            _json.dump(export, _f, indent=2)
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
    ap.add_argument("--seed", type=int, default=200)
    ap.add_argument("--agents", type=int, default=20)
    ap.add_argument("--clients", type=int, default=60)
    ap.add_argument("--invoices", type=int, default=1200)
    ap.add_argument("--n-fraud", type=int, default=0, help="collusive-ring agents (B2a); minority")
    ap.add_argument("--bustout", type=int, default=0, help="bust-out agents (B2a)")
    ap.add_argument("--rule-pad-rate", type=float, default=None, help="fraud ring's healthy rule-paid fraction")
    ap.add_argument("--fraud-decisions", type=int, default=60, help="decisions per fraud agent")
    ap.add_argument("--episode", default=None, help="namespace for invoice ids (default: fresh, idempotent)")
    ap.add_argument("--scorer", choices=["local", "grafomem"], default="local",
                    help="'local' = offline sandbox (no network); 'grafomem' = live tenant (needs ENV, post-attest)")
    ap.add_argument("--check-coupling", action="store_true",
                    help="offline gate: Spearman(capability, certified-book paid-rate); no posting")
    ap.add_argument("--check-fraud", action="store_true",
                    help="offline gate: naive-blind vs judgment-only-flags contrast (B2a); no posting")
    args = ap.parse_args(argv)

    if args.check_coupling:
        print(json.dumps(coupling_spearman(seed=args.seed, n_agents=args.agents), indent=2))
        return
    if args.check_fraud:
        print(json.dumps(fraud_contrast(seed=args.seed, n_agents=args.agents, n_fraud=args.n_fraud,
                                        bustout=args.bustout, n_invoices=args.invoices, n_clients=args.clients,
                                        rule_pad_rate=args.rule_pad_rate,
                                        fraud_decisions_per_agent=args.fraud_decisions), indent=2))
        return

    scorer = _make_scorer(args.scorer)
    try:
        ev = run_episode(scorer, seed=args.seed, n_agents=args.agents, episode=args.episode,
                         n_clients=args.clients, n_invoices=args.invoices, n_fraud=args.n_fraud,
                         bustout=args.bustout, rule_pad_rate=args.rule_pad_rate,
                         fraud_decisions_per_agent=args.fraud_decisions)
    finally:
        close = getattr(scorer, "close", None)
        if callable(close):
            close()
    print(json.dumps(asdict(ev), indent=2))


if __name__ == "__main__":
    main()
