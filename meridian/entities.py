"""Meridian entities — Pydantic v2 models, PII-FREE by construction.

Two disjoint layers, deliberately separated so the moat boundary is obvious:

  * PUBLIC records (Decision, Outcome, InvoiceObservable, ClientPublic, AgentPublic) — the only
    things that ever leave the sim. They carry synthetic ids + numeric/categorical features and
    Faker-generated *company/sector* flavor only. No personal names, emails, addresses, or government
    ids — Faker is used solely for firmographic labels (company + country), never any personal-identity
    generator. (tests/test_pii_free.py fails if the sim calls a Faker PII method.)

  * GROUND TRUTH (see generative.py) — the hidden answer key (true capability / pay-probability /
    outcome). It NEVER appears in these public records and is never posted.
"""
from __future__ import annotations

from typing import Literal

from faker import Faker
from pydantic import BaseModel, Field

# One domain in SIM-B1: invoice / receivables financing.
Sector = Literal["logistics", "manufacturing", "wholesale", "agritech", "energy", "construction"]
Currency = Literal["USD", "EUR", "GBP"]
DecisionValue = Literal["certify", "reject"]           # certify = advance, reject = decline
VerifiabilityTag = Literal["judgment", "rule"]         # only judgment+certify is CGR-scored
OutcomeValue = Literal["paid", "default", "disputed", "late", "written_off"]


class AgentPublic(BaseModel):
    """A synthetic underwriting agent's PUBLIC identity. `agent_key` is its local Ed25519 pubkey
    (hex) — the CGR grouping subject. No hidden capability here (that's ground truth)."""
    agent_key: str                                     # 64-hex Ed25519 pubkey
    agent_handle: str                                  # facet@virtualbank, e.g. underwriter-03@virtualbank
    model_id: str = "meridian-underwriter-v1"


class ClientPublic(BaseModel):
    """A counterparty as the bank sees it publicly — synthetic id + firmographics only."""
    client_id: str                                     # CLIENT-<hex>
    name: str                                          # Faker company (firmographic flavor, not a person)
    sector: Sector
    country: str                                        # ISO-ish 2-letter, firmographic


class InvoiceObservable(BaseModel):
    """The invoice as an underwriting agent OBSERVES it — features only, no hidden truth.
    `invoice_id` is stable + unique (one invoice = one decision); it is the CGR join key
    (the server pseudonymizes it identically on the decision and the outcome)."""
    invoice_id: str                                    # INV-<episode>-<hex>, unique per episode
    client_id: str
    amount: float
    currency: Currency
    tenor_days: int                                    # net terms; the outcome resolves after this
    sector: Sector
    # a NOISY public risk signal (0=risky .. 1=safe); agents see this, not the true outcome
    risk_signal: float = Field(ge=0.0, le=1.0)


class Decision(BaseModel):
    """A standard governed-decision record the sim emits. Maps 1:1 to Grafomem's
    GovernedDecisionRequest via the adapter. PII-free."""
    agent_key: str
    agent_handle: str
    model_id: str
    invoice_id: str                                    # raw id → server pseudonymizes → invoice_ref
    decision: DecisionValue
    verifiability_tag: VerifiabilityTag
    reason: str = ""
    context: dict = Field(default_factory=dict)        # observable invoice features (no truth, no PII)
    ts: str = ""                                       # sim clock, set deterministically by the driver (not posted)


class Outcome(BaseModel):
    """A standard outcome record. `invoice_ref` carries the SAME raw invoice_id as the decision —
    the server pseudonymizes both sides so they join. Only paid/default move the CGR posterior."""
    invoice_ref: str                                   # == the decision's raw invoice_id
    outcome: OutcomeValue
    outcome_date: str | None = None
    amount_recovered: float | None = None
    source: str = "meridian-sim"


def new_faker(seed: int) -> Faker:
    """A seeded Faker for reproducible firmographic labels (company/country only — never PII)."""
    fk = Faker()
    Faker.seed(seed)
    return fk
