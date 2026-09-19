# Virtual Bank Phase B — SIM-B3 definition (Meridian) — REPORT ONLY

**Status:** DEFINITION / scoping, report-only — no SIM code, no harness. **Date:** 2026-09-19.
**Roadmap position:** SIM-B1 (spine, GRADUATED) → SIM-B2 (fraud + Gate-1 τ; SIM-B2a competence-fraud catch
GRADUATED, Gate-1 τ + identity-cost pending) → **SIM-B3 = KYC / collections / credit-committee HITL**
→ SIM-B4 (auditor/regulator) → SIM-B5 (treasury/capital) → SIM-B6 (console + OSS extraction). Builds on the
SIM-B1 governed loop and SIM-B2 identity/fraud work; does not block on SIM-B2 Gate-1 τ landing but assumes it.

## What SIM-B3 is

The first **human-in-the-loop** slice: decisions that a person (not just an agent) dispositions,
on the same synthetic bank, flowing to CGR as **two-party governed disposition records**. Three
candidate sub-domains, in dependency order — SIM-B3 should take **credit-committee HITL first** (the
cleanest fit for the two-party envelope), with KYC and collections as follow-ons:

- **Credit-committee HITL** — an underwriting/limit decision escalated to a human officer who
  approves/declines with a rationale. Maps directly to a two-actor decision: the proposing agent +
  the approving officer. This is the archetype `cgr.disposition.v1` (decision 0009) was defined for.
- **KYC disposition** — onboarding a synthetic client: a HITL accept/reject/refer of an identity
  case. **PII tension (below) is sharpest here.**
- **Collections disposition** — a HITL action on a defaulted/late receivable (restructure, write-off,
  escalate), tied back to the SIM-B1/SIM-B2 outcome that produced the default.

SIM-B3 is still "one bank, synthetic, PII-free by construction, deterministic episode" — the SIM-B1
discipline — extended with a human approver principal and the two-signature record.

## The record shape — `cgr.disposition.v1` (decision 0009), not a bare governed decision

SIM-B1/SIM-B2 post `POST /v1/governed/decisions` (one actor: the agent). A HITL disposition has **two**
principals — the proposer and the human decider — and needs a defensible, tamper-evident
two-signature envelope. Decision 0009 resolved this with `cgr.disposition.v1` (a
`cgr.cosign.v1` profile): nested approver + system signatures, `grafomem.hitl.approval.v1` domain
tag, conformance-enforced. SIM-B3 is the **first real producer** of that record. Confirm before build:

- **Is `cgr.disposition.v1` implemented on the runtime yet, or spec-only?** 0009 accepted the
  *design*; SIM-B3 needs the record class + its HITL approval route live (grafomem `grafomem.hitl.*`
  approval endpoints exist as a read-only governance view — confirm the write/attest path). If it is
  spec-only, SIM-B3's first step is the runtime record class + attest route (a grafomem PR), not SIM code.
- **Approver identity (gap 3a, unresolved in 0009).** A defensible HITL approval needs a *verified
  named person*; 0009 left "verified-named-person identity NOT resolved" as a separate assurance
  dependency (KYC/IDV is not built; PoH is proof-of-trajectory). SIM-B3 must decide: model the officer as
  a **synthetic assured identity** (a seeded Ed25519 approver key labelled "verified" for the SIM,
  with the assurance gap explicitly stubbed and documented), NOT claim real IDV. This keeps SIM-B3
  honest — it demonstrates the *mechanism* (two-party signed disposition → CGR), not consumer KYC.

## PII tension — KYC without PII (must resolve before the KYC sub-domain)

Meridian is **PII-free by construction** (SIM-B1: entities are synthetic, Faker, no real personal
data). KYC is *about* personal identity. SIM-B3 must model KYC/collections **without** real PII:
synthetic subjects with **pseudonymous refs** (the `invoice_ref` HMAC-pseudonymization pattern
generalises — a per-tenant HMAC subject ref, pure-equality join preserved, no personal fields on
the signed record). The disposition record carries the *decision + rationale + pseudonymous
subject ref*, never identity attributes. This is the same primitive SIM-B2/0009 already point to
(evidence-digest + HMAC-pseudonym from `provenance.py`/`invoice_pseudonym.py`). Credit-committee
first sidesteps this (a limit decision needs no identity attributes); KYC follows once the
pseudonymous-subject shape is agreed.

## Confirmed dependencies / Step-0 to run before building

1. **`cgr.disposition.v1` runtime status** — record class + HITL attest/approve route live? (grafomem)
2. **`governed:write` scope** — the SIM's posting key now needs `governed:write` (grafomem #170, this
   week) to `POST /v1/governed/*`; the disposition/attest route's scope must be confirmed too
   (HITL approval may need its own scope — check `require_scope` on the approval write path).
3. **Approver identity model** — synthetic assured Ed25519 officer key; assurance gap stubbed +
   documented (gap 3a).
4. **Pseudonymous subject ref** — reuse the `invoice_ref` HMAC pattern for KYC/collections subjects.
5. **SIM-B2 Gate-1 τ** — assumed available for the agent side; not a hard blocker for the credit-committee
   HITL demo (which is about the human disposition, not agent calibration).

## Moat boundary (unchanged from SIM-B1/SIM-B2)

The SIM contains **no CGR / scoring / vault / disposition-signing code** and imports nothing from
`aml`/`grafomem` (test-enforced). It only calls the public API (governed decisions/outcomes + the
HITL disposition/attest route). CGR and the signed two-party record are produced entirely by the
live Grafomem runtime. SIM-B3 keeps this: the officer's signature is minted via the runtime's HITL
attest path, not in the SIM.

## SIM-B3 Definition of Done (draft — to confirm with the operator)

- **Live two-party disposition:** a credit-committee case → agent proposal `POST
  /v1/governed/decisions` → human officer disposition via the HITL attest route → a
  `cgr.disposition.v1` record persisted and **conformance-verified** on the live runtime (both
  signatures present, `grafomem.hitl.approval.v1` domain, verifies independently).
- **Join-verify (SIM-B1 discipline):** the disposition joins to its proposal and (for collections) to
  the SIM-B1/SIM-B2 outcome that triggered it — no silent no-op; `cgr_n_pending` moves as expected.
- **Tenant isolation:** the virtualbank key sees only `@virtualbank` subjects/agents; zero leak.
- **Determinism + idempotency:** everything from a seed; case ids namespaced by `--episode b3*`;
  re-runnable to identical content.
- **PII-free proof:** the signed disposition record carries no personal attributes — only a
  pseudonymous subject ref + decision + rationale; test-enforced (walk the record, assert no PII
  fields).
- **Approver honesty:** the officer identity is a synthetic assured key; the assurance gap (no real
  IDV) is documented on the record/brief, not hidden.
- **Moat boundary intact:** SIM imports nothing from `aml/grafomem` (test-enforced).

## Open questions for the operator

1. **Sub-domain order** — confirm credit-committee HITL first (recommended), KYC + collections next?
2. **`cgr.disposition.v1`** — is the runtime record class + HITL attest route in scope for SIM-B3 (likely
   a grafomem PR precedes the SIM), or already available?
3. **Approver assurance** — accept a synthetic "verified" officer identity for SIM-B3 (gap 3a stubbed),
   or does SIM-B3 require the real verified-named-person path (much larger, pulls in KYC/IDV)?
4. **Where SIM-B3 sits vs SIM-B2 Gate-1 τ** — sequence SIM-B3 after Gate-1 τ lands, or in parallel?

Report only — no SIM code, no harness, no runtime record class written here.
