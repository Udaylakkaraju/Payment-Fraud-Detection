# Generated outputs — canonical filenames

Artifacts produced by the Python pipeline:

| File | Command | Purpose |
| --- | --- | --- |
| `fraud_scored_transactions.csv` | `python fintech.py train ...` | Chronological test rows unseen by training and calibration. |
| `daily_scored_transactions.csv` | `python score_daily.py ...` | Label-free batch scoring demonstration queue. |
| `fraud_model.joblib` | `fintech.py train` | Local model artifact used by batch scoring; generated but not versioned. |
| `train_metrics_report.csv` | `fintech.py train` | Chronological test KPI block after separate threshold calibration. |
| `feature_importance.csv` | `fintech.py train` | Chronological test permutation importance for fraud-risk drivers. |
| `review_capacity_curve.csv` | `fintech.py train` | Precision, recall, and review workload at 5%, 10%, 15%, and 20% queue capacity. |
| `recovery_scenarios.csv` | `scenario_simulator.py` | Same-payment-intent recovery and policy-eligible scenarios by decline reason, issuer bank, and card brand. |
| `payment_action_matrix.csv` | `prepare_powerbi_tables.py` | Decline-level recovery evidence joined to the retry policy and recommended operations action. |

**Legacy names (removed):** `fraud_predictions.csv`, `daily_fraud_predictions.csv`, `fraud_model_output.csv`, `daily_fraud_metrics.csv`, `final_alert_output.csv` — superseded by the canonical filenames above.

Scored columns:

- `fraud_probability` / `risk_score`: model ranking score; higher means higher review priority.
- `risk_flag`: top 10% of the scored batch, matching the assumed review capacity.
- **Business review field:** `risk_bucket` (`Low`, `Medium`, `High`, `Critical`) is included in train and inference scored outputs.
