from fastapi import FastAPI, HTTPException

from backend.data_scraper import fetch_nba_daily_boxscores, get_basketball_reference_data

app = FastAPI(title="NBA Scraper API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/scrape/basketball-reference")
def scrape_basketball_reference():
    games, boxscores = get_basketball_reference_data()
    if not games or not boxscores:
        raise HTTPException(status_code=502, detail="No NBA daily game data was scraped.")

    return {
        "status": "ok",
        "source": "basketball-reference",
        "games": games,
        "boxscores": boxscores,
    }


@app.post("/scrape/nba/{game_date}")
def scrape_nba_date(game_date: str):
    try:
        games, team_boxscores, player_boxscores = fetch_nba_daily_boxscores(game_date, save=False)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "status": "ok",
        "source": "nba",
        "game_date": game_date,
        "games": games.to_dict(orient="records"),
        "boxscores": team_boxscores.to_dict(orient="records"),
        "player_boxscores": player_boxscores.to_dict(orient="records"),
    }
