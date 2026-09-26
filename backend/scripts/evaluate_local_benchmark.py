"""
evaluate_local_benchmark.py
============================
Zero-shot evaluation of retrained EfficientNet-B0 on the Indian
validation benchmark dataset.

Expected folder layout:
    datasets/indian_validation_set/
        clean/      ← images labeled as clean water
        polluted/   ← images labeled as polluted water

If the dataset is not yet available, the script prints setup instructions
and exits cleanly (no crash).

USAGE:
    cd backend
    python scripts/evaluate_local_benchmark.py

OUTPUTS:
    reports/indian_benchmark_results.json  — full metrics
    Terminal                               — clean summary
"""

import os
import sys
import json
import logging
import glob
import time

import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import numpy as np

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("benchmark_eval")

# ── Paths ─────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE, "models", "efficientnet_water_quality_group_aware.pt")
DATA_DIR  = os.path.join(BASE, "datasets", "indian_validation_set")
REPORT    = os.path.join(BASE, "reports", "indian_benchmark_results.json")

# ── Config ────────────────────────────────────────────────────────────────
IMG_SIZE   = 224
BATCH_SIZE = 32
CLASS_MAP  = {"clean": 1, "polluted": 0}   # matches model: 0=bad, 1=good
IDX_MAP    = {0: "polluted", 1: "clean"}

