# Reporting Marts

BigQuery SQL, cleaned up from `../analysis/` into stable, reporting-ready
selects. Same source table as the analysis layer:

- `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`

Every mart here queries that real payments table directly and uses
`SAFE_DIVIDE` and consistent snake_case output columns. There is no mart in
this folder that depends on a table this project doesn't actually populate —
the fraud model runs locally in Python (`fintech.py`, `score_daily.py`) and
its outputs are exported to `powerbi-data/fraud_scored_transactions.csv` and
`powerbi-data/fraud_model_holdout_metrics.csv` directly, not through BigQuery.

| Mart | Purpose |
| --- | --- |
| `mart_payment_kpis.sql` | Daily-grain authorization rate, volume, and failed-value pool for stakeholder trend reporting. |
| `mart_bank_auth_performance.sql` | Authorization rate, failed-value concentration, and top decline reason by issuer bank. |
| `mart_decline_reason_opportunity.sql` | Failed value, observed 24h recovery, and policy-eligible unrecovered pool ranked by decline reason. |
| `mart_retry_recovery.sql` | Same-payment-intent 24h recovery rate by initial decline reason (production-quality version of `../analysis/retry_recovery_by_decline_reason.sql`). |
| `mart_retry_timing_windows.sql` | Buckets failed payments by how long until the same user's next success, for retry-timing policy decisions. |

## Recommended run order

1. `mart_payment_kpis.sql` — headline trend.
2. `mart_bank_auth_performance.sql` and `mart_decline_reason_opportunity.sql` — where the failures concentrate.
3. `mart_retry_recovery.sql` and `mart_retry_timing_windows.sql` — retry policy design.
