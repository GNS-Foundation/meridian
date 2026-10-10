"""BankWorld (BANK-001-21) and the materialiser (BANK-002-11): the only code that turns Intents into entities and
movements. Scenarios never build movements. The answer key is kept in a separate container, never in outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from meridian.bank import noise
from meridian.bank.clock import ggmmaaaa
from meridian.bank.entities import (Account, Balance, Bank, Collection, Counterparty, Holder, Intent, Mandate, MavNotice, Movement, RTransaction)
from meridian.bank.sdd import add_months

# cbi_causale placeholders for codes NOT quoted in CBI-RND-001 (A-07): configurable constants
CAUSALE = {"sct_in": "48", "sct_out": "26", "cheque": "13", "sdd_debit": "A7", "sdd_credit": "A7", "sdd_r_debit": "A7", "sdd_r_credit": "A7", "mav_credit": "A7", "fee": "A7"}
JUDGMENT_FEE_DESCRIPTION = "COMMISSIONI"


@dataclass
class BankWorld:
    seed: int
    episode: str
    start_date: date
    days: list[date] = field(default_factory=list)
    banks: dict[str, Bank] = field(default_factory=dict)
    holders: dict[str, Holder] = field(default_factory=dict)
    accounts: dict[str, Account] = field(default_factory=dict)
    movements: list[Movement] = field(default_factory=list)
    balances: dict[tuple[str, str], Balance] = field(default_factory=dict)
    mandates: dict[str, Mandate] = field(default_factory=dict)
    collections: dict[str, Collection] = field(default_factory=dict)
    mav_notices: dict[str, MavNotice] = field(default_factory=dict)
    intents: list[Intent] = field(default_factory=list)
    causale: dict[str, str] = field(default_factory=lambda: dict(CAUSALE))
    _answer_rows: list[dict] = field(default_factory=list)          # ground truth — separate from outputs (BANK-002-17)
    _sdd_chains: list[dict] = field(default_factory=list)
    _mav_pairs: list[dict] = field(default_factory=list)

    # ---- index helpers (BANK-001-21) ----
    def account_by_iban(self, iban: str) -> Account | None:
        return next((a for a in self.accounts.values() if a.iban == iban), None)

    def movements_by_account_day(self, account_id: str, book_date: str) -> list[Movement]:
        return [m for m in self.movements if m.account_id == account_id and m.booking_date == book_date]

    def holder_of(self, account_id: str) -> Holder:
        return self.holders[self.accounts[account_id].holder_id]

    def bank_reference_for(self, intent: Intent, k: int = 0) -> str:
        """CRO/CRI-like reference, <= 16 chars. Explicit `intent.extra["bank_reference"]` (list or str) wins; otherwise
        derived from (seed, intent_id, k) so another scenario's presence never shifts it (BANK-002-02/15)."""
        explicit = intent.extra.get("bank_reference")
        if explicit:
            return explicit[k] if isinstance(explicit, list) else explicit
        import hashlib
        h = hashlib.blake2b(f"{self.seed}:{intent.intent_id}:{k}".encode(), digest_size=8).digest()
        return f"CRO26{int.from_bytes(h, 'big') % 10**11:011d}"

    def movement_id_for(self, intent: Intent, k: int = 0) -> str:
        return f"MOV-{intent.intent_id}-{k + 1}"

    def view(self) -> "BankWorldView":
        return BankWorldView(self)


class BankWorldView:
    """Read-only view handed to scenarios and writers (BANK-002-09, BANK-004-04): no answer key reachable."""

    def __init__(self, world: BankWorld):
        self._w = world

    @property
    def seed(self): return self._w.seed
    @property
    def episode(self): return self._w.episode
    @property
    def start_date(self): return self._w.start_date
    @property
    def days(self): return list(self._w.days)
    @property
    def banks(self): return dict(self._w.banks)
    @property
    def holders(self): return dict(self._w.holders)
    @property
    def accounts(self): return dict(self._w.accounts)
    @property
    def movements(self): return list(self._w.movements)
    @property
    def balances(self): return dict(self._w.balances)
    @property
    def mandates(self): return dict(self._w.mandates)
    @property
    def collections(self): return dict(self._w.collections)
    @property
    def mav_notices(self): return dict(self._w.mav_notices)
    @property
    def causale(self): return dict(self._w.causale)

    def account_by_iban(self, iban): return self._w.account_by_iban(iban)
    def movements_by_account_day(self, a, d): return self._w.movements_by_account_day(a, d)
    def holder_of(self, a): return self._w.holder_of(a)


