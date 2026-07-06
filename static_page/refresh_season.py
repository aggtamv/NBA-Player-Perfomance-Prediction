"""Season refresh: scrape yearly player totals + league shooting averages, re-export JSON.

Run from anywhere:  python static_page/refresh_season.py

Used by the scheduled GitHub Action (.github/workflows/refresh-season.yml). Season-level
data barely changes, so this runs on a slow cadence (monthly / yearly). Both scrapes use
plain requests against basketball-reference. Then rebuilds data/*.json.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
os.chdir(ROOT)

from backend.data_scraper import get_csv, get_shooting_avg  # noqa: E402
import export_data  # noqa: E402


def main():
    print("[season] Scraping player season totals...")
    try:
        get_csv("players_data", "totals")
    except Exception as exc:
        print(f"[season]   totals scrape failed (keeping existing): {exc}")

    print("[season] Scraping league shooting averages...")
    try:
        get_shooting_avg()
    except Exception as exc:
        print(f"[season]   shooting scrape failed (keeping existing): {exc}")

    print("[season] Re-exporting static JSON...")
    export_data.export_home()
    export_data.export_stats()
    export_data.export_prediction_players()
    print("[season] Done.")


if __name__ == "__main__":
    main()
