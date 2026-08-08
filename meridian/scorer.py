"""The moat boundary — the `Scorer` protocol.

The sim emits standard `Decision`/`Outcome` records and hands them to a `Scorer`. Grafomem's real
implementation (`grafomem_adapter.GrafomemScorer`) posts them to the public API and reads CGR back.
`LocalScorer` is an in-memory sandbox that records nothing to a network and computes NO reputation —
its existence proves the boundary: swap the scorer and Meridian is a clean, publishable sandbox with
zero CGR/vault/field code.

NOTHING in this module (or anywhere in the `meridian` package) computes a reputation score. A
`ReputationView` is a passive holder for whatever an external scorer *reports back*.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from meridian.entities import Decision, Outcome


@dataclass(frozen=True)
class DecisionReceipt:
    """What a scorer returns after accepting a decision — the join ref to reconcile against outcomes.
    `invoice_ref` is whatever the scorer keys outcomes by (Grafomem returns the pseudonymized ref;
    the raw id is what we POST on both sides)."""
    raw_invoice_id: str
    decision_id: str | None
    invoice_ref: str | None
    accepted: bool


@dataclass(frozen=True)
class ReputationView:
    """A snapshot of an agent's reputation AS REPORTED BY the scorer (e.g. Grafomem CGR). Passive."""
    agent_key: str
    agent_handle: str | None
    cgr_score: float
    confidence: float
    n_resolved: int
    n_pending: int


@runtime_checkable
class Scorer(Protocol):
    def post_decision(self, decision: Decision) -> DecisionReceipt: ...
    def post_outcome(self, outcome: Outcome) -> None: ...
    def reputation(self) -> list[ReputationView]:
        """Read reputation back. Empty when the scorer computes none (the sandbox)."""
        ...


@dataclass
class LocalScorer:
    """In-memory sandbox scorer — no network, no CGR. Records what it's given so the driver + tests
    can run the full loop offline. `reputation()` is intentionally empty: reputation lives in the
    external scorer, not the sim."""
    decisions: list[Decision] = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)

    def post_decision(self, decision: Decision) -> DecisionReceipt:
        self.decisions.append(decision)
        return DecisionReceipt(raw_invoice_id=decision.invoice_id, decision_id=None,
                               invoice_ref=decision.invoice_id, accepted=True)

    def post_outcome(self, outcome: Outcome) -> None:
        self.outcomes.append(outcome)

    def reputation(self) -> list[ReputationView]:
        return []
