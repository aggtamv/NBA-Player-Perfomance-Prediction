import argparse
from pathlib import Path

from pyspark.sql import functions as F

from pipelines.common import (
    BRONZE_PLAYER_GAME_LOGS,
    MODEL_COLUMNS,
    SILVER_PLAYER_GAME_LOGS,
    create_spark,
    read_layer_csv,
    write_layer_csv,
)


def clean_player_game_logs(input_path=BRONZE_PLAYER_GAME_LOGS, output_path=SILVER_PLAYER_GAME_LOGS, write_csv=True):
    spark = create_spark("nba-silver-player-game-logs")
    input_path = Path(input_path)
    output_path = Path(output_path)

    df = read_layer_csv(spark, input_path)

    df = df.withColumn("player", F.concat_ws(" ", F.col("firstName"), F.col("lastName")))
    df = df.withColumn("team", F.concat_ws(" ", F.col("playerteamCity"), F.col("playerteamName")))
    df = df.withColumn("opponent", F.concat_ws(" ", F.col("opponentteamCity"), F.col("opponentteamName")))
    df = df.withColumn("gameDateTs", F.to_timestamp("gameDate"))

    for column in MODEL_COLUMNS:
        df = df.withColumn(column, F.col(column).cast("double"))

    cleaned = (
        df.dropDuplicates(["personId", "gameId"])
        .dropna(subset=["personId", "gameId", "gameDateTs", "player"])
        .dropna(subset=MODEL_COLUMNS)
    )

    row_count = cleaned.count()
    csv_file = write_layer_csv(cleaned, output_path)
    spark.stop()
    return row_count, csv_file


def parse_args():
    parser = argparse.ArgumentParser(description="Clean Bronze player game logs into the Silver layer.")
    parser.add_argument("--input", default=str(BRONZE_PLAYER_GAME_LOGS), help="Bronze input directory")
    parser.add_argument("--output", default=str(SILVER_PLAYER_GAME_LOGS), help="Silver output directory")
    parser.add_argument("--csv", action="store_true", help="Accepted for compatibility; local layers are always CSV")
    return parser.parse_args()


def main():
    args = parse_args()
    row_count, output_path = clean_player_game_logs(args.input, args.output, write_csv=args.csv)
    print(f"Silver player game logs: {row_count} complete rows written to {output_path}")


if __name__ == "__main__":
    main()
