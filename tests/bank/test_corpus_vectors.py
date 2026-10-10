"""Every corpus vector is a test (corpus/bank is the contract). Positive artefact vectors reproduce their artefacts
byte-for-byte FROM THEIR INPUTS; negative vectors raise their expected rule_id. Vectors under _assumed/ carry their
A-ids in the test id and in the terminal summary (conftest) — reported, never tolerated: every vector must pass."""
from __future__ import annotations

from datetime import date

import pytest

from meridian.bank import noise
from meridian.bank.formats.camt053 import render_statement
from meridian.bank.formats.camt054 import render_notification
from meridian.bank.formats.cbi_im import render_im
from meridian.bank.formats.cbi_rh import render_flow
from meridian.bank.formats.pain002 import render_reject
from meridian.bank.generator import BankConfig, generate_world, generator_block
from meridian.bank.identifiers import cin_italiano, iban_it, mav_id, mod97
from meridian.bank.names import is_curated_person_name
from meridian.bank.validate import (XsdUnavailable, check_answer_key_row, check_bic, check_cbi_rh, check_iban, check_mav_id, check_pain002,
                                    check_remittance, check_sdd, check_xml_xsd)
from meridian.bank.entities import Intent
from tests.bank.corpus_fixture import MANIFEST, corpus_world, load_vector, read_artefact, reproduce, run

VECTORS = [m for m in MANIFEST["vectors"]]


def _param(m):
    tag = f"[{','.join(m['assumptions'])}]" if m["kind"] == "assumed" else ""
    return pytest.param(m, id=m["id"] + tag)


