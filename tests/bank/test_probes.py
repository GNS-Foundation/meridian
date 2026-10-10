"""Non-vacuity probes (BANK-005-20/21): one row per rule_id = (good artefact factory, mutation, expected rule). Each probe
asserts the mutation raises the rule and the untouched artefact passes. A rule_id with no probe row fails the suite."""
from __future__ import annotations

import re
from datetime import date

import pytest

from meridian.bank.validate import (RULES, XsdUnavailable, check_answer_key_row, check_bic, check_cbi_rh, check_iban, check_mav_id, check_pain002,
                                    check_remittance, check_name_width, check_sdd, check_xml_xsd, split_records)
from tests.bank.corpus_fixture import read_artefact

GOOD_RH = read_artefact("_assumed/cbi-rh-002-sct-in-48-full-63-chain", "RH.txt")
GOOD_RH_CHEQUE = read_artefact("_assumed/cbi-rh-004-cheque-13", "RH.txt")
GOOD_PAIN = read_artefact("_assumed/pain002-001-reject-AC04", "pain002.xml")
GOOD_CAMT = read_artefact("_assumed/camt053-001-sct-in", "camt053.xml")
GOOD_IBAN = "IT41K9910112345000000123456"
COLL = {"collection_id": "C", "settlement_date": "2026-02-10", "state": "settled"}
def MAV_CREDIT(mid, match_class): return {"movement_id": mid, "sign": "C", "instrument_ref": "1", "match_class": match_class}
ROW_NAME = {"movement_id": "M", "intent_id": "I", "counterparty_name_clean": "Fabrizia Ventoscuro", "counterparty_name_emitted": "VENTOSCURO F.", "name_noise_ops": ["initials()"], "intended_holder_id": "A", "payer_holder_id": "A"}


def _lines(text): return split_records(text)
def _join(lines): return "\r\n".join(lines) + "\r\n"
def _idx(lines, t, flag=None): return next(i for i, l in enumerate(lines) if l[1:3] == t and (flag is None or l[13:16] == flag))
def _ef(lines, nrec=None, nstmt=None):
    ef = lines[-1]
    if nrec is not None: ef = ef[:82] + f"{nrec:07d}" + ef[89:]
    if nstmt is not None: ef = ef[:45] + f"{nstmt:07d}" + ef[52:]
    return lines[:-1] + [ef]


def rh_mut(fn):
    def m():
        L = _lines(GOOD_RH); return check_cbi_rh(_join(fn(L)))
    return m


def swap(i, new):
    def f(L): L = list(L); L[i] = new; return L
    return f


