import argparse
from pathlib import Path

from pipelines.common import (
    BRONZE_PLAYER_GAME_LOGS,
    DEFAULT_DEMO_SINCE_YEAR,
    PLAYER_GAME_LOG_COLUMNS,
    PLAYER_STATISTICS_SOURCE,
    create_spark,
    write_layer_csv,
)
from pyspark.sql import functions as F


def ingest_player_game_logs(
    input_path=PLAYER_STATISTICS_SOURCE,
    output_path=BRONZE_PLAYER_GAME_LOGS,
    write_csv=True,
    since_year=DEFAULT_DEMO_SINCE_YEAR,
    row_limit=None,
):
    spark = create_spark("nba-bronze-player-game-logs")
    input_path = str(input_path)
    output_path = Path(output_path)

    raw = (
        spark.read
        .option("header", True)
        .option("inferSchema", False)
        .csv(input_path)
    )

    available_columns = [column for column in PLAYER_GAME_LOG_COLUMNS if column in raw.columns]
    raw = raw.select(*available_columns)

    if since_year:
        raw = raw.filter(F.to_timestamp("gameDate") >= F.lit(f"{since_year}-01-01 00:00:00"))

    if row_limit:
        raw = raw.limit(row_limit)

    row_count = raw.count()
    csv_file = write_layer_csv(raw, output_path)
    spark.stop()
    return row_count, csv_file


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest raw player game logs into the Bronze layer.")
    parser.add_argument("--input", default=str(PLAYER_STATISTICS_SOURCE), help="Path to PlayerStatistics.csv")
    parser.add_argument("--output", default=str(BRONZE_PLAYER_GAME_LOGS), help="Bronze output directory")
    parser.add_argument("--csv", action="store_true", help="Accepted for compatibility; local layers are always CSV")
    parser.add_argument("--since-year", type=int, default=DEFAULT_DEMO_SINCE_YEAR, help="Only ingest games from this year onward")
    parser.add_argument("--row-limit", type=int, default=None, help="Optional hard row limit for quick demo runs")
    parser.add_argument("--full", action="store_true", help="Ingest the full historical file")
    return parser.parse_args()


def main():
    args = parse_args()
    since_year = None if args.full else args.since_year
    row_count, output_path = ingest_player_game_logs(
        args.input,
        args.output,
        write_csv=args.csv,
        since_year=since_year,
        row_limit=args.row_limit,
    )
    print(f"Bronze player game logs: {row_count} rows written to {output_path}")


if __name__ == "__main__":
    main()
