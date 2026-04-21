# SQL Queries Guide

The SQL files in this folder are written in BigQuery SQL and target:

- `project-43c16c81-2fd4-4871-8ac.payment_optimization.payments`

Some profitability queries also require:

- `project-43c16c81-2fd4-4871-8ac.payment_optimization.dim_fees`

## Recommended Run Order

1. `Checking errors.sql` - Detect duplicate transaction IDs.
2. `Dim_Fees.sql` - Create `dim_fees` fee reference table.
3. Core KPI queries:
   - `Global Auth Rate.sql`
   - `Overall Auth Rate by Partner Bank (1).sql`
   - `Error Pareto Analysis.sql`
4. Deeper diagnostics:
   - `Smart Retry Analysis (LEAD Window Function).sql`
   - `Rolling 3-Day Average (Window Frame).sql`
   - `Hourly Heatmap Prep (Time Segmentation).sql`
   - `Final Heatmap Summary (Dense Reporting).sql`
   - `Customer Segmentation.sql`
   - `Cohort Analysis.sql`

## Output Mapping

Many query outputs are exported into `../Tables/` as CSV snapshots for reporting.
