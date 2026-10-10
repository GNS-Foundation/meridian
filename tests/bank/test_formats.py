"""OutputSink registry (BANK-004-01/02), the A-02 gate (BANK-004-30), the read-only view (BANK-004-04) and the CLI."""
from __future__ import annotations

import json

import pytest

from meridian.bank.__main__ import main
from meridian.bank.formats import REGISTRY, OutputSink, Selection
from meridian.bank.formats.cbi_im import AssumedLayoutRefused
from meridian.bank.generator import BankConfig, generate_world
from meridian.bank.world import BankWorldView


def test_registry_declares_sources_and_assumptions():
    assert set(REGISTRY) == {"cbi-rh", "cbi-im", "camt053", "camt054", "pain002"}
    for cls in REGISTRY.values():
        assert isinstance(cls(), OutputSink) and cls.sources and cls.version and isinstance(cls.assumptions, list)


def test_cbi_im_refuses_without_flag(tmp_path):
    w = generate_world(BankConfig(seed=1, episode="im", banks=1, accounts=3, days=2, sdd_mandates=0, mav_notices=3, scenarios=["mav-lifecycle"]))
    with pytest.raises(AssumedLayoutRefused):
        REGISTRY["cbi-im"]().emit(w.view(), Selection(), tmp_path)


def test_view_exposes_no_answer_key():
    w = generate_world(BankConfig(seed=1, episode="v", banks=1, accounts=2, days=1, sdd_mandates=0, mav_notices=0, scenarios=["baseline"]))
    v = w.view()
    assert isinstance(v, BankWorldView) and not hasattr(v, "_answer_rows") and not hasattr(v, "answer_key")


def test_cli_describe_formats(capsys):
    main(["--describe-formats"])
    rows = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert {r["format_id"] for r in rows} == set(REGISTRY) and all("assumptions" in r for r in rows)


def test_cli_episode_run(tmp_path, capsys):
    main(["--seed", "5", "--episode", "cli", "--banks", "1", "--accounts", "3", "--days", "2", "--sdd-mandates", "2", "--mav-notices", "2",
          "--out", str(tmp_path / "out"), "--episodes-dir", str(tmp_path / "episodes"), "--format", "cbi-rh,camt053,cbi-im"])
    out = capsys.readouterr().out
    assert "assumed layout (A-02)" in out and (tmp_path / "episodes" / "cli.bank.answer_key.json").exists()
    assert any(p.suffix == ".txt" for p in (tmp_path / "out" / "cli" / "cbi-rh").iterdir())
