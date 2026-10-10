# Meridian Virtual Bank — specification set (SPEC ONLY, nothing implemented)

**Branch:** `spec/virtual-bank` · **Status:** draft for Camilo's review · **Date:** 2026-10-10
**Scope of this folder:** a specification that extends Meridian from an underwriting simulator into a
generic, deterministic **virtual bank** usable as a synthetic data source by any integration project.
No code in this PR. Nothing here changes the existing `meridian/` package.

## Files

| File | Requirement block | Contents |
|---|---|---|
| `MERIDIAN-BANK-000-scope.md` | BANK-000-xx | Scope, non-goals, backward compatibility with current Meridian |
| `MERIDIAN-BANK-001-data-model.md` | BANK-001-xx | Banks, accounts, holders, balances, movements, SDD mandates, MAV notices; storage |
| `MERIDIAN-BANK-002-generator.md` | BANK-002-xx | Seed determinism, volumes, scenario hooks, answer key |
| `MERIDIAN-BANK-003-payment-instruments.md` | BANK-003-xx | SCT, SDD + R-transactions, MAV |
| `MERIDIAN-BANK-004-output-formats.md` | BANK-004-xx | CBI RH, CBI IM, camt.053/054, pain.002 behind one output interface |
| `MERIDIAN-BANK-005-acceptance.md` | BANK-005-xx | Golden files, determinism, non-vacuity probes |
| `OPEN-QUESTIONS.md` | A-xx, D-xx | Every ASSUMPTION, every decision for Camilo, the "belongs in Ulissy" list |

## Conventions

- **Requirement ids** are `BANK-<block>-<nn>`; each is one testable sentence using MUST / SHOULD / MAY.
- **ASSUMPTION** marks a statement that could not be verified against its primary source during this
  spec pass. Every assumption has an id `A-nn`, is listed in `OPEN-QUESTIONS.md`, and must be resolved
  (verified or removed) before the requirement that depends on it is implemented.
- **Verified** means: the layout, code, or rule was read in the cited document, retrieved on 2026-10-10.
  Nothing in these specs was filled in from memory; where the source could not be retrieved the item is an
  ASSUMPTION, not a guess presented as fact.
- **Client-agnostic:** no client names, no utility- or sector-specific scenarios, no personal data. Anything
  client-specific found during drafting was moved to the "belongs in Ulissy" list (ADR-0005 placement rule,
  `Ulissy-s-r-l/eu-governed-agent/docs/decisions/2026-09-23-placement-rule-meridian-vs-product.md`).
- Field positions for fixed-width records are **1-based inclusive** ranges exactly as the CBI documents print them.

## Source register (retrieved 2026-10-10)

