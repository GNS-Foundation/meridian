"""Validators with stable rule ids (BANK-005-20). Every rule id is registered in RULES so tests/bank/test_probes.py
can prove 100 % probe coverage (BANK-005-21). Checks return the list of rule ids violated; `validate_*` raise."""
from __future__ import annotations

import os
import re

from meridian.bank import noise
from meridian.bank.identifiers import BIC_RE, cin_italiano, mod97
from meridian.bank.names import is_curated_person_name
from meridian.bank.sdd import check_r_transaction

RULES: dict[str, str] = {
    # CBI RH (BANK-004-23)
    "CBI-RH-LEN-120": "every record is exactly 120 characters",
    "CBI-RH-ENVELOPE": "first record RH, last record EF",
    "CBI-RH-EF-COUNT": "EF counters equal statements / records including RH and EF",
    "CBI-RH-SEQ": "statement sequence 61 / 62* / 63* / 64",
    "CBI-RH-PROG": "progressivo consistent across the records of one statement",
    "CBI-RH-61-64-DATE": "record 64 data contabile equals record 61 pos. 78-83",
    "CBI-RH-61-64-CCY": "record 64 currency equals record 61 pos. 75-77",
    "CBI-RH-BAL": "closing balance = opening + algebraic sum of movements",
    "CBI-RH-AMT-NUM": "amount fields are 15 digits",
    "CBI-RH-62-13-CHEQUE": "cheque number filled iff causale 13",
    "CBI-RH-63-MAX5": "at most five record 63 per movement",
    "CBI-RH-63-SEQ": "RI2 requires RI1 before; RI1 requires ID1 before",
    "CBI-RH-63-YYY-NAME-40": "YYY ordering-party name fits pos. 41-80",
    "CBI-RH-63-UNSUPPORTED-FLAG": "KKK / ZZ1-ZZ3 bodies are out of scope v1",
    "CBI-RH-65-NOT-EMITTED": "record 65 is not emitted in v1",
    # identifiers (BANK-005-23)
    "IBAN-LEN-IT-27": "Italian IBAN is 27 chars starting with IT",
    "IBAN-MOD97": "ISO 7064 mod 97-10 check",
    "IBAN-CIN": "Italian CIN check",
    "BIC-LEN": "BIC is 8 or 11 chars in ISO 9362 shape",
    "MAV-ID-LEN": "MAV identifier is 17 digits",
    # SEPA (BANK-005-24)
    "SEPA-RMT-140": "unstructured remittance <= 140 chars",
    "NAME-LEN-40": "emitted counterparty name <= 40 chars",
    "SDD-REFUND-8W": "MD06 refund within 8 weeks of settlement",
    "SDD-REFUND-13M": "MD01 refund within 13 months of settlement",
    "SDD-CODE-RTYPE": "reason code permitted for the R-type (EPC173-14)",
    "SDD-CODE-SCOPE": "AC13 is B2B-only",
    "SDD-RETURN-UNSETTLED": "return / refund / reversal only after settlement",
    "SDD-RETURN-WINDOW": "return / reversal within the configured window (A-05)",
    "SDD-SEQ-AG02": "sequence-type progression (FRST/OOFF then RCUR, optional FNAL)",
    "SDD-NO-REFUSAL": "no Refusal object (A-11)",
    "PAIN002-ORGNL-MSGNM": "OrgnlMsgNmId is pain.008.001.08",
    "XML-XSD": "XML validates against the ISO 20022 XSD (skipped when XSDs are unavailable, D-02)",
    # answer key (BANK-005-25/27)
    "AK-NO-INTENT": "every movement links to an intent",
    "AK-REFUND-UNSETTLED": "a refund references a settled collection",
    "AK-MAV-PAID-NO-CREDIT": "a paid MAV has exactly one credit movement",
    "AK-THIRD-PARTY-DISTINCT": "third_party_payer: payer holder differs from intended holder",
    "AK-NAME-NOISE-REPLAY": "replaying name_noise_ops on the clean name reproduces the emitted name",
    "NOISE-INITIALS-SHAPE": "initials() output is at most surname + 3 chars",
    "NAME-NOT-CURATED": "emitted person names are built from the curated list",
}


class ValidationError(ValueError):
    def __init__(self, rule_ids: list[str], message: str = ""):
        self.rule_ids = list(rule_ids)
        super().__init__(f"{', '.join(self.rule_ids)}{': ' + message if message else ''}")


