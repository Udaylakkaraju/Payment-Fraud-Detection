# Generated outputs — canonical filenames

Artifacts produced by the Python pipeline:

| File | Command | Purpose |
| --- | --- | --- |
| `fraud_scored_transactions.csv` | `python fintech.py train ...` | Full labeled scoring table after refit-on-all-data step. |
| `daily_scored_transactions.csv` | `python score_daily.py ...` or `fintech.py infer ...` | Batch scoring of new transactions. |
| `fraud_model.joblib` | `fintech.py train` | Serialized model + vocabs + threshold metadata. |
| `train_metrics_report.csv` | `fintech.py train` | Holdout KPI block (counts, ROC-AUC column is `roc_auc`). |
| `model_benchmark_results.csv` | `benchmark_models.py` | Supervised baseline benchmarks (test-set metrics columns end in `_test` where labeled). |

**Legacy names (avoid for new runs):** `fraud_predictions.csv`, `daily_fraud_predictions.csv`, `fraud_model_output.csv` referred to older defaults and were superseded by the names above — remove or regenerate if seen in one-off folders.

Scored columns:

- **Supervised classifiers:** `fraud_probability`, `risk_score` (same value; higher = riskier), `risk_flag`.
- **Isolation Forest:** `anomaly_score` (raw `decision_function`; more negative = more anomalous), `risk_score` (negated raw so higher aligns with supervised risk rank), `risk_flag`.
