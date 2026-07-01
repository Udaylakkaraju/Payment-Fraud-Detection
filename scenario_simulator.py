import argparse
from pathlib import Path

import pandas as pd

from payments_io import CANONICAL_PAYMENTS_PATH, load_payments_legacy


REQUIRED_COLUMNS = [
    "Transaction_ID",
    "User_ID",
    "Timestamp",
    "Amount",
    "Issuer_Bank",
    "Card_Brand",
    "Status",
]
DEFAULT_DECLINE_POLICY = Path("data/reference/dim_decline_code.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate retry recovery scenarios using same-payment-intent attempts."
    )
    parser.add_argument("--input", default=str(CANONICAL_PAYMENTS_PATH))
    parser.add_argument("--output", default="outputs/recovery_scenarios.csv")
    parser.add_argument(
        "--decline-summary-output",
        default="data/sql_exports/retry_recovery_by_decline_reason.csv",
        help="Compatibility output with intent-matched recovery by decline reason.",
    )
    parser.add_argument(
        "--scenario-rates",
        default="0.05,0.10,0.15",
        help="Comma-separated assumed recovery lift rates for unrecovered failed value.",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=1440,
        help="Recovery window after initial failed payment.",
    )
    parser.add_argument(
        "--decline-policy",
        default=str(DEFAULT_DECLINE_POLICY),
        help="Decline policy dimension used to exclude non-retryable declines from scenarios.",
    )
    return parser.parse_args()


def validate_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def parse_scenario_rates(raw_rates: str) -> list[float]:
    rates = [float(rate.strip()) for rate in raw_rates.split(",") if rate.strip()]
    invalid = [rate for rate in rates if rate <= 0 or rate > 1]
    if invalid:
        raise ValueError(f"Scenario rates must be in (0, 1]: {invalid}")
    return rates


def load_retry_policy(path: Path) -> dict[str, bool]:
    policy = pd.read_csv(path, dtype={"decline_code": str})
    required = {"decline_code", "automatic_retry_allowed"}
    missing = required.difference(policy.columns)
    if missing:
        raise ValueError(f"Decline policy is missing columns: {sorted(missing)}")
    allowed = policy["automatic_retry_allowed"].astype(str).str.lower().map(
        {"true": True, "false": False}
    )
    if allowed.isna().any():
        raise ValueError("automatic_retry_allowed must contain only true/false values.")
    return dict(zip(policy["decline_code"].str.zfill(2), allowed))


def build_failed_journeys(df: pd.DataFrame, window_minutes: int) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    if df["Timestamp"].isna().any():
        raise ValueError("Invalid Timestamp values found after datetime parsing.")

    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    if df["Amount"].isna().any():
        raise ValueError("Invalid Amount values found after numeric parsing.")

    # The source encodes retry lineage as TXN-123 and TXN-123-RETRY. Matching
    # that lineage prevents an unrelated purchase by the same user from being
    # counted as recovery of the failed payment.
    df["payment_intent_id"] = df["Transaction_ID"].astype(str).str.replace(
        r"-RETRY(?:-\d+)?$", "", regex=True
    )
    df = df.sort_values(
        ["payment_intent_id", "Timestamp", "Transaction_ID"]
    ).copy()

    consistency = df.groupby("payment_intent_id").agg(
        users=("User_ID", "nunique"),
        amounts=("Amount", "nunique"),
    )
    inconsistent = consistency[(consistency["users"] > 1) | (consistency["amounts"] > 1)]
    if not inconsistent.empty:
        raise ValueError(
            "Retry lineage contains inconsistent user or amount values for "
            f"{len(inconsistent)} payment intents."
        )

    first_attempts = df.groupby("payment_intent_id", sort=False).head(1).copy()
    successful_attempts = df[df["Status"] == "00: Success"]
    first_success = successful_attempts.groupby("payment_intent_id")["Timestamp"].min()
    first_attempts["matched_success_timestamp"] = first_attempts[
        "payment_intent_id"
    ].map(first_success)
    first_attempts["minutes_to_recovery"] = (
        first_attempts["matched_success_timestamp"]
        .sub(first_attempts["Timestamp"])
        .dt.total_seconds()
        .div(60)
    )
    first_attempts["recovered_within_window"] = (
        first_attempts["Status"].ne("00: Success")
        & first_attempts["minutes_to_recovery"].between(
            0, window_minutes, inclusive="both"
        )
    )
    return first_attempts[first_attempts["Status"] != "00: Success"].copy()


def summarize_recovery_by_decline(failed_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        failed_df.groupby("Status", dropna=False)
        .agg(
            Total_Failures=("payment_intent_id", "count"),
            Recovered_Txns=("recovered_within_window", "sum"),
        )
        .reset_index()
        .rename(columns={"Status": "Initial_Error"})
    )
    summary["Recovery_Rate"] = (
        summary["Recovered_Txns"].div(summary["Total_Failures"]).mul(100).round(1)
    )
    return summary.sort_values("Total_Failures", ascending=False)