class XsdUnavailable(RuntimeError):
    """Raised when XSD validation cannot run (no schema dir / no validator): tests SKIP naming D-02."""


def _raise(v: list[str]) -> None:
    if v:
        raise ValidationError(sorted(set(v)))


# ---------------- identifiers ----------------
def check_iban(iban: str) -> list[str]:
    if len(iban) != 27 or not iban.startswith("IT"):
        return ["IBAN-LEN-IT-27"]
    v = []
    if mod97(iban[4:] + iban[:4]) != 1:
        v.append("IBAN-MOD97")
    if cin_italiano(iban[5:]) != iban[4]:
        v.append("IBAN-CIN")
    return v


def check_bic(bic: str) -> list[str]:
    return [] if BIC_RE.fullmatch(bic) else ["BIC-LEN"]


def check_mav_id(mav: str) -> list[str]:
    return [] if re.fullmatch(r"\d{17}", mav) else ["MAV-ID-LEN"]


def check_remittance(text: str) -> list[str]:
    return ["SEPA-RMT-140"] if len(text) > 140 else []


def check_name_width(name: str) -> list[str]:
    return ["NAME-LEN-40"] if len(name) > 40 else []


# ---------------- CBI RH (positions per BANK-004-11..19) ----------------
def split_records(text: str) -> list[str]:
    lines = text.split("\r\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def ibans_in_rh(lines: list[str]) -> list[str]:
    out = []
    for l in lines:
        if len(l) != 120:
            continue
        if l[1:3] == "61":
            out.append("IT" + l[101:103] + l[51:52] + l[52:57] + l[57:62] + l[62:74])
        elif l[1:3] == "63" and l[13:16] == "YY2":
            out.append(l[66:100].strip())
    return out


def check_cbi_rh(text: str) -> list[str]:
    lines = split_records(text)
    v: list[str] = []
    if any(len(l) != 120 for l in lines):
        return ["CBI-RH-LEN-120"]
    types = [l[1:3] for l in lines]
    if not lines or types[0] != "RH" or types[-1] != "EF":
        return ["CBI-RH-ENVELOPE"]
    ef = lines[-1]
    if not (ef[45:52].isdigit() and ef[82:89].isdigit()):
        return ["CBI-RH-EF-COUNT"]
    if int(ef[82:89]) != len(lines) or int(ef[45:52]) != types.count("61"):
        v.append("CBI-RH-EF-COUNT")
    i = 1
    while i < len(lines) - 1:
        if types[i] != "61":
            v.append("CBI-RH-SEQ"); break
        r61 = lines[i]; prog = r61[3:10]; ccy = r61[74:77]; d61 = r61[77:83]
        if re.fullmatch(r"\d{15}", r61[84:99]):
            opening = int(r61[84:99]) * (1 if r61[83] == "C" else -1)
        else:
            v.append("CBI-RH-AMT-NUM"); opening = 0
        total = opening; i += 1; n63 = 0; seen: list[str] = []
        while i < len(lines) - 1 and types[i] in ("62", "63"):
            l = lines[i]
            if l[3:10] != prog:
                v.append("CBI-RH-PROG")
            if types[i] == "62":
                n63 = 0; seen = []
                amt = l[26:41]
                if not re.fullmatch(r"\d{15}", amt):
                    v.append("CBI-RH-AMT-NUM"); amt = "0"
                total += int(amt) * (1 if l[25] == "C" else -1)
                if (l[41:43] == "13") != bool(l[45:61].strip()):
                    v.append("CBI-RH-62-13-CHEQUE")
            else:
                n63 += 1
                if n63 > 5:
                    v.append("CBI-RH-63-MAX5")
                flag = l[13:16]; seen.append(flag)
                if flag in ("KKK", "ZZ1", "ZZ2", "ZZ3"):
                    v.append("CBI-RH-63-UNSUPPORTED-FLAG")
                if flag == "RI2" and "RI1" not in seen[:-1]:
                    v.append("CBI-RH-63-SEQ")
                if flag == "RI1" and "ID1" not in seen[:-1]:
                    v.append("CBI-RH-63-SEQ")
                if flag == "YYY" and len(l[40:80].rstrip()) == 40 and l[80] != " ":
                    v.append("CBI-RH-63-YYY-NAME-40")
            i += 1
        if i >= len(lines) - 1 or types[i] != "64":
            v.append("CBI-RH-SEQ"); break
        r64 = lines[i]
        if r64[3:10] != prog:
            v.append("CBI-RH-PROG")
        if r64[10:13] != ccy:
            v.append("CBI-RH-61-64-CCY")
        if r64[13:19] != d61:
            v.append("CBI-RH-61-64-DATE")
        if not re.fullmatch(r"\d{15}", r64[20:35]):
            v.append("CBI-RH-AMT-NUM")
        elif int(r64[20:35]) * (1 if r64[19] == "C" else -1) != total:
            v.append("CBI-RH-BAL")
        i += 1
        if i < len(lines) - 1 and types[i] == "65":
            v.append("CBI-RH-65-NOT-EMITTED"); i += 1
    for iban in ibans_in_rh(lines):
        v += check_iban(iban)
    return v


def validate_cbi_rh(text: str) -> None:
    _raise(check_cbi_rh(text))


# ---------------- SDD ----------------
def check_sdd(collection: dict, r: dict, **kw) -> list[str]:
    return check_r_transaction(collection, r, **kw)


# ---------------- pain.002 / XML ----------------
def check_pain002(text: str) -> list[str]:
    m = re.search(r"<OrgnlMsgNmId>([^<]*)</OrgnlMsgNmId>", text)
    return ["PAIN002-ORGNL-MSGNM"] if not m or m.group(1) != "pain.008.001.08" else []


def check_xml_xsd(text: str, message: str) -> list[str]:
    """Validate against the ISO 20022 XSD `<message>.xsd` found in MERIDIAN_ISO20022_XSD_DIR (D-02: not vendored)."""
    xsd_dir = os.environ.get("MERIDIAN_ISO20022_XSD_DIR")
    if not xsd_dir:
        raise XsdUnavailable("MERIDIAN_ISO20022_XSD_DIR unset (D-02: ISO 20022 schemas are not vendored)")
    try:
        import xmlschema  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise XsdUnavailable("xmlschema not installed (dev-only dependency, D-02)") from e
    schema = xmlschema.XMLSchema(os.path.join(xsd_dir, f"{message}.xsd"))
    return [] if schema.is_valid(text) else ["XML-XSD"]


# ---------------- answer key rows ----------------
def check_answer_key_row(row: dict, *, collections: dict[str, dict] | None = None, movements: list[dict] | None = None,
                         mavs: dict[str, dict] | None = None) -> list[str]:
    v: list[str] = []
    if "movement_id" in row and not row.get("intent_id"):
        v.append("AK-NO-INTENT")
    ops = row.get("name_noise_ops") or []
    if "third_party_payer()" in ops and row.get("intended_holder_id") and row.get("intended_holder_id") == row.get("payer_holder_id"):
        v.append("AK-THIRD-PARTY-DISTINCT")
    clean, emitted = row.get("counterparty_name_clean"), row.get("counterparty_name_emitted")
    if clean and emitted is not None and ops:
        text_ops = [o for o in ops if not o.startswith("third_party_payer")]
        if "third_party_payer()" not in ops and noise.apply_name(clean, text_ops) != emitted:
            v.append("AK-NAME-NOISE-REPLAY")
        if "initials()" in ops and emitted and len(emitted) > len(clean.split()[-1]) + 3:
            v.append("NOISE-INITIALS-SHAPE")
    if emitted and row.get("holder_kind", "person") == "person" and not is_curated_person_name(emitted):
        v.append("NAME-NOT-CURATED")
    r = row.get("r_transaction")
    if r and r.get("kind") == "refund":
        coll = (collections or {}).get(row.get("collection_id", ""), row.get("collection", {}))
        if coll.get("state") != "settled":
            v.append("AK-REFUND-UNSETTLED")
    mav = row.get("mav") or ((mavs or {}).get(row.get("mav_id", "")) if mavs else None)
    if mav and mav.get("state") == "paid":
        credits = [m for m in (movements if movements is not None else row.get("movements", [])) if m.get("sign") == "C" and m.get("instrument_ref") == mav.get("mav_id")]
        if len(credits) != 1:
            v.append("AK-MAV-PAID-NO-CREDIT")
    return v
