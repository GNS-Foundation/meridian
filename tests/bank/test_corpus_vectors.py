"""Every corpus vector is a test (corpus/bank is the contract). Positive artefact vectors reproduce their artefacts
byte-for-byte; negative vectors raise their expected rule_id. Vectors under _assumed/ run as xfail(strict=False)
naming their A-ids, so a reproduced assumed vector shows up as XPASS and a broken one never masks the suite."""
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
from tests.bank.corpus_fixture import (MANIFEST, SIM_DAY, corpus_world, intents_from_rh_input, load_vector, materialise_all, read_artefact, sdd_world)

VECTORS = [m for m in MANIFEST["vectors"]]


def _param(m):
    marks = []
    if m["kind"] == "assumed":
        marks.append(pytest.mark.xfail(strict=False, reason="ASSUMPTION " + ", ".join(m["assumptions"])))
    return pytest.param(m, id=m["id"], marks=marks)


@pytest.mark.parametrize("m", [_param(m) for m in VECTORS])
def test_corpus_vector(m):
    v = load_vector(m["path"])
    vid, inp, exp = v["id"], v["input"], v["expected"]
    polarity = v.get("polarity") or ("negative" if exp.get("verdict") == "reject" else "positive")
    rule = exp.get("rule_id")

    # ---------------- CBI RH artefacts ----------------
    if vid.startswith("cbi-rh-neg"):
        assert rule in check_cbi_rh(read_artefact(m["path"], "RH.txt")); return
    if vid.startswith("cbi-rh-"):
        n = int(vid.split("-")[2]); w = corpus_world()
        materialise_all(w, intents_from_rh_input(w, vid, inp), {inp["account"]: inp["opening_cents"]})
        text = render_flow(w.view(), "BNK-CORPUS-1", SIM_DAY, [inp["account"]], f"CORPUS-RH-{n:04d}")
        assert check_cbi_rh(text) == []
        assert text == read_artefact(m["path"], "RH.txt"); return
    # ---------------- camt / pain artefacts ----------------
    if vid == "camt053-001-sct-in":
        rh = load_vector("_assumed/cbi-rh-002-sct-in-48-full-63-chain"); w = corpus_world()
        materialise_all(w, intents_from_rh_input(w, rh["id"], rh["input"]), {"ACC-MAIN": rh["input"]["opening_cents"]})
        assert render_statement(w.view(), "ACC-MAIN", SIM_DAY, 1) == read_artefact(m["path"], "camt053.xml"); return
    if vid == "camt054-001-credit-notification":
        rh = load_vector("_assumed/cbi-rh-002-sct-in-48-full-63-chain"); w = corpus_world()
        materialise_all(w, intents_from_rh_input(w, rh["id"], rh["input"]), {"ACC-MAIN": rh["input"]["opening_cents"]})
        # corpus inconsistency (reported): this derived artefact carries <ElctrncSeqNb> in Ntfctn; camt054-002 does not
        assert render_notification(w.view(), "ACC-MAIN", SIM_DAY, 1) == read_artefact(m["path"], "camt054.xml"); return
    if vid == "camt054-002-sdd-return-AM04":
        sdd = load_vector("sdd-002-return-AM04")["input"]
        w, _ = sdd_world(sdd["collection"], "return:AM04", sdd["r_transaction"]["date"], [date(2026, 2, 10), date(2026, 2, 12)])
        assert render_notification(w.view(), "ACC-MAIN", date(2026, 2, 12), 2) == read_artefact(m["path"], "camt054.xml"); return
    if vid == "camt-neg-001-element-renamed":
        try:
            assert "XML-XSD" in check_xml_xsd(read_artefact(m["path"], "camt053.xml"), "camt.053.001.08")
        except XsdUnavailable as e:
            pytest.skip(f"XSD unavailable (D-02): {e}")
        return
    if vid == "pain002-001-reject-AC04":
        sdd = load_vector("sdd-001-reject-AC04")["input"]
        w, cid = sdd_world(sdd["collection"], "reject:AC04", sdd["r_transaction"]["date"], [date(2026, 2, 9), date(2026, 2, 10)])
        coll = w.collections[cid]
        assert render_reject(w.view(), coll, w.mandates[coll.mandate_id], 1) == read_artefact(m["path"], "pain002.xml"); return
    if vid.startswith("pain002-neg"):
        assert rule in check_pain002(read_artefact(m["path"], "pain002.xml")); return
    if vid == "cbi-im-001-mav-paid-assumed":
        w = corpus_world(days=[SIM_DAY, date(2026, 1, 20)])
        its = [Intent(intent_id="MAV-I", scenario_id="corpus", kind="mav_issue", when="2026-01-05", parties={"creditor_account_id": "ACC-MAIN", "debtor_holder_id": "HLD-CLELIA"}, amount_cents=8800, extra={"mav_id": inp["mav_id"], "due_date": "2026-01-31"}),
               Intent(intent_id="MAV-P", scenario_id="corpus", kind="mav_pay", when=inp["paid_on"], parties={"creditor_account_id": "ACC-MAIN"}, amount_cents=inp["amount_cents"], extra={"mav_id": inp["mav_id"], "paying_channel": inp["paying_channel"]})]
        materialise_all(w, its, {"ACC-MAIN": 100000})
        assert render_im(w.view(), "BNK-CORPUS-1", SIM_DAY, "CORPUS-IM-0001", [inp["mav_id"]]) == read_artefact(m["path"], "IM.txt"); return
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
        w, cid = sdd_world(inp["collection"], "settle", None, [date(2026, 2, 10)])
        movs = [m_ for m_ in w.movements if m_.instrument_ref == cid]
        assert len(movs) == 2 and {(m_.account_id, m_.sign) for m_ in movs} == {("ACC-PAYER2", "D"), ("ACC-MAIN", "C")}
        assert w.collections[cid].state == "settled"; return
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
        w = corpus_world()
        it = Intent(intent_id="TP-1", scenario_id="corpus", kind="sct_in", when=SIM_DAY.isoformat(), amount_cents=12345, remittance_clean="REF 1",
                    parties={"beneficiary_account_id": "ACC-MAIN", "intended_holder_id": inp["intended_holder"]["holder_id"], "payer_holder_id": inp["payer"]["holder_id"], "payer_iban": inp["payer"]["iban"]},
                    counterparty_name_noise=inp["name_noise_ops"])
        materialise_all(w, [it], {"ACC-MAIN": 0})
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
        days = sorted({SIM_DAY, date(2026, 2, 1)} | {date.fromisoformat(p["paid_on"]) for p in pays})
        w = corpus_world(days=days)
        its = [Intent(intent_id="MAV-I", scenario_id="corpus", kind="mav_issue", when=mv["issued_on"], parties={"creditor_account_id": mv["creditor_account_id"]}, amount_cents=mv["amount_cents"], extra={"mav_id": mv["mav_id"], "due_date": mv["due_date"]})]
        its += [Intent(intent_id=f"MAV-P{i}", scenario_id="corpus", kind="mav_pay", when=p["paid_on"], parties={"creditor_account_id": mv["creditor_account_id"]}, amount_cents=p["amount_cents"], extra={"mav_id": mv["mav_id"]}) for i, p in enumerate(pays, 1)]
        materialise_all(w, its, {"ACC-MAIN": 0})
        n = w.mav_notices[mv["mav_id"]]; e = exp["answer_key"][0]
        assert n.state == e["state"]
        rows = [r for r in w._answer_rows if r.get("mav_id") == mv["mav_id"]]
        if e.get("late"): assert rows[0]["late"] is True
        if e.get("partial"): assert rows[0]["partial"] is True and rows[0]["match_class"] == "partial"
        if e.get("duplicate_payment_ids"): assert rows[-1]["match_class"] == "duplicate" and len(rows) == 2
        return
    if vid == "fee-001-debit":
        w = corpus_world()
        materialise_all(w, [Intent(intent_id="FEE-1", scenario_id="corpus", kind="fee", when=SIM_DAY.isoformat(), parties={"account_id": inp["intent"]["account"]}, amount_cents=inp["intent"]["amount_cents"], extra={"description": inp["intent"]["description"]})], {"ACC-MAIN": 0})
        mv = w.movements[0]; e = exp["answer_key"][0]
        assert mv.sign == e["sign"] and mv.amount_cents == e["amount_cents"] and mv.cbi_causale == w.causale["fee"]; return
    if vid == "bank-001-entities":
        w = generate_world(BankConfig(seed=7, episode="ent", banks=2, accounts=6, days=1, scenarios=[], sdd_mandates=0))
        holders = [a.holder_id for a in w.accounts.values()]
        assert len(holders) == len(set(holders)) == exp["accounts_per_holder"] * len(w.accounts)
        assert all(99000 <= int(b.abi) <= 99999 for b in w.banks.values()) is exp["abi_in_range"]
        assert all(is_curated_person_name(h.display_name) for h in w.holders.values() if h.kind == "person"); return
    pytest.fail(f"no test mapping for corpus vector {vid}")
