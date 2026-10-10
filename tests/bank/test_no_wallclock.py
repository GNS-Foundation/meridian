"""BANK-005-12: no wall clock, uuid4 or stdlib random on the content path (allow-list: the CLI default episode name)."""
from __future__ import annotations

import pathlib
import re

_PKG = pathlib.Path(__file__).resolve().parents[2] / "meridian" / "bank"
_FORBIDDEN = re.compile(r"datetime\.now\(|time\.time\(|uuid4\(|^\s*import random\b|^\s*from random\b|\brandom\.(random|randint|choice|seed)\(", re.M)


def test_no_wallclock_or_unseeded_randomness_on_content_path():
    offenders = []
    for p in _PKG.rglob("*.py"):
        if p.name == "__main__.py":
            continue                        # allow-listed: default episode name only
        if _FORBIDDEN.search(p.read_text()):
            offenders.append(p.name)
    assert not offenders, offenders


def test_main_wallclock_only_for_default_episode():
    text = (_PKG / "__main__.py").read_text()
    assert text.count("datetime.now(") == 1 and "allow-listed wall clock" in text
