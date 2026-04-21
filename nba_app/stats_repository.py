import pandas as pd
from sqlalchemy import inspect, text

from backend.data_scraper import create_sample, get_csv, get_shooting_avg
from .data_importer import import_all_data_to_sqlite, import_season_dataset
from .models import db

PLAYER_TOTALS_TABLE = "player_totals"
SHOOTING_AVG_TABLE = "shooting_avg"
ADJ_SHOOTING_AVG_TABLE = "adj_shooting_avg"
PREDICTION_SAMPLE_TABLE = "sample_player_statistics"

PREDICTION_INFERENCE_COLUMNS = [
    'numMinutes', 'points', 'assists', 'blocks', 'steals',
    'fieldGoalsAttempted', 'fieldGoalsMade', 'fieldGoalsPercentage',
    'threePointersAttempted', 'threePointersMade', 'threePointersPercentage',
    'freeThrowsAttempted', 'freeThrowsMade', 'freeThrowsPercentage',
    'reboundsDefensive', 'reboundsOffensive', 'reboundsTotal',
    'foulsPersonal', 'turnovers', 'plusMinusPoints'
]


def _table_exists(table_name):
    return inspect(db.engine).has_table(table_name)


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


def get_recent_prediction_stats_for_player(player_name, limit=10):
    if not _table_exists(PREDICTION_SAMPLE_TABLE):
        df, inference_cols = get_prediction_sample()
        filtered = df[df['Player'].str.contains(player_name, case=False, na=False)]
        return filtered[inference_cols].head(limit), inference_cols

    select_columns = ", ".join([f'"{column}"' for column in PREDICTION_INFERENCE_COLUMNS])
    query = f"""
        SELECT {select_columns}
        FROM "{PREDICTION_SAMPLE_TABLE}"
        WHERE LOWER(firstName || ' ' || lastName) LIKE :player_name
        ORDER BY gameDate DESC, gameId DESC
        LIMIT :limit
    """
    filtered = pd.read_sql_query(
        text(query),
        con=db.engine,
        params={"player_name": f"%{player_name.lower()}%", "limit": limit},
    )
    return filtered, PREDICTION_INFERENCE_COLUMNS
