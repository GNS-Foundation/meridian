"""Meridian synthetic underwriting agents.

Each agent has (a) a LOCAL Ed25519 identity — `agent_key` = pubkey hex, the CGR grouping subject
(no mint handshake with Grafomem; keys are supplied at decision time) — and (b) a HIDDEN capability
∈ (0,1) that governs how accurately it estimates an invoice's true pay-likelihood. High-capability
agents certify invoices that truly pay ⇒ their paid/default mix is favorable ⇒ CGR (computed by
Grafomem) climbs. That reproduces the "honest agents climb" ordering on the live runtime.

Determinism: keypairs and capability are derived from the episode seed (no unseeded RNG), so an
episode is fully reproducible — same seed ⇒ same agent_keys ⇒ same decisions.

Moat boundary: NO CGR/scoring logic here. The agent decides; Grafomem scores.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from meridian.entities import AgentPublic, Decision, InvoiceObservable


def _deterministic_ed25519(seed: int, index: int) -> tuple[ed25519.Ed25519PrivateKey, str]:
    """A reproducible Ed25519 keypair from (seed, index) — so the same episode mints the same
    agent identities. (B1 keys are free/local; B2 will model the cost of a *calibrated* identity.)"""
    priv_bytes = hashlib.blake2b(f"meridian.agent.v1:{seed}:{index}".encode(), digest_size=32).digest()
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
    pub_hex = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()
    return priv, pub_hex


@dataclass
class SyntheticAgent:
    index: int
    capability: float                                  # HIDDEN — never posted
    agent_key: str                                     # 64-hex Ed25519 pubkey (public)
    agent_handle: str
    _priv: ed25519.Ed25519PrivateKey
    model_id: str = "meridian-underwriter-v1"
    kind: str = "honest"                               # HIDDEN ground-truth label: honest | fraud_ring | bustout

    def to_public(self) -> AgentPublic:
        return AgentPublic(agent_key=self.agent_key, agent_handle=self.agent_handle, model_id=self.model_id)

    def decide(self, inv: InvoiceObservable, base_pp: float, rng: np.random.Generator, *,
               judgment_threshold: float, certify_threshold: float = 0.5) -> Decision:
        """Make an underwriting decision. Sub-threshold amounts are auto-approved by a deterministic
        RULE (verifiability_tag='rule', not CGR-scored). Larger amounts are JUDGMENT calls: the agent
        forms a capability-noised estimate of the invoice's intrinsic pay-likelihood (base_pp) and
        advances iff it clears the bar — the SELECTION channel (capable agents certify payers, reject
        defaulters). `context` carries only observable features — no ground truth, no PII."""
        context = {
            "amount": inv.amount, "currency": inv.currency, "tenor_days": inv.tenor_days,
            "sector": inv.sector, "risk_signal": inv.risk_signal, "client_id": inv.client_id,
        }
        if inv.amount < judgment_threshold:
            return Decision(
                agent_key=self.agent_key, agent_handle=self.agent_handle, model_id=self.model_id,
                invoice_id=inv.invoice_id, decision="certify", verifiability_tag="rule",
                reason=f"auto-approved: amount {inv.amount:.0f} < judgment threshold", context=context,
            )
        # judgment call — capability shrinks observation noise (weak agents ≈ blind → certify ~randomly)
        obs_noise = 0.05 + 0.75 * (1.0 - self.capability)
        estimate = float(np.clip(base_pp + rng.normal(0.0, obs_noise), 0.0, 1.0))
        advance = estimate >= certify_threshold
        return Decision(
            agent_key=self.agent_key, agent_handle=self.agent_handle, model_id=self.model_id,
            invoice_id=inv.invoice_id, decision="certify" if advance else "reject",
            verifiability_tag="judgment",
            reason=(f"advance ${inv.amount:,.0f} on invoice {inv.invoice_id} — "
                    f"assessed pay-likelihood {estimate:.2f}") if advance
                   else f"decline — assessed pay-likelihood {estimate:.2f} below bar",
            context=context,
        )


def mint_agents(seed: int, n_agents: int = 20, *, n_fraud: int = 0,
                bustout: int = 0) -> list[SyntheticAgent]:
    """Deterministically mint `n_agents` with a spread of hidden capability. The LAST `n_fraud`
    are the collusive ring and the `bustout` before those are bust-out actors (B2a). Fraud must be a
    minority; their identities/keys are indistinguishable from honest agents on the wire — the `kind`
    label is hidden ground truth, never posted."""
    assert n_fraud + bustout < n_agents, "fraud actors must be a minority"
    rng = np.random.default_rng(seed ^ 0xA6E17)
    agents: list[SyntheticAgent] = []
    for i in range(n_agents):
        capability = float(np.clip(rng.uniform(0.30, 0.92), 0.0, 1.0))
        priv, pub_hex = _deterministic_ed25519(seed, i)
        agents.append(SyntheticAgent(
            index=i, capability=capability, agent_key=pub_hex,
            agent_handle=f"underwriter-{i:02d}@virtualbank", _priv=priv,
        ))
    for a in agents[n_agents - n_fraud:]:                       # last n_fraud → the ring
        a.kind = "fraud_ring"
    for a in agents[n_agents - n_fraud - bustout:n_agents - n_fraud]:
        a.kind = "bustout"
    return agents
