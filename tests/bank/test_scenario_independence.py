"""BANK-002-15 / BANK-005-03: scenario A's movements and answer-key rows do not change when scenario B is added."""
from __future__ import annotations

from meridian.bank.generator import BankConfig, generate_world
from meridian.bank.scenarios import load_scenario


def _baseline_slice(scenarios):
    cfg = BankConfig(seed=42, episode="ind", banks=2, accounts=6, days=3, sdd_mandates=4, mav_notices=5, scenarios=scenarios)
    w = generate_world(cfg, [load_scenario(s) for s in scenarios])
    movs = sorted((m.model_dump() for m in w.movements if m.instrument_ref.startswith("baseline-")), key=lambda m: m["movement_id"])
    rows = sorted((r for r in w._answer_rows if r["scenario_id"] == "baseline"), key=lambda r: r["movement_id"])
    return movs, rows


def test_baseline_unchanged_when_other_scenarios_are_added():
    alone = _baseline_slice(["baseline"])
    with_others = _baseline_slice(["baseline", "remittance-noise", "sdd-lifecycle", "mav-lifecycle"])
    assert alone[0] and alone == with_others
