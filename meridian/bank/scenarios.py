"""Scenario hook (BANK-002-09..15): a `Scenario` reads a read-only view and returns Intents; it never mutates the
world or writes files. Discovery: BUILTIN by id, entry points `meridian.bank.scenarios`, or `pkg.module:Class`."""
from __future__ import annotations

import importlib
from datetime import date, timedelta
from typing import Protocol, runtime_checkable

import numpy as np

from meridian.bank.entities import Intent
from meridian.bank.identifiers import mav_id
from meridian.bank.sdd import add_months
from meridian.bank.world import BankWorldView


@runtime_checkable
class Scenario(Protocol):
    scenario_id: str

    def plan(self, world: BankWorldView, rng: np.random.Generator, clock: list[date]) -> list[Intent]: ...


def _accounts(world: BankWorldView) -> list[str]:
    return sorted(world.accounts)


def _holder_accounts(world: BankWorldView) -> dict[str, str]:
    return {a.holder_id: a.account_id for a in world.accounts.values()}


class Baseline:
    """Steady inbound/outbound SCTs with generic placeholders (REF/DOC/CUST, BANK-003-05) and a monthly fee."""
    scenario_id = "baseline"

    def __init__(self, sct_per_day_per_account: float = 0.6):
        self.lam = sct_per_day_per_account

    def plan(self, world, rng, clock):
        out: list[Intent] = []
        accts = _accounts(world); n = 0
        for d in clock:
            for acct in accts:
                for _ in range(int(rng.poisson(self.lam))):
                    n += 1
                    holder = world.holders[world.accounts[acct].holder_id]
                    others = [h for h in world.holders if h != holder.holder_id] or [holder.holder_id]
                    payer = others[int(rng.integers(0, len(others)))]
                    amount = int(max(100, round(rng.lognormal(mean=8.0, sigma=0.9))))
                    ref = f"{d.year}-{int(rng.integers(1, 999999)):06d}"
                    if rng.random() < 0.7:
                        out.append(Intent(intent_id=f"{self.scenario_id}-{n:05d}", scenario_id=self.scenario_id, kind="sct_in", when=d.isoformat(),
                                          parties={"beneficiary_account_id": acct, "payer_holder_id": payer}, amount_cents=amount,
                                          remittance_clean=f"REF {ref} DOC {int(rng.integers(1000, 9999))} CUST {holder.holder_id[-5:]}", links={"REF": ref}))
                    else:
                        out.append(Intent(intent_id=f"{self.scenario_id}-{n:05d}", scenario_id=self.scenario_id, kind="sct_out", when=d.isoformat(),
                                          parties={"ordering_account_id": acct}, amount_cents=amount, remittance_clean=f"PAGAMENTO DOC {int(rng.integers(1000, 9999))}"))
            if d == clock[-1]:
                for acct in accts:
                    n += 1
                    out.append(Intent(intent_id=f"{self.scenario_id}-{n:05d}", scenario_id=self.scenario_id, kind="fee", when=d.isoformat(), parties={"account_id": acct}, amount_cents=250))
        return out


class SddLifecycle:
    """FRST -> RCUR on a few mandates; one of each R-kind within the rule windows (BANK-003-12..16)."""
    scenario_id = "sdd-lifecycle"

    def plan(self, world, rng, clock):
        out: list[Intent] = []
        mandates = sorted(world.mandates)
        outcomes = ["settle", "settle", "reject:AC04", "return:AM04", "refund:MD06", "refund_unauthorised:MD01", "reversal:AM05"]
        for i, mid in enumerate(mandates):
            m = world.mandates[mid]
            when = clock[min(i % len(clock), len(clock) - 1)].isoformat()
            outcome = outcomes[i % len(outcomes)]
            out.append(Intent(intent_id=f"{self.scenario_id}-{i+1:04d}", scenario_id=self.scenario_id, kind="sdd_collect", when=when,
                              parties={"mandate_id": mid}, amount_cents=4500 + 100 * (i % 7), remittance_clean=f"SDD {mid} RATA {i % 12 + 1:02d}",
                              expected_outcome=outcome, links={"mandate": mid}))
        return out


