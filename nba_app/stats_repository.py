import pandas as pd
from sqlalchemy import inspect, text

from backend.data_scraper import create_sample, get_csv, get_shooting_avg
from .data_importer import (
    import_all_data_to_sqlite,
    import_daily_games_to_sqlite,
    import_gold_recent_form_to_sqlite,
    import_season_dataset,
)
from .models import db

PLAYER_TOTALS_TABLE = "player_totals"
SHOOTING_AVG_TABLE = "shooting_avg"
ADJ_SHOOTING_AVG_TABLE = "adj_shooting_avg"
PREDICTION_SAMPLE_TABLE = "sample_player_statistics"
PLAYER_RECENT_FORM_TABLE = "player_recent_form"
DAILY_GAMES_TABLE = "daily_games"
DAILY_TEAM_BOXSCORES_TABLE = "daily_team_boxscores"

PREDICTION_INFERENCE_COLUMNS = [
    'numMinutes', 'points', 'assists', 'blocks', 'steals',
    'fieldGoalsAttempted', 'fieldGoalsMade', 'fieldGoalsPercentage',
    'threePointersAttempted', 'threePointersMade', 'threePointersPercentage',
    'freeThrowsAttempted', 'freeThrowsMade', 'freeThrowsPercentage',
    'reboundsDefensive', 'reboundsOffensive', 'reboundsTotal',
    'foulsPersonal', 'turnovers', 'plusMinusPoints'
]


def clean_prediction_input(df, inference_columns=PREDICTION_INFERENCE_COLUMNS):
    df = df.copy()

    for column in inference_columns:
        if column not in df.columns:
            df[column] = 0
        df[column] = pd.to_numeric(df[column], errors="coerce")

    numeric = df[inference_columns]
    column_means = numeric.mean(numeric_only=True)
    df[inference_columns] = numeric.fillna(column_means).fillna(0)
    return df[inference_columns]


def complete_prediction_input_rows(df, inference_columns=PREDICTION_INFERENCE_COLUMNS):
    df = df.copy()

    for column in inference_columns:
        if column not in df.columns:
            df[column] = pd.NA
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return df.dropna(subset=inference_columns)


def _table_exists(table_name):
    return inspect(db.engine).has_table(table_name)


def _table_has_rows(table_name):
    if not _table_exists(table_name):
        return False
    return bool(db.session.execute(text(f'SELECT 1 FROM "{table_name}" LIMIT 1')).first())


def _ensure_player_recent_form_table():
    result = import_gold_recent_form_to_sqlite()
    return result["status"] != "missing" and _table_has_rows(PLAYER_RECENT_FORM_TABLE)


def get_player_totals():
    import_season_dataset("totals")

    if _table_exists(PLAYER_TOTALS_TABLE):
        latest_season = db.session.execute(
            text(f'SELECT MAX(season) FROM "{PLAYER_TOTALS_TABLE}"')
        ).scalar()

        if latest_season is not None:
            df = pd.read_sql_query(
                f'SELECT * FROM "{PLAYER_TOTALS_TABLE}" WHERE season = ?',
                con=db.engine,
                params=(latest_season,),
            )
            df = df[df["Player"] != "League Average"]
            return df.drop(columns=["season", "source_file", "Awards"], errors="ignore")

    return get_csv("players_data", "totals")


def _read_sql_table_or_empty(table_name):
    if not _table_exists(table_name):
        return pd.DataFrame()
    return pd.read_sql_table(table_name, con=db.engine)


def _fill_column_from_legacy(df, target_column, legacy_columns):
    if target_column not in df.columns:
        df[target_column] = pd.NA

    for legacy_column in legacy_columns:
        if legacy_column in df.columns:
            df[target_column] = df[target_column].combine_first(df[legacy_column])


def _normalize_daily_games_frame(df):
    if df.empty:
        return df

    df = df.copy()
    _fill_column_from_legacy(df, "team", ["0"])
    _fill_column_from_legacy(df, "score", ["1"])
    _fill_column_from_legacy(df, "state", ["2"])
    return df.drop(columns=["game_date", "source_file", "0", "1", "2"], errors="ignore")


def _normalize_daily_boxscores_frame(df):
    if df.empty:
        return df

    df = df.copy()
    _fill_column_from_legacy(df, "team", ["Unnamed_0", "Unnamed: 0", "0"])
    _fill_column_from_legacy(df, "Q1", ["1"])
    _fill_column_from_legacy(df, "Q2", ["2"])
    _fill_column_from_legacy(df, "Q3", ["3"])
    _fill_column_from_legacy(df, "Q4", ["4"])
    return df.drop(
        columns=["game_date", "source_file", "Unnamed_0", "Unnamed: 0", "0", "1", "2", "3", "4"],
        errors="ignore",
    )


