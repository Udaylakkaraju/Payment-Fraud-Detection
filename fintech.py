import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from sklearn.inspection import permutation_importance

FEATURE_COLUMNS = [
    "amount",
    "Hour",
    "Day_Index",
    "inter_txn_minutes",
    "device_code",
    "merchant_code",
    "country_code",
    "entry_code",
    "rapid_low_value",
    "is_manual_keyed",
    "is_digital_goods",
    "is_travel",
    "is_mobile",
    "is_non_us",
    "is_overnight",
]

BASE_REQUIRED_COLUMNS = [
    "transaction_id",
    "transaction_time",
    "amount",
    "user_id",
    "device_type",
    "merchant_category",
    "ip_country",
    "entry_mode",
]

TRAIN_REQUIRED_COLUMNS = BASE_REQUIRED_COLUMNS + ["is_fraud"]
SUPPORTED_MODELS = {"hist_gradient_boosting"}
MODEL_KIND = "classifier"  # Kept in output schemas for Power BI compatibility.
DEFAULT_TRAINING_INPUT = "data/processed/fraud_transactions.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the fraud-review ranking model."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Train and evaluate model.")
    train_parser.add_argument("--input", default=DEFAULT_TRAINING_INPUT)
    train_parser.add_argument(
        "--output",
        default="outputs/fraud_scored_transactions.csv",
        help="Full scored training table (train command).",
    )
    train_parser.add_argument("--model-out", default="outputs/fraud_model.joblib")
    train_parser.add_argument(
        "--model-type",
        default="hist_gradient_boosting",
        choices=sorted(SUPPORTED_MODELS),
        help="Model family to train / persist for downstream batch scoring.",
    )
    train_parser.add_argument(
        "--review-rate",
        type=float,
        default=0.10,
        help="Target share of calibration rows routed to manual review.",
    )
    train_parser.add_argument("--calibration-size", type=float, default=0.20)
    train_parser.add_argument("--test-size", type=float, default=0.20)
    train_parser.add_argument("--metrics-out", default="outputs/train_metrics_report.csv")
    train_parser.add_argument(
        "--feature-importance-out",
        default="outputs/feature_importance.csv",
        help="Permutation feature importance report from the holdout split.",
    )
    train_parser.add_argument(
        "--capacity-curve-out",
        default="outputs/review_capacity_curve.csv",
        help="Fraud-review precision/recall trade-off at several queue capacities.",
    )
    train_parser.add_argument(
        "--inference-sample-out",
        default="data/inference/fraud_inference_sample.csv",
        help="Unlabeled chronological test-period sample for batch-scoring demonstrations.",
    )
    train_parser.add_argument(
        "--daily-output",
        default="outputs/daily_scored_transactions.csv",
        help="Scored unlabeled test-period sample used as a demonstration inference queue.",
    )

    return parser.parse_args()


def validate_common_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")


def validate_train_args(args: argparse.Namespace) -> None:
    if not (0 < args.test_size < 0.5):
        raise ValueError("--test-size must be in (0, 0.5).")
    if not (0 < args.calibration_size < 0.5):
        raise ValueError("--calibration-size must be in (0, 0.5).")
    if args.test_size + args.calibration_size >= 0.8:
        raise ValueError("Calibration and test partitions must leave at least 20% for training.")
    if not (0 < args.review_rate < 0.5):
        raise ValueError("--review-rate must be in (0, 0.5).")


def train_output_columns() -> list[str]:
    cols = BASE_REQUIRED_COLUMNS + ["is_fraud", "inter_txn_minutes"]
    return cols + ["fraud_probability", "risk_score", "risk_flag", "risk_bucket"]


def infer_output_columns(has_is_fraud: bool) -> list[str]:
    tail = ["fraud_probability", "risk_score", "risk_flag", "risk_bucket"]
    out = BASE_REQUIRED_COLUMNS + ["inter_txn_minutes"] + tail
    if has_is_fraud:
        out.insert(9, "is_fraud")
    return out


