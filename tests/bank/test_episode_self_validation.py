"""BANK-005-28: a generated episode, once every format is emitted (A-02 writer allowed), passes every applicable
validator with zero rule ids. BANK-005-29: the probe that proves the check is not vacuous (IBAN check digits
computed with 97 instead of 98 must make the self-validation fail, then pass again once restored).

XML/XSD validation (BANK-005-07) is a separate test that skips naming D-02 when the schemas are unavailable."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from meridian.bank import identifiers
from meridian.bank.formats import REGISTRY, Selection
from meridian.bank.generator import BankConfig, generate_world
from meridian.bank.scenarios import BUILTIN, load_scenario
from meridian.bank.validate import (XsdUnavailable, check_answer_key_row, check_bic, check_cbi_rh, check_iban, check_mav_id, check_pain002,
                                    check_remittance, check_sdd, check_xml_xsd)
from meridian.bank.world import BankWorld

SEEDS = (11, 23, 37)
XML_MESSAGE = {"camt053": "camt.053.001.08", "camt054": "camt.054.001.08", "pain002": "pain.002.001.10"}
IBAN_RE = re.compile(r"<IBAN>([^<]*)</IBAN>")
BIC_RE = re.compile(r"<(?:BICFI|BIC)>([^<]*)</(?:BICFI|BIC)>")


def generate_episode(seed: int, out_dir: Path) -> tuple[BankWorld, list[Path]]:
    """All built-in scenarios, every registered writer, assumed layouts allowed (the CLI's --allow-assumed-layouts)."""
    cfg = BankConfig(seed=seed, episode=f"selfval-{seed}", banks=2, accounts=10, days=3, sdd_mandates=8, mav_notices=8, scenarios=sorted(BUILTIN))
    world = generate_world(cfg, [load_scenario(s) for s in cfg.scenarios])
    files: list[Path] = []
    for fid, cls in sorted(REGISTRY.items()):
        sink = cls()
        if "A-02" in cls.assumptions:
            sink.allow_assumed_layouts = True
        files += sink.emit(world.view(), Selection(), out_dir)
    return world, files


def read_artefact(p: Path) -> str:
    if p.suffix == ".txt":
        with open(p, encoding="latin-1", newline="") as fh:   # CBI records are CRLF-terminated; keep them
            return fh.read()
    return p.read_text(encoding="utf-8")


def violations_of(world: BankWorld, files: list[Path]) -> dict[str, list[str]]:
    """Subject -> sorted rule ids. Empty dict == the episode self-validates. XSD is NOT part of this (see test below)."""
    out: dict[str, list[str]] = {}

    def add(subject: str, v: list[str]) -> None:
        if v:
            out[subject] = sorted(set(v))

    for b in world.banks.values():
        add(f"bank {b.bank_id} bic", check_bic(b.bic))
    for a in world.accounts.values():
        add(f"account {a.account_id} iban", check_iban(a.iban))
    for m in world.movements:
        add(f"movement {m.movement_id} remittance", check_remittance(m.remittance_unstructured))
        if m.counterparty and m.counterparty.iban:
            add(f"movement {m.movement_id} counterparty iban", check_iban(m.counterparty.iban))
        if m.counterparty and m.counterparty.bic:
            add(f"movement {m.movement_id} counterparty bic", check_bic(m.counterparty.bic))
    for c in world.collections.values():
        add(f"collection {c.collection_id} remittance", check_remittance(c.remittance_unstructured))
        for k, r in enumerate(c.r_transactions):
            add(f"collection {c.collection_id} r-transaction {k} ({r.kind} {r.reason_code})", check_sdd(c.model_dump(), r.model_dump()))
    for n in world.mav_notices.values():
        add(f"mav {n.mav_id}", check_mav_id(n.mav_id))
    collections = {cid: c.model_dump() for cid, c in world.collections.items()}
    movements = [m.model_dump() for m in world.movements]
    mavs = {mid: n.model_dump() for mid, n in world.mav_notices.items()}
    for row in world._answer_rows:
        add(f"answer-key row {row['movement_id']}", check_answer_key_row(row, collections=collections, movements=movements, mavs=mavs, rows=world._answer_rows))
    for p in files:
        text = read_artefact(p)
        fid = p.parent.name if p.parent.name in REGISTRY else p.parent.parent.name
        if fid == "cbi-rh":
            add(str(p), check_cbi_rh(text))
        elif fid == "pain002":
            add(str(p), check_pain002(text))
        if p.suffix == ".xml":
            for iban in IBAN_RE.findall(text):
                add(f"{p} iban {iban}", check_iban(iban))
            for bic in BIC_RE.findall(text):
                add(f"{p} bic {bic}", check_bic(bic))
    return out


def _describe(v: dict[str, list[str]]) -> str:
    return "\n".join(f"  {k}: {', '.join(r)}" for k, r in sorted(v.items()))


@pytest.mark.parametrize("seed", SEEDS)
def test_episode_self_validates(seed, tmp_path):
    world, files = generate_episode(seed, tmp_path / f"s{seed}")
    assert {p.parent.name if p.parent.name in REGISTRY else p.parent.parent.name for p in files} == set(REGISTRY), "every registered writer must emit"
    assert world.accounts and world.movements and world.collections and world.mav_notices
    v = violations_of(world, files)
    assert not v, f"episode seed={seed} has {len(v)} validator violations:\n{_describe(v)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_episode_xml_validates_against_xsd(seed, tmp_path):
    """BANK-005-07 part of BANK-005-28: skipped (not passed) when the ISO 20022 schemas are unavailable (D-02)."""
    _, files = generate_episode(seed, tmp_path / f"x{seed}")
    xml = [p for p in files if p.suffix == ".xml"]
    assert xml
    v: dict[str, list[str]] = {}
    for p in xml:
        fid = p.parent.name if p.parent.name in REGISTRY else p.parent.parent.name
        try:
            r = check_xml_xsd(read_artefact(p), XML_MESSAGE[fid])
        except XsdUnavailable as e:
            pytest.skip(f"XSD validation unavailable (D-02): {e}")
        if r:
            v[str(p)] = r
    assert not v, _describe(v)


def test_probe_iban_check_digits_with_97_breaks_self_validation(monkeypatch, tmp_path):
    """BANK-005-29. `generator` binds `iban_it` by name at import, so the probe patches `identifiers.iban_it` and every
    loaded meridian.bank module that re-bound the same object; both are undone by `monkeypatch.undo()`."""
    original = identifiers.iban_it

    def iban_it_97(abi: str, cab: str, conto: str) -> str:
        body = f"{abi}{cab}{conto}"
        bban = identifiers.cin_italiano(body) + body
        check = 97 - identifiers.mod97(bban + "IT00")      # wrong base: ISO 7064 uses 98
        return f"IT{check:02d}{bban}"

    monkeypatch.setattr(identifiers, "iban_it", iban_it_97)
    for name, mod in list(sys.modules.items()):
        if name.startswith("meridian.bank") and mod is not identifiers and getattr(mod, "iban_it", None) is original:
            monkeypatch.setattr(mod, "iban_it", iban_it_97)
    with pytest.raises(AssertionError) as info:
        test_episode_self_validates(SEEDS[0], tmp_path / "broken")
    assert "IBAN-MOD97" in str(info.value), "the self-validation failed, but not because of the IBAN check digits"

    monkeypatch.undo()
    assert identifiers.iban_it is original
    test_episode_self_validates(SEEDS[0], tmp_path / "restored")
