"""GrafomemScorer — the real `Scorer`, httpx → the Grafomem public API.

Posts governed decisions + outcomes and reads CGR reputation back. Credentials come from ENV only
(never chat, never git). This is the ONLY module that talks to Grafomem; it contains no CGR logic —
it maps the sim's records onto the two ingestion endpoints and reads scores back.

Join contract (verified in B1 Step-0): the server pseudonymizes the RAW `invoice_id` identically on
the decision (`invoice_id`) and the outcome (`invoice_ref`). So we POST the SAME raw id on both
sides; do NOT pre-pseudonymize. (The DoD's live join-verify proves this resolves.)
"""
from __future__ import annotations

import os

import httpx

from meridian.entities import Decision, Outcome
from meridian.scorer import DecisionReceipt, ReputationView

_DEFAULT_UA = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


class GrafomemConfigError(RuntimeError):
    pass


class GrafomemScorer:
    """A `Scorer` backed by the live Grafomem API. Construct from ENV via `from_env()`."""

    def __init__(self, base_url: str, api_key: str, *, user_agent: str | None = None,
                 timeout: float = 40.0, transport: httpx.BaseTransport | None = None):
        if not base_url or not api_key:
            raise GrafomemConfigError("base_url and api_key are required (set them via ENV)")
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base, timeout=timeout, transport=transport,   # transport: test injection only
            headers={"X-API-Key": api_key, "Content-Type": "application/json",
                     "User-Agent": user_agent or os.environ.get("MERIDIAN_HTTP_USER_AGENT", _DEFAULT_UA)},
        )

    @classmethod
    def from_env(cls) -> "GrafomemScorer":
        base = os.environ.get("MERIDIAN_GRAFOMEM_API", "")
        key = os.environ.get("MERIDIAN_GRAFOMEM_API_KEY", "")
        if not base or not key:
            raise GrafomemConfigError(
                "MERIDIAN_GRAFOMEM_API and MERIDIAN_GRAFOMEM_API_KEY must be set (see .env.example)")
        return cls(base, key)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GrafomemScorer":
        return self

    def __exit__(self, *a) -> None:
        self.close()

    # ── Scorer protocol ───────────────────────────────────────────────────────
    def post_decision(self, decision: Decision) -> DecisionReceipt:
        r = self._client.post("/v1/governed/decisions", json={
            "decision": decision.decision,
            "reason": decision.reason,
            "invoice_id": decision.invoice_id,             # RAW id — server pseudonymizes it
            "context": decision.context,
            "model_id": decision.model_id,
            "agent_handle": decision.agent_handle,
            "verifiability_tag": decision.verifiability_tag,
            "agent_key": decision.agent_key,
        })
        r.raise_for_status()
        rec = (r.json() or {}).get("decision_record", {})
        return DecisionReceipt(
            raw_invoice_id=decision.invoice_id,
            decision_id=rec.get("decision_id"),
            invoice_ref=rec.get("invoice_id"),             # the pseudonymized ref the server stored
            accepted=True,
        )

    def post_outcome(self, outcome: Outcome) -> None:
        r = self._client.post("/v1/governed/outcomes", json={
            "invoice_ref": outcome.invoice_ref,            # SAME raw id as the decision's invoice_id
            "outcome": outcome.outcome,
            "outcome_date": outcome.outcome_date,
            "amount_recovered": outcome.amount_recovered,
            "source": outcome.source,
        })
        r.raise_for_status()

    def post_outcomes_bulk(self, outcomes: list[Outcome]) -> int:
        if not outcomes:
            return 0
        r = self._client.post("/v1/governed/outcomes/bulk", json=[{
            "invoice_ref": o.invoice_ref, "outcome": o.outcome, "outcome_date": o.outcome_date,
            "amount_recovered": o.amount_recovered, "source": o.source,
        } for o in outcomes])
        r.raise_for_status()
        return len(outcomes)

    def reputation(self) -> list[ReputationView]:
        r = self._client.get("/v1/cgr/scores")
        r.raise_for_status()
        out: list[ReputationView] = []
        for s in (r.json() or {}).get("scores", []):
            out.append(ReputationView(
                agent_key=s.get("subject_key") or "",
                agent_handle=s.get("agent_handle"),
                cgr_score=float(s.get("cgr_score", 0.0)),
                confidence=float(s.get("confidence", 0.0)),
                n_resolved=int(s.get("n_resolved", 0)),
                n_pending=int(s.get("n_pending", 0)),
            ))
        return out
