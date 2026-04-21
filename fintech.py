import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURE_COLUMNS = [
    "amount",
    "Hour",
    "Day_Index",
    "inter_txn_minutes",
    "device_code",
    "merchant_code",
    "country_code",
    "entry_code",
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
SUPPORTED_MODELS = {
    "isolation_forest",
    "hist_gradient_boosting",
    "random_forest",
    "logistic_regression",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fraud velocity modeling: train, evaluate, and infer."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Train and evaluate model.")
    train_parser.add_argument("--input", default="fintech_fraud_data.csv")
    train_parser.add_argument("--output", default="outputs/fraud_model_output.csv")
    train_parser.add_argument("--model-out", default="outputs/fraud_model.joblib")
    train_parser.add_argument(
        "--model-type",
        default="hist_gradient_boosting",
        choices=sorted(SUPPORTED_MODELS),
        help="Model family to train for production scoring.",
    )
    train_parser.add_argument("--contamination", type=float, default=0.24)
    train_parser.add_argument("--rapid-threshold-minutes", type=float, default=2.0)
    train_parser.add_argument("--test-size", type=float, default=0.25)
    train_parser.add_argument(
        "--evaluation-mode",
        default="time",
        choices=["time", "stratified"],
        help="Holdout strategy: time-based split (recommended) or stratified random split.",
    )
    train_parser.add_argument("--metrics-out", default="outputs/train_metrics_report.csv")

    infer_parser = subparsers.add_parser("infer", help="Score new/unlabeled data.")
    infer_parser.add_argument("--input", required=True)
    infer_parser.add_argument("--model", default="outputs/fraud_model.joblib")
    infer_parser.add_argument("--output", default="outputs/fraud_predictions.csv")
    infer_parser.add_argument("--rapid-threshold-minutes", type=float, default=2.0)

    return parser.parse_args()


def validate_common_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")


def validate_train_args(args: argparse.Namespace) -> None:
    if args.model_type == "isolation_forest" and not (0 < args.contamination < 0.5):
        raise ValueError("--contamination must be between 0 and 0.5.")
    if args.rapid_threshold_minutes <= 0:
        raise ValueError("--rapid-threshold-minutes must be > 0.")
    if not (0 < args.test_size < 0.5):
        raise ValueError("--test-size must be in (0, 0.5).")


def validate_infer_args(args: argparse.Namespace) -> None:
    if args.rapid_threshold_minutes <= 0:
        raise ValueError("--rapid-threshold-minutes must be > 0.")


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
    df["transaction_time"] = pd.to_datetime(df["transaction_time"], dayfirst=True, errors="coerce")
    if df["transaction_time"].isna().any():
        raise ValueError("Invalid transaction_time values found after datetime parsing.")

    df["Hour"] = df["transaction_time"].dt.hour
    df["Day_Index"] = df["transaction_time"].dt.dayofweek

    df = df.sort_values(["user_id", "transaction_time"]).copy()
    prev_txn = df.groupby("user_id", sort=False)["transaction_time"].shift(1)
    inter_minutes = (df["transaction_time"] - prev_txn).dt.total_seconds().div(60)
    df["inter_txn_minutes"] = inter_minutes.fillna(9999.0)
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


def evaluate_model(df: pd.DataFrame, model_kind: str) -> None:
    print("\nEvaluation Results:")
    print("=" * 45)

    fraud_rows = df[df["is_fraud"] == 1]
    caught_fraud = fraud_rows[fraud_rows["risk_flag"] == 1]
    catch_rate = (len(caught_fraud) / len(fraud_rows) * 100) if len(fraud_rows) > 0 else 0.0

    score_input = -df["anomaly_score"] if model_kind == "anomaly" else df["anomaly_score"]
    roc_auc = roc_auc_score(df["is_fraud"], score_input)

    cm = confusion_matrix(df["is_fraud"], df["risk_flag"], labels=[0, 1])
    tn, fp, _, tp = cm.ravel()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    false_positive_rate = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0.0

    print(f"  Total transactions:         {len(df):,}")
    print(f"  Confirmed fraud events:     {len(fraud_rows):,}")
    print(f"  Fraud caught by model:      {len(caught_fraud):,}")
    print(f"  Catch Rate (Recall):        {round(catch_rate, 1)}%")
    print(f"  ROC-AUC:                    {round(roc_auc, 2)}")
    print(f"  Precision:                  {round(precision * 100, 1)}%")
    print(f"  False Positive Rate:        {round(false_positive_rate, 1)}%")
    print(f"  True Negatives (clean):     {tn:,}")
    print(f"  False Positives (flagged):  {fp:,}")


def compute_metrics(df: pd.DataFrame, model_kind: str) -> Dict[str, float]:
    fraud_rows = df[df["is_fraud"] == 1]
    caught_fraud = fraud_rows[fraud_rows["risk_flag"] == 1]
    catch_rate = (len(caught_fraud) / len(fraud_rows) * 100) if len(fraud_rows) > 0 else 0.0

    score_input = -df["anomaly_score"] if model_kind == "anomaly" else df["anomaly_score"]
    roc_auc = roc_auc_score(df["is_fraud"], score_input)

    cm = confusion_matrix(df["is_fraud"], df["risk_flag"], labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    false_positive_rate = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0.0

    return {
        "rows": float(len(df)),
        "fraud_events": float(len(fraud_rows)),
        "fraud_caught": float(len(caught_fraud)),
        "recall_pct": catch_rate,
        "roc_auc": float(roc_auc),
        "precision_pct": precision * 100.0,
        "false_positive_rate_pct": false_positive_rate,
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
    }


def choose_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    candidate_thresholds = np.linspace(0.05, 0.95, 91)
    best_threshold = 0.5
    best_score = -1.0

    for thr in candidate_thresholds:
        y_pred = (y_prob >= thr).astype(int)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        if score > best_score:
            best_score = score
            best_threshold = float(thr)

    return best_threshold


def get_classifier_probability(model, x_data: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x_data)[:, 1]
    decision = model.decision_function(x_data)
    return 1.0 / (1.0 + np.exp(-decision))


def build_model(model_type: str, contamination: float):
    if model_type == "isolation_forest":
        return IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        )
    if model_type == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.05,
            max_depth=8,
            random_state=42,
        )
    if model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
    if model_type == "logistic_regression":
        return LogisticRegression(
            max_iter=1200,
            class_weight="balanced",
            solver="lbfgs",
            random_state=42,
        )
    raise ValueError(f"Unsupported model_type: {model_type}")


