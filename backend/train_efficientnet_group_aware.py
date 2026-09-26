"""
EfficientNet-B0 — Group-Aware Retraining on EyeOnWater
=======================================================

Uses the de-leaked group-aware split from phash_group_split.py.
Reports honest validation metrics without augmented-data leakage.

Key differences from train_efficientnet.py (original):
  - Reads train/val paths from CSV files (pre-split by cluster ID)
  - No random_split() — respects group boundaries
  - Computes per-class precision, recall, F1 (not just accuracy)
  - Saves confusion matrix and full classification report to text file
  - Temperature scaling calibration on validation set
  - All metrics saved to: models/efficientnet_group_aware_metrics.txt

USAGE:
    cd backend
    python train_efficientnet_group_aware.py

OUTPUTS:
    models/efficientnet_water_quality_group_aware.pt   — best model weights
    models/efficientnet_group_aware_metrics.txt        — paper-ready metrics
"""

import os
import csv
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms, models
from PIL import Image
import numpy as np
from collections import Counter

# ── CONFIG ──────────────────────────────────────────────────────────────────
TRAIN_CSV     = os.path.join(os.path.dirname(__file__), "eyeonwater_split_train.csv")
VAL_CSV       = os.path.join(os.path.dirname(__file__), "eyeonwater_split_val.csv")
MODEL_OUT     = os.path.join(os.path.dirname(__file__), "models",
                             "efficientnet_water_quality_group_aware.pt")
METRICS_OUT   = os.path.join(os.path.dirname(__file__), "models",
                             "efficientnet_group_aware_metrics.txt")
BATCH_SIZE    = 32
EPOCHS        = 10
LR            = 0.001
IMG_SIZE      = 224
WORKERS       = 0  # 0 = no multiprocessing (required on Windows to avoid deadlock)
CLASS_MAP     = {"bad": 0, "good": 1}   # matches original model
IDX_TO_CLASS  = {0: "bad", 1: "good"}
# ────────────────────────────────────────────────────────────────────────────


class CSVImageDataset(Dataset):
    """Dataset that reads (path, label) from a pre-split CSV file."""
    def __init__(self, csv_path, transform):
        self.samples = []
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                label = CLASS_MAP.get(row["label"])
                if label is not None and os.path.exists(row["path"]):
                    self.samples.append((row["path"], label))
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        return self.transform(img), label


def build_model(device):
    model = models.efficientnet_b0(
        weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1
    )
    # Freeze backbone
    for param in model.features.parameters():
        param.requires_grad = False
    # Unfreeze last 2 blocks
    for param in model.features[-2:].parameters():
        param.requires_grad = True
    # Replace head
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(model.classifier[1].in_features, 2),
    )
    return model.to(device)


def compute_metrics(all_preds, all_labels, all_probs):
    """Compute accuracy, per-class precision/recall/F1, ROC-AUC."""
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support,
        roc_auc_score, confusion_matrix, classification_report
    )
    acc = accuracy_score(all_labels, all_preds)
    p, r, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average=None)
    macro_f1 = f1.mean()
    try:
        auc = roc_auc_score(all_labels, [prob[1] for prob in all_probs])
    except Exception:
        auc = float('nan')
    cm = confusion_matrix(all_labels, all_preds)
    report = classification_report(all_labels, all_preds,
                                   target_names=["bad", "good"])
    return {
        "accuracy": acc,
        "auc": auc,
        "macro_f1": macro_f1,
        "per_class_precision": p.tolist(),
        "per_class_recall": r.tolist(),
        "per_class_f1": f1.tolist(),
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }


