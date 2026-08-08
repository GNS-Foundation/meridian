"""PII-free by construction. Two guarantees:
  (1) nothing the sim POSTS contains unambiguous PII (emails / SSNs);
  (2) the sim never calls a Faker PII generator (name/email/ssn/address/phone) — it uses Faker only
      for firmographic labels (company/country). Financial fields (amounts, ISO dates, tenors) are
      legitimately digit-heavy and are NOT PII, so we don't regex-scan them for phone-like runs.
Plus the structural check that a posted decision's context is observable-features-only (no truth).
"""
from __future__ import annotations

import json
import pathlib
import re

from meridian.driver import run_episode
from meridian.scorer import LocalScorer

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PKG = pathlib.Path(__file__).resolve().parents[1] / "meridian"


def _episode_blob() -> str:
    s = LocalScorer()
    run_episode(s, seed=3, n_agents=10, episode="pii", n_clients=25, n_invoices=120, write_ground_truth=False)
    return json.dumps([d.model_dump() for d in s.decisions] + [o.model_dump() for o in s.outcomes], default=str)


def test_no_email_or_ssn_in_posted_records():
    blob = _episode_blob()
    assert not _EMAIL.search(blob), "posted payload contains an email"
    assert not _SSN.search(blob), "posted payload contains an SSN"


def test_source_never_calls_faker_pii_generators():
    pii_methods = [".name(", ".first_name(", ".last_name(", ".email(", ".ssn(", ".phone",
                   ".address(", ".street_address(", ".date_of_birth("]
    offenders = []
    for p in _PKG.rglob("*.py"):
        text = p.read_text()
        for m in pii_methods:
            if m in text:
                offenders.append(f"{p.name}: Faker{m}")
    assert not offenders, f"sim calls a Faker PII generator: {offenders}"


def test_context_is_features_only_no_truth_no_pii():
    s = LocalScorer()
    run_episode(s, seed=3, n_agents=10, episode="pii", n_clients=25, n_invoices=120, write_ground_truth=False)
    allowed = {"amount", "currency", "tenor_days", "sector", "risk_signal", "client_id"}
    for d in s.decisions:
        assert set(d.context.keys()) <= allowed, f"context leaked unexpected keys: {set(d.context) - allowed}"
        assert "true_pay_prob" not in d.context and "true_outcome" not in d.context and "capability" not in d.context
