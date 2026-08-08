# Virtual Bank Phase B — B1 build brief (Meridian)

Stand up **Meridian**, a synthetic commercial + trade-finance bank, as a living tenant on Grafomem —
the spine only. B1 reproduces our prior offline validation *live*: synthetic underwriting agents make
judgment decisions that run the real governed loop on a dedicated tenant, and reputation moves on the
real runtime. Fraud (B2), KYC/collections/committee (B3), auditor/regulator (B4), treasury (B5), and
console/OSS (B6) come later.

## Confirmed ingestion mapping (B1 Step-0, approved)
- **Decision** → `POST /v1/governed/decisions`; **Outcome** → `POST /v1/governed/outcomes` (the Ulissy
  dogfood pattern). This is the path CGR scores — **no HITL, no per-decision human attest**. B1 **and**
  B2 use this direct path.
- **Gate-1 (τ)** — the CGR calibration/identity threshold (Sybil/farm resistance) — is a scoring-engine
  property, fully automatic, **no HITL**, and enters at **B2** over this same direct path.
- **HITL policy-gate + Ed25519 attest** (propose→gate→HITL→attest→execute) is the human path for
  consequential actions = the **credit-committee escalation**, entering at **B3** on the consequential
  subset only.
- **Join key = the raw `invoice_id`.** The server pseudonymizes it identically on the decision
  (`invoice_id`) and the outcome (`invoice_ref`), so posting the same raw id on both sides makes them
  join. One invoice = one decision (stable, unique id).
- CGR scores only `certify`+`verifiability_tag=judgment`; only `paid`/`default` outcomes move the
  posterior. Sub-threshold auto-approvals are `rule` (recorded, not scored).
- `agent_key` = the agent's GEIANT Ed25519 pubkey; CGR groups by it; **no mint handshake** — keys are
  supplied at decision time. B1 mints one Ed25519 keypair per agent locally.
- Tenant key scopes include **`cgr:read`** (+ `decisions:read` for the substrate) so B1 reads
  reputation back.

## Moat boundary
Meridian is the SIM (OSS-able later). It **never** contains CGR scoring, the vaulted substrate, or the
field engine. It emits standard records to Grafomem behind a `Scorer` protocol; swap the scorer and
you have a clean publishable sandbox. CGR stays in Grafomem, reached only via the public API.

## B1 Definition of Done (incl. the three added requirements)
- Private `GNS-Foundation/meridian` repo; local at `/Users/camiloayerbeposada/meridian`; `.gitignore`
  clean of secrets + ground-truth.
- `virtualbank` tenant provisioned (**Camilo-attested**) and RLS-verified isolated.
- A bounded ~20-agent episode: judgment decisions → posted → outcomes resolve → CGR reputation moves
  on the live runtime, reproducing the prior ordering (honest/capable agents climb; no fraud yet).
- **(1) Live outcome→decision join verification** — post decision + outcome with the same raw
  `invoice_id`; the evidence pack reports "N judgment-certifies posted → M resolved" from the real CGR
  posterior (n_resolved), not just "records landed". Surfaces any pre-pseudonymized-ref requirement.
- **(2) Determinism** — the generative model is seeded; no unseeded RNG; `(seed, episode)` reproducible.
- **(3) Tenant hygiene / idempotency** — invoice ids namespaced by a fresh `--episode`; a re-run never
  double-posts; row counts reported so `virtualbank` stays clean.
- The `Scorer` boundary is clean (no CGR/vault/field code in the repo).
- Evidence pack handed back for Cowork review.

## Governed-loop discipline
Repo scaffold + code commit freely (no prod state). Provisioning `virtualbank` in prod Grafomem is
consequential → prepare `ops/provision_virtualbank_tenant.sql`, hand Camilo the exact command, and
**wait for his attest** before it's applied — and before any driver run that posts to prod. The first
live driver run is the "graduation" moment → hand back evidence for Cowork review.

## B2 forward note (not a B1 blocker)
Phase A's Gate-1 win depended on τ bound to a **costly** GEIANT identity. B1 minting free local
keypairs is fine (no fraud yet), but B2's Sybil demo is credible only if the sim models the cost of a
*calibrated* identity vs a cheap one. Design that identity-cost model before B2 builds.
