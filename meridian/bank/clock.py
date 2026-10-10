"""Simulated clock (BANK-002-03): fixed epoch, whole business days, never the wall clock on the content path."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

SIM_EPOCH = date(2026, 1, 5)          # a Monday; `--start-date` overrides it and is part of the golden-file key


def business_days(start: date, n: int) -> list[date]:
    out: list[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def ggmmaa(d: date) -> str:
    return d.strftime("%d%m%y")


def ggmmaaaa(d: date) -> str:
    return d.strftime("%d%m%Y")


def iso_dt(d: date, hour: int) -> str:
    """Deterministic ISO timestamp on a sim date (statements 18:00Z, status reports 12:00Z)."""
    return datetime(d.year, d.month, d.day, hour, 0, 0, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
