"""Comparables-driven exit valuation for a venture portfolio.

A Python implementation of the Excel model in ../workbook, cell for cell:

    Exit value (per company)  = average of
        - Exit-comp estimate:    median of included M&A / IPO comps
        - Private-comp estimate: mean of included private peer valuations x step-up
      (or whichever one exists)
    Expected value to fund    = P(exit) x Exit value x fully diluted ownership
    PV                        = Expected value / (1 + r) ^ (exit year - current year)
    Expected MOIC             = Expected value / capital invested
    Net expected MOIC         = Expected value / (invested + follow-on reserves)

Stage drives only P(exit), timing and reserves. It never drives the exit value,
and the company's relationship with the hospital (pilot, deployment, none) is
deliberately not an input: it says nothing about market maturity.

Usage:
    python src/exit_valuation.py                  # base case + charts
    python src/exit_valuation.py --stepup 2.0     # change a global assumption
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"


@dataclass
class Assumptions:
    current_year: int = 2026
    discount_rate: float = 0.15
    private_stepup: float = 2.5
    legacy_exit_multiple: float = 3.0

    @classmethod
    def from_csv(cls, path: Path = DATA / "assumptions.csv") -> "Assumptions":
        v = pd.read_csv(path).set_index("parameter")["value"]
        return cls(int(v.current_year), float(v.discount_rate), float(v.private_stepup),
                   float(v.legacy_exit_multiple))


def load_inputs():
    portfolio = pd.read_csv(DATA / "portfolio.csv")
    comps = pd.read_csv(DATA / "comps.csv")
    ladder = pd.read_csv(DATA / "stage_ladder.csv").set_index("code")
    return portfolio, comps, ladder


def comp_estimates(comps: pd.DataFrame) -> pd.DataFrame:
    """Per company: count/median of exit comps and count/mean of private comps (included only)."""
    inc = comps[comps["include"].str.upper() == "Y"]
    ex = inc[inc["type"] == "Exit"].groupby("company")["value"].agg(n_exit="count", exit_median="median")
    pr = inc[inc["type"] == "Private"].groupby("company")["value"].agg(n_private="count", private_mean="mean")
    return ex.join(pr, how="outer")


def value_portfolio(portfolio: pd.DataFrame, comps: pd.DataFrame, ladder: pd.DataFrame,
                    a: Assumptions, p_scale: float = 1.0) -> pd.DataFrame:
    """Return one row per company with every column of the Excel model.

    `p_scale` multiplies every P(exit) (capped at 100%) for sensitivity analysis.
    """
    df = portfolio.merge(comp_estimates(comps), left_on="company", right_index=True, how="left")
    df[["n_exit", "n_private"]] = df[["n_exit", "n_private"]].fillna(0).astype(int)
    df[["exit_median", "private_mean"]] = df[["exit_median", "private_mean"]].fillna(0.0)

    df["stepup"] = df["stepup_override"].fillna(a.private_stepup)
    df["exit_val_exit_comps"] = df["exit_median"]
    df["exit_val_private_comps"] = df["private_mean"] * df["stepup"]
    both = (df["exit_val_exit_comps"] > 0) & (df["exit_val_private_comps"] > 0)
    df["exit_value"] = np.where(
        both,
        (df["exit_val_exit_comps"] + df["exit_val_private_comps"]) / 2,
        df[["exit_val_exit_comps", "exit_val_private_comps"]].max(axis=1),
    )

    df["p_default"] = df["stage"].map(ladder["default_p_exit"]).fillna(0.0)
    df["p_used"] = (df["p_override"].fillna(df["p_default"]) * p_scale).clip(upper=1.0)
    yrs = df["stage"].map(ladder["default_years_to_exit"])
    df["exit_year"] = df["exit_year_override"].fillna(a.current_year + yrs.fillna(0)).astype(int)

    own = df["ownership"]
    df["gross_exit_to_fund"] = df["exit_value"] * own
    df["risk_adj"] = df["p_used"] * df["gross_exit_to_fund"]
    df["risk_adj_exit_basis"] = df["p_used"] * df["exit_val_exit_comps"] * own
    df["risk_adj_private_basis"] = df["p_used"] * df["exit_val_private_comps"] * own
    df["pv_risk_adj"] = df["risk_adj"] / (1 + a.discount_rate) ** (df["exit_year"] - a.current_year)
    df["exp_moic"] = np.where(df["invested"] > 0, df["risk_adj"] / df["invested"].replace(0, np.nan), np.nan)
    df["legacy_exit"] = df["current_val"] * a.legacy_exit_multiple * own

    df["reserve_ratio"] = df["stage"].map(ladder["reserve_ratio"]).fillna(0.0)
    df["follow_on"] = df["invested"] * df["reserve_ratio"]
    df["capital_deployed"] = df["invested"] + df["follow_on"]
    df["net_exp_moic"] = df["risk_adj"] / df["capital_deployed"].replace(0, np.nan)
    return df


def summarize(v: pd.DataFrame, realized_company: str = "Company 33") -> dict[str, float]:
    real = v[v["company"] == realized_company]
    s = {
        "follow_on_reserves": v["follow_on"].sum(),
        "gross_exit_value": v["gross_exit_to_fund"].sum(),
        "risk_adjusted_value": v["risk_adj"].sum(),
        "total_invested": v["invested"].sum(),
        "pv_risk_adjusted": v["pv_risk_adj"].sum(),
        "legacy_exit_value": v["legacy_exit"].sum(),
    }
    s["expected_moic"] = s["risk_adjusted_value"] / s["total_invested"]
    s["expected_moic_ex_realized"] = ((s["risk_adjusted_value"] - real["risk_adj"].sum())
                                      / (s["total_invested"] - real["invested"].sum()))
    s["net_expected_moic"] = s["risk_adjusted_value"] / v["capital_deployed"].sum()
    return s


def sensitivity(portfolio, comps, ladder, a: Assumptions,
                stepups=(1.0, 1.5, 2.0, 2.5, 3.0, 3.5), p_scales=(0.6, 0.8, 1.0, 1.2)) -> pd.DataFrame:
    """Expected MOIC (ex realized exit) across private step-up x P(exit) scaling."""
    grid = {}
    for ps in p_scales:
        row = {}
        for su in stepups:
            aa = Assumptions(a.current_year, a.discount_rate, su, a.legacy_exit_multiple)
            row[su] = summarize(value_portfolio(portfolio, comps, ladder, aa, p_scale=ps))["expected_moic_ex_realized"]
        grid[ps] = row
    out = pd.DataFrame(grid).T
    out.index.name, out.columns.name = "p_scale", "private_stepup"
    return out


def render_charts(v: pd.DataFrame, sens: pd.DataFrame, a: Assumptions) -> None:
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

    # 1) Capital invested vs probability-weighted value, by stage (excludes realized exit).
    live = v[v["stage"] != "X"]
    order = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "D"]
    g = live.groupby("stage")[["invested", "risk_adj"]].sum().reindex(order).fillna(0) / 1e6
    x = np.arange(len(g))
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    w = 0.36
    ax.bar(x - w / 2 - 0.01, g["invested"], w, color="#86b6ef", label="Capital invested")
    ax.bar(x + w / 2 + 0.01, g["risk_adj"], w, color="#1c5cab", label="Probability-weighted exit value")
    for xi, (inv, ra) in enumerate(zip(g["invested"], g["risk_adj"])):
        if inv > 0:
            ax.text(xi + w / 2, ra + 1, f"{ra / inv:.1f}x", ha="center", fontsize=8.5, color=muted)
    ax.set_xticks(x, order)
    ax.set_ylabel("$ millions")
    ax.grid(axis="y", color=grid, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_title("Invested vs expected value by stage (synthetic portfolio; label = expected MOIC)",
                 loc="left", color=ink, fontsize=11.5, pad=12)
    fig.tight_layout()
    fig.savefig(OUT / "value_by_stage.png", dpi=160)
    plt.close(fig)

    # 2) Sensitivity heatmap (sequential, one hue).
    cmap = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#5598e7", "#104281"])
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    im = ax.imshow(sens.to_numpy(), cmap=cmap, aspect="auto")
    ax.set_xticks(range(sens.shape[1]), [f"{c:.1f}x" for c in sens.columns])
    ax.set_yticks(range(sens.shape[0]), [f"{r:.0%}" for r in sens.index])
    ax.set_xlabel("Private peer to exit step-up")
    ax.set_ylabel("P(exit) as % of base")
    vmax = sens.to_numpy().max()
    for (i, j), val in np.ndenumerate(sens.to_numpy()):
        ax.text(j, i, f"{val:.2f}x", ha="center", va="center", fontsize=9,
                color="#ffffff" if val > sens.to_numpy().min() + 0.55 * (vmax - sens.to_numpy().min()) else ink)
    ax.set_xticks(np.arange(sens.shape[1] + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(sens.shape[0] + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=surface, linewidth=2)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Expected MOIC (ex realized exit): sensitivity to the two key assumptions",
                 loc="left", color=ink, fontsize=11.5, pad=12)
    fig.tight_layout()
    fig.savefig(OUT / "moic_sensitivity.png", dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stepup", type=float, help="override the global private step-up")
    ap.add_argument("--discount", type=float, help="override the discount rate")
    ap.add_argument("--no-charts", action="store_true")
    args = ap.parse_args()

    a = Assumptions.from_csv()
    if args.stepup is not None:
        a.private_stepup = args.stepup
    if args.discount is not None:
        a.discount_rate = args.discount

    portfolio, comps, ladder = load_inputs()
    v = value_portfolio(portfolio, comps, ladder, a)
    s = summarize(v)
    sens = sensitivity(portfolio, comps, ladder, a)

    OUT.mkdir(exist_ok=True)
    v.to_csv(OUT / "valuation_output.csv", index=False)
    sens.round(3).to_csv(OUT / "moic_sensitivity.csv")
    if not args.no_charts:
        render_charts(v, sens, a)

    for k, val in s.items():
        print(f"{k:28s} {val:>16,.2f}" if "moic" in k else f"{k:28s} ${val:>15,.0f}")


if __name__ == "__main__":
    main()
