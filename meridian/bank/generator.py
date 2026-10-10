"""generate_world(config) -> BankWorld (BANK-002-05): pure, seeded, no I/O. Banks/holders/accounts from derived RNG
streams; scenarios planned in order on their own streams (BANK-002-02/15); intents materialised in date order."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from meridian.bank import SPEC_VERSION
from meridian.bank.clock import SIM_EPOCH, business_days
from meridian.bank.entities import Account, Bank, Branch, Holder, Mandate
from meridian.bank.identifiers import SYNTHETIC_ABI_MIN, fiscal_code_like, iban_it, synthetic_bic
from meridian.bank.names import curated, organisation_name, person_name
from meridian.bank.rng import rng_for
from meridian.bank.scenarios import Scenario, load_scenario
from meridian.bank.world import BankWorld, compute_balances, expire_notices, materialise

MAX_ACCOUNTS, MAX_DAYS = 5000, 60          # BANK-002-08: documented bounds, not silent clamps
ASSUMPTIONS_IN_FORCE = ["A-01", "A-02", "A-03", "A-04", "A-06", "A-07", "A-08", "A-09", "A-10"]


class BankConfig(BaseModel):
    seed: int = 42
    episode: str = "episode"
    start_date: date = SIM_EPOCH
    banks: int = Field(2, ge=1, le=20)
    accounts: int = Field(50, ge=1, le=MAX_ACCOUNTS)
    days: int = Field(5, ge=1, le=MAX_DAYS)
    sct_per_day_per_account: float = 0.6
    sdd_mandates: int = 30
    sdd_r_rate: float = 0.08
    mav_notices: int = 40
    mav_paid_rate: float = 0.85
    scenarios: list[str] = Field(default_factory=lambda: ["baseline"])
    opening_balance_cents: int = 100000
    person_share: float = 0.7


def _bank(cfg: BankConfig, i: int, rng) -> Bank:
    abi = f"{SYNTHETIC_ABI_MIN + 100 * (i + 1) + int(rng.integers(0, 100)):05d}"
    inst = "".join(chr(ord("A") + int(x)) for x in rng.integers(0, 26, size=4))
    labels = ["Roccaluna", "Lagobianco", "Montefreddo", "Valleombrosa", "Fiumedoro"]
    branches = [Branch(cab=f"{10000 + int(rng.integers(0, 89999)):05d}", label=labels[int(rng.integers(0, len(labels)))]) for _ in range(2)]
    return Bank(bank_id=f"BNK-{i+1}", name=f"Banca Finta {labels[i % len(labels)]}", abi=abi, bic=synthetic_bic(inst), branches=branches, episode=cfg.episode)


def generate_world(cfg: BankConfig, scenarios: list[Scenario] | None = None) -> BankWorld:
    w = BankWorld(seed=cfg.seed, episode=cfg.episode, start_date=cfg.start_date, days=business_days(cfg.start_date, cfg.days))
    rng_b = rng_for(cfg.seed, "banks")
    for i in range(cfg.banks):
        b = _bank(cfg, i, rng_b); w.banks[b.bank_id] = b
    rng_h = rng_for(cfg.seed, "holders"); rng_a = rng_for(cfg.seed, "accounts")
    bank_ids = sorted(w.banks)
    for i in range(cfg.accounts):
        kind = "person" if rng_h.random() < cfg.person_share else "organisation"
        name = person_name(rng_h) if kind == "person" else organisation_name(rng_h)
        hid = f"HLD-{i+1:05d}"
        labels = curated().get("organisations", [])
        w.holders[hid] = Holder(holder_id=hid, kind=kind, display_name=name, fiscal_code_like=fiscal_code_like(f"{cfg.seed}:{hid}"),
                                address_label=f"VIA {name.split()[-1].upper()} {int(rng_h.integers(1, 99))}", locality_label=w.banks[bank_ids[i % len(bank_ids)]].branches[0].label.upper(), episode=cfg.episode)
        bank = w.banks[bank_ids[i % len(bank_ids)]]; branch = bank.branches[int(rng_a.integers(0, len(bank.branches)))]
        conto = f"{int(rng_a.integers(0, 10**12)):012d}"
        aid = f"ACC-{i+1:05d}"
        w.accounts[aid] = Account(account_id=aid, bank_id=bank.bank_id, cab=branch.cab, holder_id=hid, iban=iban_it(bank.abi, branch.cab, conto), opened_on=cfg.start_date.isoformat(), episode=cfg.episode)
    rng_m = rng_for(cfg.seed, "mandates"); accts = sorted(w.accounts)
    creditor = accts[0]
    for i in range(min(cfg.sdd_mandates, max(0, len(accts) - 1))):
        debtor = accts[1 + i % (len(accts) - 1)] if len(accts) > 1 else accts[0]
        mid = f"UMR-{cfg.episode}-{i+1:04d}"[:35]
        w.mandates[mid] = Mandate(mandate_id=mid, creditor_id=f"IT00ZZZ{w.banks[bank_ids[0]].abi}0000{i+1:04d}", creditor_name=w.holder_of(creditor).display_name, creditor_account_id=creditor,
                                  debtor_account_id=debtor, debtor_name=w.holder_of(debtor).display_name, signed_on=(cfg.start_date).isoformat(), sequence_type="RCUR" if rng_m.random() < 0.8 else "FRST", episode=cfg.episode)
    scen = scenarios if scenarios is not None else [load_scenario(s) for s in cfg.scenarios]
    view = w.view()
    for s in scen:
        intents = s.plan(view, rng_for(cfg.seed, "scenario", s.scenario_id), list(w.days))
        w.intents.extend(intents)
    w.intents.sort(key=lambda i: (i.when, i.scenario_id, i.intent_id))
    for intent in w.intents:
        materialise(w, intent, rng_for(cfg.seed, "materialise", intent.intent_id))
    expire_notices(w, w.days[-1].isoformat())
    compute_balances(w, {a: cfg.opening_balance_cents for a in w.accounts})
    return w


def generator_block(cfg: BankConfig, scen_ids: list[str]) -> dict:
    return {"seed": cfg.seed, "episode": cfg.episode, "start_date": cfg.start_date.isoformat(), "config": cfg.model_dump(mode="json"),
            "scenarios": scen_ids, "spec_version": SPEC_VERSION, "assumptions_in_force": ASSUMPTIONS_IN_FORCE}
