"""Export the Flask app's dynamic data into static JSON for the GitHub Pages build.

This is the *build step* for the static site. It reproduces (in a much simpler,
read-only form) what the Flask views + stats_repository do at request time, but
writes the results to static_page/data/*.json so the browser can load them
without a server or database.

Run from the project root:

    python static_page/export_data.py

Data sources (all local CSV, no network / no DB):
    data/shooting/shooting_avg.csv
    data/adj_shooting/adj_shooting_avg.csv
    data/gold/player_recent_form/csv/data.csv
    data/totals/players_data_<latest>.csv
    data/daily_games/games_<latest>.csv  + boxscores_<latest>.csv
"""

import glob
import json
import os
import re

import numpy as np
import pandas as pd

# --- Paths -----------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

# --- Team logo mapping (mirrors backend/data_scraper.py) -------------------
TEAM_LOGOS = {
    "Atlanta Hawks": "Atlanta.svg", "Boston Celtics": "Boston.svg",
    "Brooklyn Nets": "Brooklyn.svg", "Charlotte Hornets": "charlotte-hornets.svg",
    "Chicago Bulls": "Chicago.svg", "Cleveland Cavaliers": "Cleveland.svg",
    "Dallas Mavericks": "Dallas.svg", "Denver Nuggets": "Denver.svg",
    "Detroit Pistons": "Detroit.svg", "Golden State Warriors": "Golden_State.svg",
    "Houston Rockets": "Houston.svg", "Indiana Pacers": "Indiana.svg",
    "LA Clippers": "LA_Clippers.svg", "Los Angeles Clippers": "LA_Clippers.svg",
    "Los Angeles Lakers": "LA_Lakers.svg", "Memphis Grizzlies": "Memphis.svg",
    "Miami Heat": "Miami.svg", "Milwaukee Bucks": "Milwaukee.svg",
    "Minnesota Timberwolves": "Minnesota.svg", "New Orleans Pelicans": "New_Orleans.svg",
    "New York Knicks": "New York.svg", "Oklahoma City Thunder": "Oklahoma_City.svg",
    "Orlando Magic": "Orlando.svg", "Philadelphia 76ers": "philidephia-ers.svg",
    "Phoenix Suns": "Phoenix.svg", "Portland Trail Blazers": "Portland.svg",
    "Sacramento Kings": "Sacramento.svg", "San Antonio Spurs": "San_Antonio.svg",
    "Toronto Raptors": "toronto-raptors.svg", "Utah Jazz": "Utah.svg",
    "Washington Wizards": "Washington.svg",
}
TEAM_LOGO_ALIASES = {
    "Atlanta": "Atlanta Hawks", "Boston": "Boston Celtics", "Brooklyn": "Brooklyn Nets",
    "Charlotte": "Charlotte Hornets", "Chicago": "Chicago Bulls", "Cleveland": "Cleveland Cavaliers",
    "Dallas": "Dallas Mavericks", "Denver": "Denver Nuggets", "Detroit": "Detroit Pistons",
    "Golden State": "Golden State Warriors", "Houston": "Houston Rockets", "Indiana": "Indiana Pacers",
    "LA Clippers": "LA Clippers", "L.A. Clippers": "LA Clippers", "LA Lakers": "Los Angeles Lakers",
    "L.A. Lakers": "Los Angeles Lakers", "Los Angeles Lakers": "Los Angeles Lakers",
    "Memphis": "Memphis Grizzlies", "Miami": "Miami Heat", "Milwaukee": "Milwaukee Bucks",
    "Minnesota": "Minnesota Timberwolves", "New Orleans": "New Orleans Pelicans",
    "New York": "New York Knicks", "Oklahoma City": "Oklahoma City Thunder",
    "Orlando": "Orlando Magic", "Philadelphia": "Philadelphia 76ers", "Phoenix": "Phoenix Suns",
    "Portland": "Portland Trail Blazers", "Sacramento": "Sacramento Kings",
    "San Antonio": "San Antonio Spurs", "Toronto": "Toronto Raptors", "Utah": "Utah Jazz",
    "Washington": "Washington Wizards",
}