class MavLifecycle:
    """Issue notices; pay on time, late, twice (duplicate), partially, or let expire (BANK-003-32)."""
    scenario_id = "mav-lifecycle"

    def __init__(self, notices: int = 40, paid_rate: float = 0.85):
        self.notices, self.paid_rate = notices, paid_rate

    def plan(self, world, rng, clock):
        out: list[Intent] = []
        accts = _accounts(world)
        for i in range(self.notices):
            acct = accts[i % len(accts)]
            mid = mav_id("90001", f"{i + 1:09d}")
            issued = clock[0]; due = issued + timedelta(days=26)
            amount = 5000 + int(rng.integers(0, 20000))
            out.append(Intent(intent_id=f"{self.scenario_id}-issue-{i+1:04d}", scenario_id=self.scenario_id, kind="mav_issue", when=issued.isoformat(),
                              parties={"creditor_account_id": acct}, amount_cents=amount, extra={"mav_id": mid, "due_date": due.isoformat()}))
            variant = int(rng.integers(0, 10))
            if rng.random() < self.paid_rate:
                pay_day = min(issued + timedelta(days=int(rng.integers(1, 20))), clock[-1])
                pays = [(pay_day, amount, "one_to_one")]
                if variant == 0:
                    pays.append((min(pay_day + timedelta(days=3), clock[-1]), amount, "duplicate"))
                elif variant == 1:
                    pays = [(pay_day, amount // 2, "partial")]
                elif variant == 2 and len(clock) > 1:
                    pays = [(clock[-1], amount, "late")]
                for j, (pd, amt, mc) in enumerate(pays):
                    out.append(Intent(intent_id=f"{self.scenario_id}-pay-{i+1:04d}-{j+1}", scenario_id=self.scenario_id, kind="mav_pay", when=pd.isoformat(),
                                      parties={"creditor_account_id": acct}, amount_cents=amount if mc != "partial" else amt, extra={"mav_id": mid, "paying_channel": "online"}, tags=[mc]))
        return out


class RemittanceNoise:
    """Clean vs noisy remittance pairs for matching tests (BANK-003-05, BANK-003-08)."""
    scenario_id = "remittance-noise"
    OPS = [["truncate_to(40)"], ["upper()"], ["strip_accents()"], ["drop_separators()"], ["transpose_adjacent_digits(8)"], ["drop_token(2)"],
           ["prepend_bank_boilerplate()"], ["concat_two_references()"], ["upper()", "truncate_to(40)"]]
    NAME_OPS = [["initials()"], ["swap_surname_given()"], ["truncate_to_yyy_width()"], ["upper()"], ["strip_accents()"], ["third_party_payer()"]]

    def plan(self, world, rng, clock):
        out: list[Intent] = []
        accts = _accounts(world); holders = sorted(world.holders)
        for i, ops in enumerate(self.OPS + [[]] * len(self.NAME_OPS)):
            acct = accts[i % len(accts)]
            intended = world.accounts[acct].holder_id
            name_ops = self.NAME_OPS[i - len(self.OPS)] if i >= len(self.OPS) else []
            payer = intended
            if "third_party_payer()" in name_ops:
                payer = next(h for h in holders if h != intended)
            ref = f"{clock[0].year}-{i + 1:06d}"
            out.append(Intent(intent_id=f"{self.scenario_id}-{i+1:03d}", scenario_id=self.scenario_id, kind="sct_in", when=clock[i % len(clock)].isoformat(),
                              parties={"beneficiary_account_id": acct, "intended_holder_id": intended, "payer_holder_id": payer}, amount_cents=10000 + 100 * i,
                              remittance_clean=f"REF {ref} DOC {7000 + i} CUST {intended[-5:]} Pagamento già saldato", remittance_noise=ops, counterparty_name_noise=name_ops, links={"REF": ref}))
        return out


BUILTIN: dict[str, type] = {"baseline": Baseline, "sdd-lifecycle": SddLifecycle, "mav-lifecycle": MavLifecycle, "remittance-noise": RemittanceNoise}


def load_scenario(spec: str) -> Scenario:
    """`baseline` (built-in) | entry-point name in group `meridian.bank.scenarios` | `pkg.module:ClassName`."""
    if spec in BUILTIN:
        return BUILTIN[spec]()
    if ":" in spec:
        mod, cls = spec.split(":", 1)
        return getattr(importlib.import_module(mod), cls)()
    from importlib.metadata import entry_points
    for ep in entry_points(group="meridian.bank.scenarios"):
        if ep.name == spec:
            return ep.load()()
    raise SystemExit(f"unknown scenario {spec!r} (built-ins: {', '.join(BUILTIN)})")
