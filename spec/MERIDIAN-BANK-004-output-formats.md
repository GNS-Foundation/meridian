# MERIDIAN-BANK-004 — Output formats behind one output interface

**Status:** draft · **Depends on:** BANK-001, BANK-003 · **Assumptions referenced:** A-01, A-02, A-04, A-06, A-07, A-10, A-12

## 4.1 The output interface

| Id | Requirement |
|---|---|
| BANK-004-01 | One `runtime_checkable` Protocol `OutputSink` (sibling of `Scorer`, `scorer.py:42-48`): `format_id: str`; `version: str` (the cited standard version); `emit(world: BankWorldView, selection: Selection, out_dir: Path) -> list[Path]`. Writers are pure (world in, files out), register in `meridian.bank.formats.REGISTRY`, and are selected with `--format cbi-rh,camt053,…`. |
| BANK-004-02 | Every writer MUST declare `sources: list[str]` (ids from `spec/README.md` source register) and `assumptions: list[str]` (`A-nn`) as class attributes; `--describe-formats` prints them. |
| BANK-004-03 | Encoding: CBI fixed-width files MUST be written as ASCII/Latin-1 with CR LF or LF line endings as a documented option (default `\r\n`, D-14); XML files MUST be UTF-8 without BOM. |
| BANK-004-04 | A writer MUST never read the answer key; it sees only the public `BankWorldView` (BANK-002-17). |

## 4.2 CBI RH — daily account statement (CBI-RND-001 v6.05, S1) — **Verified layout**

Function "Rendicontazione saldi e movimenti di conti correnti", flow code **RH-EF** (S3 row 30; S1 §2).
One *rendicontazione* per account per book date, each made of 120-char records in the sequence
**61, 62*, 63*, 64, [65]** (S1 §2.1 p.10). The set of rendicontazioni for one receiving company is wrapped
by a header **RH** and a trailer **EF** (S1 §2.1). A day without movements still yields 61 + 64 (S1 §2 p.10).