def get_team_logo(team_name):
    full = TEAM_LOGO_ALIASES.get(team_name, team_name)
    return TEAM_LOGOS.get(full, "nba.svg")


# The 20 features the model expects (mirrors stats_repository.PREDICTION_INFERENCE_COLUMNS)
PREDICTION_INFERENCE_COLUMNS = [
    "numMinutes", "points", "assists", "blocks", "steals",
    "fieldGoalsAttempted", "fieldGoalsMade", "fieldGoalsPercentage",
    "threePointersAttempted", "threePointersMade", "threePointersPercentage",
    "freeThrowsAttempted", "freeThrowsMade", "freeThrowsPercentage",
    "reboundsDefensive", "reboundsOffensive", "reboundsTotal",
    "foulsPersonal", "turnovers", "plusMinusPoints",
]


def _clean(obj):
    """Recursively replace NaN/inf with None so the JSON is valid."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float):
        return None if (np.isnan(obj) or np.isinf(obj)) else obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        return None if (np.isnan(f) or np.isinf(f)) else f
    return obj


def write_json(name, payload):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(payload), f, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {name} ({os.path.getsize(path) // 1024} KB)")


def latest_dated_file(folder, prefix):
    """Return the path with the most recent YYYY-MM-DD in its name."""
    pattern = os.path.join(DATA, folder, f"{prefix}_*.csv")
    files = glob.glob(pattern)
    dated = []
    for fp in files:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(fp))
        if m:
            dated.append((m.group(1), fp))
    if not dated:
        return None, None
    dated.sort()
    return dated[-1]  # (date, path)


# ===========================================================================
# 1. HOME  (daily games + latest-season totals)
# ===========================================================================
def export_home():
    game_date, games_path = latest_dated_file("daily_games", "games")
    _, box_path = latest_dated_file("daily_games", "boxscores")

    games_list, boxscores_list = [], []
    if games_path and os.path.exists(games_path):
        games = pd.read_csv(games_path, encoding="utf-8-sig")
        games.columns = [str(c).strip() for c in games.columns]
        if "score" in games.columns:
            games["score"] = pd.to_numeric(games["score"], errors="coerce").fillna(0).astype(int)
        if "team_logo" not in games.columns and "team" in games.columns:
            games["team_logo"] = games["team"].map(get_team_logo)
        else:
            games["team_logo"] = games.apply(
                lambda r: r.get("team_logo") if pd.notna(r.get("team_logo")) and str(r.get("team_logo")).strip()
                else get_team_logo(r.get("team")), axis=1)
        games_list = games.to_dict(orient="records")

    if box_path and os.path.exists(box_path):
        box = pd.read_csv(box_path, encoding="utf-8-sig")
        box.columns = [str(c).strip() for c in box.columns]
        q_cols = [c for c in ["Q1", "Q2", "Q3", "Q4", "OT", "2OT", "3OT"] if c in box.columns]
        for c in q_cols:
            box[c] = pd.to_numeric(box[c], errors="coerce").fillna(0).astype(int)
        boxscores_list = box.to_dict(orient="records")

    # Latest-season totals table
    totals_files = sorted(glob.glob(os.path.join(DATA, "totals", "players_data_*.csv")))
    totals_list, top_scorer, team_count = [], None, 0
    if totals_files:
        totals = pd.read_csv(totals_files[-1], encoding="utf-8-sig")
        totals.columns = [str(c).strip() for c in totals.columns]
        if "Player" in totals.columns:
            totals = totals[totals["Player"] != "League Average"]
        totals = totals.drop(columns=["Awards", "source_file", "season"], errors="ignore")
        if "PTS" in totals.columns:
            idx = pd.to_numeric(totals["PTS"], errors="coerce").idxmax()
            top_scorer = totals.loc[idx].to_dict()
        if "Team" in totals.columns:
            team_count = int(totals["Team"].nunique())
        totals_list = totals.to_dict(orient="records")

    metrics = {
        "player_count": len(totals_list),
        "game_count": len(games_list) // 2,
        "team_count": team_count,
        "top_scorer": top_scorer,
    }
    write_json("home.json", {
        "latest_game_date": game_date,
        "games": games_list,
        "boxscores": boxscores_list,
        "totals": totals_list,
        "metrics": metrics,
    })


# ===========================================================================
# 2. STATS  (shooting trends + adjusted efficiency + gold recent form)
# ===========================================================================
def _fmt_table_value(col, v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if col == "Year":
        return str(int(v))
    if isinstance(v, (int, float, np.integer, np.floating)):
        fv = float(v)
        if abs(fv) <= 2:
            return f"{fv * 100:.1f}%"
        return f"{fv:.2f}"
    return v


def _fmt_table(df):
    return [{c: _fmt_table_value(c, v) for c, v in rec.items()} for rec in df.to_dict(orient="records")]


def _pct(v):
    return None if v is None or pd.isna(v) else float(v) * 100


def export_stats():
    shooting = pd.read_csv(os.path.join(DATA, "shooting", "shooting_avg.csv")).sort_values("Year")
    adj = pd.read_csv(os.path.join(DATA, "adj_shooting", "adj_shooting_avg.csv")).sort_values("Year")
    shooting = shooting.drop(columns=["source_file"], errors="ignore")
    adj = adj.drop(columns=["source_file"], errors="ignore")

    raw_opts = [m for m in ["FGA_0_3", "FGA_3_10", "FGA_10_16", "FGA_16_3P", "FGA_3P",
                            "FG_0_3", "FG_3P", "TS%", "eFG%", "FTr", "3PAr"] if m in shooting.columns]
    adj_opts = [m for m in ["FG%", "2P%", "3P%", "eFG%", "TS%", "FTr", "3PAr",
                           "FG+", "2P+", "3P+", "eFG+", "TS+"] if m in adj.columns]
    raw_default = [m for m in ["FGA_0_3", "FGA_3P", "FG_0_3", "FG_3P"] if m in raw_opts]
    adj_default = [m for m in ["FG%", "3P%", "eFG%", "TS%", "FTr", "3PAr"] if m in adj_opts]

    latest_adj = adj.iloc[-1].to_dict()
    prev_adj = adj.iloc[-2].to_dict() if len(adj) > 1 else {}
    first_adj = adj.iloc[0].to_dict()
    latest_year = int(latest_adj.get("Year", 0))
    first_year = int(first_adj.get("Year", 0))

    def delta(key):
        return _pct(latest_adj.get(key, 0) - prev_adj.get(key, latest_adj.get(key, 0)))

    metrics = {
        "year_range": f"{first_year}-{latest_year}",
        "latest_year": latest_year,
        "latest_ts": _pct(latest_adj.get("TS%")), "latest_ts_delta": delta("TS%"),
        "latest_efg": _pct(latest_adj.get("eFG%")), "latest_efg_delta": delta("eFG%"),
        "latest_3par": _pct(latest_adj.get("3PAr")), "latest_3par_delta": delta("3PAr"),
        "three_point_rate_change": _pct(latest_adj.get("3PAr", 0) - first_adj.get("3PAr", 0)),
    }

    def chart_rows(df, cols):
        return df[["Year"] + cols].where(pd.notna(df[["Year"] + cols]), None).to_dict(orient="records")

    payload = {
        "shooting_chart": chart_rows(shooting, raw_opts),
        "adjusted_chart": chart_rows(adj, adj_opts),
        "shooting_columns": shooting.columns.tolist(),
        "adjusted_columns": adj.columns.tolist(),
        "shooting_table": _fmt_table(shooting.tail(10).sort_values("Year", ascending=False)),
        "adjusted_table": _fmt_table(adj.tail(10).sort_values("Year", ascending=False)),
        "raw_metric_options": raw_opts, "adjusted_metric_options": adj_opts,
        "raw_default_metrics": raw_default, "adjusted_default_metrics": adj_default,
        "metrics": metrics,
    }
    payload.update(export_recent_form())
    write_json("stats.json", payload)


def export_recent_form(limit=12):
    """Top-N players by prior-10-game scoring (mirrors get_player_recent_form_overview)."""
    path = os.path.join(DATA, "gold", "player_recent_form", "csv", "data.csv")
    if not os.path.exists(path):
        return {"recent_form_chart": [], "recent_form_table": [], "recent_form_columns": [], "metrics_extra": {}}

    df = pd.read_csv(path)
    df = df[df["player"].notna() & df["gameDate"].notna()]
    df["complete_games_in_prior_window"] = pd.to_numeric(df["complete_games_in_prior_window"], errors="coerce")
    df = df[df["complete_games_in_prior_window"] >= 10]
    df["gameDate"] = pd.to_datetime(df["gameDate"], errors="coerce")

    num_cols = ["last_10_points_avg", "last_10_assists_avg", "last_10_reboundsTotal_avg",
                "last_10_threePointersPercentage_avg", "last_10_plusMinusPoints_avg"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    latest = (df.sort_values(["player", "gameDate"], ascending=[True, False])
                .drop_duplicates("player", keep="first"))
    top = (latest.dropna(subset=["last_10_points_avg"])
                 .sort_values("last_10_points_avg", ascending=False)
                 .head(limit)).copy()
    top["team_logo"] = top["team"].map(get_team_logo)

    chart_cols = ["player", "team", "team_logo", "last_10_points_avg",
                  "last_10_assists_avg", "last_10_reboundsTotal_avg"]
    chart = top[chart_cols].where(pd.notna(top[chart_cols]), None).to_dict(orient="records")

    table_cols = ["player", "team", "opponent", "gameDate", "last_10_points_avg",
                  "last_10_assists_avg", "last_10_reboundsTotal_avg",
                  "last_10_threePointersPercentage_avg", "last_10_plusMinusPoints_avg"]
    table_cols = [c for c in table_cols if c in top.columns]

    def fmt_rf(col, v):
        if v is None or pd.isna(v):
            return "-"
        if col == "gameDate":
            return pd.to_datetime(v).strftime("%Y-%m-%d")
        if col == "last_10_threePointersPercentage_avg":
            return f"{float(v) * 100:.1f}%"
        if col.startswith("last_10_"):
            return f"{float(v):.1f}"
        return v

    table = [{c: fmt_rf(c, rec[c]) for c in table_cols} for rec in top[table_cols].to_dict(orient="records")]

    stats_extra = {
        "gold_players": int(top["player"].nunique()) if not top.empty else 0,
        "gold_top_player": top.iloc[0]["player"] if not top.empty else None,
        "gold_top_points": float(top.iloc[0]["last_10_points_avg"]) if not top.empty else None,
    }
    return {
        "recent_form_chart": chart,
        "recent_form_table": table,
        "recent_form_columns": table_cols,
        "metrics_extra": stats_extra,
    }


# ===========================================================================
# 3. PREDICTION  (per-player last-10-game feature matrices for the HF model)
# ===========================================================================
def export_prediction_players(min_games=10):
    """For every player with >=10 complete recent games, store the most recent
    10x20 feature matrix the model expects. Mirrors
    get_recent_prediction_stats_for_player -> the CSV sent to /predict_from_csv.
    """
    path = os.path.join(DATA, "gold", "player_recent_form", "csv", "data.csv")
    if not os.path.exists(path):
        write_json("players_predict.json", {"columns": PREDICTION_INFERENCE_COLUMNS, "players": {}})
        return

    df = pd.read_csv(path)
    df["gameDate"] = pd.to_datetime(df.get("gameDate"), errors="coerce")
    if "gameId" not in df.columns:
        df["gameId"] = 0
    for c in PREDICTION_INFERENCE_COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")

    players = {}
    for name, group in df.groupby("player"):
        if not isinstance(name, str) or not name.strip():
            continue
        recent = group.sort_values(["gameDate", "gameId"], ascending=[False, False])
        complete = recent.dropna(subset=PREDICTION_INFERENCE_COLUMNS).head(min_games)
        if len(complete) < min_games:
            continue
        matrix = complete[PREDICTION_INFERENCE_COLUMNS].round(4).values.tolist()
        players[name] = matrix

    write_json("players_predict.json", {
        "columns": PREDICTION_INFERENCE_COLUMNS,
        "players": players,
    })
    # Lightweight name list for the autocomplete (avoids parsing the big file just to search)
    write_json("player_names.json", {"players": sorted(players.keys())})


if __name__ == "__main__":
    print("Exporting static data ->", OUT)
    export_home()
    export_stats()
    export_prediction_players()
    print("Done.")
