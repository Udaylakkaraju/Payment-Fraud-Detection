import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fintech import (  # noqa: E402
    apply_vocab,
    build_review_capacity_curve,
    split_train_calibration_test,
)
from payments_io import normalize_payments_columns, to_legacy_payments_frame  # noqa: E402
from scenario_simulator import build_failed_journeys, summarize_scenarios  # noqa: E402


def test_normalize_payments_columns_from_snake_case() -> None:
    df = pd.DataFrame(
        {
            "transaction_id": ["TXN-1"],
            "user_id": [1],
            "payment_timestamp": ["2024-01-01 00:00:00"],
            "amount": [10.0],
            "issuer_bank": ["Chase"],
            "card_brand": ["Visa"],
            "payment_status": ["51: Insufficient Funds"],
        }
    )
    normalized = normalize_payments_columns(df)
    assert normalized.loc[0, "payment_status"] == "51: Insufficient Funds"


def test_to_legacy_payments_frame_maps_status() -> None:
    df = pd.DataFrame(
        {
            "transaction_id": ["TXN-1"],
            "user_id": [1],
            "payment_timestamp": ["2024-01-01 00:00:00"],
            "amount": [10.0],
            "issuer_bank": ["Chase"],
            "card_brand": ["Visa"],
            "payment_status": ["51: Insufficient Funds"],
        }
    )
    legacy = to_legacy_payments_frame(df)
    assert legacy.loc[0, "Status"] == "51: Insufficient Funds"


def test_build_failed_journeys_detects_recovery() -> None:
    df = pd.DataFrame(
        {
            "Transaction_ID": ["A", "A-RETRY"],
            "User_ID": [1, 1],
            "Timestamp": ["2024-01-01 00:00:00", "2024-01-01 00:30:00"],
            "Amount": [25.0, 25.0],
            "Issuer_Bank": ["Chase", "Chase"],
            "Card_Brand": ["Visa", "Visa"],
            "Status": ["51: Insufficient Funds", "00: Success"],
        }
    )
    failed = build_failed_journeys(df, window_minutes=1440)
    assert len(failed) == 1
    assert bool(failed.iloc[0]["recovered_within_window"]) is True


def test_build_failed_journeys_rejects_unrelated_next_success() -> None:
    df = pd.DataFrame(
        {
            "Transaction_ID": ["A", "B"],
            "User_ID": [1, 1],
            "Timestamp": ["2024-01-01 00:00:00", "2024-01-01 00:30:00"],
            "Amount": [25.0, 25.0],
            "Issuer_Bank": ["Chase", "Chase"],
            "Card_Brand": ["Visa", "Visa"],
            "Status": ["51: Insufficient Funds", "00: Success"],
        }
    )
    failed = build_failed_journeys(df, window_minutes=1440)
    assert len(failed) == 1
    assert bool(failed.iloc[0]["recovered_within_window"]) is False


def test_scenarios_exclude_non_retryable_declines() -> None:
    failed = pd.DataFrame(
        {
            "Transaction_ID": ["A", "B"],
            "payment_intent_id": ["A", "B"],
            "Status": ["51: Insufficient Funds", "59: Suspected Fraud"],
            "Issuer_Bank": ["Chase", "Chase"],
            "Card_Brand": ["Visa", "Visa"],
            "Amount": [100.0, 200.0],
            "recovered_within_window": [False, False],
        }
    )
    result = summarize_scenarios(
        failed,
        scenario_rates=[0.10],
        window_minutes=1440,
        retry_policy={"51": True, "59": False},
    )
    fraud_row = result[result["decline_reason"] == "59: Suspected Fraud"].iloc[0]
    total_row = result[result["decline_reason"] == "ALL_DECLINES"].iloc[0]
    assert fraud_row["estimated_incremental_recovered_amount"] == 0
    assert total_row["estimated_incremental_recovered_amount"] == 10


def test_apply_vocab_maps_unknown_categories_to_minus_one() -> None:
    vocab = {"web": 0, "mobile": 1}
    series = pd.Series(["web", "kiosk"])
    encoded = apply_vocab(series, vocab)
    assert encoded.tolist() == [0, -1]


def test_train_calibration_test_split_preserves_time_order() -> None:
    df = pd.DataFrame(
        {
            "transaction_id": list(range(10)),
            "transaction_time": pd.date_range("2024-01-01", periods=10, freq="D"),
            "is_fraud": [0, 1] * 5,
        }
    )
    train_df, calibration_df, test_df = split_train_calibration_test(
        df,
        calibration_size=0.20,
        test_size=0.20,
    )
    assert len(train_df) == 6
    assert len(calibration_df) == 2
    assert len(test_df) == 2
    assert train_df["transaction_time"].max() <= calibration_df["transaction_time"].min()
    assert calibration_df["transaction_time"].max() <= test_df["transaction_time"].min()


def test_review_capacity_curve_reports_queue_tradeoffs() -> None:
    scored = pd.DataFrame(
        {
            "is_fraud": [1, 0, 1, 0, 0, 0, 0, 0, 0, 0],
            "fraud_probability": [0.99, 0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10],
        }
    )

    curve = build_review_capacity_curve(scored, (0.10, 0.20))

    assert curve["queue_size"].tolist() == [1, 2]
    assert curve["fraud_caught"].tolist() == [1, 1]
    assert curve["precision_pct"].tolist() == [100.0, 50.0]
    assert curve["recall_pct"].tolist() == [50.0, 50.0]