# ---------------------------------------------------------------- materialiser ----
def _counterparty_from_holder(h: Holder, iban: str | None, name: str) -> Counterparty:
    return Counterparty(name=name, iban=iban, fiscal_code_like=h.fiscal_code_like[:16], address_label=h.address_label,
                        locality_label=h.locality_label, holder_id=h.holder_id)


def _base_row(w: BankWorld, intent: Intent, m: Movement) -> dict:
    return {"movement_id": m.movement_id, "intent_id": intent.intent_id, "scenario_id": intent.scenario_id, "kind": intent.kind,
            "expected_outcome": intent.expected_outcome, "links": dict(intent.links), "match_class": intent.extra.get("match_class", "one_to_one")}


def materialise(w: BankWorld, intent: Intent, rng: np.random.Generator) -> list[Movement]:
    """Turn one Intent into entities + movements; record the answer-key rows. Deterministic given (w, intent, rng)."""
    kind = intent.kind
    if kind == "sct_in":
        return _sct_in(w, intent)
    if kind == "sct_out":
        return _sct_out(w, intent)
    if kind == "fee":
        return _fee(w, intent)
    if kind == "sdd_collect":
        return _sdd_collect(w, intent)
    if kind == "mav_issue":
        return _mav_issue(w, intent)
    if kind == "mav_pay":
        return _mav_pay(w, intent)
    raise ValueError(f"unknown intent kind {kind}")


def _sct_in(w: BankWorld, intent: Intent) -> list[Movement]:
    acct = w.accounts[intent.parties["beneficiary_account_id"]]
    intended_holder_id = intent.parties.get("intended_holder_id", acct.holder_id)
    payer_holder_id = intent.parties.get("payer_holder_id", intended_holder_id)
    third_party = "third_party_payer()" in intent.counterparty_name_noise
    if third_party and payer_holder_id == intended_holder_id:
        raise ValueError("third_party_payer requires a distinct payer_holder_id")
    payer = w.holders[payer_holder_id]
    name_clean = payer.display_name
    text_ops = [o for o in intent.counterparty_name_noise if not o.startswith("third_party_payer")]
    name_emitted = noise.apply_name(name_clean, text_ops)
    rem_emitted = noise.apply_remittance(intent.remittance_clean, intent.remittance_noise)
    payer_iban = intent.parties.get("payer_iban") or next((a.iban for a in w.accounts.values() if a.holder_id == payer_holder_id), None)
    m = Movement(movement_id=w.movement_id_for(intent), account_id=acct.account_id, booking_date=intent.when, value_date=intent.when, sign="C",
                 amount_cents=intent.amount_cents, cbi_causale=w.causale["sct_in"], bank_reference=w.bank_reference_for(intent),
                 end_to_end_id=intent.extra.get("end_to_end_id") or f"E2E-{intent.intent_id}"[:35], remittance_unstructured=rem_emitted,
                 counterparty=_counterparty_from_holder(payer, payer_iban, name_emitted), instrument_ref=intent.intent_id, kind="sct_in",
                 order_date=ggmmaaaa(date.fromisoformat(intent.when)), episode=w.episode)
    w.movements.append(m)
    row = _base_row(w, intent, m)
    row.update({"remittance_clean": intent.remittance_clean, "remittance_emitted": rem_emitted, "noise_ops": list(intent.remittance_noise),
                "counterparty_name_clean": name_clean, "counterparty_name_emitted": name_emitted, "name_noise_ops": list(intent.counterparty_name_noise),
                "intended_holder_id": intended_holder_id, "payer_holder_id": payer_holder_id, "paid_by_third_party": third_party,
                "end_to_end_id": m.end_to_end_id, "holder_kind": payer.kind})
    w._answer_rows.append(row)
    return [m]


