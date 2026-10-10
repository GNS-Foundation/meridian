"""Derived, named RNG streams (BANK-002-01/02): every stream is `default_rng(blake2b("meridian.bank.v1:{seed}:{label}"))`,
so adding a scenario never reshuffles an unrelated stream and golden files stay stable."""
from __future__ import annotations

import hashlib

import numpy as np


def stream_seed(seed: int, *labels: str) -> int:
    digest = hashlib.blake2b(f"meridian.bank.v1:{seed}:{':'.join(labels)}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def rng_for(seed: int, *labels: str) -> np.random.Generator:
    return np.random.default_rng(stream_seed(seed, *labels))
