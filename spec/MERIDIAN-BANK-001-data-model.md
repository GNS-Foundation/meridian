# MERIDIAN-BANK-001 — Data model

**Status:** draft · **Depends on:** BANK-000 · **Assumptions referenced:** A-03, A-07, A-08, A-09

All models are Pydantic v2 (`pydantic>=2.6` is already a dependency, `pyproject.toml:9`) in
`meridian/bank/entities.py`, following the PUBLIC / GROUND-TRUTH split of `meridian/entities.py:1-13`:
public records can be emitted; ground truth (the answer key) never appears in an emitted file.

Identifiers are **synthetic by construction**. Where a real-world identifier has a published checksum
(IBAN), the synthetic value MUST satisfy the checksum so that downstream parsers accept it, while using
institution codes that cannot collide with a real bank (BANK-001-03, A-08).

## 1.1 Entities

| Id | Requirement |
|---|---|
| BANK-001-01 | `Bank`: `bank_id` (synthetic key), `name` (fictional, Faker `company()` only — never a person generator, per `tests/test_pii_free.py:34-43`), `abi` (5 digits), `bic` (8 or 11 chars), `country` (ISO 3166-1 alpha-2, v1 = `IT` only), `branches: list[Branch]`. |
| BANK-001-02 | `Branch`: `cab` (5 digits), `label` (fictional locality label from a closed, repo-owned list — not Faker `city()`, see D-09). |
| BANK-001-03 | **Synthetic ABI**: 5 digits drawn deterministically from a reserved range that the generator documents as fictional (D-10 asks Camilo to confirm the range; until then the generator MUST use `99000-99999` and label it `A-08`). **Synthetic BIC**: ISO 9362 layout (S13) — 4-letter institution code, 2-letter country `IT`, 2-char location code, optional 3-char branch code — with the institution code drawn from a documented fictional set (e.g. letters that spell no registered BIC is *not* checkable offline; A-08). |
| BANK-001-04 | `Account`: `account_id`, `bank_id`, `cab`, `holder_id`, `iban` (27 chars, BANK-001-05), `currency` (`EUR` in v1), `opened_on` (sim date), `account_type` (`current`), `status` (`open`/`closed`/`blocked`). |
| BANK-001-05 | **Italian IBAN** MUST be generated as `IT` + 2 check digits + CIN (1 letter) + ABI (5) + CAB (5) + account number (12 alphanumeric), total 27 chars, per S11 p.1. The **Italian CIN** MUST be computed over the 22-char BBAN body with the odd/even conversion tables and `mod 26` of S11 pp.1-2 (reference C implementation S11 pp.5-6: `VAL_PARI`, `VAL_DISPARI`, `cin = 'A' + (somma % 26)`). The **IBAN check digits** MUST be computed with ISO 7064 mod 97-10: BBAN + `IT00`, letters → `A=10 … Z=35`, `S mod 97`, `check = 98 − S` (S11 pp.2-3). Verification of the whole IBAN (`mod 97 == 1`) MUST be a unit-tested helper. (A-09: algorithm verified against an educational source, not the ISO 13616 text.) |
| BANK-001-06 | `Holder`: `holder_id`, `kind` (`person` / `organisation`), `display_name`, `fiscal_code_like` (synthetic, **not** a valid codice fiscale: MUST fail the real checksum deterministically so it can never be mistaken for a real one — D-11), `address_label` (fictional). `display_name` for `organisation` = Faker `company()`; for `person` see **D-09** (PII-free policy forbids Faker name generators today). |
| BANK-001-07 | `Balance`: `account_id`, `book_date`, `opening_book` (signed, cents), `closing_book`, `closing_available` (optional), `currency`. `closing_book` MUST equal `opening_book` + algebraic sum of the day's movements (this is the CBI record-64 rule, S1 §2.7 p.24: "deve coincidere con la somma algebrica del saldo iniziale e degli importi dei singoli movimenti"). |
| BANK-001-08 | `Movement`: `movement_id` (episode-namespaced), `account_id`, `booking_date`, `value_date`, `sign` (`D`/`C`), `amount_cents` (int ≥ 0), `cbi_causale` (2 chars, BANK-003 tables), `bank_reference` (≤ 16 chars, the CRO/CRI-like reference, S1 §2.5 pos. 62-77), `end_to_end_id` (≤ 35), `message_id` (≤ 35), `remittance_unstructured` (≤ 140, BANK-003-03), `counterparty: Counterparty`, `instrument_ref` (link to the SCT/SDD/MAV event that created it). Monetary values are **integers in cents** everywhere in the model (A-01 concerns only the *emitted* CBI representation). |
| BANK-001-09 | `Counterparty`: `name`, `iban` (may be a non-IT IBAN for inbound SCT realism; v1 MAY restrict to IT), `bic` (optional), `fiscal_code_like` (optional), `address_label` (optional). |
| BANK-001-10 | `Mandate` (SDD Core): `mandate_id` (Unique Mandate Reference, ≤ 35), `creditor_id` (synthetic Creditor Identifier, D-12 for format), `creditor_name`, `debtor_account_id`, `debtor_name`, `signed_on`, `sequence_type` (`FRST`/`RCUR`/`OOFF`/`FNAL`), `status` (`active`/`cancelled`/`expired`), `last_collection_on` (for the 36-month inactivity rule quoted in S4 MD01: "mandate was not used for 36 months and is therefore no longer valid"). |
| BANK-001-11 | `Collection` (SDD Core): `collection_id`, `mandate_id`, `requested_collection_date`, `amount_cents`, `end_to_end_id`, `remittance_unstructured`, `state` (`presented`/`settled`/`rejected`/`returned`/`refunded`/`reversed`), `r_transactions: list[RTransaction]`. |
| BANK-001-12 | `RTransaction`: `kind` (`reject`/`return`/`refund`/`reversal`), `reason_code` (ISO ExternalReturnReason code from BANK-003 table, S4), `date`, `initiator` (`debtor_psp`/`creditor_psp`/`csm`/`creditor`/`debtor`), `amount_cents`, `original_collection_id`. |
| BANK-001-13 | `MavNotice`: `mav_id` (17-digit identifier, A-03), `creditor_account_id`, `debtor_holder_id` (optional, the paying party need not be a bank customer), `amount_cents`, `due_date`, `issued_on`, `state` (`issued`/`paid`/`expired`/`cancelled`), `paid_on`, `paid_amount_cents`, `paying_channel` (`branch`/`online`/`other`). |
| BANK-001-14 | Every entity MUST carry `episode` (string) so that identifiers never collide across runs (idempotency pattern of `driver.py:10-12`). |

