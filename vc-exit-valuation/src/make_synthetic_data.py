"""Generate the synthetic 42-company portfolio and comps used in this repo.

The real model was built on a confidential venture portfolio. Every company,
valuation, ownership stake, investment amount and comparable here is randomly
generated (seeded, so the files are reproducible). Only the model structure,
stage ladder and methodology carry over from the original work.

Usage: python src/make_synthetic_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RNG = np.random.default_rng(2026)

N = 42
SECTORS = ["Bio tech"] * 18 + ["Med tech"] * 14 + ["Health Tech"] * 10
# Stage mix mirrors a typical hospital-affiliated venture portfolio:
# heavy in clinical-stage and commercial companies, one write-down, one realized exit.
STAGES = (["S7"] * 17 + ["S4"] * 10 + ["S2"] * 8 + ["S3"] * 2
          + ["S5", "S6", "S1", "D"])
REALIZED_ROW = 32  # zero-based index -> "Company 33", the realized exit

# Typical current (post-money) valuation by stage, $m (median of a lognormal).
VAL_MEDIAN = {"S1": 6, "S2": 18, "S3": 22, "S4": 45, "S5": 70, "S6": 60, "S7": 35, "D": 0}
# Exit comps relative to current valuation: earlier stage -> bigger multiple, wider spread.
EXIT_MULT = {"S1": 6.0, "S2": 4.5, "S3": 4.0, "S4": 3.0, "S5": 2.5, "S6": 2.2, "S7": 1.8}


def main() -> None:
    sectors = RNG.permutation(SECTORS)
    stages = list(RNG.permutation(STAGES))
    stages.insert(REALIZED_ROW, "X")
    assert len(stages) == N

    rows, comps = [], []
    for i in range(N):
        name, stage = f"Company {i + 1:02d}", stages[i]
        if stage == "X":
            cur = 900e6
            own = 0.035
        elif stage == "D":
            cur = 0.0
            own = round(RNG.uniform(0.02, 0.06), 4)
        else:
            cur = round(VAL_MEDIAN[stage] * 1e6 * RNG.lognormal(0, 0.45), -4)
            own = round(float(np.clip(RNG.lognormal(np.log(0.06), 0.7), 0.005, 0.45)), 4)

        entry_discount = RNG.uniform(0.35, 0.9) if stage not in ("X", "D") else RNG.uniform(0.1, 0.3)
        base = cur if cur else 15e6
        invested = round(own * base * entry_discount, -3)

        # Probability override: ~45% of companies carry a PitchBook-style
        # exit-predictor probability that replaces the stage default.
        override = None
        if stage not in ("X", "D") and RNG.random() < 0.45:
            override = round(float(np.clip(RNG.normal(0.5, 0.2), 0.1, 0.9)), 2)

        stepup = None  # blank -> global default from Assumptions
        if stage == "S7" and RNG.random() < 0.35:
            stepup = 1.0  # private peers already trade at exit-scale valuations

        exit_year_override = 2034 if i == 25 else None

        n_exit = n_priv = 0
        if stage == "X":
            comps.append([name, "Realized exit (actual)", "Exit", 900e6, "2025", "Deal terms", "Y",
                          "Actual realized exit value"])
            n_exit = 1
        elif stage != "D":
            for k in range(RNG.integers(4, 10)):
                v = round(cur * EXIT_MULT[stage] * RNG.lognormal(0, 0.6), -4)
                keep = "Y" if RNG.random() < 0.55 else "N"
                why = ("Stage- and modality-matched" if keep == "Y"
                       else RNG.choice(["Commercial-scale acquirer, not stage-matched",
                                        "Different modality", "Geography mismatch", "Stale (pre-2019)"]))
                comps.append([name, f"Exit comp {chr(65 + k)}", "Exit", v, f"{RNG.integers(2019, 2026)}",
                              "Synthetic M&A/IPO comp", keep, why])
                n_exit += keep == "Y"
            for k in range(RNG.integers(2, 6)):
                v = round(cur * RNG.lognormal(0.1, 0.5), -4)
                keep = "Y" if RNG.random() < 0.6 else "N"
                why = "Comparable stage and indication" if keep == "Y" else "Peer at different stage"
                comps.append([name, f"Private peer {chr(65 + k)}", "Private", v, f"{RNG.integers(2023, 2027)}",
                              "Synthetic private round", keep, why])
                n_priv += keep == "Y"

        note = f"Synthetic company. Stage {stage}."
        if override is not None:
            note += f" P(exit) overridden to {override:.0%} (exit-predictor style input)."
        if stepup == 1.0:
            note += " Private step-up set to 1.0x: peers already at exit-scale valuations."
        if stage == "D":
            note += " Written down; no comps, stage default P(exit) applies to a nil value."
        if stage == "X":
            note += " Realized exit: value is the actual deal, P(exit) = 100%."
        if exit_year_override:
            note += f" Exit year overridden to {exit_year_override} (long regulatory path)."

        rows.append(dict(company=name, code=f"PC-{i + 1:02d}", sector=sectors[i], stage=stage,
                         current_val=cur, ownership=own, p_override=override,
                         stepup_override=stepup, exit_year_override=exit_year_override,
                         invested=invested, notes=note))

    DATA.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(DATA / "portfolio.csv", index=False)
    pd.DataFrame(comps, columns=["company", "comp_name", "type", "value", "as_of", "source",
                                 "include", "reason"]).to_csv(DATA / "comps.csv", index=False)
    print(f"{len(rows)} companies, {len(comps)} comps written to {DATA}")


if __name__ == "__main__":
    main()