def split_train_holdout(
    df: pd.DataFrame,
    evaluation_mode: str,
    test_size: float,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if evaluation_mode == "time":
        ordered = df.sort_values("transaction_time").reset_index(drop=True)
        split_idx = int(len(ordered) * (1 - test_size))
        train_df = ordered.iloc[:split_idx].copy()
        holdout_df = ordered.iloc[split_idx:].copy()
    else:
        train_idx, holdout_idx = train_test_split(
            df.index,
            test_size=test_size,
            random_state=42,
            stratify=df["is_fraud"],
        )
        train_df = df.loc[train_idx].copy()
        holdout_df = df.loc[holdout_idx].copy()

    if train_df.empty or holdout_df.empty:
        raise ValueError("Train/holdout split produced empty partition. Adjust --test-size.")
    return train_df, holdout_df


def score_dataframe(df: pd.DataFrame, model, model_kind: str, threshold: float) -> pd.DataFrame:
    scored = df.copy()
    all_data = scored[FEATURE_COLUMNS]
    if model_kind == "anomaly":
        scored["anomaly_score"] = model.decision_function(all_data)
        scored["predicted_state"] = model.predict(all_data)
        scored["risk_flag"] = (scored["predicted_state"] == -1).astype(int)
    else:
        probabilities = get_classifier_probability(model, all_data)
        scored["anomaly_score"] = probabilities
        scored["predicted_state"] = (probabilities >= threshold).astype(int)
        scored["risk_flag"] = scored["predicted_state"].astype(int)
    return scored


def velocity_sub_analysis(df: pd.DataFrame, rapid_threshold_minutes: float) -> None:
    print(
        f"\nVelocity Sub-Analysis (Rapid Transactions < {rapid_threshold_minutes:g} min apart):"
    )
    print("=" * 45)

    rapid_txns = df[df["inter_txn_minutes"] < rapid_threshold_minutes]
    rapid_fraud = rapid_txns[rapid_txns["is_fraud"] == 1]
    rapid_caught = rapid_fraud[rapid_fraud["risk_flag"] == 1]

    if len(rapid_fraud) > 0:
        rapid_catch_rate = len(rapid_caught) / len(rapid_fraud) * 100
        print(f"  Rapid transactions total:   {len(rapid_txns):,}")
        print(f"  Fraud in rapid set:         {len(rapid_fraud):,}")
        print(f"  Caught in rapid set:        {len(rapid_caught):,}")
        print(f"  Rapid fraud catch rate:     {round(rapid_catch_rate, 1)}%")
    else:
        print("  No rapid back-to-back fraud transactions found in dataset.")


def run_live_simulation(model, vocabs: Dict[str, Dict[str, int]], model_kind: str, threshold: float) -> None:
    print("\nLive Anomaly Scan - Simulated High-Risk Transaction:")
    print("=" * 45)

    mobile_code = vocabs["device"].get("mobile", -1)
    digital_code = vocabs["merchant"].get("Digital Goods", -1)
    ru_code = vocabs["country"].get("RU", -1)
    contactless = vocabs["entry"].get("Contactless", -1)

    sample = pd.DataFrame(
        [
            {
                "amount": 1850.0,
                "Hour": 2,
                "Day_Index": 1,
                "inter_txn_minutes": 1.2,
                "device_code": mobile_code,
                "merchant_code": digital_code,
                "country_code": ru_code,
                "entry_code": contactless,
            }
        ],
        columns=FEATURE_COLUMNS,
    )
    if model_kind == "anomaly":
        sim_score = float(model.decision_function(sample)[0])
        is_risky = sim_score < 0
        score_text = f"Anomaly Score: {round(sim_score, 4)}  (negative = anomalous)"
    else:
        sim_score = float(get_classifier_probability(model, sample)[0])
        is_risky = sim_score >= threshold
        score_text = f"Risk Probability: {round(sim_score, 4)}  (>= {round(threshold, 2)} => high risk)"

    print("  Scenario: $1,850 mobile | Digital Goods | 1.2 min after prior txn | 2 AM")
    print(f"  {score_text}")
    if is_risky:
        print("  ALERT: Transaction pattern deviates significantly from normal behavior.")
    else:
        print("  Status: Within normal behavioral range.")


def save_artifact(
    model,
    vocabs: Dict[str, Dict[str, int]],
    model_type: str,
    model_kind: str,
    threshold: float,
    contamination: float | None,
    model_path: Path,
) -> None:
    artifact = {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "vocabs": vocabs,
        "model_type": model_type,
        "model_kind": model_kind,
        "threshold": threshold,
        "contamination": contamination,
        "created_utc": datetime.now(timezone.utc).isoformat(),
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
    df, vocabs = encode_for_training(df)

    train_df, holdout_df = split_train_holdout(df, args.evaluation_mode, args.test_size)
    print(
        f"\nHoldout evaluation mode: {args.evaluation_mode} | "
        f"train rows: {len(train_df):,}, holdout rows: {len(holdout_df):,}"
    )
    print(f"\nTraining model: {args.model_type}")

    model = build_model(args.model_type, args.contamination)

    if args.model_type == "isolation_forest":
        model_kind = "anomaly"
        threshold = 0.0
        model.fit(train_df[FEATURE_COLUMNS][train_df["is_fraud"] == 0])
    else:
        model_kind = "classifier"
        model.fit(train_df[FEATURE_COLUMNS], train_df["is_fraud"].to_numpy())
        train_prob = get_classifier_probability(model, train_df[FEATURE_COLUMNS])
        threshold = choose_threshold(train_df["is_fraud"].to_numpy(), train_prob)
        print(f"  Selected probability threshold: {round(threshold, 4)}")

    holdout_scored = score_dataframe(holdout_df, model, model_kind, threshold)
    print("\nHoldout Evaluation Results (Interview-Safe):")
    evaluate_model(holdout_scored, model_kind)
    velocity_sub_analysis(holdout_scored, args.rapid_threshold_minutes)
    run_live_simulation(model, vocabs, model_kind, threshold)

    holdout_metrics = compute_metrics(holdout_scored, model_kind)
    metrics_df = pd.DataFrame(
        [
            {
                "model_type": args.model_type,
                "model_kind": model_kind,
                "evaluation_mode": args.evaluation_mode,
                "test_size": args.test_size,
                "threshold": threshold,
                **holdout_metrics,
            }
        ]
    )
    metrics_df.to_csv(metrics_path, index=False)
    print(f"\nHoldout metrics report saved -> {metrics_path}")

    # Refit on full data for production artifact after holdout reporting is complete.
    if model_kind == "anomaly":
        model.fit(df[FEATURE_COLUMNS][df["is_fraud"] == 0])
    else:
        model.fit(df[FEATURE_COLUMNS], df["is_fraud"].to_numpy())

    full_scored = score_dataframe(df, model, model_kind, threshold)

    output_cols = BASE_REQUIRED_COLUMNS + ["is_fraud", "inter_txn_minutes", "anomaly_score", "risk_flag"]
    full_scored[output_cols].to_csv(output_path, index=False)
    print(f"\nScored output saved -> {output_path}")

    save_artifact(
        model=model,
        vocabs=vocabs,
        model_type=args.model_type,
        model_kind=model_kind,
        threshold=threshold,
        contamination=args.contamination if model_kind == "anomaly" else None,
        model_path=model_path,
    )


def run_inference(
    input_path: Path,
    model_path: Path,
    output_path: Path,
    rapid_threshold_minutes: float = 2.0,
) -> None:
    validate_common_path(input_path, "Input")
    validate_common_path(model_path, "Model")
    if rapid_threshold_minutes <= 0:
        raise ValueError("--rapid-threshold-minutes must be > 0.")

    artifact = load_artifact(model_path)
    model = artifact["model"]
    feature_columns: list[str] = artifact["feature_columns"]
    vocabs: Dict[str, Dict[str, int]] = artifact["vocabs"]
    model_kind: str = artifact["model_kind"]
    threshold: float = float(artifact["threshold"])

    df = pd.read_csv(input_path)
    validate_columns(df, BASE_REQUIRED_COLUMNS)
    df = prepare_base_features(df)
    df = encode_for_inference(df, vocabs)

    all_data = df[feature_columns]
    if model_kind == "anomaly":
        df["anomaly_score"] = model.decision_function(all_data)
        df["predicted_state"] = model.predict(all_data)
        df["risk_flag"] = (df["predicted_state"] == -1).astype(int)
    else:
        probabilities = get_classifier_probability(model, all_data)
        df["anomaly_score"] = probabilities
        df["predicted_state"] = (probabilities >= threshold).astype(int)
        df["risk_flag"] = df["predicted_state"].astype(int)

    rapid_count = int((df["inter_txn_minutes"] < rapid_threshold_minutes).sum())
    flagged_rapid_count = int(
        ((df["inter_txn_minutes"] < rapid_threshold_minutes) & (df["risk_flag"] == 1)).sum()
    )
    print(f"Scored transactions:           {len(df):,}")
    print(f"Flagged as high risk:          {int(df['risk_flag'].sum()):,}")
    print(f"Rapid transactions (<{rapid_threshold_minutes:g}m): {rapid_count:,}")
    print(f"Rapid + flagged transactions:  {flagged_rapid_count:,}")

    output_cols = BASE_REQUIRED_COLUMNS + ["inter_txn_minutes", "anomaly_score", "risk_flag"]
    if "is_fraud" in df.columns:
        output_cols.insert(9, "is_fraud")
    df[output_cols].to_csv(output_path, index=False)
    print(f"Predictions saved -> {output_path}")


def run_infer(args: argparse.Namespace) -> None:
    validate_infer_args(args)
    run_inference(
        input_path=Path(args.input),
        model_path=Path(args.model),
        output_path=Path(args.output),
        rapid_threshold_minutes=args.rapid_threshold_minutes,
    )


def main() -> None:
    args = parse_args()
    if args.command == "train":
        run_train(args)
    elif args.command == "infer":
        run_infer(args)
    else:
        raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
