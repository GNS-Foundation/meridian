"""Reports the ASSUMPTION ids (A-nn) carried by corpus vectors in the terminal summary. They are information for the
reviewer, never a tolerance: every vector, assumed or not, must pass (PR B)."""
from __future__ import annotations

import pytest

from tests.bank.corpus_fixture import MANIFEST

_ASSUMED = {m["id"]: m["assumptions"] for m in MANIFEST["vectors"] if m["kind"] == "assumed"}


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _ASSUMED:
        return
    passed = {r.nodeid for r in terminalreporter.stats.get("passed", [])}
    failed = {r.nodeid for r in terminalreporter.stats.get("failed", [])}
    rows = []
    for vid, aids in sorted(_ASSUMED.items()):
        node = next((n for n in passed | failed if f"[{vid}[" in n or f"[{vid}]" in n), None)
        if node:
            rows.append(f"{vid}: {', '.join(aids)} -> {'passed' if node in passed else 'FAILED'}")
    if rows:
        terminalreporter.write_sep("-", "corpus vectors depending on spec ASSUMPTIONS (reported, not tolerated)")
        for r in rows:
            terminalreporter.write_line(r)
