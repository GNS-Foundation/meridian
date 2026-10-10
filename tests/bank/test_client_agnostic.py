"""BANK-005-32: client-agnostic check. The deny-list is never stored in this public repo; it is read from
MERIDIAN_DENYLIST_FILE (case-insensitive whole-word, as the corpus lint does). Unset -> skipped with a reason."""
from __future__ import annotations

import os
import pathlib
import re

import pytest

from tests.bank.corpus_fixture import REPO

SCAN = [REPO / "meridian" / "bank", REPO / "tests" / "bank", REPO / "corpus" / "bank", REPO / "spec"]


def test_no_deny_listed_term_in_bank_package_tests_corpus_or_spec():
    path = os.environ.get("MERIDIAN_DENYLIST_FILE")
    if not path:
        pytest.skip("MERIDIAN_DENYLIST_FILE unset: the deny-list is kept outside this public repository (BANK-005-32)")
    terms = [t.strip() for t in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    pats = [(t, re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)", re.I)) for t in terms]
    hits = []
    for root in SCAN:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in (".py", ".json", ".md", ".txt", ".xml", ".yaml"):
                text = p.read_text(encoding="utf-8", errors="replace")
                hits += [f"{p.relative_to(REPO)}: {t}" for t, rx in pats if rx.search(text)]
    assert not hits, hits