| Id | Requirement |
|---|---|
| BANK-004-10 | Every record MUST be exactly **120 characters**, position 1 = filler blank, positions 2-3 = record type (S1 §2.2-2.7). |
| BANK-004-11 | **RH** (S1 §2.2 p.11): 4-8 `mittente` ABI of sending bank (n); 9-13 `ricevente` SIA code of the receiving company (an, synthetic); 14-19 `data creazione` `GGMMAA`; 20-39 `nome supporto` (an, MUST be unique per creation date + sender + receiver); 40-115 filler; 116-120 "campo non disponibile" (blank). |
| BANK-004-12 | **EF** (S1 §2.3 p.11): 4-39 same as RH; 40-45 filler; 46-52 `numero rendicontazioni` (n, count of account statements in the flow); 53-82 filler; 83-89 `numero record` (n, total records **including** RH and EF); 90-114 filler; 115-120 not available. |
| BANK-004-13 | **61 Saldo iniziale** (S1 §2.4 pp.12-13): 4-10 `numero progressivo` (n, starts at 1, same on all records of one statement); 11-23 filler; 24-28 `codice ABI originario` (f, blank unless merger); 29-33 `causale` = `93001` ordinary transmission or `93011` re-transmission; 34-49 `descrizione` (f); 50-51 `tipo conto` (f); 52 CIN; 53-57 ABI (MUST equal RH `mittente`); 58-62 CAB; 63-74 account number (12); 75-77 `codice divisa` (`EUR`); 78-83 `data contabile` `GGMMAA` (MUST equal record 64 pos. 14-19); 84 `segno` `D`/`C`; 85-99 `saldo iniziale quadratura` (n, 15); 100-101 country `IT` or `SM`; 102-103 IBAN check digits; 104-120 filler. |
| BANK-004-14 | **62 Movimento** (S1 §2.5 pp.13-14), optional, repeatable: 4-10 progressivo (= rec 61); 11-13 `progressivo movimento` `001`…`999` then wraps to `001`; 14-19 `data valuta` `GGMMAA`; 20-25 `data registrazione/contabile`; 26 `segno` `D`/`C`; 27-41 `importo` (n, 15); 42-43 `causale CBI`; 44-45 `causale interna` (f); 46-61 `numero assegno` (MUST be filled when causale = `13`, MUST be blank otherwise — the standard says the flow is rejected otherwise); 62-77 `riferimento banca` (CRO/CRI or other bank reference); 78-86 `tipo riferimento cliente` (one of `NROSUPCBI`, `PAYORDREF`, `NRPRATICA`, `NDISTINTA`, `RIFESICBI`, or blank); 87-120 `riferimento cliente – descrizione movimento` (34 chars; mandatory content rules when pos. 78-86 is set). |
| BANK-004-15 | **63 Informazioni movimento** (S1 §2.6 pp.15-23), optional after each 62, **max 5 occurrences**: 4-10 progressivo; 11-13 progressivo movimento (= rec 62); 14-16 `flag struttura`; then one of the structured bodies below or, for an unstructured record, 14-120 `descrizione` free text (107 chars). |
| BANK-004-16 | 63 structured bodies the writer MUST support: **`YYY`** (first 63 for causale `48`): 17-24 `data ordine` `GGMMAAAA`; 25-40 ordering party fiscal code/VAT; 41-80 ordering party name; 81-120 locality. **`YY2`** (optional second 63 for causale `48`): 17-66 ordering party street address; 67-100 ordering party IBAN left-aligned; 101-120 filler. **`ID1`**: 17-51 `Identificativo univoco messaggio` (mandatory for causale `26`); 52-86 `Identificativo End To End` (mandatory for causale `48`); 87-120 filler. **`RI1`**: 17-120 `Informazioni di riconciliazione` (first 104 chars). **`RI2`**: 17-52 remaining 36 chars; 53-120 filler. (A-10: the S1 prose for RI1 says "pos. 52-111", its table says 17-120; the writer follows the table.) |
| BANK-004-17 | 63 sequencing rules (S1 p.21): `RI2` requires a preceding `RI1`; `RI1` requires a preceding `ID1`; all three are optional. For SEPA remittance the writer MUST map `remittance_unstructured` (≤ 140) to `RI1` (104) + `RI2` (36) and `end_to_end_id` to `ID1` pos. 52-86 for inbound (`48`) movements. |
| BANK-004-18 | 63 bodies **out of scope v1** (documented, not emitted): `KKK` (giroconto `34` / cash pooling `Z1`), `ZZ1`/`ZZ2`/`ZZ3`/`/ZZ4/` (foreign transfers `ZI`/`ZL`). |
| BANK-004-19 | **64 Saldo finale** (S1 §2.7 p.24): 4-10 progressivo; 11-13 `codice divisa` (MUST equal rec 61 pos. 75-77); 14-19 `data contabile`; 20 `segno saldo contabile`; 21-35 `saldo contabile` (n, 15; MUST equal opening + algebraic sum of movements); 36 `segno saldo liquido` (f); 37-51 `saldo liquido` (f); 52-120 filler. |
| BANK-004-20 | **65 Liquidità future** (S1 §2.8) is optional and **not emitted** in v1. |
| BANK-004-21 | Amount representation in records 61/62/64: integer cents, right-aligned, zero-padded, no separators (**A-01** — the retrieved S1 text does not state the unit; CBI-RIB-001 v6.02 states "espresso in centesimi di Euro" for its amount fields, S2 §5.3.1). |
| BANK-004-22 | `causale CBI` values the writer MAY use are only those **quoted in S1** until CBI-STD-001 Appendix B is sourced: `48` bonifico a Vostro favore (inbound SCT), `26` bonifico (outbound), `13` Vostro assegno, `34` giroconto, `Z1` cash pooling, `ZI`/`ZL` foreign. Codes for SDD debits/credits, MAV credits and fees are **A-07** placeholders and MUST be configurable. |
| BANK-004-23 | A CBI RH validator MUST check: record length 120; sequence 61/62/63/64 per statement; progressivo consistency; 61↔64 date and currency equality; balance arithmetic; `13`↔cheque-number rule; 63 count ≤ 5; ID1/RI1/RI2 ordering; EF counters. Each check gets a non-vacuity probe (BANK-005-05). |

## 4.3 CBI IM — MAV outcomes (CBI-MAV-001 v6.01) — **ASSUMPTION A-02 throughout**

The CBI function map (S3 rows 17-19) confirms that MAV dispositions, **return flows (esiti)** and
recalls all use header/trailer **IM-EF** and the manual **CBI-MAV-001**. The manual itself could not be
retrieved on 2026-10-10 (404 at the UniCredit mirror; CBI portal requires membership). The sibling
return flow for Ri.Ba. (S2 §5) is fully verified and is structurally the published pattern for CBI
collection outcomes; it is used here **only as a model**.