L0 = _lines(GOOD_RH); I62 = _idx(L0, "62"); I64 = _idx(L0, "64"); R62 = L0[I62]; R64 = L0[I64]
PROBES = {
    "CBI-RH-LEN-120": rh_mut(swap(I62, R62[:119])),
    "CBI-RH-ENVELOPE": rh_mut(lambda L: L[1:]),
    "CBI-RH-EF-COUNT": rh_mut(lambda L: _ef(L, nrec=len(L) + 1)),
    "CBI-RH-SEQ": rh_mut(lambda L: _ef([L[0]] + L[2:], nrec=len(L) - 1)),
    "CBI-RH-PROG": rh_mut(swap(I62, R62[:3] + "0000002" + R62[10:])),
    "CBI-RH-61-64-DATE": rh_mut(swap(I64, R64[:13] + "060126" + R64[19:])),
    "CBI-RH-61-64-CCY": rh_mut(swap(I64, R64[:10] + "USD" + R64[13:])),
    "CBI-RH-BAL": rh_mut(swap(I64, R64[:20] + f"{int(R64[20:35]) + 1:015d}" + R64[35:])),
    "CBI-RH-AMT-NUM": rh_mut(swap(I62, R62[:26] + "0000000001234X5" + R62[41:])),
    "CBI-RH-62-13-CHEQUE": rh_mut(swap(I62, R62[:41] + "13" + R62[43:])),
    "CBI-RH-63-MAX5": rh_mut(lambda L: _ef(L[:I64] + [" 63" + "0000001" + "001" + "X".ljust(107)] + L[I64:], nrec=len(L) + 1)),
    "CBI-RH-63-SEQ": rh_mut(lambda L: _ef([l for l in L if l[13:16] != "RI1"], nrec=len(L) - 1)),
    "CBI-RH-63-YYY-NAME-40": rh_mut(lambda L: [(l[:40] + "M" * 41 + l[81:]) if l[13:16] == "YYY" else l for l in L]),
    "CBI-RH-63-UNSUPPORTED-FLAG": rh_mut(lambda L: [(l[:13] + "KKK" + l[16:]) if l[13:16] == "YY2" else l for l in L]),
    "CBI-RH-65-NOT-EMITTED": rh_mut(lambda L: _ef(L[:I64 + 1] + [" 65" + "0000001" + "050126".ljust(110)] + L[I64 + 1:], nrec=len(L) + 1)),
    "IBAN-LEN-IT-27": lambda: check_iban(GOOD_IBAN[:-1]),
    "IBAN-MOD97": lambda: check_iban(GOOD_IBAN[:20] + ("9" if GOOD_IBAN[20] != "9" else "8") + GOOD_IBAN[21:]),
    "IBAN-CIN": lambda: check_iban(GOOD_IBAN[:4] + ("A" if GOOD_IBAN[4] != "A" else "B") + GOOD_IBAN[5:]),
    "BIC-LEN": lambda: check_bic("FNTAITMMX"),
    "MAV-ID-LEN": lambda: check_mav_id("9000100000004261"),
    "SEPA-RMT-140": lambda: check_remittance("X" * 141),
    "NAME-LEN-40": lambda: check_name_width("X" * 41),
    "SDD-REFUND-8W": lambda: check_sdd(COLL, {"kind": "refund", "reason_code": "MD06", "date": "2026-04-08"}),
    "SDD-REFUND-13M": lambda: check_sdd(COLL, {"kind": "refund", "reason_code": "MD01", "date": "2027-03-11"}),
    "SDD-CODE-RTYPE": lambda: check_sdd(COLL, {"kind": "reject", "reason_code": "MD06", "date": "2026-02-09"}),
    "SDD-CODE-SCOPE": lambda: check_sdd(COLL, {"kind": "reject", "reason_code": "AC13", "date": "2026-02-09"}),
    "SDD-RETURN-UNSETTLED": lambda: check_sdd(COLL, {"kind": "return", "reason_code": "AM04", "date": "2026-02-09"}),
    "SDD-RETURN-WINDOW": lambda: check_sdd(COLL, {"kind": "return", "reason_code": "AM04", "date": "2026-03-30"}, return_window_days=5),
    "SDD-SEQ-AG02": lambda: check_sdd(COLL, {"kind": "sdd_collect", "sequence_type": "RCUR", "previous_sequence_type": "OOFF"}),
    "SDD-NO-REFUSAL": lambda: check_sdd(COLL, {"kind": "refusal", "reason_code": "MS02", "date": "2026-02-09"}),
    "PAIN002-ORGNL-MSGNM": lambda: check_pain002(GOOD_PAIN.replace("pain.008.001.08", "pain.008.001.02")),
    "XML-XSD": lambda: check_xml_xsd(GOOD_CAMT.replace("<Ntry>", "<Entry>").replace("</Ntry>", "</Entry>"), "camt.053.001.08"),
    "AK-NO-INTENT": lambda: check_answer_key_row({"movement_id": "M", "intent_id": None}),
    "AK-REFUND-UNSETTLED": lambda: check_answer_key_row({"r_transaction": {"kind": "refund"}, "collection": {"state": "presented"}}),
    "AK-MAV-PAID-NO-CREDIT": lambda: check_answer_key_row({"mav": {"mav_id": "1", "state": "paid"}, "movements": []}),
    "AK-MAV-DUP-UNLABELLED": lambda: check_answer_key_row({"mav": {"mav_id": "1", "state": "paid"}, "movements": [MAV_CREDIT("P1", "one_to_one"), MAV_CREDIT("P2", "one_to_one")]}),
    "AK-THIRD-PARTY-DISTINCT": lambda: check_answer_key_row({"name_noise_ops": ["third_party_payer()"], "intended_holder_id": "A", "payer_holder_id": "A"}),
    "AK-NAME-NOISE-REPLAY": lambda: check_answer_key_row({**ROW_NAME, "name_noise_ops": ["upper()"]}),
    "NOISE-INITIALS-SHAPE": lambda: check_answer_key_row({**ROW_NAME, "counterparty_name_emitted": "VENTOSCURO FA."}),
    "NAME-NOT-CURATED": lambda: check_answer_key_row({"counterparty_name_emitted": "Fabrizia Rossi"}),
}

CLEAN = {
    "cbi": lambda: check_cbi_rh(GOOD_RH) + check_cbi_rh(GOOD_RH_CHEQUE),
    "ids": lambda: check_iban(GOOD_IBAN) + check_bic("FNTAITMMXXX") + check_mav_id("90001000000042616"),
    "sepa": lambda: check_remittance("X" * 140) + check_name_width("X" * 40) + check_pain002(GOOD_PAIN)
            + check_sdd(COLL, {"kind": "refund", "reason_code": "MD06", "date": "2026-04-07"}) + check_sdd(COLL, {"kind": "return", "reason_code": "AM04", "date": "2026-02-12"}),
    "ak": lambda: check_answer_key_row({"movement_id": "M", "intent_id": "I", "name_noise_ops": ["third_party_payer()"], "intended_holder_id": "A", "payer_holder_id": "B",
                                        "counterparty_name_clean": "Fabrizia Ventoscuro", "counterparty_name_emitted": "Ottavio Pietranera"})
          + check_answer_key_row({"mav": {"mav_id": "1", "state": "paid"}, "movements": [MAV_CREDIT("P1", "one_to_one"), MAV_CREDIT("P2", "duplicate")]}),   # paid twice, labelled (BANK-001-19)
}


def test_every_rule_has_a_probe():
    missing = sorted(set(RULES) - set(PROBES)); extra = sorted(set(PROBES) - set(RULES))
    assert not missing, f"rule ids without a probe row: {missing}"
    assert not extra, f"probe rows for unregistered rule ids: {extra}"


@pytest.mark.parametrize("rule", sorted(RULES))
def test_probe_breaks_then_restores(rule):
    try:
        raised = PROBES[rule]()
    except XsdUnavailable as e:
        pytest.skip(f"XSD unavailable (D-02): {e}")
    assert rule in raised, f"{rule}: mutation not detected (got {sorted(set(raised))})"
    for name, fn in CLEAN.items():
        assert fn() == [], f"clean artefacts raise after probe ({name})"
