import csv
from pathlib import Path

import pandas as pd

from payments_io import LEGACY_PAYMENTS_PATH


OUTPUT_DIR = Path("powerbi-data")

TABLES = [
    {
        "source": Path("data/reference/dim_decline_code.csv"),
        "target": "dim_decline_code.csv",
        "columns": {},
        "purpose": "Public-reference-informed decline code and retry policy dimension.",
    },
    {
        "source": LEGACY_PAYMENTS_PATH,
        "target": "payments.csv",
        "columns": {
            "Transaction_ID": "transaction_id",
            "User_ID": "user_id",
            "Timestamp": "payment_timestamp",
            "Amount": "amount",
            "Issuer_Bank": "issuer_bank",
            "Card_Brand": "card_brand",
            "Interchange_Fee": "interchange_fee",
            "Status": "payment_status",
        },
        "purpose": "Canonical payments fact table (snake_case).",
        "optional": False,
    },
    {
        "source": Path("data/sql_exports/retry_recovery_by_decline_reason.csv"),
        "target": "retry_recovery_by_decline_reason.csv",
        "columns": {
            "Initial_Error": "decline_reason",
            "Total_Failures": "failed_transactions",
            "Recovered_Txns": "recovered_transactions_24h",
            "Recovery_Rate": "recovery_rate_pct",
        },
        "purpose": "24h retry recovery rates by decline reason.",
    },
    {
        "source": Path("data/sql_exports/decline_reason_pareto.csv"),
        "target": "decline_reason_pareto.csv",
        "columns": {
            "Error_Reason": "decline_reason",
            "Failure_Count": "failed_transactions",
            "Pct_of_Failures": "pct_of_failures",
        },
        "purpose": "Decline reason concentration (Pareto).",
    },
    {
        "source": Path("data/sql_exports/bank_auth_rate.csv"),
        "target": "bank_auth_rate.csv",
        "columns": {
            "Issuer_Bank": "issuer_bank",
            "Total_Txns_Processed": "total_transactions",
            "Overall_Auth_Rate_Pct": "auth_rate_pct",
        },
        "purpose": "Authorization rate by issuing bank.",
    },
    {
        "source": Path("data/sql_exports/hourly_auth_rate.csv"),
        "target": "hourly_auth_rate.csv",
        "columns": {
            "Day_Name": "day_name",
            "Hour_of_Day": "hour_of_day",
            "Issuer_Bank": "issuer_bank",
            "Auth_Rate_Pct": "auth_rate_pct",
        },
        "purpose": "Hourly authorization heatmap prep.",
    },
    {
        "source": Path("data/sql_exports/daily_auth_rate_trend.csv"),
        "target": "daily_auth_rate_trend.csv",
        "columns": {
            "Txn_Date": "payment_date",
            "Daily_Auth_Rate": "daily_auth_rate_pct",
            "Rolling_3Day_Avg": "rolling_3day_auth_rate_pct",
        },
        "purpose": "Daily auth rate with rolling average.",
    },
    {
        "source": Path("data/sql_exports/global_auth_rate.csv"),
        "target": "global_auth_rate.csv",
        "columns": {
            "Total_Txns": "total_transactions",
            "Success_Vol": "successful_transactions",
            "Global_Auth_Rate": "auth_rate_pct",
        },
        "purpose": "Portfolio-wide authorization rate.",
    },
    {
        "source": Path("data/sql_exports/card_brand_profitability.csv"),
        "target": "card_brand_profitability.csv",
        "columns": {
            "Card_Brand": "card_brand",
            "Gross_TPV": "gross_payment_volume",
            "Total_Fees": "total_fees",
            "Net_Profit": "net_profit",
            "Margin_Pct": "margin_pct",
        },
        "purpose": "Card brand profitability summary.",
    },
    {
        "source": Path("data/sql_exports/customer_segments.csv"),
        "target": "customer_segments.csv",
        "columns": {
            "Customer_Segment": "customer_segment",
            "User_Count": "user_count",
            "Pct_of_Total": "pct_of_users",
        },
        "purpose": "Customer segment distribution.",
    },
    {
        "source": Path("data/sql_exports/cohort_failure_rate.csv"),
        "target": "cohort_failure_rate.csv",
        "columns": {
            "Cohort_Month": "cohort_month",
            "Total_Txns": "total_transactions",
            "Failure_Rate_Pct": "failure_rate_pct",
        },
        "purpose": "Failure rate by signup cohort.",
    },
    {
        "source": Path("data/sql_exports/high_maintenance_users.csv"),
        "target": "high_maintenance_users.csv",
        "columns": {
            "User_ID": "user_id",
            "Total_Attempts": "total_attempts",
            "Failure_Count": "failed_attempts",
            "User_Failure_Rate": "user_failure_rate_pct",
        },
        "purpose": "Users with elevated payment failure rates.",
    },
    {
        "source": Path("data/sql_exports/bank_performance_bucket_summary.csv"),
        "target": "bank_performance_bucket_summary.csv",
        "columns": {
            "Issuer_Bank": "issuer_bank",
            "Performance_Bucket": "performance_bucket",
            "Hours_Count": "hours_count",
            "Pct_of_Total_Hours": "pct_of_total_hours",
        },
        "purpose": "Bank performance bucket summary for heatmaps.",
    },
    {
        "source": Path("data/sql_exports/decline_reason_cleaning_summary.csv"),
        "target": "decline_reason_cleaning_summary.csv",
        "columns": {
            "Original_Raw_Text": "raw_decline_text",
            "Clean_Error_Reason": "clean_decline_reason",
            "Count": "records",
        },
        "purpose": "Decline reason cleaning audit trail.",
    },
    {
        "source": Path("outputs/recovery_scenarios.csv"),
        "target": "recovery_scenarios.csv",
        "columns": {},
        "purpose": "Same-payment-intent recovery and policy-eligible scenario estimates.",
    },
    {
        "source": Path("outputs/fraud_scored_transactions.csv"),
        "target": "fraud_scored_transactions.csv",
        "columns": {
            "transaction_time": "transaction_timestamp",
            "amount": "transaction_amount",
            "user_id": "fraud_user_id",
        },
        "purpose": "Chronological test-period fraud scores; unseen by training and calibration.",
        "optional": True,
        "fallback_source": Path("outputs/daily_scored_transactions.csv"),
    },
    {
        "source": Path("outputs/feature_importance.csv"),
        "target": "feature_importance.csv",
        "columns": {
            "feature": "model_feature",
            "importance_mean": "importance_score",
            "importance_std": "importance_std_dev",
        },
        "purpose": "Holdout permutation feature importance.",
        "optional": True,
    },
    {
        "source": Path("outputs/train_metrics_report.csv"),
        "target": "fraud_model_holdout_metrics.csv",
        "columns": {
            "rows": "holdout_rows",
            "fraud_events": "holdout_fraud_events",
            "fraud_caught": "fraud_events_caught",
            "recall_pct": "recall_pct",
            "roc_auc": "roc_auc",
            "precision_pct": "precision_pct",
            "false_positive_rate_pct": "false_positive_rate_pct",
            "tn": "true_negatives",
            "fp": "false_positives",
            "fn": "false_negatives",
            "tp": "true_positives",
        },
        "purpose": "Chronological train/calibration/test fraud evaluation metrics.",
        "optional": True,
    },
]


