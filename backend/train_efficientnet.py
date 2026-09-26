"""
Train EfficientNet-B0 on EyeOnWater dataset (good/bad binary classification).

Dataset: backend/datasets/EyeOnWater_Dataset/
  - good/  (12,357 images - clean water)
  - bad/   (10,019 images - polluted water)

Model: EfficientNet-B0 (pre-trained on ImageNet, fine-tune last layers)
Output: models/efficientnet_water_quality.pt
Training time: ~15-20 min on RTX 4050

Usage:
    cd backend
    python train_efficientnet.py
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms, models
import time


# Config
DATASET_DIR = os.path.join(os.path.dirname(__file__), "datasets", "EyeOnWater_Dataset")
MODEL_SAVE_PATH = os.path.join(os.path.dirname(__file__), "models", "efficientnet_water_quality.pt")
BATCH_SIZE = 32
EPOCHS = 10
LEARNING_RATE = 0.001
IMG_SIZE = 224
TRAIN_SPLIT = 0.8
NUM_WORKERS = 4


def main():
    print("=" * 50)
    print("AquaWatch — Training EfficientNet-B0")
    print("=" * 50)
    print(f"Dataset: {DATASET_DIR}")
    print(f"Classes: good (clean), bad (polluted)")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Epochs: {EPOCHS}")
    print()

    # Check GPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print()

    # Data transforms
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

    # Load dataset
    print("Loading dataset...")
    full_dataset = datasets.ImageFolder(DATASET_DIR, transform=train_transform)
    print(f"Total images: {len(full_dataset)}")
    print(f"Classes: {full_dataset.classes}")
    print(f"Class mapping: {full_dataset.class_to_idx}")

    # Split into train/val
    train_size = int(TRAIN_SPLIT * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

    # Override val transform (no augmentation)
    val_dataset.dataset.transform = val_transform

    print(f"Train: {train_size} | Val: {val_size}")
    print()

    # Data loaders
    train_loader = DataLoader(
        train_dataset, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=NUM_WORKERS, pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=NUM_WORKERS, pin_memory=True
    )

    # Load pre-trained EfficientNet-B0
    print("Loading EfficientNet-B0 (pre-trained on ImageNet)...")
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)

    # Freeze early layers (only train the classifier head)
    for param in model.features.parameters():
        param.requires_grad = False

    # Unfreeze last 2 blocks for fine-tuning
    for param in model.features[-2:].parameters():
        param.requires_grad = True

    # Replace classifier head (1000 classes → 2 classes)
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(model.classifier[1].in_features, 2),
    )

    model = model.to(device)

    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=LEARNING_RATE,
    )
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

    # Training loop
    print("Starting training...")
    print("-" * 50)
    best_val_acc = 0.0
    start_time = time.time()

    for epoch in range(EPOCHS):
        # Train
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for batch_idx, (images, labels) in enumerate(train_loader):
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()

            if (batch_idx + 1) % 50 == 0:
                print(f"  Epoch {epoch+1}/{EPOCHS} | Batch {batch_idx+1}/{len(train_loader)} | Loss: {loss.item():.4f}")

        train_acc = train_correct / train_total

        # Validate
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item()
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()

        val_acc = val_correct / val_total
        elapsed = time.time() - start_time

        print(f"Epoch {epoch+1}/{EPOCHS} | Train Acc: {train_acc:.4f} | Val Acc: {val_acc:.4f} | Time: {elapsed:.0f}s")

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
            torch.save({
                'model_state_dict': model.state_dict(),
                'class_to_idx': full_dataset.class_to_idx,
                'val_acc': val_acc,
                'epoch': epoch + 1,
            }, MODEL_SAVE_PATH)
            print(f"  → Saved best model (val_acc: {val_acc:.4f})")

        scheduler.step()

    total_time = time.time() - start_time
    print()
    print("=" * 50)
    print(f"Training complete in {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Best validation accuracy: {best_val_acc:.4f} ({best_val_acc*100:.1f}%)")
    print(f"Model saved to: {MODEL_SAVE_PATH}")
    print("=" * 50)


if __name__ == "__main__":
    main()