# ── Transform ─────────────────────────────────────────────────────────────
TRANSFORM = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def load_model(model_path: str, device: torch.device):
    """Load trained EfficientNet-B0 from checkpoint."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    log.info(f"Loading model from {model_path}")
    ckpt = torch.load(model_path, map_location=device, weights_only=False)

    model = models.efficientnet_b0(weights=None)
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(model.classifier[1].in_features, 2),
    )
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()
    model = model.to(device)
    log.info(f"  Model loaded (epoch={ckpt.get('epoch','?')}, "
             f"internal_val_acc={ckpt.get('val_acc', '?'):.4f})")
    return model, ckpt.get('val_acc', None)


def load_dataset(data_dir: str):
    """Load images and labels from data_dir/class_name/ folders."""
    samples = []
    for cls_name, label in CLASS_MAP.items():
        folder = os.path.join(data_dir, cls_name)
        if not os.path.isdir(folder):
            log.warning(f"  Folder not found: {folder}")
            continue
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            for p in glob.glob(os.path.join(folder, ext)):
                samples.append((p, label, cls_name))
    return samples


def predict(model, samples, device, transform):
    """Run inference on all samples, return (preds, labels, probs)."""
    all_preds, all_labels, all_probs = [], [], []
    failed = 0
    t0 = time.time()

    for i, (path, label, cls_name) in enumerate(samples):
        try:
            img = Image.open(path).convert("RGB")
            tensor = transform(img).unsqueeze(0).to(device)
            with torch.no_grad():
                out = model(tensor)
                probs = torch.softmax(out, dim=1).cpu().numpy()[0]
                pred = int(np.argmax(probs))
            all_preds.append(pred)
            all_labels.append(label)
            all_probs.append(probs.tolist())
        except Exception as e:
            log.warning(f"  Skipped {os.path.basename(path)}: {e}")
            failed += 1

    elapsed = time.time() - t0
    log.info(f"  Inference done: {len(all_preds)} images in {elapsed:.1f}s "
             f"({failed} failed)")
    return all_preds, all_labels, all_probs


def compute_metrics(preds, labels, probs, class_names):
    """Compute accuracy, per-class precision/recall/F1, confusion matrix."""
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support,
        roc_auc_score, confusion_matrix, classification_report
    )
    preds  = np.array(preds)
    labels = np.array(labels)

    acc = float(accuracy_score(labels, preds))
    p, r, f1, sup = precision_recall_fscore_support(labels, preds,
                                                     average=None, zero_division=0)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        labels, preds, average='macro', zero_division=0)
    cm = confusion_matrix(labels, preds).tolist()
    report_str = classification_report(labels, preds,
                                       target_names=class_names, zero_division=0)
    try:
        auc = float(roc_auc_score(labels, [p[1] for p in probs]))
    except Exception:
        auc = float('nan')

    per_class = {}
    for i, cls in enumerate(class_names):
        per_class[cls] = {
            "precision": round(float(p[i]), 4),
            "recall":    round(float(r[i]), 4),
            "f1":        round(float(f1[i]), 4),
            "support":   int(sup[i]),
        }

    return {
        "accuracy": round(acc, 4),
        "roc_auc": round(auc, 4),
        "macro_precision": round(float(macro_p), 4),
        "macro_recall":    round(float(macro_r), 4),
        "macro_f1":        round(float(macro_f1), 4),
        "per_class": per_class,
        "confusion_matrix": cm,
        "classification_report": report_str,
    }


def main():
    print("=" * 65)
    print("AquaWatch — Indian Benchmark Evaluation")
    print("=" * 65)

    # Check dataset exists and has images
    if not os.path.isdir(DATA_DIR):
        print(f"\n  Dataset not found: {DATA_DIR}")
        print("  To use this script:")
        print("  1. Create: datasets/indian_validation_set/clean/")
        print("  2. Create: datasets/indian_validation_set/polluted/")
        print("  3. Add real Indian water body photos to each folder")
        print("  4. Re-run this script\n")
        return

    samples = load_dataset(DATA_DIR)
    if len(samples) == 0:
        print(f"\n  No images found in {DATA_DIR}")
        print("  Add .jpg/.jpeg/.png images to clean/ and polluted/ subfolders.\n")
        return

    # Count per class
    class_counts = {}
    for _, _, cls in samples:
        class_counts[cls] = class_counts.get(cls, 0) + 1
    log.info(f"Dataset: {len(samples)} images — {class_counts}")

    # Load model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Device: {device}")
    try:
        model, internal_val_acc = load_model(MODEL_PATH, device)
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}")
        print("  Run train_efficientnet_group_aware.py first.\n")
        return

    # Inference
    log.info(f"Running inference on {len(samples)} images...")
    preds, labels, probs = predict(model, samples, device, TRANSFORM)

    if len(preds) == 0:
        print("\n  No predictions made. Check image files.\n")
        return

    # Metrics
    log.info("Computing metrics...")
    class_names = ["polluted", "clean"]  # idx 0, 1
    try:
        metrics = compute_metrics(preds, labels, probs, class_names)
    except ImportError:
        print("  scikit-learn not installed: pip install scikit-learn")
        return

    # Build report
    report = {
        "dataset": DATA_DIR,
        "model": MODEL_PATH,
        "total_images": len(preds),
        "class_distribution": class_counts,
        "internal_val_accuracy_phash": round(float(internal_val_acc), 4)
                                        if internal_val_acc else None,
        "benchmark_metrics": metrics,
    }

    # Save
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print()
    print("=" * 65)
    print("EVALUATION RESULTS")
    print("=" * 65)
    print(f"  Dataset:                   Indian validation benchmark")
    print(f"  Total images evaluated:    {len(preds)}")
    print(f"  Class distribution:        {class_counts}")
    print()
    print(f"  Internal pHash val acc:    "
          f"{internal_val_acc*100:.2f}%" if internal_val_acc else "  Internal val acc: N/A")
    print(f"  Benchmark accuracy:        {metrics['accuracy']*100:.2f}%")
    acc_drop = (internal_val_acc - metrics['accuracy']) * 100 if internal_val_acc else None
    if acc_drop is not None:
        print(f"  Accuracy drop (OOD gap):   {acc_drop:.1f}pp")
        if acc_drop > 15:
            verdict = "SIGNIFICANT — model struggles on Indian water images"
        elif acc_drop > 5:
            verdict = "MODERATE — acceptable OOD degradation"
        else:
            verdict = "MINIMAL — model generalises well"
        print(f"  OOD Verdict:               {verdict}")
    print()
    print(f"  ROC-AUC:                   {metrics['roc_auc']:.4f}")
    print(f"  Macro F1:                  {metrics['macro_f1']:.4f}")
    print()
    print("  Per-class metrics:")
    for cls, m in metrics['per_class'].items():
        print(f"    {cls:<10}  P={m['precision']:.3f}  R={m['recall']:.3f}  "
              f"F1={m['f1']:.3f}  n={m['support']}")
    print()
    print("  Confusion Matrix (rows=actual, cols=predicted):")
    print(f"             polluted  clean")
    cm = metrics['confusion_matrix']
    for i, row in enumerate(cm):
        print(f"  {class_names[i]:<10}   {row[0]:>5}    {row[1]:>5}")
    print()
    print("  Classification Report:")
    print(metrics['classification_report'])
    print(f"  Full report saved: {REPORT}")
    print("=" * 65)


if __name__ == "__main__":
    main()
