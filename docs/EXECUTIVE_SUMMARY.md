# Executive Summary — Payments Optimization

Anchored snapshot from checked-in CSV outputs. Dollar figures are **opportunity pools**, not realized revenue.

The same canonical retry metrics are used in the [Excel analysis workbook](../deliverables/Payments_Optimization_Excel_Analysis.xlsx), [Power BI report](../Payments_Optimization_Dashboard.pbix), and verified resume claims.

---

## Headline KPIs

| Metric | Value | Interpretation |
| --- | --- | --- |
| Transactions analyzed | 51,237 | Full payments snapshot in `powerbi-data/payments.csv` |
| Authorization failure rate | 12.92% | 6,619 failed transactions |
| Failed payment value pool | $500,157.98 | Revenue at risk from declines |
| Same-intent 24h recovery | 855 intents (13.71%) | Successful retry matched through the `-RETRY` transaction lineage |
| Policy-eligible unrecovered value | $232,327.98 | Unrecovered pool limited to decline codes allowing automated retry |

---

## Top 3 Decline Drivers (by volume)

| Rank | Decline reason | Failed txns | Share of failures | 24h recovery rate |
| --- | --- | --- | --- | --- |
| 1 | 51: Insufficient Funds | 3,043 | 48.8% | **28.1%** |
| 2 | 59: Suspected Fraud | 2,092 | 33.5% | 0.0% |
| 3 | 91: Issuer System Timeout | 1,102 | 17.7% | 0.0% |

**Takeaway:** Insufficient funds is the largest failure bucket and shows the strongest natural recovery signal — the best candidate for smarter retry timing.

---

## Retry Timing Curve (when, not just whether, recovery happens)

Intent-matched insufficient-funds recoveries, bucketed by minutes between the original decline and the matched success (`retry_timing_analysis.py` → `data/sql_exports/retry_timing_windows.csv`):

| Time since decline | Share of eventual 24h recoveries | Cumulative share |
| --- | ---: | ---: |
| 0–2 hours | 8.3% | 8.3% |
| 2–6 hours | 16.0% | 24.3% |
| 6–24 hours | 75.7% | 100.0% |

**Takeaway:** almost none of the eventual recovery shows up before hour 6. A retry policy that fires within the first couple of hours is retrying before the outcome is knowable for ~92% of eventual recoveries — this is the basis for the minimum-delay specification in P1 below, replacing the earlier "test 1–24h" range with a data-backed floor.

## Interchange-Style Processing Cost by Decline Reason