def validate_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in input data: {missing_cols}")


def fit_vocab(series: pd.Series) -> Dict[str, int]:
    values = (
        series.fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .replace("", "UNKNOWN")
        .unique()
        .tolist()
    )
    return {value: idx for idx, value in enumerate(sorted(values))}


def apply_vocab(series: pd.Series, vocab: Dict[str, int]) -> pd.Series:
    normalized = (
        series.fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .replace("", "UNKNOWN")
    )
    # Unseen categories map to -1 so inference never crashes.
    return normalized.map(vocab).fillna(-1).astype(int)


def prepare_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # The synthetic files contain both ISO and day-first timestamps.
    df["transaction_time"] = pd.to_datetime(
        df["transaction_time"], format="mixed", dayfirst=True, errors="coerce"
    )
    if df["transaction_time"].isna().any():
        raise ValueError("Invalid transaction_time values found after datetime parsing.")

    df["Hour"] = df["transaction_time"].dt.hour
    df["Day_Index"] = df["transaction_time"].dt.dayofweek

    df = df.sort_values(["user_id", "transaction_time"]).copy()
    prev_txn = df.groupby("user_id", sort=False)["transaction_time"].shift(1)
    inter_minutes = (df["transaction_time"] - prev_txn).dt.total_seconds().div(60)
    df["inter_txn_minutes"] = inter_minutes.fillna(9999.0)
    df["rapid_low_value"] = (
        df["inter_txn_minutes"].lt(10) & df["amount"].lt(100)
    ).astype(int)
    df["is_manual_keyed"] = df["entry_mode"].eq("Manual_Keyed").astype(int)
    df["is_digital_goods"] = df["merchant_category"].eq("Digital Goods").astype(int)
    df["is_travel"] = df["merchant_category"].eq("Travel").astype(int)
    df["is_mobile"] = df["device_type"].eq("mobile").astype(int)
    df["is_non_us"] = df["ip_country"].ne("US").astype(int)
    df["is_overnight"] = df["Hour"].between(0, 5).astype(int)
    return df


def encode_for_training(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Dict[str, int]]]:
    device_vocab = fit_vocab(df["device_type"])
    merchant_vocab = fit_vocab(df["merchant_category"])
    country_vocab = fit_vocab(df["ip_country"])
    entry_vocab = fit_vocab(df["entry_mode"])

    df["device_code"] = apply_vocab(df["device_type"], device_vocab)
    df["merchant_code"] = apply_vocab(df["merchant_category"], merchant_vocab)
    df["country_code"] = apply_vocab(df["ip_country"], country_vocab)
    df["entry_code"] = apply_vocab(df["entry_mode"], entry_vocab)

    vocabs = {
        "device": device_vocab,
        "merchant": merchant_vocab,
        "country": country_vocab,
        "entry": entry_vocab,
    }
    return df, vocabs


def encode_for_inference(df: pd.DataFrame, vocabs: Dict[str, Dict[str, int]]) -> pd.DataFrame:
    df["device_code"] = apply_vocab(df["device_type"], vocabs["device"])
    df["merchant_code"] = apply_vocab(df["merchant_category"], vocabs["merchant"])
    df["country_code"] = apply_vocab(df["ip_country"], vocabs["country"])
    df["entry_code"] = apply_vocab(df["entry_mode"], vocabs["entry"])
    return df


