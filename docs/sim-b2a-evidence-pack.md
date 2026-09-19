# SIM-B2a — competence-fraud catch (the money demo)

**Live episode `b2a1`, seed 300, tenant `virtualbank` on the production Grafomem runtime.**
Sim-side only — no Grafomem change. A 3-agent collusive ring (of 20 underwriters) pads a healthy
book of easy RULE-tagged paids **calibrated to the honest population's raw paid-rate**, then
certifies fabricated invoices as JUDGMENT-tagged advances that all default. A naive raw paid-fraction
can't see it; the judgment-only CGR floors all three to the bottom.

## The one-line result

> Three fraud agents look **average** to a naive scorer (paid-fraction 0.483 vs honest 0.487) and
> land at the **exact bottom** of the CGR ranking (0.030 vs honest 0.533). One of them has hidden
> capability **0.907** — a "star" to any capability/naive view — and CGR still floors it, because its
> *judgment book* is fabricated defaults.

## Contrast (live, on the same agents)

| cohort | naive raw paid-fraction | CGR (judgment-only) |
|---|---|---|
| honest (17 agents) | 0.4867 | 0.5329 |
| **ring (3 agents)** | 0.4833 | **0.0303** |
| **gap** | **−0.0034  (blind ✓)** | **−0.5026  (flagged ✓)** |

Offline acceptance gate (locked as a test across seeds 200/300/137/42/7): naive `|gap| < 0.10` AND
judgment `gap < −0.30`. Live episode reproduces it: naive −0.003, judgment −0.503.

## CGR ranking — ring at the bottom

`fraud_at_bottom: true` — the bottom 3 CGR scores are exactly the 3 ring agents:

| rank | handle | kind | CGR | naive | n_resolved | hidden cap |
|---|---|---|---|---|---|---|
| 1 | underwriter-13 | honest | 0.889 | 0.686 | 7 | 0.842 |
| 2 | underwriter-12 | honest | 0.727 | 0.611 | 20 | 0.709 |
| … | … | honest | … | … | … | … |
| 17 | underwriter-02 | honest | 0.250 | 0.318 | 22 | 0.417 |
| **18** | **underwriter-19** | **fraud_ring** | **0.030** | 0.483 | 31 | 0.404 |
| **19** | **underwriter-18** | **fraud_ring** | **0.030** | 0.483 | 31 | **0.907** |
| **20** | **underwriter-17** | **fraud_ring** | **0.030** | 0.483 | 31 | 0.459 |

## DoD guarantees (all held)

- **Live join-verify:** `409 judgment-certifies posted → 409 resolved (OK)`; `cgr_n_pending: 0`. No
  silent-no-op — outcomes actually joined to decisions on the live runtime.
- **Tenant isolation:** the virtualbank key sees **80 agents, all `@virtualbank`, zero leak** (60 from
  SIM-B1 + 20 from SIM-B2a). No cross-tenant visibility.
- **Determinism + idempotency:** everything derives from `--seed 300`; invoice ids namespaced by
  `--episode b2a1` (fresh → no double-post). Re-runnable to identical content.
- **Honest coupling still holds:** capability↔CGR Spearman 0.566 on the honest cohort (noisier than
  SIM-B1's 0.85 with 17 vs 20 honest agents and smaller per-agent n, but the ordering is intact).
- **Moat boundary intact:** the SIM contains no CGR/scoring/vault code and imports nothing from
  aml/grafomem (test-enforced). CGR is computed entirely by the live Grafomem runtime.

## Episode parameters

`seed=300 · episode=b2a1 · 20 agents (3 fraud_ring) · 1200 invoices · 60 clients · KAPPA=0.9 ·
rule_pad_rate=auto-calibrated · 1380 decisions / 409 judgment-certifies / 847 outcomes (406 paid /
441 default)`

## For the WOW screen

`episodes/b2a1.export.json` (git-ignored — handed to Cowork directly) carries, per agent:
`agent_handle, agent_key, kind (hidden ground truth), capability (hidden), naive_score, cgr_score,`
and the full per-decision `timeline` (invoice_id, tag, decision, outcome). Enough to build the
naive-vs-CGR split, the ranking with the ring highlighted, and per-agent decision drill-downs from
real live data.
