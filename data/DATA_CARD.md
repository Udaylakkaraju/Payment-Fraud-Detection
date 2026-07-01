# Data Card

## Purpose

This repository uses two independent synthetic datasets to demonstrate payment-operations analytics and fraud-review prioritization. The data is suitable for portfolio analysis and software testing, not real financial decisions.

## Active datasets

### Payment attempts

- **File:** `data/raw/payments.csv`
- **Dashboard copy:** `powerbi-data/payments.csv`
- **Rows:** 51,237 payment attempts
- **Date range:** 2024-01-01 to 2024-04-01
- **Grain:** One row per payment attempt
- **Primary key:** `transaction_id`
- **Users:** 4,001 synthetic identifiers
- **Statuses:** Success, insufficient funds, suspected fraud, and issuer timeout
- **Retry convention:** A retry keeps the original transaction identifier and adds `-RETRY`

The file contains 1,237 retry attempts. Retry recovery is measured only when a successful attempt shares the original payment-intent identifier.

### Fraud transactions

- **File:** `data/processed/fraud_transactions.csv`
- **Rows:** 10,000 transactions
- **Date range:** 2024-01-01 to 2024-02-17
- **Grain:** One row per synthetic fraud transaction
- **Primary key:** `transaction_id`
- **Fraud events:** 519 (5.19%)

The active fraud labels were regenerated from the archived seed file using `data/build_fraud_dataset.py`. The motivating rapid, low-value pattern was inspired by an anonymized personal experience and generalized with legitimate counterexamples and several weaker risk signals.

Fraud exists across every entry mode and merchant category:

| Entry mode | Fraud rate |
| --- | ---: |
| Chip | 3.83% |
| Contactless | 3.08% |
| Manual keyed | 8.91% |

These rates are intentionally enriched so portfolio visuals and queue metrics remain interpretable.

## Reference data

`data/reference/dim_decline_code.csv` provides decline descriptions and a project-authored retry policy. Public documentation informs the decline semantics; retry timing and operational actions remain project assumptions.

## Dataset relationship policy

The payment and fraud snapshots were produced independently:

- Transaction identifiers are not compatible.
- Matching numeric user identifiers do not prove a shared identity.
- The datasets must not be joined on `transaction_id` or `user_id`.

Cross-domain reporting is therefore limited to separate portfolio-level summaries.

## Quality checks

- Payment and fraud transaction identifiers are unique.
- Active payment and fraud datasets contain no null cells.
- Amounts are positive.
- Fraud and legitimate outcomes occur in every major fraud-data segment.
- Chronological train, calibration, and test partitions each contain both classes.
- Power BI schema tests protect required column names and ordering.

## Known limitations

- Data distributions are synthetic and should not be treated as industry benchmarks.
- Fraud labels are modeled rather than confirmed through investigations or chargebacks.
- The payment snapshot has only four outcome categories and three months of history.
- The fraud dataset uses an enriched prevalence and simplified categorical dimensions.
- Estimated recovery is not causal uplift; a controlled experiment would be required.

## Reproduction

Rebuild the processed fraud dataset:

```powershell
.\.venv\Scripts\python.exe data/build_fraud_dataset.py
```

Run data and schema checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