## 1.2 Relationships and invariants

| Id | Requirement |
|---|---|
| BANK-001-15 | One `Account` has exactly one `Holder` in v1 (joint accounts out of scope). |
| BANK-001-16 | Every `Movement` MUST reference exactly one `instrument_ref` (an SCT leg, an SDD collection or R-transaction, a MAV payment, or a `fee`/`interest` internal event). No orphan movements. |
| BANK-001-17 | Per account and `book_date`, the ordered list of movements MUST reconcile opening → closing balance (BANK-001-07). This is the invariant the CBI RH writer and the camt.053 writer both rely on. |
| BANK-001-18 | An SDD `RTransaction` of kind `refund` MUST reference a `Collection` whose state was `settled`; a `reject` MUST reference a collection not yet settled; a `return` MUST reference a settled collection (S4: Reject/Return/Refund columns per code). Timelines: see BANK-003-10..13. |
| BANK-001-19 | A `MavNotice` in state `paid` MUST have produced exactly one credit `Movement` on `creditor_account_id`. |

## 1.3 Storage

| Id | Requirement |
|---|---|
| BANK-001-20 | Storage MUST extend what Meridian uses today: in-memory Pydantic objects during a run, plus JSON files on disk at the end (`driver.py:243-256`). **No database, no ORM, no new runtime dependency** (D-01). |
| BANK-001-21 | The in-memory world MUST be held in one `BankWorld` container (dataclass or Pydantic) with typed collections for each entity and index helpers (`account_by_iban`, `movements_by_account_day`, …), analogous to `Scenario` in `generative.py:46-56`. |
| BANK-001-22 | Serialisation MUST be Pydantic `model_dump_json()` with sorted keys and fixed float/int handling so that the **same seed yields byte-identical JSON** (BANK-005-02). Timestamps MUST be sim-clock ISO strings, never wall-clock (pattern: `driver.py:34`). |
| BANK-001-23 | Justification for *not* adding SQLite: a 1-day statement for 50 accounts × ~30 movements is a few thousand rows; the fixed-width and XML writers consume ordered in-memory lists; golden-file determinism is simpler without a storage layer. Revisit only if volumes exceed what fits in memory for a laptop episode (open: D-01). |