def _sct_out(w: BankWorld, intent: Intent) -> list[Movement]:
    acct = w.accounts[intent.parties["ordering_account_id"]]
    m = Movement(movement_id=w.movement_id_for(intent), account_id=acct.account_id, booking_date=intent.when, value_date=intent.when, sign="D",
                 amount_cents=intent.amount_cents, cbi_causale=w.causale["sct_out"], bank_reference=w.bank_reference_for(intent),
                 message_id=intent.extra.get("message_id") or f"MSG-{intent.intent_id}"[:35], end_to_end_id=intent.extra.get("end_to_end_id", ""),
                 remittance_unstructured=noise.apply_remittance(intent.remittance_clean, intent.remittance_noise),
                 customer_ref_type="NROSUPCBI", customer_ref_text=intent.extra.get("support_name") or f"SUPPORTO-{intent.intent_id}"[:34],
                 instrument_ref=intent.intent_id, kind="sct_out", episode=w.episode)
    w.movements.append(m)
    row = _base_row(w, intent, m); row.update({"remittance_clean": intent.remittance_clean, "remittance_emitted": m.remittance_unstructured, "noise_ops": list(intent.remittance_noise)})
    w._answer_rows.append(row)
    return [m]


def _fee(w: BankWorld, intent: Intent) -> list[Movement]:
    acct = w.accounts[intent.parties["account_id"]]
    cheque = intent.extra.get("instrument") == "cheque"
    m = Movement(movement_id=w.movement_id_for(intent), account_id=acct.account_id, booking_date=intent.when, value_date=intent.when, sign="D",
                 amount_cents=intent.amount_cents, cbi_causale=w.causale["cheque"] if cheque else w.causale["fee"], bank_reference=w.bank_reference_for(intent),
                 cheque_number=intent.extra.get("cheque_number", "0000000012345678") if cheque else "", remittance_unstructured=intent.extra.get("description", JUDGMENT_FEE_DESCRIPTION),
                 instrument_ref=intent.intent_id, kind="fee", episode=w.episode)
    w.movements.append(m)
    w._answer_rows.append(_base_row(w, intent, m))
    return [m]


def _sdd_collect(w: BankWorld, intent: Intent) -> list[Movement]:
    mandate = w.mandates[intent.parties["mandate_id"]]
    debtor = w.accounts[mandate.debtor_account_id]; creditor = w.accounts[mandate.creditor_account_id]
    coll = Collection(collection_id=intent.extra.get("collection_id") or f"COLL-{intent.intent_id}", mandate_id=mandate.mandate_id,
                      requested_collection_date=intent.when, amount_cents=intent.amount_cents, end_to_end_id=intent.extra.get("end_to_end_id") or f"E2E-SDD-{intent.intent_id}"[:35],
                      remittance_unstructured=noise.apply_remittance(intent.remittance_clean, intent.remittance_noise), episode=w.episode)
    outcome = intent.expected_outcome
    out: list[Movement] = []
    if outcome.startswith("reject:"):
        code = outcome.split(":", 1)[1]
        coll.state = "rejected"
        coll.r_transactions.append(RTransaction(kind="reject", reason_code=code, date=intent.extra.get("r_date", intent.when), initiator="debtor_psp", amount_cents=coll.amount_cents, original_collection_id=coll.collection_id))
    else:
        coll.settlement_date = intent.when; coll.state = "settled"
        mandate.last_collection_on = intent.when
        for k, (acct, sign, key) in enumerate(((debtor, "D", "sdd_debit"), (creditor, "C", "sdd_credit"))):
            m = Movement(movement_id=w.movement_id_for(intent, k), account_id=acct.account_id, booking_date=intent.when, value_date=intent.when, sign=sign,
                         amount_cents=coll.amount_cents, cbi_causale=w.causale[key], bank_reference=w.bank_reference_for(intent, k), end_to_end_id=coll.end_to_end_id,
                         remittance_unstructured=coll.remittance_unstructured, mandate_id=mandate.mandate_id, instrument_ref=coll.collection_id, kind="sdd_settle", episode=w.episode,
                         counterparty=Counterparty(name=mandate.creditor_name if sign == "D" else mandate.debtor_name, iban=creditor.iban if sign == "D" else debtor.iban))
            w.movements.append(m); out.append(m)
        if outcome != "settle":
            rkind, code = outcome.split(":", 1)
            rkind = {"refund_unauthorised": "refund", "refund_inactivity": "refund"}.get(rkind, rkind)
            rdate = intent.extra.get("r_date") or _default_r_date(intent.when, rkind, code)
            coll.r_transactions.append(RTransaction(kind=rkind, reason_code=code, date=rdate, initiator={"return": "debtor_psp", "refund": "debtor", "reversal": "creditor"}[rkind],
                                                    amount_cents=coll.amount_cents, original_collection_id=coll.collection_id, requested_reason_code=intent.extra.get("requested_reason_code")))
            coll.state = {"return": "returned", "refund": "refunded", "reversal": "reversed"}[rkind]
            for k, (acct, sign, key) in enumerate(((creditor, "D", "sdd_r_debit"), (debtor, "C", "sdd_r_credit")), start=2):
                m = Movement(movement_id=w.movement_id_for(intent, k), account_id=acct.account_id, booking_date=rdate, value_date=rdate, sign=sign,
                             amount_cents=coll.amount_cents, cbi_causale=w.causale[key], bank_reference=w.bank_reference_for(intent, k), end_to_end_id=coll.end_to_end_id,
                             mandate_id=mandate.mandate_id, r_reason_code=code, instrument_ref=coll.collection_id, kind="sdd_r", episode=w.episode)
                w.movements.append(m); out.append(m)
    w.collections[coll.collection_id] = coll
    for m in out:
        row = _base_row(w, intent, m); row.update({"collection_id": coll.collection_id, "remittance_clean": intent.remittance_clean, "remittance_emitted": coll.remittance_unstructured, "noise_ops": list(intent.remittance_noise)})
        w._answer_rows.append(row)
    w._sdd_chains.append({"intent_id": intent.intent_id, "collection_id": coll.collection_id, "state": coll.state, "r_transactions": [r.model_dump() for r in coll.r_transactions], "movement_ids": [m.movement_id for m in out]})
    return out


