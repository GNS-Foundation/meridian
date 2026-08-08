"""Meridian ground-truth generative model — B1, one domain (invoice / receivables financing).

Seeded (NumPy) ⇒ fully reproducible. Produces:
  * PUBLIC entities (ClientPublic, InvoiceObservable) — safe to post;
  * HIDDEN ground truth (client pay-probability, per-invoice true_pay_prob + true_outcome) — the
    answer key, written to ground_truth/ (git-ignored) and NEVER posted. CGR accuracy is measured
    offline against it, blind.

Agent *capability* is minted in agents.py; here we only build the market and its truth. An agent's
skill shows up as how accurately it can estimate `true_pay_prob` (agents.py adds capability-scaled
observation noise) — so a high-capability agent certifies invoices that truly pay, and CGR (computed
by Grafomem, not here) rewards it.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from meridian.entities import ClientPublic, InvoiceObservable, new_faker

_SECTORS = ["logistics", "manufacturing", "wholesale", "agritech", "energy", "construction"]
_CURRENCIES = ["USD", "EUR", "GBP"]
_COUNTRIES = ["US", "DE", "GB", "NL", "FR", "ES", "IT", "PL"]


@dataclass(frozen=True)
class ClientTruth:
    client_id: str
    pay_prob: float                    # hidden base creditworthiness ∈ (0,1)


@dataclass(frozen=True)
class InvoiceTruth:
    invoice_id: str
    base_pp: float                     # hidden INTRINSIC pay-likelihood (client × difficulty).
    difficulty: float                  # hidden ∈ [0,1]
    # NOTE: the invoice carries no pre-drawn outcome. The realized outcome is drawn by the driver
    # CONDITIONED ON THE ACTING AGENT'S CAPABILITY (a capable underwriter's book pays better on the
    # same raw invoice — pricing/covenants/monitoring). That coupling is what CGR recovers.


@dataclass
class Scenario:
    seed: int
    episode: str
    clients_public: list[ClientPublic]
    invoices_public: list[InvoiceObservable]
    clients_truth: dict[str, ClientTruth] = field(default_factory=dict)
    invoices_truth: dict[str, InvoiceTruth] = field(default_factory=dict)

    def base_pp(self, invoice_id: str) -> float:
        return self.invoices_truth[invoice_id].base_pp


def generate_market(seed: int, *, episode: str, n_clients: int = 40, n_invoices: int = 200) -> Scenario:
    """Build a reproducible receivables market with hidden truth. `episode` namespaces invoice ids
    so re-runs never collide in the live tenant (idempotency requirement)."""
    rng = np.random.default_rng(seed)
    fk = new_faker(seed)

    clients_public: list[ClientPublic] = []
    clients_truth: dict[str, ClientTruth] = {}
    for i in range(n_clients):
        cid = f"CLIENT-{seed:04d}-{i:04d}"
        pay_prob = float(np.clip(rng.beta(6, 3), 0.05, 0.98))   # skew toward creditworthy, hidden
        clients_public.append(ClientPublic(
            client_id=cid, name=fk.company(), sector=str(rng.choice(_SECTORS)),
            country=str(rng.choice(_COUNTRIES)),
        ))
        clients_truth[cid] = ClientTruth(client_id=cid, pay_prob=pay_prob)

    invoices_public: list[InvoiceObservable] = []
    invoices_truth: dict[str, InvoiceTruth] = {}
    for j in range(n_invoices):
        cli = clients_public[int(rng.integers(0, n_clients))]
        cid = cli.client_id
        difficulty = float(rng.uniform(0.0, 1.0))                # hidden
        base = clients_truth[cid].pay_prob
        # harder invoices erode the client's intrinsic pay-probability. Spread base_pp WIDE so the
        # accept/reject selection has real discriminative content (a capable agent can tell payers
        # from defaulters). No outcome is drawn here — the driver draws it conditioned on the agent.
        base_pp = float(np.clip(base * (1.0 - 0.85 * difficulty), 0.02, 0.99))
        # public coarse risk signal: a noisy proxy of base_pp everyone can see
        risk_signal = float(np.clip(base_pp + rng.normal(0.0, 0.15), 0.0, 1.0))
        iid = f"INV-{episode}-{j:05d}"                            # unique per episode
        amount = float(round(rng.lognormal(mean=10.5, sigma=0.7), 2))   # ~$10k–$150k
        tenor = int(rng.choice([30, 45, 60, 90]))
        invoices_public.append(InvoiceObservable(
            invoice_id=iid, client_id=cid, amount=amount, currency=str(rng.choice(_CURRENCIES)),
            tenor_days=tenor, sector=cli.sector, risk_signal=round(risk_signal, 4),
        ))
        invoices_truth[iid] = InvoiceTruth(invoice_id=iid, base_pp=base_pp,
                                           difficulty=round(difficulty, 4))

    return Scenario(seed=seed, episode=episode, clients_public=clients_public,
                    invoices_public=invoices_public, clients_truth=clients_truth,
                    invoices_truth=invoices_truth)
