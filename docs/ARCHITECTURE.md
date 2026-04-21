# Architecture Diagram

This project uses an analytics pipeline that combines SQL diagnostics, ML risk scoring, and BI reporting.

```mermaid
flowchart LR
    subgraph DL[Data Layer]
        A[Raw Payments Data\nfintech_payments(Main Table).csv]
        C[Labeled Fraud Data\nfintech_fraud_data.csv]
    end

    subgraph AL[Analytics Layer]
        B[SQL Analysis\nsql quries/*.sql]
        D[Feature Engineering\nfintech.py]
        E[Model Training\nhist_gradient_boosting]
    end

    subgraph OL[Operational Layer]
        F[Model Artifact\noutputs/fraud_model.joblib]
        G[Daily Batch Scoring\nscore_daily.py]
        H[Scored Output\noutputs/daily_fraud_predictions.csv]
        I[Business KPI Tables\nTables/*.csv + outputs/*.csv]
    end

    subgraph RL[Reporting Layer]
        J[Power BI Dashboard]
        K[Business Actions\nRetry tuning, failure fixes,\nrisk queue prioritization]
    end

    A --> B
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    B --> I
    H --> J
    I --> J
    J --> K

    classDef data fill:#E8F1FF,stroke:#2B6CB0,stroke-width:2px,color:#1A365D;
    classDef analytics fill:#E6FFFA,stroke:#0F766E,stroke-width:2px,color:#134E4A;
    classDef ops fill:#FFF7ED,stroke:#C2410C,stroke-width:2px,color:#7C2D12;
    classDef report fill:#F3E8FF,stroke:#7E22CE,stroke-width:2px,color:#581C87;

    class A,C data;
    class B,D,E analytics;
    class F,G,H,I ops;
    class J,K report;
```

## Plain-Language Flow

1. SQL finds where payment leakage happens and why.
2. Python model ranks risky transactions for review.
3. Daily scoring updates risk outputs in batch mode.
4. Power BI combines KPI and risk outputs for decisions.