def get_latest_daily_games():
    import_daily_games_to_sqlite()

    if not _table_exists(DAILY_GAMES_TABLE) or not _table_exists(DAILY_TEAM_BOXSCORES_TABLE):
        return pd.DataFrame(), pd.DataFrame(), None

    daily_game_columns = {
        row[1]
        for row in db.session.execute(text(f'PRAGMA table_info("{DAILY_GAMES_TABLE}")')).fetchall()
    }
    latest_game_date = None

    if "game_time_utc" in daily_game_columns:
        latest_game_date = db.session.execute(
            text(f'''
                SELECT MAX(game_date)
                FROM "{DAILY_GAMES_TABLE}"
                WHERE game_time_utc IS NOT NULL
                  AND TRIM(CAST(game_time_utc AS TEXT)) != ''
            ''')
        ).scalar()

    if latest_game_date is None:
        latest_game_date = db.session.execute(
            text(f'SELECT MAX(game_date) FROM "{DAILY_GAMES_TABLE}"')
        ).scalar()

    if latest_game_date is None:
        return pd.DataFrame(), pd.DataFrame(), None

    games = pd.read_sql_query(
        text(f'SELECT * FROM "{DAILY_GAMES_TABLE}" WHERE game_date = :game_date'),
        con=db.engine,
        params={"game_date": latest_game_date},
    )
    boxscores = pd.read_sql_query(
        text(f'SELECT * FROM "{DAILY_TEAM_BOXSCORES_TABLE}" WHERE game_date = :game_date'),
        con=db.engine,
        params={"game_date": latest_game_date},
    )

    return _normalize_daily_games_frame(games), _normalize_daily_boxscores_frame(boxscores), latest_game_date


def get_shooting_averages():
    shooting_avg = _read_sql_table_or_empty(SHOOTING_AVG_TABLE)
    adj_shooting_avg = _read_sql_table_or_empty(ADJ_SHOOTING_AVG_TABLE)

    if shooting_avg.empty or adj_shooting_avg.empty:
        import_all_data_to_sqlite()
        shooting_avg = _read_sql_table_or_empty(SHOOTING_AVG_TABLE)
        adj_shooting_avg = _read_sql_table_or_empty(ADJ_SHOOTING_AVG_TABLE)

    if shooting_avg.empty or adj_shooting_avg.empty:
        get_shooting_avg()
        shooting_avg = pd.read_csv('data/shooting/shooting_avg.csv')
        adj_shooting_avg = pd.read_csv('data/adj_shooting/adj_shooting_avg.csv')

    return shooting_avg, adj_shooting_avg


