"""Answer key (BANK-002-16..20): written separately from outputs to episodes/<episode>.bank.answer_key.json, sorted keys."""
from __future__ import annotations

import json
from pathlib import Path

from meridian.bank.world import BankWorld


def build_answer_key(w: BankWorld, generator: dict) -> dict:
    return {"generator": generator, "movements": sorted(w._answer_rows, key=lambda r: r["movement_id"]),
            "sdd_chains": w._sdd_chains, "mav_pairs": w._mav_pairs, "match_classes": sorted({r.get("match_class", "one_to_one") for r in w._answer_rows})}


def write_answer_key(w: BankWorld, generator: dict, episodes_dir: str | Path = "episodes") -> Path:
    p = Path(episodes_dir) / f"{w.episode}.bank.answer_key.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(build_answer_key(w, generator), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
