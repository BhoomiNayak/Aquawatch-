"""Quick verification of new thresholds on first 100 polluted images."""
import sys, os, glob
sys.path.insert(0, ".")

from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis

dataset_dir = "waterpollution"
files = glob.glob(os.path.join(dataset_dir, "*.jpg"))[:100]

levels = {"low": 0, "moderate": 0, "high": 0}
for f in files:
    try:
        with open(f, "rb") as fh:
            results = analyze_image(fh.read())
        risk = calculate_risk_from_analysis(results)
        levels[risk["risk_level"]] += 1
    except:
        pass

total = sum(levels.values())
print(f"Results on first 100 polluted images (NEW thresholds: LOW<15, MOD<35, HIGH>35):")
print(f"  LOW:      {levels['low']} ({levels['low']/total*100:.0f}%)")
print(f"  MODERATE: {levels['moderate']} ({levels['moderate']/total*100:.0f}%)")
print(f"  HIGH:     {levels['high']} ({levels['high']/total*100:.0f}%)")
print()
if levels["low"] / total < 0.3:
    print("  OK - Most polluted images now score MODERATE or HIGH")
else:
    print("  Still too many LOW - needs further tuning")
