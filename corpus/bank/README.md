# Meridian virtual bank — conformance corpus (`corpus/bank/`)

**Status:** hand-authored test vectors derived from the merged specification `spec/MERIDIAN-BANK-000..005`
(`main` @ `fc545ac`). **Nothing here implements `meridian.bank`.** The only script, `lint_corpus.py`, checks
the corpus itself (record lengths, IBAN mod-97 and CIN, balance arithmetic, manifest completeness, coverage).

## Layout

```
corpus/bank/
  MANIFEST.json            every vector: id, kind, path, covers (BANK ids), assumptions (A-ids), artefacts, expected rule_id
  lint_corpus.py           corpus checks only; exit 1 on failure; prints coverage and uncovered BANK ids
  data/                    shared synthetic data: curated fictional names (candidate list for BANK-001-06),
                           synthetic banks/accounts (ABI 99xxx, A-08), SDD reason-code table (EPC173-14 v8.0 as in BANK-003-19)
  <vector-id>/vector.json  top-level vectors: depend on no ASSUMPTION
  _assumed/<vector-id>/    vectors that depend on an A-id (named in vector.json and MANIFEST)
```

Each `vector.json`: `id`, `kind` (`positive` | `negative` | `assumed`), `assumptions`, `covers`, `title`, `input`,
`expected` (`verdict` `accept`/`reject`, `rule_id` for rejects, `answer_key` rows, artefact list), `notes`.
Artefacts (`RH.txt`, `IM.txt`, `camt053.xml`, `camt054.xml`, `pain002.xml`) sit next to `vector.json`.
Fixed-width artefacts use CR LF (BANK-004-03 default).

## How these were authored

Each vector was written as literal field values (positions per BANK-004-11..19, which transcribe CBI-RND-001 v6.05).
A scratch calculator (not committed) padded the 120-character records from those literals and computed the IBAN
check digits and Italian CIN with the algorithm of BANK-001-05 (S11); the committed files are static. `lint_corpus.py`
re-derives both independently, so an authoring slip shows up as a lint failure, not as a silently wrong vector.

## Why most writer vectors sit under `_assumed/`

The spec itself marks the CBI amount unit (A-01), the RI1 field extent (A-10), the CBI IM layout (A-02), the MAV
identifier (A-03), the ISO message versions (A-04, A-06), the synthetic ABI range (A-08) and the IBAN algorithm source
(A-09) as ASSUMPTIONS. Any artefact that encodes an amount, a camt/pain version or an IBAN therefore depends on one of
them and is filed under `_assumed/` with the A-id, as the authoring rule requires. Top-level vectors are those grounded
only in verified sources: SDD reason codes and refund windows (EPC173-14 v8.0), the 140-char remittance rule
(EPC132-08 2025), the noise operators and answer-key rules (spec-defined behaviour with no external layout).

## Operator semantics used by the vectors (BANK-003-05, BANK-003-08)

| Operator | Definition used here |
|---|---|
| `truncate_to(n)` | first `n` characters |
| `upper()` | uppercase |
| `strip_accents()` | Unicode NFD, combining marks removed |
| `drop_separators()` | hyphens removed |
| `transpose_adjacent_digits(k)` | swap the k-th and (k+1)-th **digit** of the string (digits only, 0-based) |
| `drop_token(i)` | remove the i-th whitespace-separated token (0-based) |
| `prepend_bank_boilerplate()` | prefix `BONIFICO SEPA A VS FAVORE DA ` |
| `concat_two_references()` | second `REF` reference inserted after the first |
| `initials()` | `SURNAME G.` (uppercase surname, given-name initial, dot) |
| `swap_surname_given()` | `Surname Given` |
| `truncate_to_yyy_width()` | first 40 characters (record 63 `YYY` pos. 41-80) |
| `third_party_payer()` | emitted payer ≠ intended holder; answer key keeps `intended_holder_id` |

The implementation may define these differently; if it does, the vectors (not the spec) are what to revise.

## camt / pain.002 caveat

XML artefacts follow ISO 20022 element names as known to the author and are **not** validated against the ISO XSDs
by the lint (D-02: schemas not vendored). BANK-004-44 validation happens in the implementation's tests. `BkTxCd`
values (`PMNT/RCDT/ESCT`, `PMNT/IDDT/RRTN`) are placeholders pending D-15.

## Polarity, kinds and placement

`kind` says where a vector rests: `positive` / `negative` (verified sources or spec-defined behaviour) or `assumed`
(depends on an open A-id, filed under `_assumed/`). `polarity` says what the lint expects: `positive` vectors must
raise no rule; `negative` vectors must raise exactly their `expected.rule_id`. Polarity is read from `vector.json`
(and cross-checked against `MANIFEST.json`), never inferred from a path or directory name. Rule ids that only a
future semantic validator can evaluate (answer-key and SDD timeline rules) are stated by the vector and listed in the
lint as not evaluable by the corpus check.

## Client-agnostic deny-list (BANK-005-32)

The lint can scan `corpus/` and `spec/` for a deny-list of real institution or client identifiers. That list is **never
stored in this public repository**: set `MERIDIAN_DENYLIST_FILE` to a local file (one term per line, `#` comments) and
run the lint; any case-insensitive hit fails the run. When the variable is unset the check is **skipped with a stated
reason**, not silently passed. The repository's own sweep policy is that fictional names must be sector-neutral and
must not hint at any real organisation.

## Lint self-test (non-vacuity)

`python3 corpus/bank/lint_corpus.py --self-test` mutates a copy of one known-good artefact per check (RH record length,
61↔64 date and currency, balance, cheque rule, six 63s, RI1 removed, EF count, non-numeric amount, YYY name width,
unsupported 63 body, record 65, IBAN corrupted in record 61, in record 63 YY2 and in camt XML, CIN, IBAN length, BIC
length, MAV length), asserts the expected rule is raised, and then asserts the untouched originals are clean. A check
that cannot catch its own mutation fails the self-test.

## Coverage

Run `python3 corpus/bank/lint_corpus.py`. Requirements without a vector are mostly process rules (scope, packaging,
determinism tests, CLI, storage, scenario discovery) that have no artefact to assert; they are listed by the lint so
the implementation PR can cover them with tests instead.
