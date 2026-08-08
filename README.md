# Meridian

A synthetic commercial + trade-finance bank that runs the **real governed loop** on
[Grafomem](https://github.com/GNS-Foundation) — the *spine* (B1). Synthetic underwriting agents
make judgment decisions; those decisions and their eventual outcomes are posted to Grafomem over the
public API, and **Capability-Grounded Reputation (CGR) moves on the real runtime**. This reproduces
our prior *offline* validation *live*: honest, capable agents climb; the answer key is checked blind.

## The moat boundary (non-negotiable)

Meridian is the **SIM** — open-sourceable eventually. It **never** contains CGR scoring, the vaulted
substrate, or the field engine. The sim emits standard `Decision`/`Outcome` records and posts them
through a thin adapter behind a **`Scorer` protocol** (`meridian/scorer.py`). Swap the scorer out and
you have a clean, publishable sandbox. **CGR stays in Grafomem, reached only via the public API.**

```
sim (this repo)  ──Decision/Outcome──►  Scorer protocol  ──►  GrafomemScorer (httpx)  ──►  Grafomem API
   ground-truth ledger stays LOCAL, git-ignored, never posted        (CGR/vault/field live only here)
```

## What B1 is

The spine only, one domain (**invoice / receivables financing**):
- a seeded generative ground-truth model (planted agent capability, hidden client pay-probability,
  invoices with hidden difficulty + true outcome);
- entities as Pydantic + Faker, **PII-free by construction**;
- underwriting agents bound to **local Ed25519 identities** (`agent_key` = pubkey hex);
- the posting adapter → `POST /v1/governed/decisions` + `POST /v1/governed/outcomes`;
- a bounded, **deterministic** simulated-time episode (~20 agents) that runs the loop end-to-end and
  verifies CGR actually **resolves** the outcomes (posterior moves), not a silent zero-resolve.

Later phases (not here): fraud + Gate-1 τ (B2), KYC/collections/credit-committee HITL (B3),
auditor/regulator (B4), treasury/capital (B5), console + OSS extraction (B6).

## Ingestion facts (Grafomem, confirmed in B1 Step-0)

- **Decision** → `POST /v1/governed/decisions` `{decision:"certify"|"reject", reason, invoice_id,
  context, model_id, agent_handle, verifiability_tag:"judgment"|"rule", agent_tier, agent_key}`.
- **Outcome** → `POST /v1/governed/outcomes` `{invoice_ref, outcome:paid|default|disputed|late|
  written_off, outcome_date}`. **Join key = the raw `invoice_id`** — the server pseudonymizes it on
  BOTH the decision (`invoice_id`) and the outcome (`invoice_ref`) with the same per-tenant HMAC, so
  posting the **same raw id** on both sides makes them join. One invoice = one decision (unique id).
- CGR scores only `certify`+`judgment` decisions; only `paid`/`default` outcomes move the posterior.
- Auth: the `virtualbank` tenant API key (ENV). Reputation read-back needs `cgr:read`.

## Run

```bash
cp .env.example .env      # fill MERIDIAN_GRAFOMEM_API + _API_KEY (from the provisioning NOTICE)
pip install -e ".[dev]"

# offline sandbox (no network, deterministic) — the swappable Scorer proves the boundary:
python -m meridian.driver --seed 42 --agents 20 --scorer local

# live episode against the virtualbank tenant (only after the tenant is provisioned + attested):
python -m meridian.driver --seed 42 --agents 20 --scorer grafomem
```

The live run prints an evidence pack: `N judgment-certifies posted → N resolved` (join proof),
the honest-agent reputation ordering, and per-tenant row counts (idempotent — fresh episode ids).

## Ground truth

`generative.py` writes the full answer key (true creditworthiness, true outcomes, planted capability)
to `ground_truth/` — **git-ignored, never posted**. CGR accuracy is measured offline against it, blind.
