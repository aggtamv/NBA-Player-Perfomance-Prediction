"""Daily refresh: scrape the latest match (scores + boxscores), then re-export JSON.

Run from anywhere:  python static_page/refresh_daily.py

Used by the scheduled GitHub Action (.github/workflows/refresh-daily.yml), but also
runnable locally. Scrapes via backend.scraper_client.refresh_latest_daily_games()
(NBA API first, Selenium/basketball-reference fallback), then rebuilds data/*.json.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)   # import `backend`
sys.path.insert(0, HERE)   # import `export_data`
os.chdir(ROOT)             # scraper writes to relative data/ paths

from backend.scraper_client import refresh_latest_daily_games  # noqa: E402
import export_data  # noqa: E402


def main():
    print("[daily] Scraping latest NBA games...")
    try:
        games, boxscores = refresh_latest_daily_games()
        print(f"[daily]   scraped games={len(games)} boxscore_rows={len(boxscores)}")
    except Exception as exc:
        # Non-fatal: still re-export so the site rebuilds from whatever CSVs exist.
        print(f"[daily]   scrape failed (keeping existing data): {exc}")

    print("[daily] Re-exporting static JSON...")
    export_data.export_home()
    export_data.export_stats()
    export_data.export_prediction_players()
    print("[daily] Done.")


if __name__ == "__main__":
    main()
