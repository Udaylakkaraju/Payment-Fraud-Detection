# Data Dictionary

This dictionary documents the main source tables and generated outputs used in the payments optimization and fraud analytics project.

---

## Payments Table

Canonical file: `powerbi-data/payments.csv`  
Raw source: `data/raw/payments.csv`

| Column | Description |
| --- | --- |
| `Transaction_ID` | Unique payment transaction identifier. |
| `User_ID` | Customer/user identifier used for retry and journey analysis. |
| `Timestamp` | Payment timestamp. |
| `Amount` | Transaction amount. |
| `Issuer_Bank` | Issuing bank associated with the card/payment. |
| `Card_Brand` | Card network or brand. |
| `Interchange_Fee` | Estimated interchange fee for the transaction. |
| `Status` | Payment result or decline reason, including `00: Success`. |

Power BI columns: `transaction_id`, `user_id`, `payment_timestamp`, `amount`, `issuer_bank`, `card_brand`, `interchange_fee`, `payment_status`.

---

## Fraud Table

Source file: `data/processed/fraud_transactions.csv`

| Column | Description |
| --- | --- |
| `transaction_id` | Unique fraud-model transaction identifier. |
| `transaction_time` | Timestamp used for feature engineering and time-based holdout. |
| `amount` | Transaction amount. |
| `is_fraud` | Fraud label used for supervised training/evaluation. |
| `user_id` | User identifier used for velocity features. |
| `device_type` | Device category used for model features. |
| `merchant_category` | Merchant category used for model features. |
| `ip_country` | Country derived from IP/location signal. |
| `entry_mode` | Payment/card entry mode. |

---

## Scored Outputs

Files:

- `outputs/fraud_scored_transactions.csv`
- `outputs/daily_scored_transactions.csv`

Power BI file: `powerbi-data/fraud_scored_transactions.csv`

| Column | Description |
| --- | --- |
| `transaction_id` | Transaction identifier from the fraud dataset. |
| `transaction_timestamp` | Parsed transaction timestamp (renamed from `transaction_time` in Power BI export). |
| `transaction_amount` | Transaction amount (renamed from `amount` in Power BI export). |
| `fraud_user_id` | Fraud-snapshot user identifier; compatibility name expected by the existing PBIX. |
| `device_type` | Original device category. |
| `merchant_category` | Original merchant category. |
| `ip_country` | Original country signal. |
| `entry_mode` | Original payment entry mode. |
| `is_fraud` | Fraud label, included when available in the input. |
| `inter_txn_minutes` | Minutes since the user's previous transaction; high default means no prior transaction. |
| `fraud_probability` | Supervised model fraud probability. |
| `risk_score` | Consistent risk ranking field where higher means riskier. |
| `risk_flag` | Binary review flag based on model threshold or anomaly prediction. |
| `risk_bucket` | Business-friendly bucket: `Low`, `Medium`, `High`, or `Critical`. |

---

## Scenario Output

File: `outputs/recovery_scenarios.csv`
Power BI file: `powerbi-data/recovery_scenarios.csv`

| Column | Description |
| --- | --- |
| `decline_reason` | Initial failed payment status or `ALL_DECLINES` summary row. |
| `issuer_bank` | Issuer bank segment or `ALL_BANKS` summary row. |
| `card_brand` | Card brand segment or `ALL_BRANDS` summary row. |
| `failed_txns` | Count of initially failed payment intents in the segment. |
| `failed_amount` | Value of the initial failed payment intents. |
| `recovered_txns_observed` | Initially failed intents with a successful linked retry inside the configured window. |
| `recovered_amount_observed` | Initial failed value for intents with a successful linked retry. |
| `observed_recovery_rate_pct` | Linked recovered intents divided by initially failed intents. |
| `unrecovered_amount_pool` | Failed value not observed as recovered within the window. |
| `decline_code` | Normalized decline code used for policy lookup. |
| `automatic_retry_allowed` | Whether the decline policy permits automated retry. |
| `scenario_eligible_unrecovered_amount` | Unrecovered value after non-retryable declines are excluded. |
| `window_minutes` | Recovery window used by the scenario simulator. |
| `scenario_recovery_lift_pct` | Assumed incremental recovery rate for scenario planning. |
| `estimated_incremental_recovered_amount` | Estimated additional recovered amount under the scenario assumption. |

---

## Power BI Helper Tables

Folder: `powerbi-data/`

| File | Purpose |
| --- | --- |
| `payments.csv` | Standardized payment operations fact table. |
| `retry_recovery_by_decline_reason.csv` | Recovery rate and recovered transactions by decline reason. |
| `decline_reason_pareto.csv` | Failure concentration by decline reason. |
| `bank_auth_rate.csv` | Authorization rate by issuer bank. |
| `hourly_auth_rate.csv` | Day/hour/bank authorization heatmap source. |
| `daily_auth_rate_trend.csv` | Daily auth rate and rolling 3-day trend. |
| `global_auth_rate.csv` | Single-row global authorization summary. |
| `fraud_scored_transactions.csv` | Fraud review queue and risk bucket source. |
| `feature_importance.csv` | Fraud model feature importance source. |
| `review_capacity_curve.csv` | Precision, recall, and workload trade-off across review capacities. |
| `payment_action_matrix.csv` | Decline-level recovery evidence, retry policy, and operations action. |
| `fraud_model_holdout_metrics.csv` | Focused holdout model metrics. |
| `recovery_scenarios.csv` | Retry recovery scenario estimates. |
