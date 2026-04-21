import argparse
from pathlib import Path
from typing import Callable, Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from fintech import FEATURE_COLUMNS, TRAIN_REQUIRED_COLUMNS, encode_for_training, prepare_base_features, validate_columns


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark supervised fraud models on labeled transaction data."
    )
    parser.add_argument("--input", default="fintech_fraud_data.csv", help="Input labeled CSV.")
    parser.add_argument(
        "--output",
        default="outputs/model_benchmark_results.csv",
        help="Output CSV with model comparison metrics.",
    )
    parser.add_argument(
        "--topk-frac",
        type=float,
        default=0.05,
        help="Top fraction for Precision@K / Recall@K (0 < value <= 1).",
    )
    parser.add_argument(
        "--fraud-cost",
        type=float,
        default=1.0,
        help="Relative cost of missed fraud (FN).",
    )
    parser.add_argument(
        "--review-cost",
        type=float,
        default=0.1,
        help="Relative cost of false positives (manual review burden).",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace, input_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not (0 < args.topk_frac <= 1):
        raise ValueError("--topk-frac must be in (0, 1].")
    if args.fraud_cost <= 0 or args.review_cost <= 0:
        raise ValueError("--fraud-cost and --review-cost must be > 0.")


def to_probability(model, x_test: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x_test)[:, 1]
    # Fallback for models exposing decision_function only.
    decision = model.decision_function(x_test)
    return 1.0 / (1.0 + np.exp(-decision))


def evaluate_rank_metrics(y_true: np.ndarray, y_prob: np.ndarray, topk_frac: float) -> Dict[str, float]:
    n = len(y_true)
    k = max(1, int(n * topk_frac))
    top_idx = np.argsort(y_prob)[::-1][:k]
    y_top = y_true[top_idx]
    positives_top = int(y_top.sum())
    total_positives = int(y_true.sum())

    precision_at_k = positives_top / k
    recall_at_k = positives_top / total_positives if total_positives > 0 else 0.0
    return {
        "topk_count": float(k),
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
    }


def choose_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    # Grid search threshold to maximize F1-ish balance (precision + recall harmonic behavior)
    candidate_thresholds = np.linspace(0.05, 0.95, 91)
    best_threshold = 0.5
    best_score = -1.0
    for thr in candidate_thresholds:
        y_pred = (y_prob >= thr).astype(int)
        p = precision_score(y_true, y_pred, zero_division=0)
        r = recall_score(y_true, y_pred, zero_division=0)
        if p + r == 0:
            score = 0.0
        else:
            score = 2 * p * r / (p + r)
        if score > best_score:
            best_score = score
            best_threshold = thr
    return float(best_threshold)


def evaluate_model(
    name: str,
    model,
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    x_test: pd.DataFrame,
    y_test: np.ndarray,
    topk_frac: float,
    fraud_cost: float,
    review_cost: float,
) -> Dict[str, float]:
    model.fit(x_train, y_train)
    y_prob = to_probability(model, x_test)

    threshold = choose_threshold(y_test, y_prob)
    y_pred = (y_prob >= threshold).astype(int)

    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)
    rank_metrics = evaluate_rank_metrics(y_test, y_prob, topk_frac)

    fn = int(((y_test == 1) & (y_pred == 0)).sum())
    fp = int(((y_test == 0) & (y_pred == 1)).sum())
    cost_score = fn * fraud_cost + fp * review_cost

    return {
        "model": name,
        "threshold": round(threshold, 4),
        "roc_auc": round(float(roc_auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "precision_at_k": round(float(rank_metrics["precision_at_k"]), 4),
        "recall_at_k": round(float(rank_metrics["recall_at_k"]), 4),
        "topk_count": int(rank_metrics["topk_count"]),
        "false_negatives": fn,
        "false_positives": fp,
        "cost_score": round(float(cost_score), 2),
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    validate_args(args, input_path)

    print("Loading and preparing labeled fraud data...")
    df = pd.read_csv(input_path)
    validate_columns(df, TRAIN_REQUIRED_COLUMNS)
    df["is_fraud"] = df["is_fraud"].astype(int)

    df = prepare_base_features(df)
    df, _ = encode_for_training(df)

    x = df[FEATURE_COLUMNS]
    y = df["is_fraud"].to_numpy()

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=42, stratify=y
    )

    print("Training benchmark models...")
    models: List[tuple[str, Callable[[], object]]] = [
        (
            "LogisticRegression",
            lambda: LogisticRegression(
                max_iter=1200,
                class_weight="balanced",
                solver="lbfgs",
                random_state=42,
            ),
        ),
        (
            "RandomForest",
            lambda: RandomForestClassifier(
                n_estimators=300,
                max_depth=12,
                min_samples_leaf=4,
                class_weight="balanced_subsample",
                random_state=42,
                n_jobs=-1,
            ),
        ),
        (
            "HistGradientBoosting",
            lambda: HistGradientBoostingClassifier(
                max_iter=300,
                learning_rate=0.05,
                max_depth=8,
                random_state=42,
            ),
        ),
    ]

    rows: List[Dict[str, float]] = []
    for model_name, build_model in models:
        print(f"  Evaluating: {model_name}")
        row = evaluate_model(
            name=model_name,
            model=build_model(),
            x_train=x_train,
            y_train=y_train,
            x_test=x_test,
            y_test=y_test,
            topk_frac=args.topk_frac,
            fraud_cost=args.fraud_cost,
            review_cost=args.review_cost,
        )
        rows.append(row)

    result_df = pd.DataFrame(rows).sort_values(
        by=["cost_score", "pr_auc", "precision_at_k"], ascending=[True, False, False]
    )
    result_df.to_csv(output_path, index=False)

    print("\nBenchmark complete.")
    print(result_df.to_string(index=False))
    print(f"\nSaved benchmark report -> {output_path}")


if __name__ == "__main__":
    main()
