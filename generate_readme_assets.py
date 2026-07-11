"""Generate professional README key visuals from existing analysis CSVs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "readme_assets"

BG = "#F7F8FA"
INK = "#1A2332"
MUTED = "#5C6B7A"
NAVY = "#1E3A5F"
AMBER = "#C47B2D"
TEAL = "#2F6F6A"
RISK = "#8B3A3A"

FIGSIZE = (10, 5.2)
DPI = 160


def _first_existing(*candidates: Path) -> Path:
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "None of these paths exist:\n" + "\n".join(str(c) for c in candidates)
    )


def _style_axes(ax, title: str, subtitle: str) -> None:
    ax.set_facecolor(BG)
    ax.figure.patch.set_facecolor(BG)
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", color=INK, pad=28)
    ax.text(
        0.0,
        1.02,
        subtitle,
        transform=ax.transAxes,
        fontsize=10.5,
        color=MUTED,
        ha="left",
        va="bottom",
    )
    ax.tick_params(colors=MUTED, labelsize=10)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#D0D5DC")
    ax.grid(axis="x", color="#E4E7EC", linewidth=0.8)
    ax.set_axisbelow(True)


def _short_reason(reason: str) -> str:
    if "Insufficient" in reason:
        return "Insufficient Funds"
    if "Fraud" in reason:
        return "Suspected Fraud"
    if "Timeout" in reason:
        return "Issuer Timeout"
    return reason.split(": ", 1)[-1] if ": " in reason else reason


def _money(n: float) -> str:
    if abs(n) >= 1000:
        return f"${n:,.0f}"
    return f"${n:,.2f}"


def chart_01_decline_concentration() -> Path:
    path = _first_existing(
        ROOT / "outputs" / "payment_action_matrix.csv",
        ROOT / "powerbi-data" / "payment_action_matrix.csv",
    )
    df = pd.read_csv(path).sort_values("failed_value", ascending=True)
    total = df["failed_value"].sum()
    nsf = float(df.loc[df["decline_code"] == 51, "failed_value"].iloc[0])
    fraud = float(df.loc[df["decline_code"] == 59, "failed_value"].iloc[0])
    share = (nsf + fraud) / total * 100

    labels = [_short_reason(r) for r in df["decline_reason"]]
    values = df["failed_value"].tolist()
    colors = [
        AMBER if code in (51, 59) else NAVY for code in df["decline_code"]
    ]

    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.barh(labels, values, color=colors, height=0.62)
    _style_axes(
        ax,
        "Two decline reasons drive most failed value",
        (
            f"{_money(nsf)} NSF + {_money(fraud)} fraud "
            f"≈ {share:.0f}% of failed payment value"
        ),
    )
    ax.set_xlabel("Failed payment value ($)", color=MUTED)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + total * 0.012,
            bar.get_y() + bar.get_height() / 2,
            _money(val),
            va="center",
            ha="left",
            color=INK,
            fontsize=10,
        )
    ax.set_xlim(0, max(values) * 1.18)
    out = OUT_DIR / "01_decline_concentration.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def chart_02_retry_timing() -> Path:
    path = ROOT / "data" / "sql_exports" / "retry_timing_windows.csv"
    df = pd.read_csv(path)
    nsf = df[df["decline_reason"].str.contains("Insufficient", na=False)].copy()
    recovered = nsf[~nsf["retry_window"].str.contains("Not recovered", na=False)].copy()

    window_map = {
        "31-120 min": "0–2 hours",
        "2-6 hours": "2–6 hours",
        "6-24 hours": "6–24 hours",
    }
    order = ["0–2 hours", "2–6 hours", "6–24 hours"]
    recovered["label"] = recovered["retry_window"].map(window_map)
    recovered = recovered.set_index("label").loc[order].reset_index()

    total_rec = recovered["failed_txns"].sum()
    recovered["share_pct"] = recovered["failed_txns"] / total_rec * 100

    colors = [NAVY, NAVY, AMBER]
    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.barh(
        recovered["label"],
        recovered["share_pct"],
        color=colors,
        height=0.62,
    )
    peak = float(recovered.loc[recovered["label"] == "6–24 hours", "share_pct"].iloc[0])
    _style_axes(
        ax,
        "Most recoveries arrive after 6 hours",
        f"{peak:.1f}% of eventual NSF recoveries land in the 6–24 hour window",
    )
    ax.set_xlabel("Share of eventual NSF recoveries (%)", color=MUTED)
    for bar, row in zip(bars, recovered.itertuples()):
        ax.text(
            bar.get_width() + 1.2,
            bar.get_y() + bar.get_height() / 2,
            f"{row.share_pct:.1f}%  (n={int(row.failed_txns)})",
            va="center",
            ha="left",
            color=INK,
            fontsize=10,
        )
    ax.set_xlim(0, 100)
    out = OUT_DIR / "02_retry_timing_curve.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def chart_03_cost_exposure() -> Path:
    path = _first_existing(
        ROOT / "outputs" / "interchange_cost_exposure.csv",
        ROOT / "powerbi-data" / "interchange_cost_exposure.csv",
    )
    df = pd.read_csv(path).sort_values("total_interchange_fee", ascending=True)
    zero_cost = float(
        df.loc[df["recovered_txns"] == 0, "total_interchange_fee"].sum()
    )

    labels = [_short_reason(r) for r in df["decline_reason"]]
    values = df["total_interchange_fee"].tolist()
    colors = [
        RISK if rec == 0 else (TEAL if code == 51 else NAVY)
        for code, rec in zip(df["decline_code"], df["recovered_txns"])
    ]

    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.barh(labels, values, color=colors, height=0.62)
    _style_axes(
        ax,
        "Processing cost on zero-recovery declines",
        f"{_money(zero_cost)} on fraud + timeout with 0% recovery in this snapshot",
    )
    ax.set_xlabel("Total interchange / processing fee ($)", color=MUTED)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    for bar, row in zip(bars, df.itertuples()):
        retry = "retry allowed" if bool(row.automatic_retry_allowed) else "no auto-retry"
        ax.text(
            bar.get_width() + max(values) * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{_money(row.total_interchange_fee)}  ·  recovered {int(row.recovered_txns)}  ·  {retry}",
            va="center",
            ha="left",
            color=INK,
            fontsize=9.5,
        )
    ax.set_xlim(0, max(values) * 1.55)
    out = OUT_DIR / "03_retry_cost_exposure.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def chart_04_review_capacity() -> Path:
    path = _first_existing(
        ROOT / "outputs" / "review_capacity_curve.csv",
        ROOT / "powerbi-data" / "review_capacity_curve.csv",
    )
    df = pd.read_csv(path).sort_values("review_capacity_pct")
    x = df["review_capacity_pct"].astype(float)
    labels = [f"{int(v)}%" for v in x]
    idx = range(len(df))
    best = df.loc[df["review_capacity_pct"] == 10.0].iloc[0]

    fig, ax = plt.subplots(figsize=FIGSIZE)
    width = 0.36
    prec_colors = [AMBER if v == 10.0 else NAVY for v in x]
    lift_colors = [AMBER if v == 10.0 else TEAL for v in x]

    bars1 = ax.bar(
        [i - width / 2 for i in idx],
        df["precision_pct"],
        width=width,
        color=prec_colors,
        label="Precision %",
    )
    ax2 = ax.twinx()
    bars2 = ax2.bar(
        [i + width / 2 for i in idx],
        df["precision_lift_vs_baseline"],
        width=width,
        color=lift_colors,
        alpha=0.9,
        label="Precision lift (×)",
    )

    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    ax.set_title(
        "10% review capacity is the strongest tested queue",
        loc="left",
        fontsize=15,
        fontweight="bold",
        color=INK,
        pad=28,
    )
    ax.text(
        0.0,
        1.02,
        (
            f"{best['precision_pct']:.1f}% precision vs "
            f"{best['baseline_fraud_rate_pct']:.1f}% baseline "
            f"({best['precision_lift_vs_baseline']:.2f}× lift)"
        ),
        transform=ax.transAxes,
        fontsize=10.5,
        color=MUTED,
        ha="left",
        va="bottom",
    )
    ax.set_xticks(list(idx))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Review capacity (% of scored volume)", color=MUTED)
    ax.set_ylabel("Precision (%)", color=MUTED)
    ax2.set_ylabel("Precision lift vs baseline (×)", color=MUTED)
    ax.tick_params(colors=MUTED)
    ax2.tick_params(colors=MUTED)
    for spine in ("top",):
        ax.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)
    for spine in ("left", "bottom", "right"):
        ax.spines[spine].set_color("#D0D5DC")
        ax2.spines[spine].set_color("#D0D5DC")
    ax.grid(axis="y", color="#E4E7EC", linewidth=0.8)
    ax.set_axisbelow(True)

    for bar, val in zip(bars1, df["precision_pct"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.15,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK,
        )
    for bar, val in zip(bars2, df["precision_lift_vs_baseline"]):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.03,
            f"{val:.2f}×",
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK,
        )

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper right", labelcolor=MUTED)

    out = OUT_DIR / "04_review_capacity.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
            "axes.unicode_minus": False,
        }
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = [
        chart_01_decline_concentration(),
        chart_02_retry_timing(),
        chart_03_cost_exposure(),
        chart_04_review_capacity(),
    ]
    print(f"Wrote {len(written)} assets to {OUT_DIR}")
    for path in written:
        size = path.stat().st_size
        print(f"  {path.name}: {size:,} bytes ({path})")


if __name__ == "__main__":
    main()
