# MERIDIAN-BANK-002 — Generator: determinism, volumes, scenario hooks, answer key

**Status:** draft · **Depends on:** BANK-001 · **Assumptions referenced:** none (mechanics only)

## 2.1 Determinism

| Id | Requirement |
|---|---|
| BANK-002-01 | All randomness MUST derive from one integer `--seed` through `numpy.random.default_rng` and `Faker.seed`, exactly as `generative.py:62-63`. No `random`, `time`, `uuid4`, `datetime.now()` on the content path. |
| BANK-002-02 | Sub-generators MUST use **derived, named streams** so that adding a scenario does not reshuffle unrelated output: `rng_for(seed, "accounts")`, `rng_for(seed, "sct", scenario_id)`, … implemented as `default_rng(blake2b(f"meridian.bank.v1:{seed}:{label}"))` (pattern: `agents.py:29`). Golden files MUST stay stable when a *new* scenario is added that does not touch an existing stream (BANK-005-03). |
| BANK-002-03 | The sim clock MUST start at a fixed epoch (`driver.py:34` uses `2026-01-01Z`) and advance by whole business days; `--start-date` MAY override it and is part of the golden-file key. |
| BANK-002-04 | Identifiers MUST be namespaced by `--episode` (default: `s{seed}-{YYYYmmddHHMMSS}` as in `driver.py:165`); passing `--episode` explicitly MUST reproduce exact ids. |
| BANK-002-05 | The generator MUST be a pure function `generate_world(config) -> BankWorld` with no I/O; writers (BANK-004) and the answer-key exporter are the only I/O. |

## 2.2 Volume parameters (CLI and `BankConfig`)

| Id | Requirement |
|---|---|
| BANK-002-06 | `--banks N` (default 2), `--accounts N` (default 50), `--days N` (default 5 business days), `--sct-per-day-per-account λ` (Poisson, default 0.6), `--sdd-mandates N` (default 30), `--sdd-r-rate p` (default 0.08 of collections produce an R-transaction), `--mav-notices N` (default 40), `--mav-paid-rate p` (default 0.85). All defaults are starting points for Camilo (D-13). |
| BANK-002-07 | Amount distributions MUST be documented and seed-driven (Meridian uses lognormal for invoices, `generative.py:90`); v1 proposes lognormal for SCT, a mandate-fixed amount ± small noise for recurring SDD, and the notice amount for MAV. |
| BANK-002-08 | Volume parameters MUST be bounded (`--accounts ≤ 5000`, `--days ≤ 60` in v1) so a full episode with all writers completes on a laptop in under a minute; the bound is a documented constant, not a silent clamp. |

## 2.3 Scenario hooks

The scenario hook is the extension point that lets a downstream project add its own behaviour **without
forking**. It is modelled on the `Scorer` protocol (`scorer.py:42-48`): a `runtime_checkable` Protocol,
an in-repo default implementation, and discovery by name.

| Id | Requirement |
|---|---|
| BANK-002-09 | `Scenario` Protocol: `scenario_id: str`; `plan(world: BankWorldView, rng, clock) -> list[Intent]`. A scenario reads a **read-only view** of the world and returns `Intent`s; it never mutates the world or writes files. |
| BANK-002-10 | `Intent` is the generic unit of purpose: `intent_id`, `scenario_id`, `kind` (`sct_in`/`sct_out`/`sdd_collect`/`sdd_r`/`mav_issue`/`mav_pay`/`fee`), `when` (sim date), `parties` (account/holder/counterparty refs), `amount_cents`, `remittance_clean` (the intended text), `remittance_noise` (list of noise operators to apply, BANK-003-05), `expected_outcome` (e.g. `settle`, `reject:AM04`, `return:AC04`, `refund:MD06`), `links` (free-form ids a downstream project may need, e.g. its own document numbers), `tags`. |
| BANK-002-11 | The **core** turns `Intent`s into entities and movements (`materialise(intent) -> list[Movement] + instrument objects`) and is the only code that knows instrument rules (BANK-003). Scenarios never build movements directly. |
| BANK-002-12 | Scenario discovery: (a) built-in scenarios registered in `meridian.bank.scenarios.BUILTIN`; (b) third-party scenarios via Python entry points group `meridian.bank.scenarios`; (c) `--scenario pkg.module:ClassName` for ad-hoc use. A downstream project ships its own package and runs `python -m meridian.bank --scenario its.package:Scenario`. |
| BANK-002-13 | Built-in scenarios v1 (all client-agnostic): `baseline` (steady SCT in/out, fees); `sdd-lifecycle` (FRST→RCUR, one of each R-kind within rule windows); `mav-lifecycle` (issue, pay on time, pay late, expire); `remittance-noise` (clean vs noisy remittance pairs for matching tests). |
| BANK-002-14 | A built-in **bridge scenario** `receivables-bridge` MAY consume the existing `generate_market()` market (`generative.py:59`) so that each Meridian invoice can appear as an inbound SCT referencing the invoice id in the remittance — this is the only coupling to the underwriting sim and MUST be optional. |
| BANK-002-15 | Scenario ordering and RNG streams MUST make scenarios independent: scenario A's output MUST NOT change when scenario B is added or removed (test: BANK-005-03). |

## 2.4 Answer key (ground truth)

| Id | Requirement |
|---|---|
| BANK-002-16 | The answer key MUST link **every movement** to its `Intent`: `movement_id → {intent_id, scenario_id, kind, expected_outcome, remittance_clean, remittance_emitted, links, counterparty truth}`; plus the SDD collection ↔ R-transaction chains and MAV notice ↔ payment pairs. |
| BANK-002-17 | The answer key MUST be written **separately from outputs**: `episodes/<episode>.bank.answer_key.json`. Emitted format files go under `out/<episode>/<format>/…`. No field of the answer key may be derivable from the emitted files alone except through the match the downstream project is meant to perform. |
| BANK-002-18 | The answer key MUST stay out of git: `.gitignore` already ignores `episodes/` (`.gitignore:13`); the `out/` directory MUST be added to `.gitignore` in the implementation PR. |
| BANK-002-19 | Hard cases MUST be labelled explicitly in the answer key, not implied: `match_class ∈ {one_to_one, one_to_many, many_to_one, partial, duplicate, unmatched_noise}`. |
| BANK-002-20 | The answer key MUST contain a `generator` block: `seed`, `episode`, `start_date`, config, list of scenarios with versions, spec version, and the `A-nn` assumptions in force at generation time, so a downstream result can be audited against the spec state that produced it. |
