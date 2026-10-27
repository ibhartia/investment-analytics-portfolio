"""Earnings call sentiment scorecard.

Rebuilds the composite scores, per-company summary and quarter-over-quarter
trend from the raw dimension scores, runs data-quality checks, and renders
the charts used in the README.

Usage:
    python src/scorecard.py                # from earnings-call-sentiment/
    python src/scorecard.py --weights custom_weights.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"

DIMENSIONS = [
    "mgmt_tone",
    "fwd_guidance",
    "risk_language",
    "analyst_sentiment",
    "fin_health",
    "strat_clarity",
]
SCORE_MIN, SCORE_MAX = -5, 5


def load_weights(path: Path = DATA / "weights.csv") -> pd.Series:
    w = pd.read_csv(path).set_index("dimension")["weight"].astype(float)
    return w.reindex(DIMENSIONS)


def load_scores(path: Path = DATA / "scores.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["call_date"] = pd.to_datetime(df["call_date"], format="%m/%d/%Y", errors="coerce")
    return df


def validate(scores: pd.DataFrame, weights: pd.Series) -> list[str]:
    """Return a list of data-quality issues (empty list = clean)."""
    issues: list[str] = []
    if abs(weights.sum() - 1.0) > 1e-9:
        issues.append(f"Weights sum to {weights.sum():.4f}, expected 1.0")
    if weights.isna().any():
        issues.append(f"Missing weights for: {list(weights[weights.isna()].index)}")

    dims = scores[DIMENSIONS]
    bad = (dims < SCORE_MIN) | (dims > SCORE_MAX)
    for idx, col in zip(*bad.to_numpy().nonzero()):
        r = scores.iloc[idx]
        issues.append(f"{r.ticker} {r.quarter}: {DIMENSIONS[col]} out of range")

    for _, r in scores[scores["call_date"].isna()].iterrows():
        issues.append(f"{r.ticker} {r.quarter}: invalid or missing call date")

    dupes = scores[scores.duplicated(["ticker", "quarter"], keep=False)]
    for _, r in dupes.iterrows():
        issues.append(f"{r.ticker} {r.quarter}: duplicate ticker/quarter row")

    # Call dates for a ticker should be strictly increasing in file order.
    for t, g in scores.groupby("ticker", sort=False):
        if not g["call_date"].is_monotonic_increasing:
            issues.append(f"{t}: call dates are out of chronological order")
    return issues


def add_composite(scores: pd.DataFrame, weights: pd.Series) -> pd.DataFrame:
    """Weighted composite, matching the workbook's ROUND(SUMPRODUCT, 2).

    Analyst Sentiment can be N/A when a transcript has no Q&A; in that case
    the remaining weights are re-normalised so the composite stays on the
    -5..+5 scale.
    """
    out = scores.copy()
    dims = out[DIMENSIONS]
    present = dims.notna()
    w = present.mul(weights, axis=1)
    out["composite"] = (dims.fillna(0).mul(weights, axis=1).sum(axis=1) / w.sum(axis=1)).round(2)
    return out


def company_summary(scored: pd.DataFrame) -> pd.DataFrame:
    scored = scored.sort_values(["ticker", "call_date"])
    agg = scored.groupby(["ticker", "company"], sort=True).agg(
        quarters=("quarter", "count"),
        **{f"avg_{d}": (d, "mean") for d in DIMENSIONS},
        avg_composite=("composite", "mean"),
        first_composite=("composite", "first"),
        latest_composite=("composite", "last"),
    )
    agg["trend"] = (agg["latest_composite"] - agg["first_composite"]).round(2)
    agg["direction"] = agg["trend"].map(lambda x: "up" if x > 0 else ("down" if x < 0 else "flat"))
    return agg.round(2).reset_index().sort_values("avg_composite", ascending=False)


def render_charts(scored: pd.DataFrame, summary: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": grid,
        "axes.labelcolor": muted, "xtick.color": muted, "ytick.color": muted,
        "figure.facecolor": surface, "axes.facecolor": surface,
    })

    # 1) Dimension heatmap: average score per company x dimension (diverging).
    labels = ["Mgmt tone", "Fwd guidance", "Risk language", "Analyst sent.", "Fin. health", "Strat. clarity"]
    hm = summary.set_index("ticker")[[f"avg_{d}" for d in DIMENSIONS]]
    cmap = LinearSegmentedColormap.from_list("div", ["#e34948", "#f0efec", "#2a78d6"])
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    im = ax.imshow(hm.to_numpy(), cmap=cmap, vmin=-5, vmax=5, aspect="auto")
    ax.set_xticks(range(len(labels)), labels, rotation=0, fontsize=9)
    ax.set_yticks(range(len(hm)), hm.index)
    for (i, j), v in pd.DataFrame(hm.to_numpy()).stack().items():
        ax.text(j, i, f"{v:+.1f}", ha="center", va="center", fontsize=8.5, color=ink)
    ax.set_xticks([x - 0.5 for x in range(1, len(labels))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(hm))], minor=True)
    ax.grid(which="minor", color=surface, linewidth=2)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, ticks=[-5, -3, 0, 3, 5])
    cb.outline.set_visible(False)
    cb.set_label("Average score (-5 very negative to +5 very positive)", color=muted)
    ax.set_title("Average sentiment by dimension, sorted by composite", loc="left", color=ink, fontsize=12, pad=12)
    fig.tight_layout()
    fig.savefig(OUT / "dimension_heatmap.png", dpi=160)
    plt.close(fig)

    # 2) Composite drift: latest vs first quarter, per company (dumbbell).
    s = summary.sort_values("latest_composite")
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for i, r in enumerate(s.itertuples()):
        ax.plot([r.first_composite, r.latest_composite], [i, i], color="#b7d3f6", lw=2, zorder=1)
    ax.scatter(s["first_composite"], range(len(s)), s=46, color="#86b6ef", zorder=2,
               edgecolor=surface, linewidth=2, label="First quarter scored")
    ax.scatter(s["latest_composite"], range(len(s)), s=46, color="#1c5cab", zorder=3,
               edgecolor=surface, linewidth=2, label="Latest quarter scored")
    for i, r in enumerate(s.itertuples()):
        ax.text(max(r.first_composite, r.latest_composite) + 0.08, i, f"{r.trend:+.2f}",
                va="center", fontsize=8.5, color=muted)
    ax.set_yticks(range(len(s)), s["ticker"])
    ax.axvline(0, color=grid, lw=1)
    ax.set_xlim(-0.5, 4.5)
    ax.set_xlabel("Weighted composite score")
    ax.grid(axis="x", color=grid, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_title("Sentiment drift: first vs latest scored call", loc="left", color=ink, fontsize=12, pad=12)
    fig.tight_layout()
    fig.savefig(OUT / "composite_drift.png", dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, default=DATA / "weights.csv")
    ap.add_argument("--no-charts", action="store_true")
    args = ap.parse_args()

    weights = load_weights(args.weights)
    scores = load_scores()
    issues = validate(scores, weights)
    if issues:
        print("Data-quality issues:")
        for i in issues:
            print("  -", i)
    else:
        print(f"Validation passed: {len(scores)} transcripts, {scores.ticker.nunique()} companies.")

    scored = add_composite(scores, weights)
    summary = company_summary(scored)
    OUT.mkdir(exist_ok=True)
    scored.to_csv(OUT / "scored_transcripts.csv", index=False, date_format="%Y-%m-%d")
    summary.to_csv(OUT / "company_summary.csv", index=False)
    if not args.no_charts:
        render_charts(scored, summary)

    cols = ["ticker", "quarters", "avg_composite", "latest_composite", "trend"]
    print(summary[cols].to_string(index=False))


if __name__ == "__main__":
    main()