def write_standardized_csv(source: Path, target: Path, column_map: dict[str, str]) -> None:
    if source.resolve() == target.resolve():
        raise ValueError(f"Source and target must differ: {source}")
    with source.open("r", newline="", encoding="utf-8-sig") as src:
        reader = csv.DictReader(src)
        if reader.fieldnames is None:
            raise ValueError(f"Source file has no header: {source}")

        output_fields = [column_map.get(field, field) for field in reader.fieldnames]
        with target.open("w", newline="", encoding="utf-8") as dst:
            writer = csv.DictWriter(dst, fieldnames=output_fields)
            writer.writeheader()
            for row in reader:
                writer.writerow(
                    {
                        column_map.get(field, field): value
                        for field, value in row.items()
                    }
                )


def resolve_source(table: dict) -> tuple[Path, dict[str, str]]:
    source = table["source"]
    column_map = table.get("columns", {})
    if source.exists():
        return source, column_map

    fallback = table.get("fallback_source")
    if fallback is not None and Path(fallback).exists():
        return Path(fallback), table.get("fallback_columns", column_map)

    if table.get("optional"):
        return source, column_map
    raise FileNotFoundError(f"Missing source file: {source}")


def write_readme(table_rows: list[dict[str, str]]) -> None:
    lines = [
        "# Power BI Data",
        "",
        "Power BI-ready CSVs with simplified filenames and consistent snake_case columns.",
        "Generated by `prepare_powerbi_tables.py` from checked-in analysis exports and Python outputs.",
        "",
        "| File | Source | Purpose |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{row['target']}` | `{row['source']}` | {row['purpose']} |"
        for row in table_rows
    )
    lines.append("")
    (OUTPUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    readme_rows = []
    for table in TABLES:
        try:
            source, column_map = resolve_source(table)
        except FileNotFoundError:
            if table.get("optional"):
                print(f"Skipped optional table (missing source): {table['target']}")
                continue
            raise

        target = OUTPUT_DIR / table["target"]
        write_standardized_csv(source, target, column_map)
        readme_rows.append(
            {
                "target": table["target"],
                "source": str(source).replace("\\", "/"),
                "purpose": table.get("purpose", "Standardized Power BI import table."),
            }
        )
        print(f"Wrote {target}")

    write_readme(readme_rows)


if __name__ == "__main__":
    main()
