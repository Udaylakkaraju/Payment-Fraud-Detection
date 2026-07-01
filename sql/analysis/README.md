# SQL Queries Guide

Reporting-ready KPI / mart selects live under [`../marts/`](../marts/).

The SQL files in this folder are written in BigQuery SQL and target:

- `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`

Some profitability queries also require:

- `project-43c16c81-2fd4-4871-8ac.payment_optimization.dim_fees`

## Recommended Run Order

1. `data_quality_checks.sql` - Detect duplicate transaction IDs.
2. `dim_fees.sql` - Create `dim_fees` fee reference table.
3. Core KPI queries:
   - `global_auth_rate.sql`
   - `bank_auth_rate.sql`
   - `decline_reason_pareto.sql`
4. Deeper diagnostics:
   - `retry_recovery_by_decline_reason.sql`
   - `daily_auth_rate_trend.sql`
   - `hourly_auth_rate.sql`
   - `bank_performance_bucket_summary.sql`
   - `customer_segments.sql`
   - `cohort_failure_rate.sql`

## Query Catalog

| File | Business question | Key SQL techniques |
| --- | --- | --- |
| `global_auth_rate.sql` | What share of payment attempts succeed portfolio-wide? | Conditional aggregation |
| `bank_auth_rate.sql` | Which issuing banks approve at the lowest rates? | Grouped conditional aggregation |
| `decline_reason_pareto.sql` | Which decline reasons account for most failures? | Window share-of-total (Pareto) |
| `retry_recovery_by_decline_reason.sql` | Which failed intents recover through a linked retry within 24h? | First-success window functions, intent lineage joins |
| `daily_auth_rate_trend.sql` | Is authorization performance trending up or down? | Rolling window frames |
| `hourly_auth_rate.sql` | When during the week do failures cluster? | Time-part extraction, segmentation |
| `bank_performance_bucket_summary.sql` | How often does each bank operate in a degraded state? | Dense bucketing for heatmap reporting |
| `card_brand_profitability.sql` | Which card brands are most profitable after fees? | Fact-to-dimension financial joins |
| `customer_segments.sql` | How do users break down by payment behavior? | CASE-based segmentation |
| `cohort_failure_rate.sql` | Do newer signup cohorts fail more often? | Cohort bucketing |
| `high_maintenance_users.sql` | Which users generate outsized failure volume? | HAVING-filtered aggregates |
| `decline_reason_cleaning_summary.sql` | Are raw decline strings mapped to clean categories? | String parsing / regex cleanup |
| `weekend_activity_analysis.sql` | Does weekend traffic behave differently? | Day-type segmentation |

## Output Mapping

Query outputs are exported into [`../../data/sql_exports/`](../../data/sql_exports/) as CSV snapshots (same base filenames). `prepare_powerbi_tables.py` converts them into the stable Power BI contracts in `powerbi-data/`.
