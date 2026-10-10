"""BANK-005-33: the PII scan of tests/test_pii_free.py catches a Faker name call planted in a copy of meridian/bank/."""
from __future__ import annotations

import shutil

import pytest

from tests import test_pii_free as tpf
from tests.bank.corpus_fixture import REPO


def test_probe_faker_name_in_bank_package_is_caught(tmp_path, monkeypatch):
    copy = tmp_path / "meridian"
    shutil.copytree(REPO / "meridian" / "bank", copy / "bank")
    monkeypatch.setattr(tpf, "_PKG", copy)
    tpf.test_source_never_calls_faker_pii_generators()               # clean copy passes
    planted = copy / "bank" / "_planted.py"
    planted.write_text("from faker import Faker\nfk = Faker()\nNAME = fk.na" + "me()\n")   # split so this file never contains the literal
    with pytest.raises(AssertionError):
        tpf.test_source_never_calls_faker_pii_generators()           # planted call is caught
    planted.unlink()
    tpf.test_source_never_calls_faker_pii_generators()               # restored copy passes again


def test_emitted_person_names_are_curated():
    from meridian.bank.generator import BankConfig, generate_world
    from meridian.bank.names import is_curated_person_name
    w = generate_world(BankConfig(seed=3, episode="pii", banks=1, accounts=12, days=2, sdd_mandates=3, mav_notices=3, scenarios=["baseline", "remittance-noise"]))
    for m in w.movements:
        if m.counterparty and m.counterparty.holder_id and w.holders[m.counterparty.holder_id].kind == "person":
            assert is_curated_person_name(m.counterparty.name), m.counterparty.name
