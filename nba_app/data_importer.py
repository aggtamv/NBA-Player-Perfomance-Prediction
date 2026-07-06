import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from backend.data_scraper import repair_dataframe_text
from .models import db

DATA_ROOT = Path("data")

SEASON_DATASETS = {
    "adj_shooting": "player_adj_shooting",
    "advanced": "player_advanced",
    "per_game": "player_per_game",
    "per_minute": "player_per_minute",
    "per_poss": "player_per_poss",
    "play-by-play": "player_play_by_play",
    "shooting": "player_shooting",
    "totals": "player_totals",
}

ARCHIVE_DATASETS = {
    "Games.csv": "archive_games",
    "LeagueSchedule24_25.csv": "archive_league_schedule",
    "Players.csv": "archive_players",
    "PlayerStatistics.csv": "archive_player_statistics",
    "TeamHistories.csv": "archive_team_histories",
    "TeamStatistics.csv": "archive_team_statistics",
}

AVG_DATASETS = {
    "adj_shooting/adj_shooting_avg.csv": "adj_shooting_avg",
    "shooting/shooting_avg.csv": "shooting_avg",
}

GOLD_DATASETS = {
    "player_recent_form/csv/data.csv": "player_recent_form",
}


def _normalize_column_name(name):
    name = str(name).strip().replace("\ufeff", "")
    name = re.sub(r"^Unnamed: \d+_level_\d+_", "", name)
    name = re.sub(r"_?Unnamed: \d+_level_\d+$", "", name)
    name = name.replace(" ", "_")
    name = name.replace("-", "_")
    name = re.sub(r"[^0-9A-Za-z_%+./]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "column"


def _dedupe_columns(columns):
    seen = {}
    deduped = []

    for column in columns:
        base = _normalize_column_name(column)
        count = seen.get(base, 0)
        seen[base] = count + 1
        deduped.append(base if count == 0 else f"{base}_{count + 1}")

    return deduped


def _flatten_columns(columns):
    flattened = []

    for column in columns:
        if not isinstance(column, tuple):
            flattened.append(column)
            continue

        parts = [
            str(part).strip()
            for part in column
            if str(part).strip() and not str(part).startswith("Unnamed:")
        ]
        flattened.append("_".join(parts) if parts else column[-1])

    return _dedupe_columns(flattened)


def _looks_like_multi_header(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()
        second_line = handle.readline()

    return "_level_" in first_line and "Rk," in second_line


def _read_csv(csv_path):
    header = [0, 1] if _looks_like_multi_header(csv_path) else 0
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False, header=header)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    df.columns = _flatten_columns(df.columns)
    return repair_dataframe_text(df)


def _extract_year(csv_path):
    match = re.search(r"players_data_(\d{4})\.csv$", csv_path.name)
    return int(match.group(1)) if match else None


def _extract_date_from_name(csv_path, prefix):
    match = re.search(rf"{re.escape(prefix)}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$", csv_path.name)
    return match.group(1) if match else None


def _source_signature(csv_paths):
    parts = []
    for csv_path in sorted(csv_paths):
        stat = csv_path.stat()
        parts.append(f"{csv_path.as_posix()}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


def _ensure_import_metadata_table():
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS data_imports (
            source_name TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            source_mtime_ns INTEGER NOT NULL,
            imported_rows INTEGER NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    db.session.commit()


def _metadata_matches(table_name, csv_paths):
    if not csv_paths:
        return False

    _ensure_import_metadata_table()
    signature = _source_signature(csv_paths)
    result = db.session.execute(
        text("""
            SELECT source_path
            FROM data_imports
            WHERE source_name = :source_name
        """),
        {"source_name": table_name},
    ).scalar()

    return result == signature


def _record_import(table_name, csv_paths, imported_rows):
    _ensure_import_metadata_table()
    signature = _source_signature(csv_paths)
    db.session.execute(
        text("""
            INSERT OR REPLACE INTO data_imports
                (source_name, source_path, source_mtime_ns, imported_rows, imported_at)
            VALUES
                (:source_name, :source_path, 0, :imported_rows, CURRENT_TIMESTAMP)
        """),
        {
            "source_name": table_name,
            "source_path": signature,
            "imported_rows": imported_rows,
        },
    )
    db.session.commit()


def _replace_table(table_name, frames, csv_paths):
    frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not frames:
        return 0

    df = pd.concat(frames, ignore_index=True, sort=False)
    df.to_sql(table_name, con=db.engine, if_exists="replace", index=False)
    _create_common_indexes(table_name)
    _record_import(table_name, csv_paths, len(df))
    return len(df)


def _import_table_if_changed(table_name, csv_paths, frame_builder):
    csv_paths = [Path(csv_path) for csv_path in csv_paths if Path(csv_path).exists()]
    if not csv_paths:
        return {"table": table_name, "rows": 0, "status": "missing"}

    if _metadata_matches(table_name, csv_paths):
        _create_common_indexes(table_name)
        return {"table": table_name, "rows": None, "status": "unchanged"}

    rows = _replace_table(table_name, frame_builder(csv_paths), csv_paths)
    return {"table": table_name, "rows": rows, "status": "imported"}


def _create_common_indexes(table_name):
    columns = {
        row[1]
        for row in db.session.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
    }
    index_columns = [
        column
        for column in (
            "season",
            "Player",
            "player",
            "game_date",
            "gameDate",
            "game_id",
            "gameId",
            "person_id",
            "personId",
            "team",
            "Team",
            "teamId",
            "teamCity",
            "teamName",
        )
        if column in columns
    ]

    for column in index_columns:
        index_name = _normalize_column_name(f"idx_{table_name}_{column}")
        db.session.execute(
            text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{column}")')
        )
    db.session.commit()


def _season_frames(csv_paths, extra_columns=None):
    frames = []
    for csv_path in sorted(csv_paths):
        df = _read_csv(csv_path)
        df.insert(0, "season", _extract_year(csv_path))
        df.insert(1, "source_file", csv_path.as_posix())
        if extra_columns:
            for key, value in extra_columns.items():
                df[key] = value
        frames.append(df)
    return frames


def _dated_frames(csv_paths, date_prefix):
    frames = []
    for csv_path in sorted(csv_paths):
        df = _read_csv(csv_path)
        if df.empty:
            continue
        df.insert(0, "game_date", _extract_date_from_name(csv_path, date_prefix))
        df.insert(1, "source_file", csv_path.as_posix())
        frames.append(df)
    return frames


def _boxscore_frames(csv_paths):
    frames = []
    for csv_path in sorted(csv_paths):
        df = _read_csv(csv_path)
        df.insert(0, "game_date", csv_path.parent.name)
        df.insert(1, "source_file", csv_path.as_posix())
        frames.append(df)
    return frames


def import_season_dataset(folder, force=False):
    table_name = SEASON_DATASETS[folder]
    csv_paths = sorted((DATA_ROOT / folder).glob("players_data_*.csv"))
    if force:
        rows = _replace_table(table_name, _season_frames(csv_paths), csv_paths)
        return {"table": table_name, "rows": rows, "status": "imported"}

    return _import_table_if_changed(table_name, csv_paths, _season_frames)


def import_daily_games_to_sqlite(force=False):
    games_paths = sorted((DATA_ROOT / "daily_games").glob("games_*.csv"))
    boxscore_paths = sorted((DATA_ROOT / "daily_games").glob("boxscores_*.csv"))

    if force:
        games_rows = _replace_table("daily_games", _dated_frames(games_paths, "games"), games_paths)
        boxscore_rows = _replace_table(
            "daily_team_boxscores",
            _dated_frames(boxscore_paths, "boxscores"),
            boxscore_paths,
        )
        return [
            {"table": "daily_games", "rows": games_rows, "status": "imported"},
            {"table": "daily_team_boxscores", "rows": boxscore_rows, "status": "imported"},
        ]

    return [
        _import_table_if_changed("daily_games", games_paths, lambda paths: _dated_frames(paths, "games")),
        _import_table_if_changed(
            "daily_team_boxscores",
            boxscore_paths,
            lambda paths: _dated_frames(paths, "boxscores"),
        ),
    ]


def import_gold_recent_form_to_sqlite(force=False):
    table_name = GOLD_DATASETS["player_recent_form/csv/data.csv"]
    csv_path = DATA_ROOT / "gold" / "player_recent_form" / "csv" / "data.csv"
    builder = lambda paths: [_read_csv(paths[0])]

    if not csv_path.exists():
        return {"table": table_name, "rows": 0, "status": "missing"}

    if force:
        rows = _replace_table(table_name, builder([csv_path]), [csv_path])
        return {"table": table_name, "rows": rows, "status": "imported"}

    return _import_table_if_changed(table_name, [csv_path], builder)


def import_all_data_to_sqlite(force=False):
    results = []

    for folder, table_name in SEASON_DATASETS.items():
        results.append(import_season_dataset(folder, force=force))

    for relative_path, table_name in AVG_DATASETS.items():
        csv_path = DATA_ROOT / relative_path
        builder = lambda paths: [_read_csv(paths[0]).assign(source_file=paths[0].as_posix())]
        if force:
            rows = _replace_table(table_name, builder([csv_path]), [csv_path])
            results.append({"table": table_name, "rows": rows, "status": "imported"})
        else:
            results.append(_import_table_if_changed(table_name, [csv_path], builder))

    results.extend(import_daily_games_to_sqlite(force=force))
    results.append(import_gold_recent_form_to_sqlite(force=force))

    game_team_paths = sorted((DATA_ROOT / "boxscores").glob("*/*_team_boxscore.csv"))
    game_player_paths = sorted((DATA_ROOT / "boxscores").glob("*/*_player_boxscore.csv"))
    daily_player_paths = sorted((DATA_ROOT / "boxscores").glob("*/player_boxscores_*.csv"))
    results.append(_import_table_if_changed("game_team_boxscores", game_team_paths, _boxscore_frames))
    results.append(_import_table_if_changed("game_player_boxscores", game_player_paths, _boxscore_frames))
    results.append(_import_table_if_changed("daily_player_boxscores", daily_player_paths, lambda paths: _dated_frames(paths, "player_boxscores")))

    for filename, table_name in ARCHIVE_DATASETS.items():
        csv_path = DATA_ROOT / "archive" / filename
        builder = lambda paths: [_read_csv(paths[0]).assign(source_file=paths[0].as_posix())]
        results.append(_import_table_if_changed(table_name, [csv_path], builder))

    sample_path = DATA_ROOT / "samples" / "PlayerStatistics.csv"
    builder = lambda paths: [_read_csv(paths[0]).assign(source_file=paths[0].as_posix())]
    results.append(_import_table_if_changed("sample_player_statistics", [sample_path], builder))

    return results