def get_player_recent_form_overview(limit=12, candidate_limit=5000):
    if not _ensure_player_recent_form_table():
        return pd.DataFrame()

    columns = [
        "personId",
        "player",
        "gameDate",
        "team",
        "opponent",
        "complete_games_in_prior_window",
        "last_10_points_avg",
        "last_10_assists_avg",
        "last_10_reboundsTotal_avg",
        "last_10_threePointersPercentage_avg",
        "last_10_plusMinusPoints_avg",
    ]
    select_columns = ", ".join([f'"{column}"' for column in columns])
    query = f"""
        SELECT {select_columns}
        FROM "{PLAYER_RECENT_FORM_TABLE}"
        WHERE player IS NOT NULL
          AND gameDate IS NOT NULL
          AND CAST(complete_games_in_prior_window AS REAL) >= 10
        ORDER BY gameDate DESC, gameId DESC
        LIMIT :candidate_limit
    """
    df = pd.read_sql_query(
        text(query),
        con=db.engine,
        params={"candidate_limit": candidate_limit},
    )

    if df.empty:
        return df

    numeric_columns = [
        "complete_games_in_prior_window",
        "last_10_points_avg",
        "last_10_assists_avg",
        "last_10_reboundsTotal_avg",
        "last_10_threePointersPercentage_avg",
        "last_10_plusMinusPoints_avg",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["gameDate"] = pd.to_datetime(df["gameDate"], errors="coerce")
    latest_per_player = (
        df.sort_values(["player", "gameDate"], ascending=[True, False])
        .drop_duplicates("player", keep="first")
    )
    return (
        latest_per_player
        .dropna(subset=["last_10_points_avg"])
        .sort_values("last_10_points_avg", ascending=False)
        .head(limit)
    )


def get_prediction_sample():
    df = _read_sql_table_or_empty(PREDICTION_SAMPLE_TABLE)

    if df.empty:
        import_all_data_to_sqlite()
        df = _read_sql_table_or_empty(PREDICTION_SAMPLE_TABLE)

    if df.empty:
        return create_sample('PlayerStatistics.csv', 'data/samples')

    if 'Player' not in df.columns and {'firstName', 'lastName'}.issubset(df.columns):
        df['Player'] = df['firstName'].fillna('') + ' ' + df['lastName'].fillna('')

    return df, PREDICTION_INFERENCE_COLUMNS


def get_prediction_player_names():
    if _ensure_player_recent_form_table():
        query = f"""
            SELECT DISTINCT player AS Player
            FROM "{PLAYER_RECENT_FORM_TABLE}"
            WHERE player IS NOT NULL
              AND TRIM(player) != ''
            ORDER BY Player
        """
        return pd.read_sql_query(query, con=db.engine)['Player'].tolist()

    if not _table_exists(PREDICTION_SAMPLE_TABLE):
        df, _ = get_prediction_sample()
        return sorted(df['Player'].dropna().unique()) if df is not None and 'Player' in df.columns else []

    query = f"""
        SELECT DISTINCT firstName || ' ' || lastName AS Player
        FROM "{PREDICTION_SAMPLE_TABLE}"
        WHERE firstName IS NOT NULL
          AND lastName IS NOT NULL
        ORDER BY Player
    """
    return pd.read_sql_query(query, con=db.engine)['Player'].tolist()


def search_prediction_player_names(query, limit=12):
    query = (query or "").strip().lower()
    if len(query) < 2:
        return []

    if _ensure_player_recent_form_table():
        sql = f"""
            SELECT DISTINCT player AS Player
            FROM "{PLAYER_RECENT_FORM_TABLE}"
            WHERE player IS NOT NULL
              AND LOWER(player) LIKE :query
            ORDER BY Player
            LIMIT :limit
        """
        return pd.read_sql_query(
            text(sql),
            con=db.engine,
            params={"query": f"%{query}%", "limit": limit},
        )['Player'].tolist()

    if not _table_exists(PREDICTION_SAMPLE_TABLE):
        return [
            name for name in get_prediction_player_names()
            if query in name.lower()
        ][:limit]

    sql = f"""
        SELECT DISTINCT firstName || ' ' || lastName AS Player
        FROM "{PREDICTION_SAMPLE_TABLE}"
        WHERE firstName IS NOT NULL
          AND lastName IS NOT NULL
          AND LOWER(firstName || ' ' || lastName) LIKE :query
        ORDER BY Player
        LIMIT :limit
    """
    return pd.read_sql_query(
        text(sql),
        con=db.engine,
        params={"query": f"%{query}%", "limit": limit},
    )['Player'].tolist()


def get_recent_prediction_stats_for_player(player_name, limit=10, candidate_limit=100):
    if _ensure_player_recent_form_table():
        select_columns = ", ".join([f'"{column}"' for column in PREDICTION_INFERENCE_COLUMNS])
        query = f"""
            SELECT {select_columns}
            FROM "{PLAYER_RECENT_FORM_TABLE}"
            WHERE LOWER(player) LIKE :player_name
            ORDER BY gameDate DESC, gameId DESC
            LIMIT :candidate_limit
        """
        filtered = pd.read_sql_query(
            text(query),
            con=db.engine,
            params={"player_name": f"%{player_name.lower()}%", "candidate_limit": candidate_limit},
        )
        filtered = complete_prediction_input_rows(filtered, PREDICTION_INFERENCE_COLUMNS).head(limit)
        if len(filtered) < limit:
            raise ValueError(f"Only found {len(filtered)} complete games for {player_name}; {limit} are required.")
        return filtered[PREDICTION_INFERENCE_COLUMNS], PREDICTION_INFERENCE_COLUMNS

    if not _table_exists(PREDICTION_SAMPLE_TABLE):
        df, inference_cols = get_prediction_sample()
        filtered = df[df['Player'].str.contains(player_name, case=False, na=False)]
        filtered = complete_prediction_input_rows(filtered, inference_cols).head(limit)
        if len(filtered) < limit:
            raise ValueError(f"Only found {len(filtered)} complete games for {player_name}; {limit} are required.")
        return filtered[inference_cols], inference_cols

    select_columns = ", ".join([f'"{column}"' for column in PREDICTION_INFERENCE_COLUMNS])
    query = f"""
        SELECT {select_columns}
        FROM "{PREDICTION_SAMPLE_TABLE}"
        WHERE LOWER(firstName || ' ' || lastName) LIKE :player_name
        ORDER BY gameDate DESC, gameId DESC
        LIMIT :candidate_limit
    """
    filtered = pd.read_sql_query(
        text(query),
        con=db.engine,
        params={"player_name": f"%{player_name.lower()}%", "candidate_limit": candidate_limit},
    )
    filtered = complete_prediction_input_rows(filtered, PREDICTION_INFERENCE_COLUMNS).head(limit)
    if len(filtered) < limit:
        raise ValueError(f"Only found {len(filtered)} complete games for {player_name}; {limit} are required.")
    return filtered[PREDICTION_INFERENCE_COLUMNS], PREDICTION_INFERENCE_COLUMNS