def compute_metrics(df: pd.DataFrame) -> Dict[str, float]:
    fraud_rows = df[df["is_fraud"] == 1]
    caught_fraud = fraud_rows[fraud_rows["risk_flag"] == 1]
    catch_rate = (len(caught_fraud) / len(fraud_rows) * 100) if len(fraud_rows) > 0 else 0.0

    score_input = df["fraud_probability"]
    roc_auc = roc_auc_score(df["is_fraud"], score_input)
    pr_auc = average_precision_score(df["is_fraud"], score_input)

    cm = confusion_matrix(df["is_fraud"], df["risk_flag"], labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    false_positive_rate = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0.0
    topk_count = max(1, int(len(df) * 0.05))
    topk = df.assign(_rank_score=score_input).nlargest(topk_count, "_rank_score")
    topk_fraud = int(topk["is_fraud"].sum())
    total_fraud = int(df["is_fraud"].sum())

    return {
        "rows": float(len(df)),
        "fraud_events": float(len(fraud_rows)),
        "fraud_caught": float(len(caught_fraud)),
        "recall_pct": catch_rate,
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "precision_pct": precision * 100.0,
        "precision_at_5pct": topk_fraud / topk_count,
        "recall_at_5pct": topk_fraud / total_fraud if total_fraud else 0.0,
        "top_5pct_queue_size": float(topk_count),
        "flagged_queue_size": float(df["risk_flag"].sum()),
        "false_positive_rate_pct": false_positive_rate,
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
    }


def print_evaluation(metrics: Dict[str, float]) -> None:
    """Print the small metric set used in the project story."""
    print("\nEvaluation Results:")
    print("=" * 45)
    labels = [
        ("Total transactions", "rows", ",.0f"),
        ("Confirmed fraud events", "fraud_events", ",.0f"),
        ("Fraud caught by model", "fraud_caught", ",.0f"),
        ("Catch Rate (Recall)", "recall_pct", ".1f"),
        ("ROC-AUC", "roc_auc", ".2f"),
        ("Precision", "precision_pct", ".1f"),
        ("False Positive Rate", "false_positive_rate_pct", ".1f"),
    ]
    for label, key, spec in labels:
        suffix = "%" if "pct" in key else ""
        print(f"  {label + ':':29} {format(metrics[key], spec)}{suffix}")


def build_review_capacity_curve(
    scored: pd.DataFrame,
    review_rates: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20),
) -> pd.DataFrame:
    """Measure the human-review trade-off at practical queue capacities."""
    if scored.empty:
        raise ValueError("Cannot build a capacity curve from an empty scored dataset.")
    if "is_fraud" not in scored.columns:
        raise ValueError("Capacity-curve evaluation requires is_fraud labels.")

    ranked = scored.sort_values("fraud_probability", ascending=False)
    total_fraud = int(ranked["is_fraud"].sum())
    baseline_rate = float(ranked["is_fraud"].mean())
    rows = []
    for review_rate in review_rates:
        if not (0 < review_rate < 1):
            raise ValueError("Every review rate must be in (0, 1).")
        queue_size = max(1, int(round(len(ranked) * review_rate)))
        queue = ranked.head(queue_size)
        fraud_caught = int(queue["is_fraud"].sum())
        precision = fraud_caught / queue_size
        recall = fraud_caught / total_fraud if total_fraud else 0.0
        rows.append(
            {
                "review_capacity_pct": review_rate * 100,
                "queue_size": queue_size,
                "fraud_caught": fraud_caught,
                "clean_transactions_reviewed": queue_size - fraud_caught,
                "precision_pct": precision * 100,
                "recall_pct": recall * 100,
                "baseline_fraud_rate_pct": baseline_rate * 100,
                "precision_lift_vs_baseline": (
                    precision / baseline_rate if baseline_rate else 0.0
                ),
            }
        )
    return pd.DataFrame(rows).round(2)


def save_review_capacity_curve(
    scored: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_review_capacity_curve(scored).to_csv(output_path, index=False)
    print(f"Review capacity curve saved -> {output_path}")


def choose_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    review_rate: float = 0.10,
) -> float:
    """Set the operating point from calibration scores and review capacity."""
    if len(y_true) != len(y_prob):
        raise ValueError("Calibration labels and probabilities must have equal length.")
    if not (0 < review_rate < 1):
        raise ValueError("review_rate must be in (0, 1).")
    return float(np.quantile(y_prob, 1 - review_rate))


