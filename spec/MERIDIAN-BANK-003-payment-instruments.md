# MERIDIAN-BANK-003 — Payment instruments: SCT, SDD Core + R-transactions, MAV

**Status:** draft · **Depends on:** BANK-001, BANK-002 · **Assumptions referenced:** A-03, A-04, A-05, A-07, A-11, A-12

Instrument rules live in the core `materialise()` step (BANK-002-11). Scenarios express *intent*;
this block defines what the core does with it and which rules it enforces.

## 3.1 SEPA Credit Transfer (SCT) — inbound and outbound

| Id | Requirement |
|---|---|
| BANK-003-01 | An `sct_in` intent MUST produce one **credit** movement on the beneficiary account with `cbi_causale = 48` ("Bonifico a Vostro favore", quoted in S1 §2.6 footnote, p.15) and an `sct_out` intent one **debit** movement with `cbi_causale = 26` (S1 §2.5 pos. 78-86 text and §2.6 p.21 "causale CBI 26"). |
| BANK-003-02 | Each SCT MUST carry `end_to_end_id` (≤ 35 chars: `EndToEndId`, Type `Max35Text`, S6) and, for outbound, `message_id` (≤ 35). Both are deterministic from the intent id. |
| BANK-003-03 | **Free-text remittance** MUST be modelled as `remittance_unstructured`, **max 140 characters**: ISO `RemittanceInformation/Unstructured` (`Ustrd`), Type `Max140Text`, ISO Length 1..140, SEPA Length 1..140 (**S6** EPC132-08 2025 V1.0 index 2.165). The CBI side corroborates: "Informazioni di riconciliazione … di lunghezza massima pari a 140 caratteri" (S1 §2.6 p.21). Only one `Ustrd` occurrence is allowed (S6 index 2.165 usage rule). |
| BANK-003-04 | Structured remittance (`Strd`, incl. ISO 11649 creditor reference, S6 index 2.166 and ref. [7]) is **out of scope v1**; a scenario MAY place an RF-creditor-reference-shaped string inside the unstructured text, flagged in the answer key. |
| BANK-003-05 | **Noise operators** on remittance text MUST be explicit, composable, seed-driven, and recorded in the answer key (`remittance_clean` vs `remittance_emitted`): `truncate_to(n)`, `upper()`, `strip_accents()`, `drop_separators()`, `transpose_adjacent_digits(k)`, `drop_token(i)`, `prepend_bank_boilerplate()`, `concat_two_references()`. The *vocabulary* of what the reference means (bill number, customer code, document id) is **scenario-owned**, generic placeholders only in the Foundation repo (`REF`, `DOC`, `CUST`). |
| BANK-003-06 | Realism rules for the CBI side (BANK-004): for inbound SCT the ordering party name goes to record 63 `YYY` pos. 41-80 and locality to 81-120; `end_to_end_id` to 63 `ID1` pos. 52-86; remittance to `RI1`+`RI2` (S1 §2.6). Record 62 pos. 87-120 (34 chars) MAY additionally carry a truncated remittance only when pos. 78-86 is blank (**A-12**: bank practice, not a rule found in S1). |
| BANK-003-07 | Counterparty IBANs for inbound SCT MUST be synthetic-valid (BANK-001-05) and, for non-IT counterparties if enabled, MUST use country-specific lengths from a maintained table with a cited source (D-17); v1 default `IT` only. |
| BANK-003-08 | **Counterparty-name noise.** The ordering-party name of an inbound SCT (and the debtor name on an SDD collection) MUST be subject to explicit, composable, seed-driven noise operators recorded in the answer key exactly like remittance noise (BANK-003-05): `counterparty_name_clean`, `counterparty_name_emitted`, and the ordered operator list. Operators v1: `initials()` (surname plus initial, e.g. `ROSSI M.`); `swap_surname_given()`; `truncate_to_yyy_width()` (40 chars = record 63 `YYY` ordering-party name, pos. 41-80, S1 §2.6 p.16); `upper()`; `strip_accents()`; `third_party_payer()` — the ordering party is a **different holder** from the intended debtor: the emitted record carries the payer's name and IBAN, the answer key keeps `intended_holder_id` and sets `match_class` accordingly (BANK-002-19). All names, clean or noised, are built only from the curated list (BANK-001-06). |

