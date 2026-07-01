from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "fraud_seed_v1.csv"
CANDIDATE = ROOT / "data" / "processed" / "fraud_transactions.csv"


def test_candidate_is_dashboard_compatible() -> None:
    source = pd.read_csv(SOURCE)
    candidate = pd.read_csv(CANDIDATE)
    unchanged = [column for column in source.columns if column != "is_fraud"]

    assert candidate.columns.tolist() == source.columns.tolist()
    assert len(candidate) == len(source)
    assert candidate[unchanged].equals(source[unchanged])


def test_candidate_has_overlapping_fraud_patterns() -> None:
    candidate = pd.read_csv(CANDIDATE)

    assert 0.04 <= candidate["is_fraud"].mean() <= 0.06
    for column in ["entry_mode", "merchant_category", "device_type", "ip_country"]:
        grouped = candidate.groupby(column)["is_fraud"]
        assert grouped.sum().gt(0).all()
        assert grouped.mean().lt(0.15).all()


def test_simple_rule_is_not_a_label_shortcut() -> None:
    candidate = pd.read_csv(CANDIDATE)
    flagged = candidate["entry_mode"].eq("Manual_Keyed") & candidate[
        "merchant_category"
    ].isin(["Digital Goods", "Travel"])

    precision = candidate.loc[flagged, "is_fraud"].mean()
    recall = candidate.loc[flagged, "is_fraud"].sum() / candidate["is_fraud"].sum()
    assert precision < 0.15
    assert recall < 0.65


def test_temporal_holdout_has_comparable_prevalence() -> None:
    candidate = pd.read_csv(CANDIDATE)
    candidate["_timestamp"] = pd.to_datetime(
        candidate["transaction_time"], dayfirst=True
    )
    ordered = candidate.sort_values(["_timestamp", "transaction_id"])
    split = int(len(ordered) * 0.70)

    development_rate = ordered.iloc[:split]["is_fraud"].mean()
    holdout_rate = ordered.iloc[split:]["is_fraud"].mean()
    assert abs(development_rate - holdout_rate) < 0.025
