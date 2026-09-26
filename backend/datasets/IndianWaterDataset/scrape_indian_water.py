import os
from pathlib import Path
from icrawler.builtin import GoogleImageCrawler

SEARCH_QUERIES = {
    "Bellandur_Lake_Bangalore": "Bellandur lake white foam Bangalore polluted water",
    "Yamuna_River_Delhi": "Yamuna river toxic foam Delhi pollution",
    "Hussain_Sagar_Hyderabad": "Hussain Sagar Hyderabad algae pollution",
    "Polluted_Lakes_India": "polluted lake garbage India water pollution",
    "Dirty_Rivers_India": "dirty river water floating waste India pollution",
    "Urban_Drains_India": "urban drain sewage foam water India pollution",
}

OUTPUT_DIR = Path("dataset_indian_raw")
IMAGES_PER_QUERY = 40

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    for folder, keyword in SEARCH_QUERIES.items():
        target = OUTPUT_DIR / folder
        target.mkdir(parents=True, exist_ok=True)
        print(f"\nDownloading up to {IMAGES_PER_QUERY} images for: {keyword}")
        crawler = GoogleImageCrawler(storage={"root_dir": str(target)})
        crawler.crawl(keyword=keyword, max_num=IMAGES_PER_QUERY)
    print("\nDone. Review the images manually before using them as a research test set.")
    print(f"Raw images are in: {OUTPUT_DIR.resolve()}")

if __name__ == "__main__":
    main()
