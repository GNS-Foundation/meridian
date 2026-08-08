"""GrafomemScorer maps records onto the two ingestion endpoints correctly (mocked httpx — no network).
Critically: the SAME raw invoice_id is posted on both the decision and the outcome (the server-side
pseudonym join contract)."""
from __future__ import annotations

import json

import httpx

from meridian.entities import Decision, Outcome
from meridian.grafomem_adapter import GrafomemScorer

_CAPTURED: list[httpx.Request] = []


def _handler(request: httpx.Request) -> httpx.Response:
    _CAPTURED.append(request)
    if request.url.path == "/v1/governed/decisions":
        return httpx.Response(200, json={"decision_record": {"decision_id": "dec-1", "invoice_id": "OUT-pseudo"}})
    if request.url.path.startswith("/v1/governed/outcomes"):
        return httpx.Response(200, json={"invoice_ref": "OUT-pseudo", "outcome": "paid", "idempotent": False})
    if request.url.path == "/v1/cgr/scores":
        return httpx.Response(200, json={"scores": [
            {"agent_handle": "underwriter-00@virtualbank", "subject_key": "k0", "cgr_score": 0.66,
             "confidence": 3.0, "n_resolved": 2, "n_pending": 1}]})
    return httpx.Response(404)


def _scorer():
    return GrafomemScorer("https://api.example", "test-key", transport=httpx.MockTransport(_handler))


def test_decision_posts_raw_invoice_id_and_cgr_fields():
    _CAPTURED.clear()
    g = _scorer()
    d = Decision(agent_key="k0", agent_handle="underwriter-00@virtualbank", model_id="m",
                 invoice_id="INV-ep-00001", decision="certify", verifiability_tag="judgment",
                 reason="advance", context={"amount": 50000, "sector": "logistics"})
    rec = g.post_decision(d); g.close()
    req = next(r for r in _CAPTURED if r.url.path == "/v1/governed/decisions")
    body = json.loads(req.content)
    assert body["invoice_id"] == "INV-ep-00001"          # RAW id (server pseudonymizes)
    assert body["decision"] == "certify" and body["verifiability_tag"] == "judgment"
    assert body["agent_key"] == "k0" and body["context"]["amount"] == 50000
    assert req.headers["X-API-Key"] == "test-key"
    assert rec.raw_invoice_id == "INV-ep-00001" and rec.decision_id == "dec-1"


def test_outcome_posts_same_raw_id_as_decision():
    _CAPTURED.clear()
    g = _scorer()
    g.post_outcome(Outcome(invoice_ref="INV-ep-00001", outcome="paid", outcome_date="2026-03-01T00:00:00Z")); g.close()
    req = next(r for r in _CAPTURED if r.url.path == "/v1/governed/outcomes")
    body = json.loads(req.content)
    assert body["invoice_ref"] == "INV-ep-00001"         # SAME raw id ⇒ joins server-side
    assert body["outcome"] == "paid"


def test_reputation_parses_cgr_scores():
    g = _scorer()
    reps = g.reputation(); g.close()
    assert len(reps) == 1
    r = reps[0]
    assert r.agent_key == "k0" and r.cgr_score == 0.66 and r.n_resolved == 2 and r.n_pending == 1
