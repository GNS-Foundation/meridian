# MERIDIAN-BANK-000 — Scope, non-goals, backward compatibility

**Status:** draft · **Depends on:** nothing · **Assumptions referenced:** none

## 0.1 Purpose

Meridian today is a receivables-financing *underwriting* simulator: it mints synthetic agents, invoices
and outcomes, and posts `Decision`/`Outcome` records to Grafomem behind a swappable `Scorer`
(`README.md:3-19`). It has no bank accounts, movements, statements or payment instruments
(MERIDIEN_BRIEF audit, 2026-10-10).

This block defines a **virtual bank** extension: a deterministic generator of synthetic banks, accounts,
account holders, balances and movements, driven by payment instruments (SCT, SDD with R-transactions,
MAV), emitted through pluggable output formats (CBI RH, CBI IM, camt.053/054, pain.002), with a
separately stored answer key that links every movement to the purpose that produced it.

The extension exists so that **any** integration project (reconciliation engines, treasury tooling,
governed-agent demos) can obtain realistic, reproducible bank-side files without touching a real bank
and without client data.

## 0.2 Requirements

| Id | Requirement |
|---|---|
| BANK-000-01 | The virtual bank MUST be **client-agnostic**: no client names, no sector- or utility-specific scenarios, no real institution identifiers (ABI, BIC, IBAN), no personal data, anywhere in code, fixtures or golden files. |
| BANK-000-02 | The virtual bank MUST live in a new sub-package `meridian.bank` inside `GNS-Foundation/meridian`; the existing package modules (`entities.py`, `generative.py`, `agents.py`, `fraud.py`, `scorer.py`, `grafomem_adapter.py`, `driver.py`) MUST NOT be modified by the extension except to add optional, backward-compatible imports. |
| BANK-000-03 | Every existing test in `tests/` MUST keep passing unchanged. `python -m meridian.driver` MUST keep its current CLI, defaults, outputs and determinism (`tests/test_determinism.py`). |
| BANK-000-04 | The existing moat boundary MUST hold for the new package: `tests/test_boundary.py::test_no_cgr_or_vault_or_field_implementation_in_package` and `::test_package_never_imports_grafomem_internals` MUST be extended to cover `meridian/bank/**`. The virtual bank computes **no reputation** and imports nothing from `aml`, `grafomem`, `cgr`. |
| BANK-000-05 | The virtual bank MUST be usable **offline**: a full episode (generate → emit all formats → write answer key) MUST run with no network access and no credentials. Posting to Grafomem, if ever wanted, MUST go through the existing `Scorer` protocol or a sibling protocol; it is out of scope for this block. |
| BANK-000-06 | The virtual bank MUST reuse Meridian's existing patterns rather than replace them: NumPy `default_rng(seed)` + seeded Faker for determinism (`generative.py:62-63`); episode-namespaced identifiers for idempotency (`driver.py:10-12,165`); JSON answer key under `episodes/` kept out of git (`driver.py:243-256`, `.gitignore:9-14`); PII-free-by-construction tests (`tests/test_pii_free.py`). |
| BANK-000-07 | The virtual bank MUST be **standards-first**: every emitted layout cites its source document and version in code comments and in `spec/README.md`'s source register; any layout element not verified against its source MUST carry an `A-nn` ASSUMPTION marker in code and in `OPEN-QUESTIONS.md`. |
| BANK-000-08 | Scenario-specific behaviour (which movements happen, with which remittance text, with which errors) MUST be injectable through the scenario hook of BANK-002 so a downstream project can add its own scenarios **without forking** this repository. |
| BANK-000-09 | The extension MUST NOT introduce a database. Runtime state is in-memory; persistence is file-based (JSON answer key, emitted format files). See BANK-001-20..22 and D-01. |
| BANK-000-10 | The extension MUST remain licensed under the repository licence (Apache-2.0 per PR #2) and MUST NOT vendor third-party documents (CBI/EPC PDFs, ISO XSDs) without a licensing decision (D-02). |

## 0.3 Non-goals (v1)

- Real bank connectivity, real CBI/SEPA network participation, real IBAN/BIC directories.
- Interbank messages (pacs.*), SCT Inst, SDD B2B (only SDD Core is in scope), SEPA Request-to-Pay.
- SDD **Refusal** and **Request for cancellation** flows (A-11).
- RiBa, bollettini postali, F24, cheques beyond the CBI causale needed for golden realism.
- pagoPA settlement flows (D-05 decided: a *generic* pagoPA FdR instrument is a future Foundation block **BANK-006**, separate PR; not v1).
- Fraud/AML typologies on the bank side (Meridian's existing `fraud.py` stays underwriting-only).
- Any CGR/CCR scoring logic (moat boundary).

## 0.4 Backward-compatibility matrix

| Existing element | Effect of this extension |
|---|---|
| `meridian/entities.py` models | Untouched. New models live in `meridian/bank/entities.py`. |
| `generate_market()`, `mint_agents()` | Untouched; MAY be called by a scenario that wants invoice-backed SCTs (BANK-002-14). |
| `Scorer` protocol | Untouched. Output formats use a **new** protocol `OutputSink` (BANK-004-01); the two are siblings. |
| `python -m meridian.driver` | Untouched. New CLI: `python -m meridian.bank` (D-07). |
| `episodes/`, `ground_truth/` git-ignore | Reused; new answer-key files follow `episodes/<episode>.bank.*.json`. |
| `tests/test_boundary.py`, `tests/test_pii_free.py` | Extended (not weakened) to scan `meridian/bank/**`. |
| `pyproject.toml` dependencies | No new **runtime** dependency. One optional **dev** dependency proposed for XSD validation (BANK-005-07, D-02). |
