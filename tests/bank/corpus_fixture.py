"""Builds BankWorlds for the corpus vectors FROM THE CORPUS ONLY: banks/holders/accounts from
corpus/bank/data/synthetic_banks.json, every artefact fact from the vector's `input` (corpus revision G-1).
No test-side fixture value is involved: a field missing from the corpus makes the reproduction fail."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from meridian.bank.entities import Account, Bank, Branch, Holder, Intent, Mandate
from meridian.bank.formats.camt053 import render_statement
from meridian.bank.formats.camt054 import render_notification
from meridian.bank.formats.cbi_im import render_im
from meridian.bank.formats.cbi_rh import render_flow
from meridian.bank.formats.pain002 import render_reject
from meridian.bank.rng import rng_for
from meridian.bank.world import BankWorld, compute_balances, expire_notices, materialise

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus" / "bank"
MANIFEST = json.loads((CORPUS / "MANIFEST.json").read_text(encoding="utf-8"))
DATA = json.loads((CORPUS / "data" / "synthetic_banks.json").read_text(encoding="utf-8"))


def load_vector(path: str) -> dict:
    return json.loads((CORPUS / path / "vector.json").read_text(encoding="utf-8"))


def read_artefact(path: str, name: str) -> str:
    with open(CORPUS / path / name, encoding="utf-8", newline="") as fh:
        return fh.read()


def corpus_world(episode: str, days: list[date], sia_receiver: str | None = None) -> BankWorld:
    """Banks, holders and accounts exactly as corpus/bank/data/synthetic_banks.json describes them."""
    w = BankWorld(seed=0, episode=episode, start_date=days[0], days=days)
    for b in DATA["banks"]:
        w.banks[b["bank_id"]] = Bank(bank_id=b["bank_id"], name=b["name"], abi=b["abi"], bic=b["bic"], branches=[Branch(cab=c, label="") for c in b["cab"]],
                                     sia_receiver=sia_receiver or b.get("sia_receiver", ""), episode=episode)
    for h in DATA["holders"]:
        w.holders[h["holder_id"]] = Holder(holder_id=h["holder_id"], kind=h["kind"], display_name=h["display_name"], fiscal_code_like=h["fiscal_code_like"],
                                           address_label=h["address_label"], locality_label=h["locality_label"], episode=episode)
    abi_to_bank = {b["abi"]: b["bank_id"] for b in DATA["banks"]}
    for a in DATA["accounts"]:
        iban = a["iban"]
        w.accounts[a["account_id"]] = Account(account_id=a["account_id"], bank_id=abi_to_bank[iban[5:10]], cab=iban[10:15], holder_id=a["holder_id"], iban=iban, episode=episode)
    return w


def run(w: BankWorld, intents: list[Intent], opening: dict[str, int]) -> None:
    for it in sorted(intents, key=lambda i: (i.when, i.intent_id)):
        materialise(w, it, rng_for(w.seed, "materialise", it.intent_id))
    expire_notices(w, w.days[-1].isoformat())
    compute_balances(w, opening)


def _iso(d: str) -> date:
    return date.fromisoformat(d)


def rh_intents(inp: dict) -> list[Intent]:
    """Intents from a cbi-rh vector `input` (every artefact fact is explicit in the input)."""
    out: list[Intent] = []
    for k, it in enumerate(inp.get("intents", []), start=1):
        iid = f"INT-{k:04d}"; when = it.get("booking_date", inp["header"]["book_date"])
        base = {"bank_reference": it["bank_reference"]}
        if it["kind"] == "sct_in":
            out.append(Intent(intent_id=iid, scenario_id="corpus", kind="sct_in", when=when,
                              parties={"beneficiary_account_id": inp["account"], "payer_holder_id": it["payer_holder_id"], "payer_iban": it["payer_iban"]},
                              amount_cents=it["amount_cents"], remittance_clean=it["remittance"], counterparty_name_noise=it.get("name_noise_ops", []),
                              extra={**base, "end_to_end_id": it["end_to_end_id"], "order_date": it["order_date"]}))
        elif it["kind"] == "sct_out":
            out.append(Intent(intent_id=iid, scenario_id="corpus", kind="sct_out", when=when, parties={"ordering_account_id": inp["account"]}, amount_cents=it["amount_cents"],
                              extra={**base, "message_id": it["message_id"], "customer_ref_type": it["customer_ref_type"], "customer_ref_text": it["customer_ref_text"]}))
        elif it["kind"] == "fee":
            out.append(Intent(intent_id=iid, scenario_id="corpus", kind="fee", when=when, parties={"account_id": inp["account"]}, amount_cents=it["amount_cents"],
                              extra={**base, "instrument": it.get("instrument", ""), "cheque_number": it.get("cheque_number", "")}))
    return out


def rh_world(inp: dict) -> BankWorld:
    h = inp["header"]
    w = corpus_world("corpus", [_iso(h["book_date"])], sia_receiver=h["sia_receiver"])
    run(w, rh_intents(inp), {inp["account"]: inp["opening_cents"]})
    return w


def sdd_world(inp: dict, outcome: str) -> tuple[BankWorld, str]:
    """World for the SDD-based artefact vectors (camt054-002, pain002-001): mandate and collection from the input."""
    r = inp["r_transaction"]
    days = sorted({_iso(inp["settlement_date"]), _iso(r["date"])})
    w = corpus_world(inp["episode"], days)
    w.mandates[inp["mandate_id"]] = Mandate(mandate_id=inp["mandate_id"], creditor_id=inp["creditor_id"], creditor_name=inp["creditor"], creditor_account_id=inp["creditor_account_id"],
                                           debtor_account_id=inp["debtor_account_id"], debtor_name=inp["debtor"], signed_on="2025-06-01", sequence_type=inp["sequence_type"], episode=inp["episode"])
    it = Intent(intent_id="SDD-0001", scenario_id="corpus", kind="sdd_collect", when=inp["settlement_date"], parties={"mandate_id": inp["mandate_id"]}, amount_cents=inp["amount_cents"],
                expected_outcome=outcome, extra={"collection_id": inp["collection_id"], "end_to_end_id": inp["end_to_end_id"], "r_date": r["date"]})
    run(w, [it], {inp["creditor_account_id"]: 100000, inp["debtor_account_id"]: 100000})
    return w, inp["collection_id"]


# ---------------- reproduction: vector -> (actual artefact text, expected artefact text) ----------------
def reproduce(m: dict) -> tuple[str, str]:
    """Render the artefact of an artefact-bearing POSITIVE vector from its input. Used by the vector tests and by the
    writer-mutation probes (tests/bank/test_corpus_probes.py)."""
    v = load_vector(m["path"]); vid, inp = v["id"], v["input"]
    if vid.startswith("cbi-rh-"):
        w = rh_world(inp); h = inp["header"]
        return render_flow(w.view(), h["bank_id"], _iso(h["book_date"]), [inp["account"]], h["support_name"]), read_artefact(m["path"], "RH.txt")
    if vid.startswith("camt053-"):
        w = rh_world(inp)
        return render_statement(w.view(), inp["account"], _iso(inp["header"]["book_date"]), inp["msg_seq"]), read_artefact(m["path"], "camt053.xml")
    if vid == "camt054-001-credit-notification":
        w = rh_world(inp)
        return render_notification(w.view(), inp["account"], _iso(inp["header"]["book_date"]), inp["msg_seq"]), read_artefact(m["path"], "camt054.xml")
    if vid == "camt054-002-sdd-return-AM04":
        r = inp["r_transaction"]; w, _ = sdd_world(inp, f"{r['kind']}:{r['reason_code']}")
        return render_notification(w.view(), inp["account"], _iso(r["date"]), inp["msg_seq"]), read_artefact(m["path"], "camt054.xml")
    if vid == "pain002-001-reject-AC04":
        r = inp["r_transaction"]; w, cid = sdd_world(inp, f"{r['kind']}:{r['reason_code']}")
        coll = w.collections[cid]
        return render_reject(w.view(), coll, w.mandates[coll.mandate_id], inp["msg_seq"]), read_artefact(m["path"], "pain002.xml")
    if vid == "cbi-im-001-mav-paid-assumed":
        h = inp["header"]; w = corpus_world("corpus", sorted({_iso(h["creation_date"]), _iso(inp["paid_on"])}), sia_receiver=h["sia_receiver"])
        its = [Intent(intent_id="MAV-I", scenario_id="corpus", kind="mav_issue", when=inp["issued_on"], parties={"creditor_account_id": inp["creditor_account_id"], "debtor_holder_id": inp["debtor_holder_id"]}, amount_cents=inp["amount_cents"], extra={"mav_id": inp["mav_id"], "due_date": inp["due_date"]}),
               Intent(intent_id="MAV-P", scenario_id="corpus", kind="mav_pay", when=inp["paid_on"], parties={"creditor_account_id": inp["creditor_account_id"]}, amount_cents=inp["amount_cents"], extra={"mav_id": inp["mav_id"], "paying_channel": inp["paying_channel"]})]
        run(w, its, {inp["creditor_account_id"]: 100000})
        return render_im(w.view(), h["bank_id"], _iso(h["creation_date"]), h["support_name"], [inp["mav_id"]]), read_artefact(m["path"], "IM.txt")
    raise KeyError(f"no reproduction for {vid}")


ARTEFACT_POSITIVES = [m for m in MANIFEST["vectors"] if m["artefacts"] and (m.get("polarity") or ("negative" if m["expected_rule_id"] else "positive")) == "positive"]
