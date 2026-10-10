# OPEN-QUESTIONS — assumptions, decisions for Camilo, and what belongs in Ulissy

**Date:** 2026-10-10 · Companion to `MERIDIAN-BANK-00x`. Every `A-nn` below is referenced from at least one
requirement. An assumption is closed only by citing the primary source (document id, version, page) in
`spec/README.md`'s source register and removing the marker from code.

## A — ASSUMPTIONS (unverified against primary source on 2026-10-10)

| Id | Assumption | Why it is an assumption | Used by | How to close |
|---|---|---|---|---|
| A-01 | CBI RH amount fields (rec 61 pos 85-99, rec 62 pos 27-41, rec 64 pos 21-35) are integer **euro cents** with implicit two decimals. | The retrieved CBI-RND-001 v6.05 text does not state the unit for these fields; the sibling CBI-RIB-001 v6.02 (§5.3.1) says "espresso in centesimi di Euro" for its amount field. | BANK-004-21, BANK-003-33 | Check CBI-STD-001 general rules on numeric fields, or a real RH sample. |
| A-02 | **Entire CBI IM layout** (MAV outcomes): header `IM`, trailer `EF`, 7 records 14/20/30/40/50/51/70, outcome via causale in rec 14. | CBI-MAV-001 v6.01 not retrievable (UniCredit mirror 404; CBI portal membership). Only the flow code `IM-EF ↔ CBI-MAV-001` is verified (S3). Structure borrowed from CBI-RIB-001 v6.02 §5. | BANK-004-30..32, BANK-005-04 | Obtain CBI-MAV-001 v6.01 (Camilo via a bank or CBI member) and re-derive every position. |
| A-03 | MAV identifier = 17 digits shaped like the RAV code (`N1` 5 in 80000–99999, `N2` 9, `CIN10` 1, `CIN93` 2) with placeholder check-digit algorithms. | Only the RAV structure is in a retrieved primary source (AgID/AER, S12 §2.1); MAV bancario length "17" comes from secondary sources; CIN10/CIN93 algorithms are not published in S12 ("La verifica … viene eseguita da AER"). | BANK-001-13, BANK-003-30 | CBI-MAV-001 field definition of the MAV code, or ABI technical note. |
| A-04 | SDD **Core** C2PSP message versions are pain.008.001.08 / pain.002.001.10 (2025 IGs). | EPC130-08 2025 V1.0 not retrievable (404 on guessed URLs; EPC HTML pages 403). Verified for **B2B** (EPC131-08 2025 V1.0, S5) and for pain.002.001.10 in SCT (EPC132-08 2025 V1.0, S6). | BANK-003-21, BANK-004-50..51 | Download EPC130-08 2025 V1.0 from the EPC document library in a browser and quote §2.3.1. |
| A-05 | SDD Return and Reversal time windows (and "Reject = before settlement" phrasing) per the SDD Core Rulebook. | EPC016-06 2025 v1.1 not retrievable (403). S4 verifies only the 8-week (`MD06`) and 13-month (`MD01`) refund windows. | BANK-003-13, BANK-003-16, BANK-005-24 | Quote the rulebook sections for Return (Debtor PSP) and Reversal (Creditor) deadlines. |
| A-06 | camt.053.001.08 / camt.054.001.08 are the appropriate SEPA customer-reporting versions today. | EPC188-09 **v5.0** not retrievable; retrieved **v2.0** maps to `.001.02`; a live `.001.08` implementation is documented by SIX SPS 2023 (S10, Swiss, not EPC). | BANK-004-40 | Retrieve EPC188-09 v5.0 and confirm the camt versions it maps to. |
| A-07 | CBI causale codes for **SDD debit/credit, MAV credit, fees** (and any code not quoted inside CBI-RND-001). | CBI-STD-001 Appendix B ("Tabella Causali CBI") not retrievable. Verified codes are only those quoted in S1: `13`, `26`, `34`, `48`, `Z1`, `ZI`, `ZL`, and rec-61 `93001`/`93011`. | BANK-003-11, BANK-003-31, BANK-003-40, BANK-004-22 | Obtain CBI-STD-001 Appendix B (and Appendix D currency codes). |
| A-08 | Synthetic ABI range `99000–99999` and fictional BIC institution codes do not collide with real identifiers. | No offline authoritative list of assigned ABI/BIC codes was retrieved; ISO 9362 layout verified only via secondary sources (S13). | BANK-001-03 | Camilo to confirm a reserved/test range (Banca d'Italia ABI list; SWIFT test BIC convention). |
| A-09 | Italian CIN tables and ISO 7064 mod 97-10 as described in the Fauser note (S11) match ISO 13616 / ABI rules. | S11 is an educational source with reference code, not the ISO/ABI text. The algorithm is internally consistent and widely implemented, but the standard text was not retrieved. | BANK-001-05, BANK-005-23 | Cross-check with ISO 13616-1 registry entry for IT, or validate generated IBANs with two independent public validators. |
| A-10 | Record 63 `RI1` reconciliation field occupies pos. **17-120** (104 chars). | CBI-RND-001 v6.05 is internally inconsistent: prose on p.21 says "pos. 52-111", the table on p.22 says 17-120. Spec follows the table (104 chars + RI2's 36 = 140, consistent with the 140-char remittance). | BANK-004-16 | Confirm with CBI or a real RH sample containing `RI1`. |
| A-11 | SDD Refusal and Request for cancellation are safe to omit in v1. | Scope choice, not a source gap; recorded as an assumption because `MS02` lists Refusal among its R-types (S4 p.10). | BANK-003-17 | Camilo's call. |
| A-12 | Banks commonly place a truncated remittance in rec 62 pos. 87-120 when pos. 78-86 is blank. | S1 defines pos. 87-120 as "Riferimento cliente – descrizione movimento" with mandatory content only when 78-86 holds a keyword; free use is bank practice, not a rule in S1. | BANK-003-06 | Inspect real RH samples; otherwise keep it off by default. |

## D — Decisions (status as of review round 1, 2026-10-10)

All decisions below are **decided** unless marked otherwise. "Decided (default)" means Camilo confirmed the spec default.

| Id | Decision | Resolution |
|---|---|---|
| D-01 | Storage. | **Decided (default):** Meridian's in-memory objects + JSON files; no database, no ORM (BANK-001-20..23). |
| D-02 | XSD validation dependency and ISO 20022 schema files. | **Decided (default):** `xmlschema` (or `lxml`) as **dev-only** dependency; XSD files **not** committed; tests skip with a reason unless `MERIDIAN_ISO20022_XSD_DIR` is set (BANK-005-07). |
| D-03 | camt versions. | **Decided (default):** `.001.08` only; version is a writer constant (BANK-004-40). |
| D-04 | CBI IM on assumption A-02. | **Decided:** build now, **gated** behind `--allow-assumed-layouts`, golden files under `tests/golden/_assumed/` with `xfail` (BANK-004-30, BANK-005-04); re-verify when CBI-MAV-001 is sourced. |
| D-05 | pagoPA FdR ("identificativoFlusso") instrument placement. | **Decided:** the *generic* pagoPA FdR instrument belongs in the **Foundation** as a future block **BANK-006**, in a **separate PR** (not written in this PR, not v1). *Client-specific* treasury reconciliation (a given body's treasury accounts, FdR-to-ledger mapping) stays in **Ulissy**. |
| D-06 | Packaging. | **Decided (default):** sub-package `meridian.bank` in this repo (BANK-000-02). |
| D-07 | CLI entry. | **Decided (default):** `python -m meridian.bank` only; no console script in v1. |
| D-08 | Field naming language. | **Decided (default):** Italian CBI terms kept verbatim for CBI-specific fields (`causale`, `progressivo`), English elsewhere. |
| D-09 | Holder person names vs the PII-free test. | **Decided: option (a).** Holders MAY be persons; person display names come only from the repo-owned curated list `meridian/bank/data/fictional_names.*`; Faker name generators stay forbidden with no allow-list; a non-vacuity probe proves the scan catches a Faker name call (BANK-001-06, BANK-005-31, BANK-005-33). |
| D-10 | Synthetic ABI range and real-identifier deny-list. | **Decided (default):** ABI `99000–99999` (A-08 stays open until a reserved range is confirmed by source); deny-list empty until supplied (BANK-005-32). |
| D-11 | `fiscal_code_like`. | **Decided (default):** deliberately checksum-invalid synthetic code, documented (BANK-001-06). |
| D-12 | Synthetic SEPA Creditor Identifier format. | **Decided (default):** structurally valid, synthetic national id; the CI structure source MUST be cited before implementation (BANK-001-10). |
| D-13 | Default volumes. | **Decided (default):** as listed in BANK-002-06. |
| D-14 | CBI line endings and encoding. | **Decided (default):** `\r\n`, Latin-1 (BANK-004-03). |
| D-15 | `BkTxCd` Domain/Family/SubFamily mapping. | **Decided (default):** fixed at implementation with the ISO external code list cited in the source register (BANK-004-41). |
| D-16 | pain.002 `TxSts` scope. | **Decided (default):** rejects only (`RJCT`) in pain.002; returns/refunds reported through camt.054 entries (BANK-004-51, BANK-004-43). |
| D-17 | Non-IT counterparties for inbound SCT. | **Decided (default):** no, `IT` only in v1 (BANK-003-07). |

## Belongs in Ulissy (placement check, ADR-0005)

Found while drafting; **deliberately excluded** from the Foundation spec. These describe or position a
commercial delivery, not the neutral synthetic bank:

- Any mapping to a specific client's billing system, open-item format, or import files
  (the trigger case for this spec was a client reconciliation POC; that mapping is Ulissy material).
- Client-specific remittance vocabularies (bill numbering schemes, customer-code formats, operator matching
  rules and thresholds). The Foundation ships only generic placeholders and noise operators (BANK-003-05).
- pagoPA treasury-account reconciliation for a specific public body (c/c numbers, FdR-to-ledger mapping) — the
  *generic* pagoPA instrument is D-05.
- Lists of a client's actual banks (ABI/BIC) and any real statement samples used for calibration.
- Excel/POI statement exports mimicking a particular bank's home-banking download.
- Deployment kit, runbooks, DORA register entries, evidence packs for a client engagement — already Ulissy per
  the ADR-0005 placement rule (Ulissy internal document).

## Verification gaps summary

| Area | Verified | Assumption |
|---|---|---|
| CBI RH records RH/EF/61/62/63/64 | ✔ S1 (positions quoted) | A-01 units, A-10 RI1 extent, A-12 practice |
| CBI IM | flow code only (S3) | A-02 everything else |
| SDD reason codes + R-types + 8w/13m | ✔ S4 | A-05 other windows |
| ISO versions pain.008/.002, pain.001 | ✔ S5, S6 (B2B, SCT) | A-04 Core by analogy |
| 140-char remittance | ✔ S6 index 2.165; S1 p.21 | — |
| camt.053/054 version | S9 (.02), S10 (.08) | A-06 EPC v5.0 |
| IBAN/CIN | S11 | A-09 |
| BIC | S13 (secondary) | A-08 |
| MAV id | S12 (RAV) | A-03 |
| CBI causali | S1 subset | A-07 |
