from pathlib import Path

import pandas as pd
import pytest

from prepare_powerbi_tables import build_payment_action_matrix, write_standardized_csv


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_csv_preserves_legacy_leading_schema() -> None:
    columns = pd.read_csv(
        ROOT / "powerbi-data" / "recovery_scenarios.csv", nrows=0
    ).columns.tolist()
    assert columns[:12] == [
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


def test_fraud_csv_preserves_pbix_user_alias() -> None:
    columns = pd.read_csv(
        ROOT / "powerbi-data" / "fraud_scored_transactions.csv", nrows=0
    ).columns.tolist()
    assert "fraud_user_id" in columns


def test_metrics_csv_preserves_legacy_leading_schema() -> None:
    columns = pd.read_csv(
        ROOT / "powerbi-data" / "fraud_model_holdout_metrics.csv", nrows=0
    ).columns.tolist()
    assert columns[:16] == [
        "model_type",
        "model_kind",
        "evaluation_mode",
        "test_size",
        "threshold",
        "holdout_rows",
        "holdout_fraud_events",
        "fraud_events_caught",
        "recall_pct",
        "roc_auc",
        "precision_pct",
        "false_positive_rate_pct",
        "true_negatives",
        "false_positives",
        "false_negatives",
        "true_positives",
    ]


def test_standardizer_rejects_source_target_collision(tmp_path: Path) -> None:
    source = tmp_path / "same.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Source and target must differ"):
        write_standardized_csv(source, source, {})


def test_powerbi_payments_matches_legacy_source_row_count() -> None:
    legacy = pd.read_csv(ROOT / "data" / "raw" / "payments.csv")
    powerbi = pd.read_csv(ROOT / "powerbi-data" / "payments.csv")
    assert len(powerbi) == len(legacy) == 51_237
    assert powerbi["transaction_id"].is_unique


def test_payment_action_matrix_is_decline_level_and_policy_backed(tmp_path: Path) -> None:
    output = tmp_path / "payment_action_matrix.csv"
    build_payment_action_matrix(output_path=output)
    matrix = pd.read_csv(output)

    assert matrix["decline_reason"].is_unique
    assert "ALL_DECLINES" not in set(matrix["decline_reason"])
    assert matrix["operational_action"].notna().all()
    assert matrix["automatic_retry_allowed"].notna().all()
