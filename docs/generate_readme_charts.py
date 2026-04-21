from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VIS_DIR = ROOT / "docs" / "visuals"
VIS_DIR.mkdir(parents=True, exist_ok=True)


def chart_failure_mix() -> None:
    df = pd.read_csv(ROOT / "Tables" / "Error Pareto Analysis.csv")
    top = df.sort_values("Failure_Count", ascending=False).head(3)

    plt.figure(figsize=(8, 4.5))
    bars = plt.bar(top["Error_Reason"], top["Failure_Count"], color=["#2563EB", "#0EA5E9", "#7C3AED"])
    plt.title("Top Failure Reasons")
    plt.ylabel("Failure Count")
    plt.xticks(rotation=20, ha="right")
    for bar, pct in zip(bars, top["Pct_of_Failures"]):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{pct:.1f}%", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(VIS_DIR / "01-failure-mix.png", dpi=160)
    plt.close()


def chart_retry_recovery() -> None:
    df = pd.read_csv(ROOT / "Tables" / "Smart Retry Analysis (LEAD Window Function).csv")
    total_failures = int(df["Total_Failures"].sum())
    recovered = int(df["Recovered_Txns"].sum())
    unrecovered = total_failures - recovered

    plt.figure(figsize=(6, 4.5))
    plt.pie(
        [recovered, unrecovered],
        labels=["Recovered within 24h", "Not recovered within 24h"],
        colors=["#16A34A", "#DC2626"],
        autopct="%1.1f%%",
        startangle=140,
    )
    plt.title("Retry Recovery Opportunity")
    plt.tight_layout()
    plt.savefig(VIS_DIR / "02-retry-recovery.png", dpi=160)
    plt.close()


def chart_holdout_confusion() -> None:
    df = pd.read_csv(ROOT / "outputs" / "train_metrics_report.csv")
    row = df.iloc[0]
    matrix = [[int(row["tn"]), int(row["fp"])], [int(row["fn"]), int(row["tp"])]]

    fig, ax = plt.subplots(figsize=(5.8, 4.8))
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks([0, 1], labels=["Pred: Non-Fraud", "Pred: Fraud"])
    ax.set_yticks([0, 1], labels=["Actual: Non-Fraud", "Actual: Fraud"])
    ax.set_title("Holdout Confusion Matrix")

    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{matrix[i][j]:,}", ha="center", va="center", color="#111827", fontsize=11)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(VIS_DIR / "03-holdout-confusion.png", dpi=160)
    plt.close()


if __name__ == "__main__":
    chart_failure_mix()
    chart_retry_recovery()
    chart_holdout_confusion()
    print(f"Charts generated in: {VIS_DIR}")
