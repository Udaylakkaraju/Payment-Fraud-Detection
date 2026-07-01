"""Build the active dashboard-compatible synthetic fraud dataset.

The source file is never modified. The candidate preserves every row and field
except ``is_fraud`` so it can be evaluated before any Power BI source changes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "fraud_seed_v1.csv"
OUTPUT_DIR = ROOT / "data" / "processed"
CANDIDATE = OUTPUT_DIR / "fraud_transactions.csv"
REPORT = OUTPUT_DIR / "fraud_generation_report.json"

SEED = 20_240_629
TARGET_EXPECTED_FRAUD_RATE = 0.05


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sigmoid(values: pd.Series | np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(values, dtype=float), -30, 30)
    return 1.0 / (1.0 + np.exp(-clipped))


def _calibrate_group(risk_score: pd.Series) -> np.ndarray:
    low, high = -10.0, 2.0
    for _ in range(80):
        midpoint = (low + high) / 2.0
        if _sigmoid(risk_score + midpoint).mean() < TARGET_EXPECTED_FRAUD_RATE:
            low = midpoint
        else:
            high = midpoint
    return _sigmoid(risk_score + (low + high) / 2.0)


def _calibrated_probabilities(
    risk_score: pd.Series, transaction_time: pd.Series
) -> np.ndarray:
    """Calibrate weekly baselines so calendar time is not a label shortcut."""
    timestamps = pd.to_datetime(transaction_time, dayfirst=True)
    week = timestamps.dt.to_period("W")
    probabilities = pd.Series(index=risk_score.index, dtype=float)
    for _, indexes in risk_score.groupby(week).groups.items():
        probabilities.loc[indexes] = _calibrate_group(risk_score.loc[indexes])
    return probabilities.to_numpy()


def _risk_inputs(source: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    timestamps = pd.to_datetime(source["transaction_time"], dayfirst=True)
    chronological = source.assign(_timestamp=timestamps).sort_values(
        ["user_id", "_timestamp", "transaction_id"]
    )
    gaps = chronological.groupby("user_id")["_timestamp"].diff().dt.total_seconds()
    seconds_since_previous = gaps.reindex(source.index)

    rapid_low_value = seconds_since_previous.lt(600) & source["amount"].lt(100)
    overnight = timestamps.dt.hour.between(0, 5)

    # These are deliberately modest effects. No individual field determines the
    # label, and all channels/categories retain legitimate and fraudulent rows.
    score = (
        0.75 * source["entry_mode"].eq("Manual_Keyed")
        + 0.65 * source["merchant_category"].eq("Digital Goods")
        + 0.20 * source["merchant_category"].eq("Travel")
        + 0.30 * source["device_type"].eq("mobile")
        + 0.25 * source["ip_country"].ne("US")
        + 1.00 * rapid_low_value
        + 0.20 * overnight
    )
    return score.astype(float), rapid_low_value


def _segment_rates(data: pd.DataFrame, column: str) -> dict[str, dict[str, float | int]]:
    summary = data.groupby(column, dropna=False)["is_fraud"].agg(["size", "sum", "mean"])
    return {
        str(index): {
            "transactions": int(row["size"]),
            "fraud_transactions": int(row["sum"]),
            "fraud_rate": round(float(row["mean"]), 6),
        }
        for index, row in summary.iterrows()
    }


def _rule_metrics(data: pd.DataFrame) -> dict[str, float | int]:
    flagged = data["entry_mode"].eq("Manual_Keyed") & data["merchant_category"].isin(
        ["Digital Goods", "Travel"]
    )
    true_positives = int((flagged & data["is_fraud"].eq(1)).sum())
    positives = int(data["is_fraud"].sum())
    return {
        "flagged_transactions": int(flagged.sum()),
        "precision": round(true_positives / int(flagged.sum()), 6),
        "recall": round(true_positives / positives, 6),
    }


def _temporal_rates(data: pd.DataFrame) -> dict[str, float | int]:
    ordered = data.assign(
        _timestamp=pd.to_datetime(data["transaction_time"], dayfirst=True)
    ).sort_values(["_timestamp", "transaction_id"])
    split = int(len(ordered) * 0.70)
    development, holdout = ordered.iloc[:split], ordered.iloc[split:]
    return {
        "development_rows": len(development),
        "development_fraud_rate": round(float(development["is_fraud"].mean()), 6),
        "holdout_rows": len(holdout),
        "holdout_fraud_rate": round(float(holdout["is_fraud"].mean()), 6),
    }


def main() -> None:
    source = pd.read_csv(SOURCE)
    score, rapid_low_value = _risk_inputs(source)
    probabilities = _calibrated_probabilities(score, source["transaction_time"])
    labels = np.random.default_rng(SEED).binomial(1, probabilities).astype(int)

    candidate = source.copy()
    candidate["is_fraud"] = labels

    unchanged_columns = [column for column in source.columns if column != "is_fraud"]
    assert candidate.columns.tolist() == source.columns.tolist()
    assert len(candidate) == len(source)
    assert candidate[unchanged_columns].equals(source[unchanged_columns])
    assert candidate["transaction_id"].is_unique
    assert not candidate.isna().any().any()
    assert set(candidate["is_fraud"].unique()).issubset({0, 1})
    for column in ["entry_mode", "merchant_category", "device_type", "ip_country"]:
        assert candidate.groupby(column)["is_fraud"].sum().gt(0).all()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(CANDIDATE, index=False)

    rapid_mask = rapid_low_value.fillna(False)
    report = {
        "status": "active_processed_dataset",
        "source_file": str(SOURCE.relative_to(ROOT)),
        "source_sha256": _sha256(SOURCE),
        "processed_file": str(CANDIDATE.relative_to(ROOT)),
        "seed": SEED,
        "invariants": {
            "rows_preserved": len(candidate) == len(source),
            "schema_preserved": candidate.columns.tolist() == source.columns.tolist(),
            "non_label_values_preserved": candidate[unchanged_columns].equals(
                source[unchanged_columns]
            ),
            "row_count": len(candidate),
            "column_count": len(candidate.columns),
            "duplicate_transaction_ids": int(candidate["transaction_id"].duplicated().sum()),
            "null_cells": int(candidate.isna().sum().sum()),
        },
        "fraud_prevalence": {
            "original_transactions": int(source["is_fraud"].sum()),
            "original_rate": round(float(source["is_fraud"].mean()), 6),
            "processed_transactions": int(candidate["is_fraud"].sum()),
            "processed_rate": round(float(candidate["is_fraud"].mean()), 6),
            "target_expected_rate": TARGET_EXPECTED_FRAUD_RATE,
        },
        "processed_probability_range": {
            "minimum": round(float(probabilities.min()), 6),
            "maximum": round(float(probabilities.max()), 6),
        },
        "simple_rule_comparison": {
            "rule": "Manual_Keyed and merchant category in (Digital Goods, Travel)",
            "original": _rule_metrics(source),
            "processed": _rule_metrics(candidate),
        },
        "processed_rapid_low_value": {
            "definition": "same-user previous transaction under 10 minutes and amount under 100",
            "transactions": int(rapid_mask.sum()),
            "fraud_transactions": int(candidate.loc[rapid_mask, "is_fraud"].sum()),
            "fraud_rate": round(float(candidate.loc[rapid_mask, "is_fraud"].mean()), 6),
        },
        "processed_temporal_split": _temporal_rates(candidate),
        "processed_segment_rates": {
            column: _segment_rates(candidate, column)
            for column in ["entry_mode", "merchant_category", "device_type", "ip_country"]
        },
        "limitations": [
            "Labels remain synthetic and are suitable for portfolio demonstration, not production decisions.",
            "The 5% expected prevalence is intentionally enriched for an educational dataset.",
            "Risk relationships are modeled assumptions, not estimates learned from bank data.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
