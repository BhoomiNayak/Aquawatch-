"""Run full pipeline on try_dataset images and show detailed breakdown."""
import os
import sys
import glob

sys.path.insert(0, ".")
os.environ["MPLCONFIGDIR"] = "C:/tmp/mpl"

from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis
from app.services.yolo_detector import detect_water_quality_local

# EfficientNet
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import io

MODEL_PATH = "models/efficientnet_water_quality.pt"


def load_eff():
    if not os.path.exists(MODEL_PATH):
        return None, None
    ckpt = torch.load(MODEL_PATH, map_location="cuda" if torch.cuda.is_available() else "cpu", weights_only=False)
    model = models.efficientnet_b0(weights=None)
    model.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(model.classifier[1].in_features, 2))
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval().to("cuda" if torch.cuda.is_available() else "cpu")
    idx_to_class = {v: k for k, v in ckpt['class_to_idx'].items()}
    return model, idx_to_class


def predict_eff(model, idx_to_class, image_bytes):
    if model is None:
        return {"prediction": "N/A", "confidence": 0}
    device = next(model.parameters()).device
    t = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    x = t(img).unsqueeze(0).to(device)
    with torch.no_grad():
        out = model(x)
        probs = torch.softmax(out, 1)
        conf, pred = torch.max(probs, 1)
    return {"prediction": idx_to_class[pred.item()], "confidence": round(conf.item(), 2)}


def main():
    model, idx_to_class = load_eff()

    folder = "datasets/try_dataset"
    files = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        files.extend(glob.glob(os.path.join(folder, ext)))

    print("=" * 100)
    print("TRY_DATASET — Full Pipeline Test")
    print("=" * 100)

    for f in sorted(files):
        name = os.path.basename(f)[:35]
        with open(f, "rb") as fh:
            img_bytes = fh.read()

        cv = analyze_image(img_bytes)
        risk = calculate_risk_from_analysis(cv)
        yolo = detect_water_quality_local(img_bytes)
        eff = predict_eff(model, idx_to_class, img_bytes)

        print(f"\n{name}")
        print(f"  CV score: {risk['composite_score']}  ({risk['risk_level']})")
        print(f"  Forel-Ule: {cv['forel_ule']['fu_index']} ({cv['forel_ule']['fu_color_name']})")
        print(f"  Algae: {cv['algae']['algae_percentage']}%  |  Foam: {cv['foam']['foam_coverage_percentage']}%  |  Clarity: {cv['turbidity']['turbidity_score']}")
        print(f"  Oil sheen: {cv['oil_sheen']['oil_coverage_percentage']}% ({cv['oil_sheen']['confidence']})  |  Color abn: {cv['color_abnormality']['color_abnormality_score']}  |  Debris: {cv['surface_debris']['contour_density']}")
        print(f"  YOLO: {yolo['prediction']} ({yolo['confidence']*100:.0f}%)")
        print(f"  EfficientNet: {eff['prediction']} ({eff['confidence']*100:.0f}%)")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
