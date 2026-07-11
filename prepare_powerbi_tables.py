import csv
from pathlib import Path

import pandas as pd

from payments_io import LEGACY_PAYMENTS_PATH


OUTPUT_DIR = Path("powerbi-data")
ACTION_MATRIX_OUTPUT = Path("outputs/payment_action_matrix.csv")

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
        "source": Path("data/sql_exports/retry_timing_windows.csv"),
        "target": "retry_timing_windows.csv",
        "columns": {
            "decline_reason": "decline_reason",
            "retry_window": "retry_window",
            "failed_txns": "failed_transactions",
            "failed_amount": "failed_amount",
            "pct_of_decline_reason": "pct_of_decline_reason",
        },
        "purpose": "When intent-matched recoveries actually happen, bucketed by minutes-to-recovery.",
        "optional": True,
    },
    {
        "source": Path("outputs/interchange_cost_exposure.csv"),
        "target": "interchange_cost_exposure.csv",
        "columns": {},
        "purpose": "Interchange-style processing cost by decline reason, flagging cost sunk on non-recoverable declines.",
        "optional": True,
    },
    {
        "source": ACTION_MATRIX_OUTPUT,
        "target": "payment_action_matrix.csv",
        "columns": {},
        "purpose": "Decline-level evidence, retry policy, and recommended operations action.",
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
        "source": Path("outputs/review_capacity_curve.csv"),
        "target": "review_capacity_curve.csv",
        "columns": {},
        "purpose": "Human-review precision and recall trade-off by queue capacity.",
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


def build_payment_action_matrix(
    scenarios_path: Path = Path("outputs/recovery_scenarios.csv"),
    policy_path: Path = Path("data/reference/dim_decline_code.csv"),
    output_path: Path = ACTION_MATRIX_OUTPUT,
) -> None:
    """Create one decision-ready row per decline reason from existing outputs."""
    scenarios = pd.read_csv(scenarios_path)
    policy = pd.read_csv(policy_path)

    detail = scenarios.loc[
        (scenarios["scenario_recovery_lift_pct"] == 10.0)
        & (scenarios["decline_reason"] != "ALL_DECLINES")
    ].copy()
    if detail.empty:
        raise ValueError("No decline-level 10% scenario rows were found.")

    matrix = (
        detail.groupby(["decline_code", "decline_reason"], as_index=False)
        .agg(
            failed_transactions=("failed_txns", "sum"),
            failed_value=("failed_amount", "sum"),
            recovered_transactions_24h=("recovered_txns_observed", "sum"),
            recovered_value_24h=("recovered_amount_observed", "sum"),
            policy_eligible_unrecovered_value=(
                "scenario_eligible_unrecovered_amount",
                "sum",
            ),
            estimated_recovery_at_10pct=(
                "estimated_incremental_recovered_amount",
                "sum",
            ),
        )
    )
    matrix["observed_recovery_rate_pct"] = (
        matrix["recovered_transactions_24h"]
        .div(matrix["failed_transactions"])
        .mul(100)
        .round(2)
    )

    policy_columns = [
        "decline_code",
        "policy_class",
        "automatic_retry_allowed",
        "recommended_wait_min_minutes",
        "recommended_wait_max_minutes",
        "operational_action",
        "customer_action",
        "policy_note",
    ]
    matrix["decline_code"] = matrix["decline_code"].astype(str)
    policy["decline_code"] = policy["decline_code"].astype(str)
    matrix = matrix.merge(policy[policy_columns], on="decline_code", how="left")
    matrix = matrix.sort_values("failed_value", ascending=False)

    money_columns = [
        "failed_value",
        "recovered_value_24h",
        "policy_eligible_unrecovered_value",
        "estimated_recovery_at_10pct",
    ]
    matrix[money_columns] = matrix[money_columns].round(2)
    output_path.parent.mkdir(exist_ok=True)
    matrix.to_csv(output_path, index=False)


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
    build_payment_action_matrix()
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