def _default_r_date(settlement: str, rkind: str, code: str) -> str:
    s = date.fromisoformat(settlement)
    if rkind == "refund" and code == "MD06":
        return (s + timedelta(days=56)).isoformat()
    if rkind == "refund" and code == "MD01":
        return add_months(s, 13).isoformat()
    return (s + timedelta(days=2)).isoformat()


def _mav_issue(w: BankWorld, intent: Intent) -> list[Movement]:
    n = MavNotice(mav_id=intent.extra["mav_id"], creditor_account_id=intent.parties["creditor_account_id"], debtor_holder_id=intent.parties.get("debtor_holder_id"),
                  amount_cents=intent.amount_cents, due_date=intent.extra["due_date"], issued_on=intent.when, episode=w.episode)
    w.mav_notices[n.mav_id] = n
    w._mav_pairs.append({"intent_id": intent.intent_id, "mav_id": n.mav_id, "state": n.state, "payments": []})
    return []


def _mav_pay(w: BankWorld, intent: Intent) -> list[Movement]:
    n = w.mav_notices[intent.extra["mav_id"]]
    acct = w.accounts[n.creditor_account_id]
    duplicate = n.state == "paid"
    m = Movement(movement_id=w.movement_id_for(intent), account_id=acct.account_id, booking_date=intent.when, value_date=intent.when, sign="C",
                 amount_cents=intent.amount_cents or n.amount_cents, cbi_causale=w.causale["mav_credit"], bank_reference=w.bank_reference_for(intent),
                 remittance_unstructured=f"MAV {n.mav_id}", instrument_ref=n.mav_id, kind="mav_pay", episode=w.episode)
    w.movements.append(m)
    if not duplicate:
        n.state = "paid"; n.paid_on = intent.when; n.paid_amount_cents = m.amount_cents; n.paying_channel = intent.extra.get("paying_channel", "online")
    row = _base_row(w, intent, m)
    row.update({"mav_id": n.mav_id, "late": intent.when > n.due_date, "partial": m.amount_cents < n.amount_cents,
                "match_class": "duplicate" if duplicate else ("partial" if m.amount_cents < n.amount_cents else "one_to_one")})
    w._answer_rows.append(row)
    pair = next(p for p in w._mav_pairs if p["mav_id"] == n.mav_id)
    pair["payments"].append({"movement_id": m.movement_id, "paid_on": intent.when, "amount_cents": m.amount_cents, "duplicate": duplicate}); pair["state"] = n.state
    return [m]


def compute_balances(w: BankWorld, opening: dict[str, int]) -> None:
    """BANK-001-07/17: per account and book date, closing = opening + algebraic sum; opening of the next day = closing."""
    days = [d.isoformat() for d in w.days]
    for acct in w.accounts.values():
        running = opening.get(acct.account_id, 0)
        for d in days:
            movs = w.movements_by_account_day(acct.account_id, d)
            closing = running + sum(m.amount_cents if m.sign == "C" else -m.amount_cents for m in movs)
            w.balances[(acct.account_id, d)] = Balance(account_id=acct.account_id, book_date=d, opening_book=running, closing_book=closing, currency=acct.currency)
            running = closing
