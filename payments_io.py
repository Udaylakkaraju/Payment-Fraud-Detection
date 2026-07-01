"""Shared payments CSV loading with legacy and Power BI column support."""

from pathlib import Path

import pandas as pd

CANONICAL_PAYMENTS_PATH = Path("powerbi-data/payments.csv")
LEGACY_PAYMENTS_PATH = Path("data/raw/payments.csv")

# Internal snake_case names used across Python pipelines.
SNAKE_CASE_COLUMNS = [
    "transaction_id",
    "user_id",
    "payment_timestamp",
    "amount",
    "issuer_bank",
    "card_brand",
    "interchange_fee",
    "payment_status",
]

# Legacy PascalCase names retained for scenario_simulator internals.
LEGACY_COLUMN_MAP = {
    "transaction_id": "Transaction_ID",
    "user_id": "User_ID",
    "payment_timestamp": "Timestamp",
    "amount": "Amount",
    "issuer_bank": "Issuer_Bank",
    "card_brand": "Card_Brand",
    "payment_status": "Status",
}

REVERSE_LEGACY_MAP = {value: key for key, value in LEGACY_COLUMN_MAP.items()}


def resolve_payments_path(path: Path | None = None) -> Path:
    if path is not None:
        candidate = Path(path)
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Payments file not found: {candidate}")

    if CANONICAL_PAYMENTS_PATH.exists():
        return CANONICAL_PAYMENTS_PATH
    if LEGACY_PAYMENTS_PATH.exists():
        return LEGACY_PAYMENTS_PATH

    raise FileNotFoundError(
        "No payments file found. Expected "
        f"{CANONICAL_PAYMENTS_PATH} or {LEGACY_PAYMENTS_PATH}."
    )


def normalize_payments_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.rename(columns=REVERSE_LEGACY_MAP)
    missing = [
        col
        for col in SNAKE_CASE_COLUMNS
        if col not in renamed.columns and col != "interchange_fee"
    ]
    if missing:
        raise ValueError(f"Missing required payments columns after normalization: {missing}")
    return renamed


def to_legacy_payments_frame(df: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_payments_columns(df)
    legacy = normalized.rename(columns=LEGACY_COLUMN_MAP)
    required = list(LEGACY_COLUMN_MAP.values())
    return legacy[required].copy()


def load_payments(path: Path | None = None) -> pd.DataFrame:
    payments_path = resolve_payments_path(path)
    return normalize_payments_columns(pd.read_csv(payments_path))


def load_payments_legacy(path: Path | None = None) -> pd.DataFrame:
    return to_legacy_payments_frame(pd.read_csv(resolve_payments_path(path)))
