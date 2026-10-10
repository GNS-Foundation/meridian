"""Builds the BankWorld that the corpus artefact vectors assume (corpus/bank/data/synthetic_banks.json + README).

GAP G-1 (reported in the PR): the corpus vector `input` blocks omit several facts that the artefacts encode (ordering
party fiscal code / address / locality, bank references, header support names, creation date). They are supplied here
as fixtures, documented per field, so byte-for-byte reproduction is from input + these fixture conventions."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from meridian.bank.entities import Account, Bank, Branch, Holder, Intent, Mandate
from meridian.bank.world import BankWorld, compute_balances, expire_notices, materialise
from meridian.bank.rng import rng_for

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus" / "bank"
MANIFEST = json.loads((CORPUS / "MANIFEST.json").read_text(encoding="utf-8"))
BANKS = json.loads((CORPUS / "data" / "synthetic_banks.json").read_text(encoding="utf-8"))
IBAN = {a["account_id"]: a["iban"] for a in BANKS["accounts"]}
SIM_DAY = date(2026, 1, 5)                                 # corpus sim date (RH header 050126, camt 2026-01-05)
FIXTURE = {                                                 # G-1: facts the vector inputs omit
    "fiscal_code_like": "FBRZVNT99Z99Z999",                # record 63 YYY pos. 25-40 (16 chars)
    "address_label": "VIA DEI PINI FINTI 12",              # record 63 YY2 pos. 17-66
    "locality_label": "ROCCALUNA",                         # record 63 YYY pos. 81-120
    "sia_receiver": "A1B2C",                               # RH header pos. 9-13
}


def load_vector(path: str) -> dict:
    return json.loads((CORPUS / path / "vector.json").read_text(encoding="utf-8"))


def read_artefact(path: str, name: str) -> str:
    with open(CORPUS / path / name, encoding="utf-8", newline="") as fh:
        return fh.read()


def corpus_world(episode: str = "corpus", days: list[date] | None = None) -> BankWorld:
    w = BankWorld(seed=0, episode=episode, start_date=SIM_DAY, days=days or [SIM_DAY])
    b1, b2 = BANKS["banks"]
    w.banks["BNK-CORPUS-1"] = Bank(bank_id="BNK-CORPUS-1", name=b1["name"], abi=b1["abi"], bic=b1["bic"], branches=[Branch(cab="12345", label="Roccaluna")], sia_receiver=FIXTURE["sia_receiver"], episode=episode)
    w.banks["BNK-CORPUS-2"] = Bank(bank_id="BNK-CORPUS-2", name=b2["name"], abi=b2["abi"], bic=b2["bic"], branches=[Branch(cab="54321", label="Lagobianco")], sia_receiver=FIXTURE["sia_receiver"], episode=episode)
    H = lambda hid, kind, name, fc: Holder(holder_id=hid, kind=kind, display_name=name, fiscal_code_like=fc, address_label=FIXTURE["address_label"], locality_label=FIXTURE["locality_label"], episode=episode)
    w.holders["HLD-ORG"] = H("HLD-ORG", "organisation", "Nebbialunga Servizi Finti S.r.l.", "99999999990")
    w.holders["HLD-PAYER"] = H("HLD-PAYER", "person", "Fabrizia Ventoscuro", FIXTURE["fiscal_code_like"])
    w.holders["HLD-OTTAVIO"] = H("HLD-OTTAVIO", "person", "Ottavio Pietranera", "PTRTTV99Z99Z999Z")
    w.holders["HLD-CLELIA"] = H("HLD-CLELIA", "person", "Clelia Marmorosa", "MRMCLL99Z99Z999Z")
    w.accounts["ACC-MAIN"] = Account(account_id="ACC-MAIN", bank_id="BNK-CORPUS-1", cab="12345", holder_id="HLD-ORG", iban=IBAN["ACC-MAIN"], episode=episode)
    w.accounts["ACC-PAYER"] = Account(account_id="ACC-PAYER", bank_id="BNK-CORPUS-2", cab="54321", holder_id="HLD-PAYER", iban=IBAN["ACC-PAYER"], episode=episode)
    w.accounts["ACC-PAYER2"] = Account(account_id="ACC-PAYER2", bank_id="BNK-CORPUS-2", cab="54321", holder_id="HLD-OTTAVIO", iban=IBAN["ACC-PAYER2"], episode=episode)
    return w


def holder_by_name(w: BankWorld, name: str) -> str:
    return next(h.holder_id for h in w.holders.values() if h.display_name == name)


def rh_vector_number(vector_id: str) -> int:
    return int(re.search(r"cbi-rh-(\d{3})", vector_id).group(1))


def intents_from_rh_input(w: BankWorld, vector_id: str, inp: dict) -> list[Intent]:
    """Map a cbi-rh vector `input.intents` onto Intents. G-1: bank references are the corpus authoring sequence
    (vector n -> CRO26 + (n-1)), the support name is CORPUS-RH-000n, the outbound descr is SUPPORTO-CORPUS-000n."""
    n = rh_vector_number(vector_id)
    out: list[Intent] = []
    for k, it in enumerate(inp.get("intents", []), start=1):
        iid = f"INT-{n:04d}-{k:04d}"
        ref = f"CRO26{n - 1:011d}"
        if it["kind"] == "sct_in":
            out.append(Intent(intent_id=iid, scenario_id="corpus", kind="sct_in", when=SIM_DAY.isoformat(),
                              parties={"beneficiary_account_id": inp["account"], "payer_holder_id": holder_by_name(w, it["payer"]), "payer_iban": it["payer_iban"]},
                              amount_cents=it["amount_cents"], remittance_clean=it["remittance"], counterparty_name_noise=["upper()"],
                              extra={"end_to_end_id": it["end_to_end_id"], "bank_reference": ref}))
        elif it["kind"] == "sct_out":
            out.append(Intent(intent_id=iid, scenario_id="corpus", kind="sct_out", when=SIM_DAY.isoformat(), parties={"ordering_account_id": inp["account"]},
                              amount_cents=it["amount_cents"], extra={"message_id": it["message_id"], "support_name": f"SUPPORTO-CORPUS-{n:04d}", "bank_reference": ref}))
        elif it["kind"] == "fee":
            out.append(Intent(intent_id=iid, scenario_id="corpus", kind="fee", when=SIM_DAY.isoformat(), parties={"account_id": inp["account"]},
                              amount_cents=it["amount_cents"], extra={"instrument": it.get("instrument", ""), "bank_reference": ref}))
    return out


def materialise_all(w: BankWorld, intents: list[Intent], opening: dict[str, int]) -> None:
    for it in sorted(intents, key=lambda i: (i.when, i.intent_id)):
        materialise(w, it, rng_for(w.seed, "materialise", it.intent_id))
    expire_notices(w, w.days[-1].isoformat())
    compute_balances(w, opening)


def sdd_world(collection: dict, outcome: str, r_date: str | None, days: list[date]) -> tuple[BankWorld, str]:
    """World for the SDD vectors: mandate UMR-CORPUS-0001, creditor ACC-MAIN, debtor ACC-PAYER2 (debtor name per vector)."""
    w = corpus_world(days=days)
    w.mandates["UMR-CORPUS-0001"] = Mandate(mandate_id="UMR-CORPUS-0001", creditor_id="IT00ZZZ99101000000001", creditor_name=collection["creditor"], creditor_account_id="ACC-MAIN",
                                            debtor_account_id="ACC-PAYER2", debtor_name=collection["debtor"], signed_on="2025-06-01", sequence_type=collection.get("sequence_type", "RCUR"), episode="corpus")
    it = Intent(intent_id="SDD-0001", scenario_id="corpus", kind="sdd_collect", when=collection["settlement_date"], parties={"mandate_id": "UMR-CORPUS-0001"},
                amount_cents=collection["amount_cents"], expected_outcome=outcome, extra={"collection_id": collection["collection_id"], "end_to_end_id": collection["end_to_end_id"], **({"r_date": r_date} if r_date else {})})
    materialise_all(w, [it], {"ACC-MAIN": 100000, "ACC-PAYER2": 100000})
    return w, collection["collection_id"]