def get_classifier_probability(model, x_data: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x_data)[:, 1]
    decision = model.decision_function(x_data)
    return 1.0 / (1.0 + np.exp(-decision))


def assign_risk_buckets(scored: pd.DataFrame) -> pd.Series:
    if scored.empty:
        return pd.Series(dtype="object")

    # Relative queue tiers remain useful even when calibrated probabilities are
    # low. The flag is threshold-based; the bucket is percentile-based.
    percentile_rank = scored["risk_score"].rank(method="first", pct=True)
    conditions = [
        percentile_rank > 0.99,
        percentile_rank > 0.95,
        percentile_rank > 0.80,
    ]

    return pd.Series(
        np.select(conditions, ["Critical", "High", "Medium"], default="Low"),
        index=scored.index,
    )


def save_feature_importance(
    model,
    holdout_df: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = permutation_importance(
        model,
        holdout_df[FEATURE_COLUMNS],
        holdout_df["is_fraud"].to_numpy(),
        scoring="average_precision",
        n_repeats=10,
        random_state=42,
        n_jobs=1,  # Small holdout; predictable local execution is preferable here.
    )
    order = np.argsort(result.importances_mean)[::-1]
    rows = [
        {
            "feature": FEATURE_COLUMNS[idx],
            "importance_mean": round(float(result.importances_mean[idx]), 6),
            "importance_std": round(float(result.importances_std[idx]), 6),
            "rank": rank,
            "note": "Permutation importance on chronological test split using average precision.",
        }
        for rank, idx in enumerate(order, start=1)
    ]

    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"Feature importance report saved -> {output_path}")


def build_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_depth=5,
        min_samples_leaf=30,
        class_weight="balanced",
        categorical_features=[
            False, False, False, False,
            True, True, True, True,
            False, False, False, False, False, False, False,
        ],
        random_state=42,
    )


def split_train_calibration_test(
    df: pd.DataFrame,
    calibration_size: float,
    test_size: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if calibration_size <= 0 or test_size <= 0 or calibration_size + test_size >= 1:
        raise ValueError("Invalid train/calibration/test proportions.")

    # Train on the past, set review capacity on the next period, and report once
    # on the latest period. This avoids tuning the queue on the final test data.
    ordered = df.sort_values(["transaction_time", "transaction_id"]).reset_index(drop=True)
    train_end = int(len(ordered) * (1 - calibration_size - test_size))
    calibration_end = int(len(ordered) * (1 - test_size))
    train_df = ordered.iloc[:train_end].copy()
    calibration_df = ordered.iloc[train_end:calibration_end].copy()
    test_df = ordered.iloc[calibration_end:].copy()

    if train_df.empty or calibration_df.empty or test_df.empty:
        raise ValueError("Train/calibration/test split produced an empty partition.")
    for name, partition in [
        ("train", train_df),
        ("calibration", calibration_df),
        ("test", test_df),
    ]:
        if partition["is_fraud"].nunique() < 2:
            raise ValueError(f"{name} partition must contain both fraud classes.")
    return train_df, calibration_df, test_df


def score_dataframe(
    df: pd.DataFrame,
    model,
    threshold: float,
    review_rate: float | None = None,
) -> pd.DataFrame:
    scored = df.copy()
    all_data = scored[FEATURE_COLUMNS]
    probabilities = get_classifier_probability(model, all_data)
    scored["fraud_probability"] = probabilities
    scored["risk_score"] = probabilities
    scored["predicted_state"] = (probabilities >= threshold).astype(int)
    if review_rate is None:
        scored["risk_flag"] = scored["predicted_state"].astype(int)
    else:
        percentile_rank = scored["risk_score"].rank(method="first", pct=True)
        scored["risk_flag"] = (percentile_rank > 1 - review_rate).astype(int)
    scored["risk_bucket"] = assign_risk_buckets(scored)
    return scored


def save_artifact(
    model,
    vocabs: Dict[str, Dict[str, int]],
    model_type: str,
    model_kind: str,
    threshold: float,
    model_path: Path,
    training_metadata: dict | None = None,
) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "vocabs": vocabs,
        "model_type": model_type,
        "model_kind": model_kind,
        "threshold": threshold,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "training_metadata": training_metadata or {},
    }
    joblib.dump(artifact, model_path)
    print(f"Model artifact saved -> {model_path}")