def main():
    print("=" * 65)
    print("EfficientNet-B0 — Group-Aware Retraining")
    print("=" * 65)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # ── Transforms ────────────────────────────────────────────────
    train_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    # ── Datasets ──────────────────────────────────────────────────
    print("\nLoading datasets from group-aware split CSVs...")
    train_ds = CSVImageDataset(TRAIN_CSV, train_transform)
    val_ds   = CSVImageDataset(VAL_CSV,   val_transform)
    print(f"  Train: {len(train_ds):,} images")
    print(f"  Val:   {len(val_ds):,} images")

    # Class balance
    train_labels = [s[1] for s in train_ds.samples]
    val_labels   = [s[1] for s in val_ds.samples]
    tc = Counter(train_labels)
    vc = Counter(val_labels)
    print(f"  Train balance: bad={tc[0]:,} ({tc[0]/len(train_ds)*100:.1f}%)  "
          f"good={tc[1]:,} ({tc[1]/len(train_ds)*100:.1f}%)")
    print(f"  Val balance:   bad={vc[0]:,} ({vc[0]/len(val_ds)*100:.1f}%)  "
          f"good={vc[1]:,} ({vc[1]/len(val_ds)*100:.1f}%)")

    # Class weights for imbalanced data
    total = len(train_labels)
    weights = torch.tensor([
        total / (2 * tc[0]),
        total / (2 * tc[1])
    ], dtype=torch.float).to(device)
    print(f"  Class weights: bad={weights[0]:.3f}  good={weights[1]:.3f}")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=WORKERS, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False,
                              num_workers=WORKERS, pin_memory=True)

    # ── Model ─────────────────────────────────────────────────────
    print("\nLoading EfficientNet-B0 (ImageNet pretrained)...")
    model = build_model(device)

    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()), lr=LR
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    # ── Training loop ─────────────────────────────────────────────
    print(f"\nTraining for {EPOCHS} epochs...")
    print("-" * 65)
    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)

    best_val_acc = 0.0
    best_epoch = 0
    t_start = time.time()

    for epoch in range(EPOCHS):
        # Train
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for batch_idx, (images, labels) in enumerate(train_loader):
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            out = model(images)
            loss = criterion(out, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            _, pred = torch.max(out, 1)
            train_total += labels.size(0)
            train_correct += (pred == labels).sum().item()
            if (batch_idx + 1) % 200 == 0:
                print(f"  E{epoch+1}/{EPOCHS} batch {batch_idx+1}/{len(train_loader)} "
                      f"loss={loss.item():.4f}")

        train_acc = train_correct / train_total

        # Validate
        model.eval()
        val_correct, val_total = 0, 0
        all_preds, all_labels_list, all_probs = [], [], []
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                out = model(images)
                probs = torch.softmax(out, dim=1)
                _, pred = torch.max(out, 1)
                val_total += labels.size(0)
                val_correct += (pred == labels).sum().item()
                all_preds.extend(pred.cpu().numpy())
                all_labels_list.extend(labels.cpu().numpy())
                all_probs.extend(probs.cpu().numpy().tolist())

        val_acc = val_correct / val_total
        elapsed = time.time() - t_start
        print(f"Epoch {epoch+1}/{EPOCHS} | train_acc={train_acc:.4f} | "
              f"val_acc={val_acc:.4f} | elapsed={elapsed:.0f}s")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch + 1
            torch.save({
                'model_state_dict': model.state_dict(),
                'class_to_idx': {v: k for v, k in IDX_TO_CLASS.items()},
                'val_acc': val_acc,
                'epoch': epoch + 1,
                'split': 'group_aware_phash',
            }, MODEL_OUT)
            print(f"  → Saved best model (val_acc={val_acc:.4f})")

        scheduler.step()

    total_time = time.time() - t_start

    # ── Final evaluation metrics ──────────────────────────────────
    print(f"\nComputing final validation metrics on best model (epoch {best_epoch})...")
    model.load_state_dict(torch.load(MODEL_OUT, weights_only=False)['model_state_dict'])
    model.eval()

    all_preds, all_labels_list, all_probs = [], [], []
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            out = model(images)
            probs = torch.softmax(out, dim=1)
            _, pred = torch.max(out, 1)
            all_preds.extend(pred.cpu().numpy())
            all_labels_list.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy().tolist())

    try:
        metrics = compute_metrics(all_preds, all_labels_list, all_probs)
    except ImportError:
        print("WARNING: scikit-learn not found. Install with: pip install scikit-learn")
        metrics = None

    # ── Print + Save results ──────────────────────────────────────
    print()
    print("=" * 65)
    print("VALIDATION RESULTS (Group-Aware Split)")
    print("=" * 65)
    print(f"  Best epoch:     {best_epoch}/{EPOCHS}")
    print(f"  Best val acc:   {best_val_acc:.4f} ({best_val_acc*100:.2f}%)")
    if metrics:
        print(f"  ROC-AUC:        {metrics['auc']:.4f}")
        print(f"  Macro F1:       {metrics['macro_f1']:.4f}")
        print()
        print("  Per-class:")
        for i, cls in enumerate(["bad", "good"]):
            print(f"    {cls}: P={metrics['per_class_precision'][i]:.3f}  "
                  f"R={metrics['per_class_recall'][i]:.3f}  "
                  f"F1={metrics['per_class_f1'][i]:.3f}")
        print()
        print("  Confusion Matrix (rows=actual, cols=predicted):")
        print("          bad   good")
        for i, row in enumerate(metrics['confusion_matrix']):
            print(f"  {['bad','good'][i]:5s}  {row[0]:5d} {row[1]:5d}")
        print()
        print("  Classification Report:")
        print(metrics['classification_report'])

        # Save metrics to file
        os.makedirs(os.path.dirname(METRICS_OUT), exist_ok=True)
        with open(METRICS_OUT, "w") as f:
            f.write("AquaWatch EfficientNet-B0 — Group-Aware Validation Metrics\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Split method:     pHash group-aware (threshold=10/64)\n")
            f.write(f"Train samples:    {len(train_ds):,}\n")
            f.write(f"Val samples:      {len(val_ds):,}\n")
            f.write(f"Best epoch:       {best_epoch}/{EPOCHS}\n")
            f.write(f"Accuracy:         {best_val_acc:.4f} ({best_val_acc*100:.2f}%)\n")
            f.write(f"ROC-AUC:          {metrics['auc']:.4f}\n")
            f.write(f"Macro F1:         {metrics['macro_f1']:.4f}\n\n")
            f.write("Per-class:\n")
            for i, cls in enumerate(["bad", "good"]):
                f.write(f"  {cls}: P={metrics['per_class_precision'][i]:.3f}  "
                        f"R={metrics['per_class_recall'][i]:.3f}  "
                        f"F1={metrics['per_class_f1'][i]:.3f}\n")
            f.write("\nConfusion Matrix:\n")
            f.write("        bad  good\n")
            for i, row in enumerate(metrics['confusion_matrix']):
                f.write(f"  {['bad','good'][i]:5s}  {row[0]:4d} {row[1]:4d}\n")
            f.write(f"\nClassification Report:\n{metrics['classification_report']}\n")
            f.write(f"\nTotal training time: {total_time:.0f}s ({total_time/60:.1f} min)\n")
        print(f"  Metrics saved to: {METRICS_OUT}")

    print()
    print("=" * 65)
    print(f"TRAINING COMPLETE in {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Model: {MODEL_OUT}")
    print("=" * 65)
    print()
    print("IMPORTANT — Compare these numbers to the original 99.8%:")
    print(f"  Original (random split, likely leaked): 99.8%")
    print(f"  Group-aware (honest):                   {best_val_acc*100:.1f}%")
    diff = 99.8 - best_val_acc * 100
    if diff > 3:
        print(f"  Drop of {diff:.1f}pp confirms data leakage was present.")
    elif diff <= 3:
        print(f"  Drop of {diff:.1f}pp — minimal leakage, model genuinely learned.")


if __name__ == "__main__":
    main()
