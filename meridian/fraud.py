"""B2a fraud injection — competence-fraud vectors, all caught by JUDGMENT-ONLY CGR.

The whole point: a fraud agent's *raw* book looks healthy (a naive paid-fraction can't distinguish
it), but its *judgment-tagged* book is rotten — and CGR scores only judgment+certify, so it collapses
the fraud agent while the naive scorer stays blind.

Vectors (fabricated invoices have no real underlying; certifying them yields judgment-tagged defaults):
  * fraud_ring — pads ~`rule_pad_rate` easy RULE-tagged PAIDS (healthy to naive) + the rest
    JUDGMENT-tagged fabricated DEFAULTS (tank judgment-only CGR). The Phase-A pattern.
  * bustout — real early JUDGMENT paids (build standing), then a coordinated JUDGMENT default cluster.

Fraud is invisible on the wire: the posted Decision/Outcome look normal; only the hidden `kind`
(ground truth, never posted) marks them. This module emits (Decision, realized_outcome) pairs; the
driver posts them and records the answer key.
"""
from __future__ import annotations

import numpy as np

from meridian.agents import SyntheticAgent
from meridian.entities import Currency, Decision, Sector

_SECTORS: list[Sector] = ["logistics", "manufacturing", "wholesale", "agritech", "energy", "construction"]
_CCY: list[Currency] = ["USD", "EUR", "GBP"]


def _fabricated_context(rng, *, amount: float, risk_signal: float, idx: int) -> dict:
    return {"amount": round(amount, 2), "currency": str(rng.choice(_CCY)),
            "tenor_days": int(rng.choice([30, 45, 60, 90])), "sector": str(rng.choice(_SECTORS)),
            "risk_signal": round(risk_signal, 4), "client_id": f"CLIENT-FAB-{idx:04d}"}


def _decision(agent: SyntheticAgent, invoice_id: str, tag: str, reason: str, ctx: dict) -> Decision:
    return Decision(agent_key=agent.agent_key, agent_handle=agent.agent_handle, model_id=agent.model_id,
                    invoice_id=invoice_id, decision="certify", verifiability_tag=tag, reason=reason, context=ctx)


def fraud_stream(agent: SyntheticAgent, n: int, rng: np.random.Generator, *, episode: str,
                 judgment_threshold: float, rule_pad_rate: float) -> list[tuple[Decision, str]]:
    """Return `n` (Decision, realized_outcome) pairs for a fraud agent. Deterministic given `rng`."""
    out: list[tuple[Decision, str]] = []
    if agent.kind == "bustout":
        n_good = int(round(n * 0.6))                           # build real standing, then default-cluster
        for k in range(n):
            iid = f"INV-{episode}-B{agent.index:02d}-{k:05d}"
            amt = float(rng.uniform(judgment_threshold * 1.2, 150_000))
            good = k < n_good
            ctx = _fabricated_context(rng, amount=amt, risk_signal=rng.uniform(0.55, 0.85), idx=agent.index * 1000 + k)
            d = _decision(agent, iid, "judgment",
                          "advance (established relationship)" if good else "advance (final tranche)", ctx)
            out.append((d, "paid" if good else "default"))
        return out

    # fraud_ring: healthy rule-pads + fabricated judgment-defaults
    n_rule = int(round(n * rule_pad_rate))
    for k in range(n):
        iid = f"INV-{episode}-F{agent.index:02d}-{k:05d}"
        if k < n_rule:                                          # RULE pad → PAID (looks healthy to naive)
            amt = float(rng.uniform(2_000, judgment_threshold * 0.9))
            ctx = _fabricated_context(rng, amount=amt, risk_signal=rng.uniform(0.75, 0.97), idx=agent.index * 1000 + k)
            out.append((_decision(agent, iid, "rule", "auto-approved: small, low-risk", ctx), "paid"))
        else:                                                  # JUDGMENT fabricated → DEFAULT (tanks CGR)
            amt = float(rng.uniform(judgment_threshold * 1.2, 150_000))
            ctx = _fabricated_context(rng, amount=amt, risk_signal=rng.uniform(0.55, 0.80), idx=agent.index * 1000 + k)
            out.append((_decision(agent, iid, "judgment", "advance on receivable", ctx), "default"))
    return out
