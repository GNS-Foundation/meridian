# MERIDIAN-BANK-005 — Acceptance: golden files, determinism, non-vacuity probes

**Status:** draft · **Depends on:** BANK-001..004 · **Assumptions referenced:** A-02 (IM golden files are provisional)

Meridian already enforces determinism (`tests/test_determinism.py`), PII-freedom (`tests/test_pii_free.py`)
and the moat boundary (`tests/test_boundary.py`). This block extends those three and adds golden files and
non-vacuity probes. All tests run offline with `pytest` (dev extra, `pyproject.toml:16`).

## 5.1 Golden files

| Id | Requirement |
|---|---|
| BANK-005-01 | For every `OutputSink` there MUST be at least one golden file under `tests/golden/<format_id>/<case>.<ext>` generated from a **pinned** `(seed, episode, start_date, config, scenarios)` tuple recorded in `tests/golden/<format_id>/<case>.meta.json`. Golden files are **public test fixtures**: they contain only synthetic identifiers and no answer-key content (BANK-000-01, BANK-004-04). |
| BANK-005-02 | `test_golden_<format>` MUST regenerate the file from the pinned tuple and assert **byte-identical** equality with the committed golden file (not "semantically equal"). |
| BANK-005-03 | `test_scenario_independence` MUST generate the `baseline` scenario alone and `baseline + <other>` and assert that the `baseline` stream's movements and the `baseline`-only golden slice are byte-identical (BANK-002-02, BANK-002-15). |
| BANK-005-04 | Golden files for layouts marked ASSUMPTION (CBI IM, A-02) MUST live under `tests/golden/_assumed/` and the test MUST be marked `xfail(strict=False, reason="A-02")` so the suite stays green while clearly separating assumed from verified layouts. |

## 5.2 Determinism

| Id | Requirement |
|---|---|
| BANK-005-10 | `test_same_seed_episode_byte_identical`: two runs of `generate_world` + all writers with the same tuple MUST produce byte-identical files and answer key (pattern: `tests/test_determinism.py:16-26`). |
| BANK-005-11 | `test_different_seed_changes_content` (pattern: `tests/test_determinism.py:29-32`). |
| BANK-005-12 | `test_no_wallclock_on_content_path`: static scan of `meridian/bank/**` forbidding `datetime.now(`, `time.time(`, `uuid.uuid4(`, `random.` (stdlib) outside an allow-list (CLI default episode name only). |

## 5.3 Validators and non-vacuity probes

A validator that never fails is worthless. Every validation rule MUST have a probe that **breaks it on
purpose, watches it fail, and restores**. Mechanically: take the golden (or a freshly generated) artefact,
apply one mutation, assert the validator raises with the expected rule id, then re-validate the unmutated
artefact and assert it passes.

| Id | Requirement |
|---|---|
| BANK-005-20 | Every validator rule MUST have a stable `rule_id` (`CBI-RH-LEN-120`, `CBI-RH-61-64-DATE`, `IBAN-MOD97`, `SEPA-RMT-140`, `SDD-REFUND-8W`, …) surfaced in the raised error. |
| BANK-005-21 | `tests/test_probes.py` MUST be **table-driven**: one row per `rule_id` = `(artefact factory, mutation, expected rule_id)`. A test MUST fail if a validator exposes a `rule_id` with no probe row (coverage of validators by probes = 100 %). |
| BANK-005-22 | Minimum probe set for CBI RH (BANK-004-23): truncate a record to 119 chars; swap record 64 date vs 61; off-by-one closing balance; causale `13` with blank cheque number; six 63 records; `RI2` without `RI1`; EF record count off by one; non-numeric amount. |
| BANK-005-23 | Minimum probe set for identifiers: IBAN with one digit changed (mod-97 fails); CIN letter changed; 26-char IBAN; BIC of 9 chars; MAV id of 16 digits. |
| BANK-005-24 | Minimum probe set for SEPA: `Ustrd` of 141 chars; refund dated 8 weeks + 1 day after settlement with `MD06`; refund `MD01` dated 13 months + 1 day; reject carrying a code whose S4 column does not include "Reject" (e.g. `MD06`); return before settlement; `OrgnlMsgNmId` mismatch. |
| BANK-005-25 | Minimum probe set for the answer key: a movement with no `intent_id`; an SDD refund whose original collection is not `settled`; a `paid` MAV with no credit movement. |
| BANK-005-26 | XML: a mutated element name MUST fail XSD validation (BANK-005-07); the probe is skipped (not passed) when XSDs are unavailable, and the skip reason names D-02. |

## 5.4 Existing guardrails extended

| Id | Requirement |
|---|---|
| BANK-005-30 | `tests/test_boundary.py` forbidden-identifier scan and import scan MUST include `meridian/bank/**` (BANK-000-04). |
| BANK-005-31 | `tests/test_pii_free.py::test_source_never_calls_faker_pii_generators` MUST include `meridian/bank/**`; if D-09 allows person names for holders, the allow-list MUST be explicit (one function, one file) and the emitted-payload scan MUST still forbid emails and government-id patterns. |
| BANK-005-32 | A new `test_client_agnostic.py` MUST fail if any file under `meridian/bank/**`, `tests/golden/**` or `spec/**` contains a string from a maintained deny-list of real institution identifiers (real ABI codes list is *not* vendored; the deny-list holds only names/patterns Camilo supplies, D-10) or any of the client names recorded in `OPEN-QUESTIONS.md` "belongs in Ulissy". |

## 5.5 XSD validation (optional dev dependency)

| Id | Requirement |
|---|---|
| BANK-005-07 | camt.053/054 and pain.002 outputs MUST validate against the official ISO 20022 XSD of the chosen version. Proposed dev-only dependency: `xmlschema` (pure Python) **or** `lxml`; neither is a runtime dependency (BANK-000-10). XSD files are **not** committed until D-02 is decided; the test downloads them to a cache dir when `MERIDIAN_ISO20022_XSD_DIR` is set, otherwise skips with a reason. |

## 5.6 Definition of Done for the implementation PR (not this spec PR)

- All BANK-005 tests green except the `xfail` rows explicitly tied to open `A-nn` ids.
- `spec/OPEN-QUESTIONS.md` updated: each `A-nn` either marked **verified (source, date)** and removed from code markers, or still open and reflected by an `xfail`/`--allow-assumed-layouts` gate.
- Golden files regenerated only through a documented `make golden` step that prints the pinned tuple; a golden change in a PR MUST be accompanied by the reason in the PR body.
