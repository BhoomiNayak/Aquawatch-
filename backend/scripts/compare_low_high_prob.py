"""
compare_low_high_prob.py
========================
Label-boundary sanity check for the OOD analysis.

The binary task is Low(0)=clean vs Moderate/High(1,2)=polluted. If the
benchmark's "Low" images are actually mildly-polluted urban water that still
looks dirty, then EfficientNet's chance-level ROC-AUC (0.49) partly reflects a
subjective/near-unseparable label boundary, not only model failure.

This builds a contact-sheet montage of the 10 images with the LOWEST predicted
P(polluted) and the 10 with the HIGHEST, each captioned with image id, model
P(polluted), the human consensus label, and the water-body name — so we can
eyeball whether "Low" == visually clean.

Output:
    reports/low_high_prob_montage.png

Usage:
    cd backend
    python scripts/compare_low_high_prob.py
"""
import os
import csv

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(__file__))
IMG_DIR  = os.path.join(BASE, "datasets", "local_benchmark", "images")
PROB_CSV = os.path.join(BASE, "reports", "benchmark_probs.csv")
META_CSV = os.path.join(BASE, "datasets", "local_benchmark", "indian_validation_set.csv")
OUT_PNG  = os.path.join(BASE, "reports", "low_high_prob_montage.png")

THUMB = 260          # thumbnail edge (px)
CAP_H = 58           # caption strip height
COLS  = 5
PAD   = 8
LABEL_NAME = {0: "Low", 1: "Moderate", 2: "High"}


def load_meta():
    with open(META_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    fcol = "image_id" if "image_id" in rows[0] else "filename"
    return {r[fcol]: r for r in rows}


def load_probs():
    with open(PROB_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["p_polluted"] = float(r["p_polluted"])
        r["gt3"] = int(r["gt3"])
    return rows


def font(size):
    for fp in (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"):
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def make_cell(rec, meta, f_small, f_big):
    """One captioned thumbnail (THUMB x THUMB+CAP_H)."""
    cell = Image.new("RGB", (THUMB, THUMB + CAP_H), (245, 245, 245))
    path = os.path.join(IMG_DIR, rec["image_id"])
    try:
        im = Image.open(path).convert("RGB")
        im.thumbnail((THUMB, THUMB))
        ox = (THUMB - im.width) // 2
        oy = (THUMB - im.height) // 2
        cell.paste(im, (ox, oy))
    except Exception as e:
        d = ImageDraw.Draw(cell)
        d.text((6, 6), f"missing\n{e}", fill=(200, 0, 0), font=f_small)

    d = ImageDraw.Draw(cell)
    gt = rec["gt3"]
    # colour the caption strip by consensus label (green=Low, amber=Mod, red=High)
    strip_col = {0: (46, 139, 87), 1: (218, 165, 32), 2: (178, 34, 34)}[gt]
    d.rectangle([0, THUMB, THUMB, THUMB + CAP_H], fill=strip_col)
    name = (meta.get(rec["image_id"], {}).get("water_body_name", "") or "")[:26]
    d.text((6, THUMB + 4),
           f"{rec['image_id']}  P(pol)={rec['p_polluted']:.2f}",
           fill=(255, 255, 255), font=f_small)
    d.text((6, THUMB + 22),
           f"consensus: {LABEL_NAME[gt]}", fill=(255, 255, 255), font=f_big)
    d.text((6, THUMB + 40), name, fill=(255, 255, 255), font=f_small)
    return cell


def make_grid(records, meta, title, f_small, f_big, f_title):
    rows = (len(records) + COLS - 1) // COLS
    gw = COLS * THUMB + (COLS + 1) * PAD
    gh = 40 + rows * (THUMB + CAP_H) + (rows + 1) * PAD
    grid = Image.new("RGB", (gw, gh), (255, 255, 255))
    d = ImageDraw.Draw(grid)
    d.text((PAD, 8), title, fill=(0, 0, 0), font=f_title)
    for i, rec in enumerate(records):
        r, c = divmod(i, COLS)
        x = PAD + c * (THUMB + PAD)
        y = 40 + PAD + r * (THUMB + CAP_H + PAD)
        grid.paste(make_cell(rec, meta, f_small, f_big), (x, y))
    return grid


def main():
    meta = load_meta()
    probs = load_probs()
    probs.sort(key=lambda r: r["p_polluted"])
    lowest = probs[:10]
    highest = probs[-10:][::-1]

    f_small = font(13)
    f_big = font(16)
    f_title = font(22)

    g_low = make_grid(
        lowest, meta,
        "10 LOWEST P(polluted)  — model most confident these are CLEAN",
        f_small, f_big, f_title)
    g_high = make_grid(
        highest, meta,
        "10 HIGHEST P(polluted)  — model most confident these are POLLUTED",
        f_small, f_big, f_title)

    W = max(g_low.width, g_high.width)
    H = g_low.height + g_high.height + 3 * PAD
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    canvas.paste(g_low, (0, PAD))
    canvas.paste(g_high, (0, g_low.height + 2 * PAD))

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    canvas.save(OUT_PNG)

    # Text summary to stdout
    def summarize(name, recs):
        dist = {}
        for r in recs:
            dist[LABEL_NAME[r["gt3"]]] = dist.get(LABEL_NAME[r["gt3"]], 0) + 1
        print(f"\n{name}:")
        for r in recs:
            print(f"  {r['image_id']}  P(pol)={r['p_polluted']:.3f}  "
                  f"consensus={LABEL_NAME[r['gt3']]:<8}  "
                  f"{meta.get(r['image_id'],{}).get('water_body_name','')}")
        print(f"  -> consensus mix among these 10: {dist}")

    print("=" * 60)
    print("LABEL-BOUNDARY CHECK")
    print("=" * 60)
    summarize("LOWEST P(polluted) [model says CLEAN]", lowest)
    summarize("HIGHEST P(polluted) [model says POLLUTED]", highest)
    print(f"\nSaved montage: {OUT_PNG}")


if __name__ == "__main__":
    main()
