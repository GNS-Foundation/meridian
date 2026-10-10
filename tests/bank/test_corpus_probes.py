"""Non-vacuity probes for the corpus tests themselves: patch a writer, assert the artefact vectors STOP reproducing,
restore (pytest's monkeypatch undoes every patch at teardown; each test also re-asserts reproduction before it ends)."""
from __future__ import annotations

import pytest

import meridian.bank.formats.camt053 as camt053
import meridian.bank.formats.cbi_rh as cbi_rh
import meridian.bank.formats.pain002 as pain002
from tests.bank.corpus_fixture import ARTEFACT_POSITIVES, reproduce

RH = [m for m in ARTEFACT_POSITIVES if m["id"].startswith("cbi-rh-")]
CAMT053 = [m for m in ARTEFACT_POSITIVES if m["id"].startswith("camt053-")]
PAIN002 = [m for m in ARTEFACT_POSITIVES if m["id"].startswith("pain002-")]


def _all_match(vectors):
    return [m["id"] for m in vectors if reproduce(m)[0] != reproduce(m)[1]]


@pytest.fixture(autouse=True)
def _clean_before_and_after():
    assert _all_match(RH + CAMT053 + PAIN002) == [], "precondition: vectors reproduce before the probe"
    yield
    assert _all_match(RH + CAMT053 + PAIN002) == [], "probe left state behind: vectors no longer reproduce"


def test_probe_cbi_rh_record_61_causale(monkeypatch):
    monkeypatch.setattr(cbi_rh, "CAUSALE_61_ORDINARY", cbi_rh.CAUSALE_61_RETRANSMISSION)   # 93001 -> 93011
    broken = _all_match(RH)
    assert sorted(broken) == sorted(m["id"] for m in RH), f"RH vectors still reproduce under a patched writer: {set(m['id'] for m in RH) - set(broken)}"
    monkeypatch.undo()
    assert _all_match(RH) == []


def test_probe_camt053_amount(monkeypatch):
    original = camt053.cents
    monkeypatch.setattr(camt053, "cents", lambda amount: original(amount + 1))             # every amount off by one cent
    assert sorted(_all_match(CAMT053)) == sorted(m["id"] for m in CAMT053)
    monkeypatch.undo()
    assert _all_match(CAMT053) == []


def test_probe_pain002_status_code(monkeypatch):
    monkeypatch.setattr(pain002, "TX_STATUS_REJECT", "ACTC")                                 # RJCT -> ACTC
    assert sorted(_all_match(PAIN002)) == sorted(m["id"] for m in PAIN002)
    monkeypatch.undo()
    assert _all_match(PAIN002) == []


def test_probe_sets_are_not_empty():
    assert RH and CAMT053 and PAIN002
