"""BANK-005-10/11: same (seed, episode, start_date, config, scenarios) -> byte-identical files and answer key."""
from __future__ import annotations

import json
from pathlib import Path

from meridian.bank.answer_key import build_answer_key
from meridian.bank.formats import REGISTRY, Selection
from meridian.bank.generator import BankConfig, generate_world, generator_block
from meridian.bank.scenarios import load_scenario

CFG = dict(episode="det", banks=2, accounts=8, days=3, sdd_mandates=6, mav_notices=8, scenarios=["baseline", "sdd-lifecycle", "mav-lifecycle", "remittance-noise"])


def run(seed: int, out: Path) -> tuple[dict[str, bytes], str]:
    cfg = BankConfig(seed=seed, **CFG)
    scen = [load_scenario(s) for s in cfg.scenarios]
    w = generate_world(cfg, scen)
    files: dict[str, bytes] = {}
    for fid, cls in REGISTRY.items():
        sink = cls(); sink.allow_assumed_layouts = True
        for p in sink.emit(w.view(), Selection(), out / str(seed)):
            files[str(p.relative_to(out / str(seed)))] = p.read_bytes()
    ak = json.dumps(build_answer_key(w, generator_block(cfg, cfg.scenarios)), sort_keys=True, ensure_ascii=False)
    return files, ak


def test_same_seed_byte_identical(tmp_path):
    f1, a1 = run(42, tmp_path / "a"); f2, a2 = run(42, tmp_path / "b")
    assert f1.keys() == f2.keys() and len(f1) > 0
    assert all(f1[k] == f2[k] for k in f1)
    assert a1 == a2


def test_different_seed_changes_content(tmp_path):
    f1, a1 = run(1, tmp_path / "a"); f2, a2 = run(2, tmp_path / "b")
    assert a1 != a2
