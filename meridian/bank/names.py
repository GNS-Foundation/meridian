"""Curated fictional names (BANK-001-06, D-09 option a) and organisation names.

Person display names come ONLY from meridian/bank/data/fictional_names.json (repo-owned, reviewed). Organisation
names use Faker `company()` (firmographic flavour, never a person generator — tests/test_pii_free.py).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

_DATA = Path(__file__).resolve().parent / "data" / "fictional_names.json"


@lru_cache(maxsize=1)
def curated() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def person_name(rng: np.random.Generator) -> str:
    c = curated()
    return f"{c['given'][int(rng.integers(0, len(c['given'])))]} {c['surnames'][int(rng.integers(0, len(c['surnames'])))]}"


def is_curated_person_name(name: str) -> bool:
    """True when every token of `name` is BUILT FROM the curated given/surname lists (BANK-001-06, BANK-005-31):
    exact match, accent-insensitive match (after `strip_accents()`), an initial `G.` of a curated given name, or a
    truncation prefix (>= 3 chars, after `truncate_to_yyy_width()`) of a curated token. Any other token fails."""
    from meridian.bank.noise import strip_accents
    c = curated()
    norm = lambda t: strip_accents(t).lower()
    given = {norm(g) for gg in c["given"] for g in gg.split()}
    surn = {norm(s) for s in c["surnames"]}
    initials = {norm(g)[0] + "." for g in c["given"]}
    pool = given | surn
    tokens = [norm(t) for t in name.replace("-", " ").split() if t]
    def ok(t: str) -> bool:
        return t in pool or t in initials or (len(t) >= 3 and any(w.startswith(t) for w in pool))
    return bool(tokens) and all(ok(t) for t in tokens)


def organisation_name(rng: np.random.Generator) -> str:
    c = curated()
    return c["organisations"][int(rng.integers(0, len(c["organisations"])))]
