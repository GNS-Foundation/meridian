"""SDD Core rules (BANK-003-10..21). The reason-code table is DATA (BANK-003-20): data/sdd_reason_codes.json,
transcribing EPC173-14 v8.0 (S4). Refund windows: MD06 <= 8 weeks (56 days) after settlement; MD01 <= 13 months
(BANK-003-14/15, verified in S4). Return/reversal windows are A-05: enforced only when configured."""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "sdd_reason_codes.json"
REFUND_AUTHORISED_DAYS = 56


@lru_cache(maxsize=1)
def reason_codes() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def allowed_kinds(code: str) -> list[str]:
    return reason_codes()["codes"].get(code, [])


def is_b2b_only(code: str) -> bool:
    return reason_codes().get("scheme_scope", {}).get(code) == "B2B-only"


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, last))


def check_sequence(previous: str | None, current: str) -> list[str]:
    """BANK-003-10: FRST/OOFF first, then RCUR, optional FNAL; RCUR after OOFF or OOFF after RCUR -> AG02."""
    if previous is None:
        return [] if current in ("FRST", "OOFF") else ["SDD-SEQ-AG02"]
    if previous == "OOFF" or current in ("FRST", "OOFF"):
        return ["SDD-SEQ-AG02"]
    if previous == "FNAL":
        return ["SDD-SEQ-AG02"]
    return []


def check_r_transaction(collection: dict, r: dict, *, return_window_days: int | None = None) -> list[str]:
    """Rule ids violated by an R-transaction `r` on `collection` (dicts or model dumps)."""
    v: list[str] = []
    kind = r.get("kind")
    if kind == "sdd_collect":
        return check_sequence(r.get("previous_sequence_type"), r.get("sequence_type", "RCUR"))
    if kind == "refusal":
        return ["SDD-NO-REFUSAL"]
    code = r.get("reason_code", "")
    if is_b2b_only(code):
        v.append("SDD-CODE-SCOPE")
    if kind not in allowed_kinds(code):
        v.append("SDD-CODE-RTYPE")
    settlement = collection.get("settlement_date")
    rdate = date.fromisoformat(r["date"]) if r.get("date") else None
    sdate = date.fromisoformat(settlement) if settlement else None
    if kind in ("return", "refund", "reversal"):
        if collection.get("state") not in (None, "settled", "returned", "refunded", "reversed") or sdate is None or (rdate and rdate < sdate):
            v.append("SDD-RETURN-UNSETTLED")
    if kind == "refund" and rdate and sdate:
        if code == "MD06" and rdate > sdate + timedelta(days=REFUND_AUTHORISED_DAYS):
            v.append("SDD-REFUND-8W")
        if code == "MD01" and rdate > add_months(sdate, 13):
            v.append("SDD-REFUND-13M")
    if kind in ("return", "reversal") and return_window_days is not None and rdate and sdate and rdate > sdate + timedelta(days=return_window_days):
        v.append("SDD-RETURN-WINDOW")
    return v
