import argparse
from pathlib import Path

from fintech import run_inference


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score daily payment transactions using a saved fraud model artifact."
    )
    parser.add_argument("--input", required=True, help="Path to daily transactions CSV.")
    parser.add_argument(
        "--model",
        default="outputs/fraud_model.joblib",
        help="Path to trained model artifact.",
    )
    parser.add_argument(
        "--output",
        default="outputs/daily_fraud_predictions.csv",
        help="Path to write scored daily output.",
    )
    parser.add_argument(
        "--rapid-threshold-minutes",
        type=float,
        default=2.0,
        help="Threshold for rapid transaction stats.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_inference(
        input_path=Path(args.input),
        model_path=Path(args.model),
        output_path=Path(args.output),
        rapid_threshold_minutes=args.rapid_threshold_minutes,
    )


if __name__ == "__main__":
    main()
