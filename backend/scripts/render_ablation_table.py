"""
render_ablation_table.py
========================
Rebuild the paper-ready ablation table from a saved ablation_results*.json
WITHOUT re-running the (slow) model inference.

Usage:
    python scripts/render_ablation_table.py reports/ablation_results_local.json
"""
import json
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(__file__))


def render(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        r = json.load(f)

    n = r["n_labeled"]
    gt = {int(k): v for k, v in r["gt_distribution_3class"].items()}
    gtb = {int(k): v for k, v in r["gt_distribution_binary"].items()}
    base = gtb.get(1, 0) / (sum(gtb.values()) or 1)

    L = []
    L.append("=" * 70)
    L.append("ABLATION RESULTS -- Indian Water Benchmark (local_benchmark, human-labeled)")
    L.append("=" * 70)
    L.append(f"Labeled images: {n}")
    L.append(f"GT (3-class): Low={gt.get(0,0)}  Moderate={gt.get(1,0)}  High={gt.get(2,0)}")
    L.append(f"GT (binary):  clean(Low)={gtb.get(0,0)}  polluted(Mod+High)={gtb.get(1,0)}")
    L.append("")
    L.append("BINARY FRAMING (clean vs polluted)")
    L.append("-" * 70)
    L.append(f"{'Model':<26}{'Acc':>7}{'Prec':>7}{'Rec':>7}{'F1':>7}{'Cov':>7}")
    L.append("-" * 70)
    for m in r["binary_framing"]:
        if m.get("n", 0) == 0:
            L.append(f"{m['model']:<26}  (no predictions)")
            continue
        L.append(f"{m['model']:<26}"
                 f"{m['accuracy']*100:>6.1f}%"
                 f"{m['precision_polluted']*100:>6.1f}%"
                 f"{m['recall_polluted']*100:>6.1f}%"
                 f"{m['f1_polluted']*100:>6.1f}%"
                 f"{m['coverage']*100:>6.0f}%")
    L.append("")
    L.append("THREE-CLASS FRAMING (Low / Moderate / High)")
    L.append("-" * 70)
    L.append(f"{'Model':<26}{'Acc':>7}{'MacroF1':>9}")
    L.append("-" * 70)
    for m in r["threeclass_framing"]:
        if m.get("n", 0) == 0:
            continue
        L.append(f"{m['model']:<26}{m['accuracy']*100:>6.1f}%{m['macro_f1']*100:>8.1f}%")
    L.append("")
    L.append("VERDICT")
    L.append("-" * 70)
    singles = [m for m in r["binary_framing"]
               if m["model"] != "Ensemble (baseline_v1)" and m.get("n")]
    best = max(singles, key=lambda m: m["f1_polluted"])
    ens = next(m for m in r["binary_framing"] if m["model"] == "Ensemble (baseline_v1)")
    delta = (ens["f1_polluted"] - best["f1_polluted"]) * 100
    L.append(f"Best single model: {best['model']} (F1={best['f1_polluted']*100:.1f}%, "
             f"prec={best['precision_polluted']*100:.1f}%)")
    L.append(f"Ensemble:          F1={ens['f1_polluted']*100:.1f}%, "
             f"prec={ens['precision_polluted']*100:.1f}%, rec={ens['recall_polluted']*100:.1f}%")
    L.append(f"Base rate (always-polluted) accuracy = {base*100:.1f}%")
    L.append("")
    L.append("Interpretation:")
    L.append(f"  - Ensemble binary accuracy ({ens['accuracy']*100:.1f}%) ~= base rate "
             f"({base*100:.1f}%): it predicts 'polluted' almost always")
    L.append(f"    (recall {ens['recall_polluted']*100:.1f}%, precision ~= base rate). "
             f"That is base-rate matching, not skill.")
    L.append(f"  - Every model has near-zero specificity on clean water "
             f"(see confusion matrices in JSON).")
    L.append(f"  - Three-class severity accuracy (27-32%) is at/below the majority-class "
             f"baseline ({max(gt.values())/n*100:.1f}%): severity grading fails OOD.")
    L.append(f"  - EfficientNet internal val acc was 99.9%; on real Indian water it is "
             f"{next(m['accuracy']*100 for m in r['binary_framing'] if m['model']=='EfficientNet-only'):.1f}% "
             f"binary. That OOD collapse is the headline finding.")
    L.append("=" * 70)
    return "\n".join(L)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        BASE, "reports", "ablation_results_local.json")
    table = render(src)
    out = src.replace("ablation_results", "ablation_table").replace(".json", ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(table)
    print(table)
    print(f"\nSaved: {out}")
