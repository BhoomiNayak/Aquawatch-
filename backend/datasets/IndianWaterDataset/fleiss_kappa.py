import pandas as pd
from statsmodels.stats.inter_rater import fleiss_kappa

CSV_FILE = "image_metadata.csv"

def main():
    df = pd.read_csv(CSV_FILE)
    cols = ["annotator_1", "annotator_2", "annotator_3"]

    # Values must be 0, 1, or 2. Blank rows are ignored.
    votes = df[cols].dropna()
    if votes.empty:
        print("No annotations found yet.")
        return

    try:
        votes = votes.astype(int)
    except ValueError:
        print("Annotations must contain only 0, 1, or 2.")
        return

    counts = []
    for _, row in votes.iterrows():
        counts.append([
            int((row == 0).sum()),
            int((row == 1).sum()),
            int((row == 2).sum())
        ])

    score = fleiss_kappa(counts, method="fleiss")
    print(f"Fleiss' Kappa: {score:.3f}")

if __name__ == "__main__":
    main()
