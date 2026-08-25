"""
Train YOLOv8n-seg on river water quality dataset.
"""

import os

from ultralytics import YOLO


def main():
    dataset_path = os.path.join(
        os.path.dirname(__file__),
        "datasets",
        "data.yaml"
    )

    print("=" * 50)
    print("AquaWatch — Training YOLOv8n-seg")
    print("=" * 50)
    print(f"Dataset: {dataset_path}")
    print("Classes: clean_water, turbid_water, polluted_water")
    print()

    model = YOLO("yolov8n-seg.pt")

    model.train(
        data=dataset_path,
        epochs=50,
        imgsz=640,
        batch=16,
        device=0,
        project="runs/segment",
        name="aquawatch",
        patience=10,
        workers=4,
        exist_ok=True,
        plots=False,
    )

    print("\n" + "=" * 50)
    print("Training complete!")
    print("Best model: runs/segment/aquawatch/weights/best.pt")
    print("=" * 50)


if __name__ == "__main__":
    main()
