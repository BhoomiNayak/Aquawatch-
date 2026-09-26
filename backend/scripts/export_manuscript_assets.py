"""
export_manuscript_assets.py
===========================
Generate final manuscript assets from already-computed result files:

  reports/figure1_ndci_timeseries.png    Sentinel-2 monthly NDCI per lake
                                          (polluted vs clean reference)
  reports/figure2_ood_vs_satellite.png    Two-panel contrast:
                                            (A) ground classifier ROC (AUC~0.49)
                                            (B) satellite NDCI separation
  reports/paper_table_1_lake_summary.csv   Paper-ready per-lake summary

Inputs (must exist; produced earlier in the pipeline):
  reports/sentinel_ndci_monthly.csv
  reports/sentinel_lake_summary.csv
  reports/benchmark_probs.csv

Usage:
  cd backend
  python scripts/export_manuscript_assets.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("MPLCONFIGDIR", "C:/tmp/mpl")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(__file__))
REPORTS = os.path.join(BASE, "reports")

MONTHLY = os.path.join(REPORTS, "sentinel_ndci_monthly.csv")
SUMMARY = os.path.join(REPORTS, "sentinel_lake_summary.csv")
PROBS = os.path.join(REPORTS, "benchmark_probs.csv")

FIG1 = os.path.join(REPORTS, "figure1_ndci_timeseries.png")
FIG2 = os.path.join(REPORTS, "figure2_ood_vs_satellite.png")
TABLE1 = os.path.join(REPORTS, "paper_table_1_lake_summary.csv")

CAT_COLOR = {"polluted": "#b22222", "moderate": "#daa520",
             "clean_reference": "#2e8b57", "unknown": "#666666"}
CAT_STYLE = {"polluted": "-", "moderate": "--", "clean_reference": ":", "unknown": "-"}
CLEAN_CATS = {"clean_reference"}

plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "figure.dpi": 300,
})


def _require(path: str):
    if not os.path.exists(path):
        sys.exit(f"Missing required input: {path}\n"
                 f"Run the upstream scripts (sentinel_ndci_timeseries.py / "
                 f"calibrate_threshold.py) first.")


def clean_baseline_from_summary(sdf: pd.DataFrame) -> float:
    ref = sdf[sdf["category"].isin(CLEAN_CATS)]
    if len(ref) and "ndci_p75" in ref:
        return float(ref["ndci_p75"].mean())
    return 0.0155


# ── Figure 1: NDCI monthly time-series ──────────────────────────────────────
def figure1(mdf: pd.DataFrame, baseline: float):
    valid = mdf.dropna(subset=["ndci_mean"]).copy()
    valid = valid.sort_values("date")
    fig, ax = plt.subplots(figsize=(12, 5.5))

    for lake, g in valid.groupby("lake"):
        g = g.sort_values("date")
        cat = g["category"].iloc[0]
        ax.plot(g["date"], g["ndci_mean"],
                CAT_STYLE.get(cat, "-"), color=CAT_COLOR.get(cat, "#666"),
                marker="o", ms=3, lw=1.7, label=f"{lake} ({cat.replace('_',' ')})")

    ax.axhline(baseline, color="black", lw=1.0, ls="-.", alpha=0.7,
               label=f"clean-reference baseline ({baseline:.3f})")
    ax.axhline(0, color="grey", lw=0.5, alpha=0.4)
    ax.set_title("Figure 1. Sentinel-2 monthly NDCI (chlorophyll proxy) over water pixels")
    ax.set_ylabel("NDCI  (higher = more chlorophyll / eutrophication)")
    ax.set_xlabel("Month")

    dates = sorted(valid["date"].unique())
    step = max(1, len(dates) // 16)
    ax.set_xticks(dates[::step])
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, ncol=2, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG1, dpi=300)
    plt.close(fig)
    print(f"  wrote {FIG1}")


# ── Figure 2: OOD classifier failure vs satellite separation ────────────────
def figure2(pdf: pd.DataFrame, sdf: pd.DataFrame, baseline: float):
    from sklearn.metrics import roc_curve, roc_auc_score

    y = pdf["gt_binary"].to_numpy()
    p = pdf["p_polluted"].to_numpy()
    fpr, tpr, _ = roc_curve(y, p)
    auc = roc_auc_score(y, p)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5.5))

    # Panel A — ground classifier ROC (chance-level)
    axA.plot(fpr, tpr, color="#b22222", lw=2, label=f"EfficientNet (AUC = {auc:.2f})")
    axA.plot([0, 1], [0, 1], color="grey", lw=1, ls="--", label="chance (AUC = 0.50)")
    axA.set_xlim(0, 1); axA.set_ylim(0, 1)
    axA.set_xlabel("False positive rate")
    axA.set_ylabel("True positive rate")
    axA.set_title("(A) Ground classifier on Indian benchmark\nno OOD discrimination")
    axA.legend(loc="lower right", fontsize=9)
    axA.grid(alpha=0.25)

    # Panel B — satellite NDCI median per lake, grouped by category
    order = {"polluted": 0, "moderate": 1, "clean_reference": 2, "unknown": 3}
    s = sdf.copy()
    s["ord"] = s["category"].map(order).fillna(9)
    s = s.sort_values(["ord", "ndci_median"], ascending=[True, False])
    colors = [CAT_COLOR.get(c, "#666") for c in s["category"]]
    ypos = np.arange(len(s))
    axB.barh(ypos, s["ndci_median"], color=colors, edgecolor="black", lw=0.4)
    axB.set_yticks(ypos)
    axB.set_yticklabels(s["lake"], fontsize=9)
    axB.invert_yaxis()
    axB.axvline(baseline, color="black", lw=1.2, ls="-.",
                label=f"clean baseline ({baseline:.3f})")
    axB.axvline(0, color="grey", lw=0.5, alpha=0.4)
    axB.set_xlabel("Median NDCI")
    axB.set_title("(B) Sentinel-2 NDCI\nclean separation of eutrophic vs clear water")
    axB.legend(loc="lower right", fontsize=9)
    axB.grid(axis="x", alpha=0.25)

    # category legend for panel B
    from matplotlib.patches import Patch
    handles = [Patch(color=CAT_COLOR[c], label=c.replace("_", " "))
               for c in ["polluted", "moderate", "clean_reference"]]
    axB.legend(handles=handles + [plt.Line2D([0], [0], color="black", ls="-.",
               label=f"clean baseline ({baseline:.3f})")],
               loc="lower right", fontsize=8)

    fig.suptitle("Figure 2. Cross-modal contrast: ground classifier fails OOD (A) "
                 "while satellite NDCI discriminates (B)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(FIG2, dpi=300)
    plt.close(fig)
    print(f"  wrote {FIG2}  (classifier AUC={auc:.4f})")


# ── Table 1: paper-ready lake summary ───────────────────────────────────────
def table1(sdf: pd.DataFrame, baseline: float):
    order = {"polluted": 0, "moderate": 1, "clean_reference": 2}
    t = sdf.copy()
    t["ord"] = t["category"].map(order).fillna(9)
    t = t.sort_values(["ord", "ndci_median"], ascending=[True, False])

    out = pd.DataFrame({
        "Water body": t["lake"],
        "Category": t["category"].str.replace("_", " "),
        "Months (n)": t["n_months"].astype(int),
        "NDCI mean": t["ndci_mean"].round(4),
        "NDCI median": t["ndci_median"].round(4),
        "NDCI p75": t["ndci_p75"].round(4),
        "NDCI latest": t["ndci_latest"].round(4),
        "Latest month": t["latest_date"],
        "Exceeds clean baseline": (t["ndci_median"] > baseline).map({True: "yes", False: "no"}),
    })
    out.to_csv(TABLE1, index=False)
    print(f"  wrote {TABLE1}")
    print("\n" + out.to_string(index=False))


def main():
    for p in (MONTHLY, SUMMARY, PROBS):
        _require(p)
    os.makedirs(REPORTS, exist_ok=True)

    mdf = pd.read_csv(MONTHLY)
    sdf = pd.read_csv(SUMMARY)
    pdf = pd.read_csv(PROBS)
    baseline = clean_baseline_from_summary(sdf)

    print(f"Clean-reference baseline (mean of clean p75): {baseline:.4f}")
    print("Generating manuscript assets...")
    figure1(mdf, baseline)
    figure2(pdf, sdf, baseline)
    table1(sdf, baseline)
    print("\nDone.")


if __name__ == "__main__":
    main()
