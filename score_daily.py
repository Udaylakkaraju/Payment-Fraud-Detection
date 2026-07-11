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
        default="outputs/daily_scored_transactions.csv",
        help="Path to write scored daily output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_inference(
        input_path=Path(args.input),
        model_path=Path(args.model),
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