## 3.2 SEPA Direct Debit Core — collections and R-transactions

Scheme vocabulary per **S4** (EPC173-14 v8.0, 28 Nov 2024). The rulebook itself (EPC016-06 2025 v1.1)
could not be retrieved (403); timelines not quoted in S4 are **A-05**.

| Id | Requirement |
|---|---|
| BANK-003-10 | An `sdd_collect` intent MUST reference an active `Mandate` (BANK-001-10) with a consistent `sequence_type` progression (`FRST` or `OOFF` first, then `RCUR`, optional `FNAL`); a violation MUST yield reject `AG02` ("Recurrent after a one-off; One-off after a recurrent", S4 p.6). |
| BANK-003-11 | Settlement MUST produce one **debit** movement on the debtor account and one **credit** movement on the creditor account (both banks are virtual). The `cbi_causale` for SDD debit/credit is **A-07** (CBI-STD-001 Appendix B not retrieved) and MUST be a configurable constant with an `A-07` marker. |
| BANK-003-12 | **Reject** (before settlement): no movements; a pain.002 status `RJCT` with reason code (BANK-004-51). Codes permitted for Reject per S4 "Type of R-trans." column: `AC01 AC04 AC06 AG01 AG02 AM04 AM05 BE05 CNOR DNOR ED05 FF01 MD01 MD02 MD07 MS02 MS03 RC01 RR01 RR02 RR03 RR04 SL01` (`AC13` is B2B-only and MUST NOT be used for Core). |
| BANK-003-13 | **Return** (after settlement, initiated by the Debtor PSP): reverses the two settlement movements with a second pair of movements. Codes permitted for Return per S4: `AC01 AC04 AC06 AG01 AG02 AM04 AM05 BE05 MD01 MD07 MS02 MS03 RC01 RR01 RR02 RR03 RR04 SL01`. Return deadline: **A-05** (rulebook not retrieved; the generator MUST take the window from config `sdd.return_window_days` with the assumption id in the answer key). |
| BANK-003-14 | **Refund of an authorised collection**: code **`MD06`** only — "Unconditional Refund of a collection (SDD Core – until **8 weeks** after debit date)" (S4 p.9). The generator MUST date the refund within `[settlement_date, settlement_date + 8 weeks]` and MUST be able to generate the *out-of-window* negative case for probes (BANK-005-24). |
| BANK-003-15 | **Refund of an unauthorised collection**: code **`MD01`** — "Refund for an unauthorised transaction (until **13 months** after debit date) (For SDD Core collections only)" (S4 p.8). Dated within `(settlement_date, settlement_date + 13 months]`. The 36-month mandate-inactivity cause is also `MD01` (S4 p.8) and MUST be a distinct `expected_outcome` in the intent. |
| BANK-003-16 | **Reversal** (creditor-initiated after settlement): codes per S4 `AM05`, `MS02`, `MS03`; window **A-05**. |
| BANK-003-17 | **Refusal** and **Request for cancellation** are out of scope (**A-11**). `MS02` appears in S4 with "Refusal" among its R-types; the generator MUST NOT emit a Refusal object even though the code is permitted for Reject/Return/Reversal. |
| BANK-003-18 | Data-protection alternates: when a scenario asks for `AC04`, `AM04`, `MD07`, `RR01-RR04` the core MAY substitute `MS03` under a config flag `sdd.data_protection_country=true` (S4: "Only to be used in case national legislation (e.g., data protection laws) does not allow the use of AC04, AM04, MD07, RR01, RR02, RR03 and RR04", p.10). The substitution MUST be recorded in the answer key. |
| BANK-003-19 | Full reason-code table the implementation MUST ship (verified in S4 pp.5-13, with S4's "Type of R-trans." column): `AC01` Incorrect Account Number (Reject, Return); `AC04` Closed Account Number (Reject, Return); `AC06` Blocked Account (Reject, Return); `AC13` Invalid Debtor Account Type (Reject, Return; **B2B only**); `AG01` Transaction Forbidden (Reject, Return); `AG02` Invalid Bank Operation Code (Reject, Return); `AM04` Insufficient Funds (Reject, Return); `AM05` Duplication (Reject, Return, Reversal); `BE05` Unrecognised Initiating Party (Reject, Return); `CNOR` Creditor Bank Is Not Registered (Reject); `DNOR` Debtor Bank Is Not Registered (Reject); `ED05` Settlement Failed (Reject); `FF01` Invalid File Format (Reject); `MD01` No Mandate (Reject, Return, Refund); `MD02` Missing Mandatory Mandate Information (Reject); `MD06` Refund Request By End Customer (Refund); `MD07` End Customer Deceased (Reject, Return); `MS02` Not Specified Reason Customer Generated (Reject, Return, Reversal, Refusal); `MS03` Not Specified Reason Agent Generated (Reject, Return, Reversal); `RC01` Bank Identifier Incorrect (Reject, Return); `RR01` Missing Debtor Account Or Identification (Reject, Return); `RR02` Missing Debtor Name Or Address (Reject, Return); `RR03` Missing Creditor Name Or Address (Reject, Return); `RR04` Regulatory Reason (Reject, Return); `SL01` Specific Service Offered By Debtor Agent (Reject, Return). |
| BANK-003-20 | The table in BANK-003-19 MUST be stored as data (one row per code with `r_types`, `scheme_scope`, `source="EPC173-14 v8.0"`) so the validator (BANK-005-24) can reject a kind/code pair the source does not allow. |
| BANK-003-21 | Message versions for any SDD XML the bank emits or expects: pain.008.001.08 (collection) and pain.002.001.10 (status) — **A-04**, verified for SDD B2B in S5 and for pain.002 in S6; to be re-verified against EPC130-08 2025 when retrievable. |

## 3.3 MAV — Pagamento Mediante Avviso

| Id | Requirement |
|---|---|
| BANK-003-30 | A `mav_issue` intent MUST create a `MavNotice` with a **17-digit** identifier. **A-03**: the public structure retrieved is for the sibling **RAV** code (S12 §2.1): `N1` 5 digits in `80000–99999`, `N2` 9 digits, `CIN 10` 1 digit, `CIN 93` 2 digits. The MAV bancario identifier is reported as 17 digits by secondary sources only; its check-digit algorithms were not found in any retrieved source. The generator MUST therefore use the RAV-shaped layout with **placeholder** check digits (`mod 10` of digits for CIN10, `mod 93` for CIN93), clearly marked `A-03`, and MUST make the algorithm pluggable. |
| BANK-003-31 | A `mav_pay` intent MUST produce one **credit** movement on the creditor account (cbi_causale **A-07**), set the notice to `paid` with `paid_on`, `paid_amount_cents`, `paying_channel`, and feed the CBI IM outcome writer (BANK-004-30..32). |
| BANK-003-32 | Scenario-level MAV variants the core MUST support: paid on time, paid late, paid twice (duplicate, answer-key `match_class=duplicate`), partially paid (if the assumed layout permits; else flagged unsupported), expired unpaid. |
| BANK-003-33 | MAV amounts are carried in cents (BANK-001-08) and emitted per A-01. |

## 3.4 Fees and internal events

| Id | Requirement |
|---|---|
| BANK-003-40 | A `fee` intent MUST produce one debit movement with a configurable causale (**A-07**) and a boilerplate description; fees exist so statements are not implausibly clean. No interest computation in v1. |