`outputs/interchange_cost_exposure.csv` — observed cost, not a modeled placeholder (see [Operational Impact](#operational-impact-modeled-not-measured) below for the placeholder-based figures):

| Decline reason | Attempts | Processing cost | Recovered | Retry-eligible per policy? |
| --- | ---: | ---: | ---: | --- |
| Suspected fraud | 2,092 | $3,327.09 | 0 | No |
| Issuer system timeout | 1,102 | $1,518.01 | 0 | Yes — but 0% observed recovery |
| Insufficient funds | 3,043 | $4,486.05 | 855 | Yes |

**Takeaway:** blocking fraud from auto-retry avoids $3,327.09 in processing cost on transactions with a structural 0% recovery rate. Issuer timeout is currently classified as retry-eligible in the policy dimension (`data/reference/dim_decline_code.csv`, `technical_retry` class), but this snapshot shows 0 of 1,102 attempts recovering — $1,518.01 in processing cost sitting on a decline type behaving like a hard decline here. Flagged in P3 below as a policy assumption to test, not a settled conclusion (single-snapshot observation).

---

## Top 3 Retry Opportunities (by unrecovered dollars)

Using `outputs/recovery_scenarios.csv` at a conservative **10% incremental lift** on the unrecovered pool:

| Decline + bank + brand | Unrecovered pool | Est. 10% uplift |
| --- | --- | --- |
| Insufficient Funds · Chase · Visa | $26,118 | $2,612 |
| Insufficient Funds · Chase · Mastercard | $15,123 | $1,512 |
| Insufficient Funds · Wells Fargo · Mastercard | $14,185 | $1,419 |

Portfolio-wide at 10% lift on the policy-eligible pool: **~$23,233** estimated incremental recovery (scenario framing, not guaranteed).

---

## Fraud Review Queue (chronological test context)

| Metric | Value | Notes |
| --- | --- | --- |
| Evaluation | 60% train / 20% calibration / 20% test | Test rows are unseen by training and calibration |
| Test ROC-AUC | 0.621 | Moderate ranking signal, not production performance |
| Review queue | 200 transactions (top 10%) | Capacity-capped batch queue |
| Recall | 17.3% | 19 of 110 test fraud events in the queue |
| Precision | 9.5% | Versus 5.5% test prevalence |

**Takeaway:** Batch scoring (`score_daily.py`) produces a ranked review queue via `risk_bucket` and `risk_flag`. Treat model metrics as workflow demonstration, not production fraud performance.

---

## Recommended Actions

| Priority | Recommendation | Value driver | Effort | Risk | Owner | Measurement window |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | Retry policy for insufficient funds — set a **minimum 6-hour retry delay** (76% of eventual recoveries land in the 6–24h window; only 8.3% recover in the first 2 hours), prioritizing Bank of America / Capital One Visa paths (observed recovery >30%) | Largest unrecovered pool ($26K+ top segment); timing curve shows early retries fail predictably, not randomly | Medium (requires retry-orchestration change + holdout design) | Low — retry-eligible codes only, no fraud/customer-action declines touched | Payments ops / retry engineering | 4–6 week A/B test comparing immediate vs. 6h-delayed retry, min. sample sized per experiment table below |
| P2 | Decline-reason triage — exclude suspected fraud and customer-action declines from any automated retry; route to verification flows | Prevents false "recovery" attempts and compliance/chargeback exposure; avoids $3,327.09 in processing cost on transactions with 0% observed recovery | Low (policy/config change) | Low | Payments ops | Immediate; monitor false-retry rate monthly |
| P3 | Issuer timeout — re-test the `automatic_retry_allowed = true` policy classification. This snapshot shows 0 of 1,102 timeout attempts recovering ($1,518.01 in processing cost with zero return), despite policy currently treating it as a technical retry class. Investigate bank/time heatmaps for systemic timeout clusters in parallel. | Second-largest failure share (17.7%); a policy-vs-observed-data mismatch worth resolving before the next retry-config release | Medium (needs issuer/infra coordination + policy review) | Medium — outside internal control; retry misclassification risk | Payments infra / issuer relations | Pull a 90-day sample before changing the policy flag; monthly heatmap review in the meantime |
| P4 | Fraud operations — review `High`/`Critical` buckets first from daily scored output; hold queue at capacity-limited top 10% | Concentrates limited review capacity (1.7× baseline precision) | Low (workflow adoption, no model change) | Low | Fraud ops | Weekly queue-size and precision tracking |

**Note:** priority, effort, and risk are directional judgment calls based on the data patterns above, not a formal RICE/ICE scoring exercise — flag this if presenting to a stakeholder who expects a quantified prioritization model.

---

## Operational Impact (Modeled, Not Measured)

The dollar and rate figures above are observed in the data. Analyst-hours and net-contribution figures below are **not**: they are illustrative calculations built on placeholder operating assumptions, included to show how this analysis would translate into a business case — not as claims of realized savings.

**Assumptions (replace with real operating data before use):**

| Assumption | Placeholder value | Source |
| --- | --- | --- |
| Analyst review time per fraud-flagged transaction | 4 minutes | Illustrative — not measured |
| Fully-loaded analyst hourly cost | $35/hour | Illustrative — not measured |
| Retry attempt processing cost (network/interchange) | $0.05/attempt | Illustrative — not measured |
| Monthly transaction volume (for scaling) | ~17,000/month (51,237 over 3 months) | Derived from snapshot period |

**Derived, modeled figures (illustrative only):**

- If the fraud model were run monthly at the same 2,000-row batch size and 10%-capacity queue, review effort would be ~200 transactions × 4 min = **13.3 analyst-hours/month**, versus reviewing the full batch (2,000 × 4 min = 133 hours) — a modeled **~120-hour/month reduction in review load**, *not* a measured time savings, since no pre-ranking baseline was operated.
- At $35/hour, that modeled reduction is worth **~$4,200/month** in analyst time — again, a modeled placeholder, not an observed cost saving.
- The $23,232.80 illustrative 10% recovery scenario, net of an assumed $0.05/attempt retry cost across the ~6,237 eligible retries (~$312 in processing cost), nets to **~$22,921 modeled net contribution** — before any chargeback, false-retry, or compliance costs are factored in.
- **None of these figures should appear in a resume bullet or be cited as a result.** They exist to demonstrate business-case reasoning; they become real only after operating data replaces the placeholders and/or the experiment below is run.

### Validating the 10% recovery assumption

The 10% uplift is an assumption, not an observed effect. To turn it into a measured result would require a controlled experiment: randomly assign eligible insufficient-funds declines to a delayed-retry treatment window (6h, per the retry-timing curve above) versus the current immediate-retry control, size the sample using the existing 28.1% baseline recovery rate to detect a meaningful lift (roughly low thousands of transactions per arm at conventional power/significance thresholds, refined once a true baseline variance is available), and measure incremental authorization rate over a 4–6 week window while monitoring chargeback and complaint-rate guardrails. Until that test runs, the recovery scenario stays labeled as a scenario — the 6h delay is a data-backed starting point for the experiment, not a claim it's already been validated.

---

## What to A/B Test Next

| Experiment | Success metric | Guardrail |
| --- | --- | --- |
| Delayed retry (2h vs 24h) on insufficient funds | Incremental auth rate on retried cohort | Chargeback / complaint rate |
| Bank routing for low auth-rate issuer × hour | Auth rate uplift on routed volume | Latency / cost per txn |
| Review capacity 5% vs 10% | Fraud caught per reviewer hour | Queue size and review burden |

---

## Data Notes

- Payments and fraud tables are independent synthetic snapshots with different transaction IDs and no verified shared user namespace; they are not joined.
- SQL marts in `sql/marts/` target BigQuery; local Python pipelines run on checked-in CSVs.
- See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for column definitions.
