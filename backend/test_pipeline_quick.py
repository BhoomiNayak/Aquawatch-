"""Quick test: submit images to live backend and verify pipeline."""
import requests

API = "http://localhost:8002/api/v1"

print("Testing full pipeline on live backend...")
print("=" * 60)

for fname in ['algae.jpg', 'Maintain-A-Healthy-Pond.jpg', 'turbid1.jpg']:
    try:
        files = {'image': (fname, open(f'test_images/{fname}', 'rb'), 'image/jpeg')}
        data = {'latitude': 13.05, 'longitude': 77.59, 'contamination_type': 'others'}
        resp = requests.post(f"{API}/analyze-water", files=files, data=data, timeout=60)
        if resp.status_code == 201:
            r = resp.json()
            risk = r['risk']
            yolo = r.get('yolo_detection', {})
            eff = r.get('efficientnet', {})
            print(f"{fname}")
            print(f"  Score: {risk['composite_score']}  Level: {risk['risk_level'].upper()}")
            print(f"  YOLO: {yolo.get('prediction', 'N/A')} ({yolo.get('confidence', 0)*100:.0f}%)")
            print(f"  EfficientNet: {eff.get('prediction', 'N/A')} ({eff.get('confidence', 0)*100:.0f}%)")
            print()
        else:
            print(f"{fname}: ERROR {resp.status_code}")
            print(f"  {resp.text[:200]}")
            print()
    except Exception as e:
        print(f"{fname}: EXCEPTION - {e}")
        print()

print("=" * 60)
print("Done. If all 3 returned scores, pipeline is working.")
