# Architecture Diagram

This project runs as a simple analytics pipeline: SQL diagnostics + ML risk scoring + BI reporting.

```mermaid
flowchart LR
    A[Raw Payments Data\nfintech_payments(Main Table).csv] --> B[SQL Analysis Layer\nsql quries/*.sql]
    C[Labeled Fraud Data\nfintech_fraud_data.csv] --> D[Feature Engineering\nfintech.py]
    D --> E[Model Training\nhist_gradient_boosting]
    E --> F[Model Artifact\noutputs/fraud_model.joblib]
    F --> G[Daily Batch Scoring\nscore_daily.py]
    G --> H[Scored Output\noutputs/daily_fraud_predictions.csv]
    B --> I[Business KPI Tables\nTables/*.csv + outputs/*.csv]
    H --> J[Power BI Dashboard]
    I --> J
    J --> K[Business Actions\nRetry tuning, failure fixes,\nrisk queue prioritization]
```

## Plain-Language Flow

1. SQL finds where payment leakage happens and why.
2. Python model ranks risky transactions for review.
3. Daily scoring updates risk outputs in batch mode.
4. Power BI combines KPI and risk outputs for decisions.