@pytest.mark.parametrize("m", [_param(m) for m in VECTORS])
def test_corpus_vector(m):
    v = load_vector(m["path"])
    vid, inp, exp = v["id"], v["input"], v["expected"]
    polarity = v.get("polarity") or ("negative" if exp.get("verdict") == "reject" else "positive")
    rule = exp.get("rule_id")

    # ---------------- CBI RH artefacts ----------------
    if vid.startswith("cbi-rh-neg"):
        assert rule in check_cbi_rh(read_artefact(m["path"], "RH.txt")); return
    if vid.startswith(("cbi-rh-", "camt053-", "camt054-", "pain002-001", "cbi-im-")):
        actual, expected = reproduce(m)
        if vid.startswith("cbi-rh-"):
            assert check_cbi_rh(actual) == []
        assert actual == expected; return
    if vid == "camt-neg-001-element-renamed":
        try:
            assert "XML-XSD" in check_xml_xsd(read_artefact(m["path"], "camt053.xml"), "camt.053.001.08")
        except XsdUnavailable as e:
            pytest.skip(f"XSD unavailable (D-02): {e}")
        return
    if vid.startswith("pain002-neg"):
        assert rule in check_pain002(read_artefact(m["path"], "pain002.xml")); return
    # ---------------- identifiers ----------------
    if vid == "ident-001-iban-valid":
        assert [iban_it(*t) for t in inp["abi_cab_conto"]] == exp["ibans"]
        assert all(check_iban(i) == [] for i in exp["ibans"])
        ex = exp["s11_worked_example"]; assert cin_italiano(ex["bban"][1:]) == ex["bban"][0] and 98 - mod97(ex["bban"] + "IT00") == int(ex["check"]); return
    if vid == "ident-002-bic":
        assert all(check_bic(b) == [] for b in inp["bics"]); return
    if vid == "ident-003-mav-id-17":
        assert mav_id(inp["n1"], inp["n2"]) == exp["mav_id"] and check_mav_id(exp["mav_id"]) == []; return
    if vid.startswith("ident-neg"):
        key = "iban" if "iban" in inp else "bic" if "bic" in inp else "mav_id"
        fn = {"iban": check_iban, "bic": check_bic, "mav_id": check_mav_id}[key]
        assert rule in fn(inp[key]); return
    # ---------------- SDD ----------------
    if vid == "sdd-007-settlement-pair":
        c = inp["collection"]; w = corpus_world("corpus", [date.fromisoformat(c["settlement_date"])])
        from meridian.bank.entities import Mandate
        w.mandates[c["mandate_id"]] = Mandate(mandate_id=c["mandate_id"], creditor_id=c["creditor_id"], creditor_name=c["creditor"], creditor_account_id=c["creditor_account_id"], debtor_account_id=c["debtor_account_id"], debtor_name=c["debtor"], signed_on="2025-06-01", sequence_type=c["sequence_type"])
        run(w, [Intent(intent_id="S", scenario_id="corpus", kind="sdd_collect", when=c["settlement_date"], parties={"mandate_id": c["mandate_id"]}, amount_cents=c["amount_cents"], expected_outcome="settle", extra={"collection_id": c["collection_id"], "end_to_end_id": c["end_to_end_id"]})], {c["creditor_account_id"]: 0, c["debtor_account_id"]: 0})
        movs = [m_ for m_ in w.movements if m_.instrument_ref == c["collection_id"]]
        assert len(movs) == 2 and {(m_.account_id, m_.sign) for m_ in movs} == {(c["debtor_account_id"], "D"), (c["creditor_account_id"], "C")}
        assert w.collections[c["collection_id"]].state == "settled"; return
    if vid.startswith("sdd-neg"):
        assert rule in check_sdd({**inp["collection"], "state": "settled"}, inp["r_transaction"]); return
    if vid.startswith("sdd-"):
        assert check_sdd({**inp["collection"], "state": "settled"}, inp["r_transaction"]) == []
        if inp["r_transaction"].get("substituted"):
            assert inp["r_transaction"]["requested_reason_code"] != inp["r_transaction"]["reason_code"]
        return
    # ---------------- remittance noise ----------------
    if vid == "rmt-neg-001-ustrd-141":
        assert rule in check_remittance(inp["remittance_emitted"]); return
    if vid.startswith("rmt-noise"):
        assert noise.apply_remittance(inp["remittance_clean"], inp["noise_ops"]) == exp["remittance_emitted"]
        assert check_remittance(exp["remittance_emitted"]) == []; return
    # ---------------- counterparty-name noise ----------------
    if vid == "name-noise-006-third_party_payer":
        w = corpus_world("corpus", [date(2026, 1, 5)])
        it = Intent(intent_id="TP-1", scenario_id="corpus", kind="sct_in", when="2026-01-05", amount_cents=12345, remittance_clean="REF 1",
                    parties={"beneficiary_account_id": "ACC-MAIN", "intended_holder_id": inp["intended_holder"]["holder_id"], "payer_holder_id": inp["payer"]["holder_id"], "payer_iban": inp["payer"]["iban"]},
                    counterparty_name_noise=inp["name_noise_ops"])
        run(w, [it], {"ACC-MAIN": 0})
        mv = w.movements[0]; row = w._answer_rows[0]
        assert mv.counterparty.name == exp["emitted_counterparty"]["name"] and mv.counterparty.iban == exp["emitted_counterparty"]["iban"]
        e = exp["answer_key"][0]
        assert row["intended_holder_id"] == e["intended_holder_id"] and row["payer_holder_id"] == e["payer_holder_id"] and row["paid_by_third_party"] is True
        assert check_answer_key_row(row) == []; return
    if vid.startswith("name-noise"):
        assert noise.apply_name(inp["counterparty_name_clean"], inp["name_noise_ops"]) == exp["counterparty_name_emitted"]
        assert is_curated_person_name(exp["counterparty_name_emitted"]); return
    if vid.startswith("name-neg"):
        row = inp.get("answer_key_row") or {k: v_ for k, v_ in inp.items() if k != "curated_list"}
        assert rule in check_answer_key_row(row); return
    # ---------------- answer key ----------------
    if vid == "ak-001-match-classes":
        assert all(check_answer_key_row(r) == [] for r in exp["answer_key"])
        blk = generator_block(BankConfig(seed=42, episode="corpus"), ["corpus@0"])
        assert set(exp["generator"]) <= set(blk) | {"scenarios"}; return
    if vid.startswith("ak-neg"):
        row = inp.get("answer_key_row") or inp
        assert rule in check_answer_key_row(row); return
    # ---------------- MAV variants (A-03) ----------------
    if vid.startswith("mav-"):
        mv = inp["mav"]; pays = mv.get("payments") or ([{"paid_on": mv["paid_on"], "amount_cents": mv.get("paid_amount_cents", mv["amount_cents"])}] if mv.get("paid_on") else [])
        days = sorted({date.fromisoformat(mv["issued_on"]), date(2026, 2, 1)} | {date.fromisoformat(p["paid_on"]) for p in pays})
        w = corpus_world("corpus", days)
        its = [Intent(intent_id="MAV-I", scenario_id="corpus", kind="mav_issue", when=mv["issued_on"], parties={"creditor_account_id": mv["creditor_account_id"]}, amount_cents=mv["amount_cents"], extra={"mav_id": mv["mav_id"], "due_date": mv["due_date"]})]
        its += [Intent(intent_id=f"MAV-P{i}", scenario_id="corpus", kind="mav_pay", when=p["paid_on"], parties={"creditor_account_id": mv["creditor_account_id"]}, amount_cents=p["amount_cents"], extra={"mav_id": mv["mav_id"]}) for i, p in enumerate(pays, 1)]
        run(w, its, {"ACC-MAIN": 0})
        n = w.mav_notices[mv["mav_id"]]; e = exp["answer_key"][0]
        assert n.state == e["state"]
        rows = [r for r in w._answer_rows if r.get("mav_id") == mv["mav_id"]]
        if e.get("late"): assert rows[0]["late"] is True
        if e.get("partial"): assert rows[0]["partial"] is True and rows[0]["match_class"] == "partial"
        if e.get("duplicate_payment_ids"): assert rows[-1]["match_class"] == "duplicate" and len(rows) == 2
        return
    if vid == "fee-001-debit":
        w = corpus_world("corpus", [date(2026, 1, 5)])
        run(w, [Intent(intent_id="FEE-1", scenario_id="corpus", kind="fee", when="2026-01-05", parties={"account_id": inp["intent"]["account"]}, amount_cents=inp["intent"]["amount_cents"], extra={"description": inp["intent"]["description"]})], {"ACC-MAIN": 0})
        mv = w.movements[0]; e = exp["answer_key"][0]
        assert mv.sign == e["sign"] and mv.amount_cents == e["amount_cents"] and mv.cbi_causale == w.causale["fee"]; return
    if vid == "bank-001-entities":
        w = corpus_world("corpus", [date(2026, 1, 5)])                       # the corpus data file itself (G-3)
        holders = [a.holder_id for a in w.accounts.values()]
        assert len(holders) == len(set(holders)) == exp["accounts_per_holder"] * len(w.accounts)
        assert all(99000 <= int(b.abi) <= 99999 for b in w.banks.values()) is exp["abi_in_range"]
        assert {(b["abi"], b["cab"]) for b in exp["branches"]} <= {(bk.abi, br.cab) for bk in w.banks.values() for br in bk.branches}
        assert all(is_curated_person_name(h.display_name) for h in w.holders.values() if h.kind == "person")
        g = generate_world(BankConfig(seed=7, episode="ent", banks=2, accounts=6, days=1, scenarios=[], sdd_mandates=0))
        assert len({a.holder_id for a in g.accounts.values()}) == len(g.accounts); return
    pytest.fail(f"no test mapping for corpus vector {vid}")
