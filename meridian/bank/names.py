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
    """True when every token of `name` (case/accents as in the list) belongs to the curated given or surname lists
    (initials like 'F.' are allowed only as the first letter of a curated given name)."""
    c = curated()
    tokens = [t for t in name.replace("-", " ").split() if t]
    given = {g.lower() for g in c["given"] for g in g.split()}
    surn = {s.lower() for s in c["surnames"]}
    initials = {g[0].lower() + "." for g in c["given"]}
    return bool(tokens) and all(t.lower() in given or t.lower() in surn or t.lower() in initials for t in tokens)


def organisation_name(rng: np.random.Generator) -> str:
    c = curated()
    return c["organisations"][int(rng.integers(0, len(c["organisations"])))]