def summarize_scenarios(
    failed_df: pd.DataFrame,
    scenario_rates: list[float],
    window_minutes: int,
    retry_policy: dict[str, bool],
) -> pd.DataFrame:
    group_cols = ["Status", "Issuer_Bank", "Card_Brand"]
    base = (
        failed_df.groupby(group_cols, dropna=False)
        .agg(
            failed_txns=("Transaction_ID", "count"),
            failed_amount=("Amount", "sum"),
            recovered_txns_observed=("recovered_within_window", "sum"),
            recovered_amount_observed=(
                "Amount",
                lambda amount: amount[failed_df.loc[amount.index, "recovered_within_window"]].sum(),
            ),
        )
        .reset_index()
        .rename(
            columns={
                "Status": "decline_reason",
                "Issuer_Bank": "issuer_bank",
                "Card_Brand": "card_brand",
            }
        )
    )
    base["observed_recovery_rate_pct"] = (
        base["recovered_txns_observed"].div(base["failed_txns"]).fillna(0).mul(100)
    )
    base["unrecovered_amount_pool"] = (
        base["failed_amount"] - base["recovered_amount_observed"]
    ).clip(lower=0)
    base["decline_code"] = base["decline_reason"].astype(str).str.extract(
        r"^([0-9A-Z]{2}):", expand=False
    )
    base["automatic_retry_allowed"] = base["decline_code"].map(retry_policy).fillna(False)
    base["scenario_eligible_unrecovered_amount"] = base[
        "unrecovered_amount_pool"
    ].where(base["automatic_retry_allowed"], 0.0)

    rows = []
    for _, record in base.iterrows():
        for rate in scenario_rates:
            rows.append(
                {
                    **record.to_dict(),
                    "window_minutes": window_minutes,
                    "scenario_recovery_lift_pct": rate * 100,
                    "estimated_incremental_recovered_amount": record[
                        "scenario_eligible_unrecovered_amount"
                    ]
                    * rate,
                }
            )

    total = {
        "decline_reason": "ALL_DECLINES",
        "issuer_bank": "ALL_BANKS",
        "card_brand": "ALL_BRANDS",
        "failed_txns": int(failed_df["Transaction_ID"].count()),
        "failed_amount": float(failed_df["Amount"].sum()),
        "recovered_txns_observed": int(failed_df["recovered_within_window"].sum()),
        "recovered_amount_observed": float(
            failed_df.loc[failed_df["recovered_within_window"], "Amount"].sum()
        ),
    }
    total["observed_recovery_rate_pct"] = (
        total["recovered_txns_observed"] / total["failed_txns"] * 100
        if total["failed_txns"]
        else 0
    )
    total["unrecovered_amount_pool"] = max(
        total["failed_amount"] - total["recovered_amount_observed"], 0
    )
    total["decline_code"] = "ALL"
    total["automatic_retry_allowed"] = None
    total["scenario_eligible_unrecovered_amount"] = float(
        base["scenario_eligible_unrecovered_amount"].sum()
    )
    for rate in scenario_rates:
        rows.append(
            {
                **total,
                "window_minutes": window_minutes,
                "scenario_recovery_lift_pct": rate * 100,
                "estimated_incremental_recovered_amount": total[
                    "scenario_eligible_unrecovered_amount"
                ]
                * rate,
            }
        )

    output = pd.DataFrame(rows)
    money_cols = [
        "failed_amount",
        "recovered_amount_observed",
        "unrecovered_amount_pool",
        "scenario_eligible_unrecovered_amount",
        "estimated_incremental_recovered_amount",
    ]
    output[money_cols] = output[money_cols].round(2)
    output["observed_recovery_rate_pct"] = output["observed_recovery_rate_pct"].round(2)
    output["scenario_recovery_lift_pct"] = output["scenario_recovery_lift_pct"].round(2)
    # Power BI's existing CSV query is locked to the original 12-column schema.
    # Keep those fields first and append policy metadata so refreshes remain
    # backward compatible even when Csv.Document specifies Columns=12.
    legacy_columns = [
        "decline_reason",
        "issuer_bank",
        "card_brand",
        "failed_txns",
        "failed_amount",
        "recovered_txns_observed",
        "recovered_amount_observed",
        "observed_recovery_rate_pct",
        "unrecovered_amount_pool",
        "window_minutes",
        "scenario_recovery_lift_pct",
        "estimated_incremental_recovered_amount",
    ]
    policy_columns = [
        "decline_code",
        "automatic_retry_allowed",
        "scenario_eligible_unrecovered_amount",
    ]
    output = output[legacy_columns + policy_columns]
    return output.sort_values(
        ["estimated_incremental_recovered_amount", "failed_amount"],
        ascending=False,
    )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    decline_summary_path = Path(args.decline_summary_output)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if args.window_minutes <= 0:
        raise ValueError("--window-minutes must be > 0.")

    scenario_rates = parse_scenario_rates(args.scenario_rates)
    decline_policy_path = Path(args.decline_policy)
    if not decline_policy_path.exists():
        raise FileNotFoundError(f"Decline policy file not found: {decline_policy_path}")
    retry_policy = load_retry_policy(decline_policy_path)
    df = load_payments_legacy(input_path)
    validate_columns(df)
    failed_df = build_failed_journeys(df, args.window_minutes)
    output = summarize_scenarios(
        failed_df, scenario_rates, args.window_minutes, retry_policy
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    decline_summary_path.parent.mkdir(parents=True, exist_ok=True)
    summarize_recovery_by_decline(failed_df).to_csv(decline_summary_path, index=False)
    print(f"Recovery scenario report saved -> {output_path}")
    print(f"Decline recovery summary saved -> {decline_summary_path}")
    print(
        output[output["decline_reason"] == "ALL_DECLINES"]
        .head(len(scenario_rates))
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