| Ref | Document | Where retrieved | Used for |
|---|---|---|---|
| S1 | **CBI-RND-001 v6.05** "Rendicontazioni", CBI Standard tecnici, release 05/03/2013, 55 pp. | https://babons.it/wp-content/uploads/CBI-RND.pdf (mirror of the Consorzio CBI document) | CBI RH layout: records RH, EF, 61, 62, 63 (all structured variants), 64 |
| S2 | **CBI-RIB-001 v6.02** "Ricevute Bancarie – Ri.Ba.", CBI Standard tecnici, 27-05-2010, 21 pp. | https://online-smallbusiness.unicredit.it/nb/it/doc/CBI-RIB-001_6_02.pdf | Documented analogue for a CBI return-flow ("esiti") structure; cents convention for CBI amounts |
| S3 | "Elenco delle Funzioni del Servizio CBI" (record-type / manual map), 19/04/2016 | https://docs.eos-solutions.it/Images/PR000384-0/CBI_RecordType.pdf | Flow codes: RH-EF ↔ CBI-RND-001; IM-EF ↔ CBI-MAV-001 (dispositions, esiti, richiami); SDD returns ↔ STIN-MO-001 |
| S4 | **EPC173-14 v8.0** "Guidance on Reason Codes for SDD R-transactions", 28 Nov 2024 | https://europeanpaymentscouncil.eu/sites/default/files/kb/file/2024-11/EPC173-14%20v8.0%20Guidance%20on%20Reason%20Codes%20for%20SDD%20R-transactions.pdf | SDD reason codes, R-transaction type per code, 8-week / 13-month refund windows |
| S5 | **EPC131-08 2025 V1.0** SDD B2B Customer-to-PSP Implementation Guidelines, issued 28 Nov 2024, effective 5 Oct 2025 | https://www.europeanpaymentscouncil.eu/sites/default/files/kb/file/2025-10/EPC131-08%20SDD%20B2B%20C2PSP%20IG%202025%20V1.0.pdf | ISO versions pain.008.001.08, pain.002.001.10 (B2B); used by analogy for Core (A-04) |
| S6 | **EPC132-08 2025 V1.0** SCT Customer-to-PSP Implementation Guidelines, issued 28 Nov 2024, effective 5 Oct 2025 | https://www.europeanpaymentscouncil.eu/sites/default/files/kb/file/2025-10/EPC132-08%20SCT%20C2PSP%20IG%202025%20V1.0.pdf | pain.001.001.09, pain.002.001.10; Remittance Information/Unstructured = Max140Text |
| S7 | **EPC130-08 v7.0** SDD Core Customer-to-Bank IG (older generation) | https://www.sepaesp.es/f/websepa/secciones/Instrumentos/EPC130-08_SDD_core_C2B_IG.pdf | Confirms the Reject dataset is reported to the Creditor via pain.002 (DS-05) |
| S8 | **EPC087-22 v3.1** Migration to the 2019 version of ISO 20022, 09 May 2023 | https://www.europeanpaymentscouncil.eu/sites/default/files/kb/file/2023-05/EPC087-22%20v3.1%20... | Context: 19 Nov 2023 migration; inter-PSP pacs versions |
| S9 | **EPC188-09 v2.0** Recommendation on Customer Reporting SCT and SDD | https://dirittobancario.it/wp-content/uploads/sites/default/files/allegati/epc188-09_v2.0_recommendation_on_customer_reporting_sct_and_sdd.pdf | Mapping of SDD mandate / end-to-end data into camt.052/053/054 (then .001.02) |
| S10 | **SIX Swiss Payment Standards – IG Cash Management v2.0.2** (SPS 2023, effective 20 Nov 2023) | https://www.six-group.com/dam/download/banking-services/standardization/sps/ig-cash-management-v2.0.2-en.pdf | Documented live implementation of camt.052/053/054 **.001.08** |
| S11 | "Algoritmi per il calcolo e la verifica del codice IBAN", ITT Fauser (educational, with C reference code, 22/04/2022) | https://netlab.fauser.edu/risorse/classi3/tp/iban.pdf | Italian IBAN structure, Italian CIN tables, ISO 7064 mod 97-10 check digits |
| S12 | AgID / Agenzia delle Entrate-Riscossione, "RAV con pagoPA per PSP" | https://www.agid.gov.it/sites/default/files/repository_files/agengiaentraterisc_rav_psp.pdf | 17-digit RAV code structure (used as analogue for MAV identifiers, A-03) |
| S13 | ISO 9362 BIC structure (secondary: Wikipedia "ISO 9362", ACT treasurers wiki) | https://en.wikipedia.org/wiki/ISO_9362 · https://wiki.treasurers.org/wiki/Business_identifier_code | BIC8/BIC11 layout |

**Not retrievable on 2026-10-10 (HTTP 403/404), therefore ASSUMPTION where relied upon:** CBI-MAV-001 v6.01;
CBI-STD-001 (Appendix B causali, Appendix D currencies); EPC016-06 2025 SDD Core Rulebook v1.1;
EPC130-08 2025 SDD Core C2PSP IG V1.0; EPC188-09 v5.0; the iso20022.org message catalogue. See `OPEN-QUESTIONS.md`.

## Existing Meridian code this spec builds on (read 2026-10-10)

- Seeding: `meridian/generative.py:62-63` (NumPy `default_rng(seed)` + `Faker.seed(seed)`), `meridian/agents.py:26-33, 88-91`
  (blake2b-derived keys), `meridian/driver.py:34` (fixed sim epoch).
- Answer key handling: `meridian/driver.py:243-256` writes `episodes/<episode>.export.json`; `.gitignore:9-14`
  keeps `episodes/` and `ground_truth/` out of git.
- Swappable output: `meridian/scorer.py:42-48` (`Scorer` protocol), `meridian/grafomem_adapter.py` (the only
  network module), `tests/test_boundary.py` (moat tests), `tests/test_pii_free.py`, `tests/test_determinism.py`.
