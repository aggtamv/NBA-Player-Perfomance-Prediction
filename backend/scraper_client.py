import os
import threading
from datetime import date

import pandas as pd
import requests

from backend.data_scraper import fetch_latest_nba_daily_boxscores, get_basketball_reference_data

_REFRESH_LOCK = threading.Lock()
_REFRESH_IN_PROGRESS = False


def _scraper_api_url():
    return os.getenv("SCRAPER_API_URL", "").rstrip("/")


def _save_daily_games(games, boxscores, game_date=None):
    game_date = game_date or date.today().isoformat()
    daily_dir = os.path.join("data", "daily_games")
    os.makedirs(daily_dir, exist_ok=True)

    games_df = pd.DataFrame(games)
    boxscores_df = pd.DataFrame(boxscores)

    if games_df.empty or boxscores_df.empty:
        return games_df, boxscores_df

    games_df.to_csv(
        os.path.join(daily_dir, f"games_{game_date}.csv"),
        index=False,
        encoding="utf-8-sig",
    )
    boxscores_df.to_csv(
        os.path.join(daily_dir, f"boxscores_{game_date}.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    return games_df, boxscores_df


def refresh_latest_daily_games():
    api_url = _scraper_api_url()

    if api_url:
        response = requests.post(f"{api_url}/scrape/basketball-reference", timeout=120)
        response.raise_for_status()
        payload = response.json()
        games = payload.get("games", [])
        boxscores = payload.get("boxscores", [])
        games_df, boxscores_df = _save_daily_games(games, boxscores)
        return games_df, boxscores_df

    try:
        games_df, boxscores_df, _ = fetch_latest_nba_daily_boxscores()
        if not games_df.empty and not boxscores_df.empty:
            return games_df, boxscores_df
    except Exception as exc:
        print(f"NBA API latest scraper failed; falling back to Basketball Reference: {exc}")

    games, boxscores = get_basketball_reference_data()
    return _save_daily_games(games, boxscores)


def refresh_latest_daily_games_if_needed(background=True):
    global _REFRESH_IN_PROGRESS

    with _REFRESH_LOCK:
        if _REFRESH_IN_PROGRESS:
            return False
        _REFRESH_IN_PROGRESS = True

    def run_refresh():
        global _REFRESH_IN_PROGRESS
        try:
            refresh_latest_daily_games()
        except Exception as exc:
            print(f"Failed to refresh NBA daily games through scraper client: {exc}")
        finally:
            with _REFRESH_LOCK:
                _REFRESH_IN_PROGRESS = False

    if background:
        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()
    else:
        run_refresh()

    return True