def load_artifact(model_path: Path) -> dict:
    artifact = joblib.load(model_path)
    required_keys = {"model", "feature_columns", "vocabs", "model_kind", "threshold"}
    missing = required_keys.difference(artifact.keys())
    if missing:
        raise ValueError(f"Model artifact missing keys: {sorted(missing)}")
    return artifact


def run_train(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)
    model_path = Path(args.model_out)
    metrics_path = Path(args.metrics_out)
    feature_importance_path = Path(args.feature_importance_out)
    capacity_curve_path = Path(args.capacity_curve_out)
    inference_sample_path = Path(args.inference_sample_out)
    daily_output_path = Path(args.daily_output)

    validate_common_path(input_path, "Input")
    validate_train_args(args)

    print("Loading Data...")
    df = pd.read_csv(input_path)
    validate_columns(df, TRAIN_REQUIRED_COLUMNS)
    df["is_fraud"] = df["is_fraud"].astype(int)

    print(f"  Total transactions: {len(df)}")
    print(f"  Fraud events:       {int(df['is_fraud'].sum())}")
    print(f"  Fraud rate:         {round(df['is_fraud'].mean() * 100, 1)}%")

    df = prepare_base_features(df)
    train_raw, calibration_raw, test_raw = split_train_calibration_test(
        df,
        args.calibration_size,
        args.test_size,
    )
    train_df, vocabs = encode_for_training(train_raw.copy())
    calibration_df = encode_for_inference(calibration_raw.copy(), vocabs)
    test_df = encode_for_inference(test_raw.copy(), vocabs)
    print(
        f"\nChronological split | train: {len(train_df):,} | "
        f"calibration: {len(calibration_df):,} | test: {len(test_df):,}"
    )
    print(f"\nTraining model: {args.model_type}")

    model = build_model()
    model.fit(train_df[FEATURE_COLUMNS], train_df["is_fraud"].to_numpy())
    calibration_prob = get_classifier_probability(model, calibration_df[FEATURE_COLUMNS])
    threshold = choose_threshold(
        calibration_df["is_fraud"].to_numpy(),
        calibration_prob,
        review_rate=args.review_rate,
    )
    print(
        f"  Calibration threshold for {args.review_rate:.0%} review capacity: "
        f"{round(threshold, 4)}"
    )

    test_scored = score_dataframe(test_df, model, threshold, args.review_rate)
    print("\nChronological Test Results (Interview-Safe):")
    test_metrics = compute_metrics(test_scored)
    print_evaluation(test_metrics)

    metrics_df = pd.DataFrame(
        [
            {
                "dataset": str(input_path).replace("\\", "/"),
                "model_type": args.model_type,
                "model_kind": MODEL_KIND,
                "evaluation_mode": "time",
                "train_rows": len(train_df),
                "calibration_rows": len(calibration_df),
                "test_rows": len(test_df),
                "train_fraud_rate_pct": train_df["is_fraud"].mean() * 100,
                "calibration_fraud_rate_pct": calibration_df["is_fraud"].mean() * 100,
                "test_fraud_rate_pct": test_df["is_fraud"].mean() * 100,
                "calibration_size": args.calibration_size,
                "test_size": args.test_size,
                "threshold": threshold,
                "threshold_source": "calibration_score_quantile",
                "target_review_rate": args.review_rate,
                "risk_flag_method": "batch_top_review_rate",
                "probability_threshold_flag_rate_pct": (
                    test_scored["predicted_state"].mean() * 100
                ),
                **test_metrics,
            }
        ]
    )
    # Preserve the original Power BI-facing metric schema first. Existing M
    # queries specify a fixed CSV column count, so new split metadata must be
    # appended rather than inserted ahead of holdout_rows after standardizing.
    legacy_metric_columns = [
        "model_type",
        "model_kind",
        "evaluation_mode",
        "test_size",
        "threshold",
        "rows",
        "fraud_events",
        "fraud_caught",
        "recall_pct",
        "roc_auc",
        "precision_pct",
        "false_positive_rate_pct",
        "tn",
        "fp",
        "fn",
        "tp",
    ]
    additional_metric_columns = [
        column for column in metrics_df.columns if column not in legacy_metric_columns
    ]
    metrics_df = metrics_df[legacy_metric_columns + additional_metric_columns]
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(metrics_path, index=False)
    print(f"\nChronological test metrics saved -> {metrics_path}")
    save_feature_importance(model, test_df, feature_importance_path)
    save_review_capacity_curve(test_scored, capacity_curve_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    test_scored[train_output_columns()].to_csv(output_path, index=False)
    print(f"Chronological test-scored output saved -> {output_path}")

    inference_sample_path.parent.mkdir(parents=True, exist_ok=True)
    test_raw[BASE_REQUIRED_COLUMNS].to_csv(inference_sample_path, index=False)
    unlabeled_scored = score_dataframe(
        test_df.drop(columns=["is_fraud"]),
        model,
        threshold,
        args.review_rate,
    )
    daily_output_path.parent.mkdir(parents=True, exist_ok=True)
    unlabeled_scored[infer_output_columns(has_is_fraud=False)].to_csv(
        daily_output_path, index=False
    )
    print(f"Unlabeled inference sample saved -> {inference_sample_path}")
    print(f"Unlabeled scored queue saved -> {daily_output_path}")

    save_artifact(
        model=model,
        vocabs=vocabs,
        model_type=args.model_type,
        model_kind=MODEL_KIND,
        threshold=threshold,
        model_path=model_path,
        training_metadata={
            "dataset": str(input_path).replace("\\", "/"),
            "evaluation_mode": "time",
            "train_rows": len(train_df),
            "calibration_rows": len(calibration_df),
            "test_rows": len(test_df),
            "threshold_source": "calibration_score_quantile",
            "target_review_rate": args.review_rate,
            "risk_flag_method": "batch_top_review_rate",
            "artifact_scope": "train_partition_only",
        },
    )


def run_inference(
    input_path: Path,
    model_path: Path,
    output_path: Path,
) -> None:
    validate_common_path(input_path, "Input")
    validate_common_path(model_path, "Model")
    artifact = load_artifact(model_path)
    model = artifact["model"]
    feature_columns: list[str] = artifact["feature_columns"]
    vocabs: Dict[str, Dict[str, int]] = artifact["vocabs"]
    threshold: float = float(artifact["threshold"])
    review_rate = artifact.get("training_metadata", {}).get("target_review_rate")

    df = pd.read_csv(input_path)
    validate_columns(df, BASE_REQUIRED_COLUMNS)
    df = prepare_base_features(df)
    df = encode_for_inference(df, vocabs)

    if feature_columns != FEATURE_COLUMNS:
        raise ValueError("Model artifact feature schema does not match this scorer.")
    df = score_dataframe(df, model, threshold, review_rate)

    print(f"Scored transactions:           {len(df):,}")
    print(f"Flagged as high risk:          {int(df['risk_flag'].sum()):,}")

    df[infer_output_columns("is_fraud" in df.columns)].to_csv(output_path, index=False)
    print(f"Predictions saved -> {output_path}")


def main() -> None:
    args = parse_args()
    run_train(args)


if __name__ == "__main__":
    main()