| Id | Requirement |
|---|---|
| BANK-004-30 | The IM writer MUST be implemented behind the same `OutputSink` interface but MUST be marked `assumptions=["A-02"]` and MUST refuse to run unless `--allow-assumed-layouts` is passed, until CBI-MAV-001 is sourced and the layout re-verified. |
| BANK-004-31 | Assumed structure (modelled on S2 §5.1 p.16-17): header `IM`, trailer `EF`, each outcome = 7 records of 120 chars in sequence **14, 20, 30, 40, 50, 51, 70**, outcome expressed by a `causale` in record 14 pos. 29-33 (S2 uses `30006` returned, `30008` recalled, `30010` paid). The MAV codes, positions and outcome vocabulary are **unknown** and MUST be taken from CBI-MAV-001 when available. |
| BANK-004-32 | The writer MUST carry: MAV identifier (A-03), amount (cents, A-01), payment date, paying channel, creditor account, and the creditor's reference; field positions TBD. |

## 4.4 SEPA camt.053 / camt.054 (ISO 20022, Bank-to-Customer)

| Id | Requirement |
|---|---|
| BANK-004-40 | Target message versions: **camt.053.001.08** (BankToCustomerStatement) and **camt.054.001.08** (BankToCustomerDebitCreditNotification). **A-06**: EPC188-09 v5.0 could not be retrieved; the retrieved v2.0 (S9) maps to `.001.02`; a documented live implementation of `.001.08` is S10 (SIX SPS 2023). Version is a writer constant so `.001.02` can be added later (D-03). |
| BANK-004-41 | camt.053 content per statement: `GrpHdr` (MsgId episode-namespaced, CreDtTm sim clock); one `Stmt` per account per book date with `Acct/Id/IBAN`, `Bal` OPBD and CLBD matching BANK-001-07, one `Ntry` per movement with `Amt`, `CdtDbtInd`, `Sts/Cd=BOOK`, `BookgDt`, `ValDt`, `BkTxCd` (Domain/Family/SubFamily per the mapping chosen in D-15), `NtryDtls/TxDtls` with `Refs/EndToEndId`, `Refs/MndtId` for SDD (S9 row "The unique Mandate reference" → `References/MandateIdentification`), `RltdPties`, `RmtInf/Ustrd` (≤ 140). |
| BANK-004-42 | camt.054 content: one notification per account per day for the selected movement subset (default: all credits), same `TxDtls` shape as camt.053. |
| BANK-004-43 | SDD R-transactions MUST appear as entries with `RtrInf/Rsn/Cd` = reason code (BANK-003 table) and `RtrInf/OrgnlBkTxCd`; the exact element path for `.001.08` MUST be confirmed against the ISO schema at implementation (D-02). |
| BANK-004-44 | XML MUST validate against the official ISO 20022 XSD for the chosen version (BANK-005-07); schema files are not vendored without D-02. |

## 4.5 SEPA pain.002 — Customer Payment Status Report

| Id | Requirement |
|---|---|
| BANK-004-50 | Target version **pain.002.001.10** — verified in **S5** (EPC131-08 2025 V1.0 §2.3.1 "Use of the Customer Payment Status Report (pain.002.001.10)") and **S6** (EPC132-08 2025 V1.0). **A-04**: the SDD *Core* 2025 C2PSP IG (EPC130-08) could not be retrieved; the older EPC130-08 v7.0 (S7 §2.3.1) confirms that the Reject dataset DS-05 is carried to the Creditor via pain.002 (then `.001.03`). |
| BANK-004-51 | The pain.002 writer MUST report, per original SDD collection: `OrgnlGrpInfAndSts` (original pain.008 MsgId, `OrgnlMsgNmId = pain.008.001.08` per A-04), `OrgnlPmtInfAndSts/TxInfAndSts` with `OrgnlEndToEndId`, `TxSts` (`RJCT` for rejects; status values for returns/refunds per D-16), `StsRsnInf/Rsn/Cd` from the BANK-003 reason table, `OrgnlTxRef` (amount, mandate id, debtor IBAN). |
| BANK-004-52 | Because the virtual bank is also the *Creditor's* bank in these episodes, the pain.002 is emitted to the creditor-side folder (`out/<episode>/pain002/<creditor_id>/…`), distinct from the debtor-side statement files. |
