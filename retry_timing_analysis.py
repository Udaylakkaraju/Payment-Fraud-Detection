"""Time-to-recovery curve and interchange cost-of-attempt analysis.

Reuses the same intent-matched failed-journey logic as scenario_simulator.py
(payment_intent_id lineage via the TXN-123 / TXN-123-RETRY suffix) so the
recovery counts here always agree with outputs/recovery_scenarios.csv and
data/sql_exports/retry_recovery_by_decline_reason.csv.

What this adds on top of that existing recovery-rate summary:

1. WHEN recovery happens, not just whether it happens. Declines are bucketed
   by minutes-to-recovery into a simple retry-timing curve. This is the
   difference between "28.1% of insufficient-funds declines recover within
   24 hours" and "most of that 28.1% doesn't show up until hour 6+" -- the
   second version is what actually informs a retry delay policy.
2. Interchange-style processing cost sitting on declines that structurally
   cannot recover (fraud, issuer timeout), to quantify the cost avoided by
   correctly excluding those codes from automatic retry.
"""

import argparse
from pathlib import Path

import pandas as pd

from payments_io import CANONICAL_PAYMENTS_PATH, load_payments_legacy
from scenario_simulator import build_failed_journeys, REQUIRED_COLUMNS, validate_columns

TIMING_BUCKET_ORDER = [
    "00-05 min",
    "06-30 min",
    "31-120 min",
    "2-6 hours",
    "6-24 hours",
    "Not recovered within 24h",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a time-to-recovery curve and interchange cost-of-attempt summary."
    )
    parser.add_argument("--input", default=str(CANONICAL_PAYMENTS_PATH))
    parser.add_argument("--window-minutes", type=int, default=1440)
    parser.add_argument(
        "--timing-output", default="data/sql_exports/retry_timing_windows.csv"
    )
    parser.add_argument(
        "--cost-output", default="outputs/interchange_cost_exposure.csv"
    )
    return parser.parse_args()


def bucket_minutes(minutes: float, window_minutes: int) -> str:
    if pd.isna(minutes) or minutes < 0 or minutes > window_minutes:
        return "Not recovered within 24h"
    if minutes <= 5:
        return "00-05 min"
    if minutes <= 30:
        return "06-30 min"
    if minutes <= 120:
        return "31-120 min"
    if minutes <= 360:
        return "2-6 hours"
    return "6-24 hours"


def build_timing_curve(failed_df: pd.DataFrame, window_minutes: int) -> pd.DataFrame:
    failed_df = failed_df.copy()
    failed_df["retry_window"] = failed_df["minutes_to_recovery"].apply(
        bucket_minutes, window_minutes=window_minutes
    )
    summary = (
        failed_df.groupby(["Status", "retry_window"])
        .agg(failed_txns=("Transaction_ID", "count"), failed_amount=("Amount", "sum"))
        .reset_index()
        .rename(columns={"Status": "decline_reason"})
    )
    summary["retry_window"] = pd.Categorical(
        summary["retry_window"], categories=TIMING_BUCKET_ORDER, ordered=True
    )
    summary["pct_of_decline_reason"] = (
        summary.groupby("decline_reason")["failed_txns"].transform(
            lambda x: (x / x.sum() * 100).round(2)
        )
    )
    summary["failed_amount"] = summary["failed_amount"].round(2)
    return summary.sort_values(["decline_reason", "retry_window"])


def build_cost_exposure(failed_df: pd.DataFrame, retry_policy_path: Path) -> pd.DataFrame:
    policy = pd.read_csv(retry_policy_path, dtype={"decline_code": str})
    failed_df = failed_df.copy()
    failed_df["decline_code"] = (
        failed_df["Status"].astype(str).str.extract(r"^([0-9A-Z]{2}):", expand=False)
    )
    summary = (
        failed_df.groupby(["decline_code", "Status"])
        .agg(
            attempts=("Transaction_ID", "count"),
            total_interchange_fee=("Interchange_Fee", "sum"),
            recovered_txns=("recovered_within_window", "sum"),
        )
        .reset_index()
        .rename(columns={"Status": "decline_reason"})
    )
    summary = summary.merge(
        policy[["decline_code", "automatic_retry_allowed"]], on="decline_code", how="left"
    )
    summary["total_interchange_fee"] = summary["total_interchange_fee"].round(2)
    summary["avg_interchange_fee_per_attempt"] = (
        summary["total_interchange_fee"] / summary["attempts"]
    ).round(4)
    summary["cost_with_zero_recovery"] = (
        (summary["recovered_txns"] == 0) & (~summary["automatic_retry_allowed"].fillna(False))
    )
    return summary.sort_values("total_interchange_fee", ascending=False)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = load_payments_legacy(input_path)
    validate_columns(df)

    # load_payments_legacy() normalizes to the legacy PascalCase schema used by
    # scenario_simulator, which does not carry Interchange_Fee. Read it
    # separately from the raw file and merge it back in by Transaction_ID.
    raw = pd.read_csv(input_path)
    interchange_col = "Interchange_Fee" if "Interchange_Fee" in raw.columns else "interchange_fee"
    if interchange_col not in raw.columns:
        raise ValueError(
            "Interchange_Fee column is required for cost-of-attempt analysis but "
            f"was not found in {input_path}."
        )
    id_col = "Transaction_ID" if "Transaction_ID" in raw.columns else "transaction_id"
    fee_lookup = raw[[id_col, interchange_col]].rename(
        columns={id_col: "Transaction_ID", interchange_col: "Interchange_Fee"}
    )

    failed_df = build_failed_journeys(df, args.window_minutes)
    failed_df = failed_df.merge(fee_lookup, on="Transaction_ID", how="left")
    if failed_df["Interchange_Fee"].isna().any():
        raise ValueError("Some failed transactions could not be matched to an interchange fee.")

    timing_curve = build_timing_curve(failed_df, args.window_minutes)
    timing_path = Path(args.timing_output)
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    timing_curve.to_csv(timing_path, index=False)

    cost_exposure = build_cost_exposure(
        failed_df, Path("data/reference/dim_decline_code.csv")
    )
    cost_path = Path(args.cost_output)
    cost_path.parent.mkdir(parents=True, exist_ok=True)
    cost_exposure.to_csv(cost_path, index=False)

    print(f"Retry timing curve saved -> {timing_path}")
    print(timing_curve.to_string(index=False))
    print()
    print(f"Interchange cost exposure saved -> {cost_path}")
    print(cost_exposure.to_string(index=False))


if __name__ == "__main__":
    main()
